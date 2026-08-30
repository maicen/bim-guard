"""Load the repository's own migration seeds into an offline E2E database.

WHY THIS EXISTS

    Three rule packs -- ``BUILDING-CODE-PART9``, ``BUILDING-CODE-PART9-EXT``
    and the corrosion catalogs ``BIMGUARD-GC-001``/``CC-001``/``MC-001`` -- ship
    as rows of ``supabase/migrations/20260806180500_seed_static_data_assets.sql``
    rather than as files under ``data/rulesets/``. A machine without Supabase
    therefore starts with an empty ``static_data_assets`` table, the
    architectural analysis fails with *Missing static asset
    ruleset:BUILDING-CODE-PART9*, and the corrosion engines silently fall back
    to their built-in catalogs. Neither is a code defect; both are simply a
    database that was never populated.

    This module reads those rows out of the migration -- the same payload a
    ``supabase db push`` would install -- and writes them through
    :class:`~app.services.static_data_service.StaticDataService`, the shipped
    write path. What that proves and does not prove:

    * PROVES: the rule packs parse, seed and evaluate, and the engines read
      their catalogs from the database rather than from constants.
    * DOES NOT PROVE: the Supabase network path, its RLS policies, or that a
      deployed database actually holds these rows.

USAGE

    Called by ``scripts/e2e_server.py --seed-db``; not imported by the
    application.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SEED_SQL = _REPO_ROOT / "supabase" / "migrations" / "20260806180500_seed_static_data_assets.sql"

#: Column order of the migration's ``insert into public.static_data_assets``.
_COLUMNS = (
    "asset_key",
    "source_path",
    "format",
    "content_json",
    "content_text",
    "content_sha256",
    "migrated_at",
    "active",
)


def _split_literals(tuple_body: str) -> list[str]:
    """Split one SQL ``values`` tuple into its literals.

    Handles the only two forms the migration uses: single-quoted strings, in
    which an embedded quote is doubled per the SQL standard, and bare integers.

    Args:
        tuple_body: The text between the tuple's outer parentheses.

    Returns:
        The literals in column order, quotes stripped and doubled quotes
        collapsed.
    """
    values: list[str] = []
    index = 0
    length = len(tuple_body)
    while index < length:
        char = tuple_body[index]
        if char in " \t\r\n,":
            index += 1
            continue
        if char == "'":
            index += 1
            chunk: list[str] = []
            while index < length:
                if tuple_body[index] == "'":
                    if index + 1 < length and tuple_body[index + 1] == "'":
                        chunk.append("'")
                        index += 2
                        continue
                    index += 1
                    break
                chunk.append(tuple_body[index])
                index += 1
            values.append("".join(chunk))
            continue
        end = index
        while end < length and tuple_body[end] not in ",)":
            end += 1
        values.append(tuple_body[index:end].strip())
        index = end
    return values


def parse_seed_assets(sql_path: Path = _SEED_SQL) -> list[dict]:
    """Return every ``static_data_assets`` row the seed migration inserts.

    Args:
        sql_path: The migration to read. Defaults to the shipped seed file.

    Returns:
        One dict per row, keyed by :data:`_COLUMNS`.
    """
    sql = sql_path.read_text(encoding="utf-8")
    rows: list[dict] = []
    for match in re.finditer(r"\nvalues \(", sql):
        start = match.end()
        # Scan to the closing parenthesis, ignoring anything inside a literal.
        index, depth, in_string = start, 1, False
        while index < len(sql) and depth:
            char = sql[index]
            if in_string:
                if char == "'":
                    if index + 1 < len(sql) and sql[index + 1] == "'":
                        index += 2
                        continue
                    in_string = False
            elif char == "'":
                in_string = True
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    break
            index += 1
        literals = _split_literals(sql[start:index])
        if len(literals) != len(_COLUMNS):
            raise ValueError(
                f"{sql_path.name}: expected {len(_COLUMNS)} literals, got {len(literals)}"
            )
        rows.append(dict(zip(_COLUMNS, literals)))
    return rows


def install_static_assets(verbose: bool = True) -> list[str]:
    """Write the migration's asset rows into the configured database.

    Returns:
        The asset keys installed, in migration order.
    """
    from app.services.static_data_service import StaticDataService

    service = StaticDataService()
    installed: list[str] = []
    for row in parse_seed_assets():
        payload = json.loads(row["content_json"]) if row["format"] == "json" else row["content_json"]
        service.upsert_asset(
            asset_key=row["asset_key"],
            source_path=row["source_path"],
            format_name=row["format"],
            payload=payload,
            content_text=row["content_text"],
        )
        installed.append(row["asset_key"])
        if verbose:
            size = len(row["content_json"])
            print(f"[e2e-db] static asset {row['asset_key']} ({size} bytes)")
    return installed


def rule_counts(verbose: bool = True) -> dict[str, int]:
    """Report how many rules each shipped ruleset holds in the database.

    The application seeds the rules table itself on startup
    (``app.main._seed_library``); this only reads the result back, so the
    numbers reported are the ones the running server will evaluate.

    Returns:
        Ruleset id to row count, ``-1`` where the count could not be read.
    """
    from app.services.rules_service import RuleService

    service = RuleService()
    counts: dict[str, int] = {}
    for ruleset_id in (
        "BUILDING-CODE-PART9",
        "BUILDING-CODE-PART9-EXT",
        "BIMGUARD-GC-001",
        "BIMGUARD-CC-001",
        "BIMGUARD-MC-001",
        "BIMGUARD-MM-001",
        "BIMGUARD-XM-001",
        "BIMGUARD-SB-001",
    ):
        try:
            counts[ruleset_id] = len(service.list_by_ruleset(ruleset_id))
        except Exception as exc:  # pragma: no cover - reported, not raised
            print(f"[e2e-db] counting {ruleset_id} failed: {exc}")
            counts[ruleset_id] = -1
        if verbose:
            print(f"[e2e-db] ruleset {ruleset_id}: {counts[ruleset_id]} rules")
    return counts


if __name__ == "__main__":
    install_static_assets()
    rule_counts()
