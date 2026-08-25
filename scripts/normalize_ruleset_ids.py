"""One-time normalization for ruleset_id values across rules and rule folders.

This script normalizes whitespace and case-variant duplicates so folder backfill
and lookups remain stable.

Usage:
    uv run python scripts/normalize_ruleset_ids.py --dry-run
    uv run python scripts/normalize_ruleset_ids.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from postgrest.exceptions import APIError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.persistence import PersistenceService
from app.services.rules_service import RuleService
from app.utils import now_iso_utc


def _canonicalize_rows(rows: list[dict]) -> dict[int, str]:
    """Return target normalized ruleset_id values keyed by row id."""
    canonical_by_key: dict[str, str] = {}
    targets: dict[int, str] = {}

    for row in sorted(rows, key=lambda item: int(item.get("id") or 0)):
        row_id = int(row.get("id") or 0)
        current = RuleService.normalize_ruleset_id(row.get("ruleset_id") or "")
        if not current:
            targets[row_id] = ""
            continue

        key = current.lower()
        canonical = canonical_by_key.setdefault(key, current)
        targets[row_id] = canonical

    return targets


def _normalize_rules_table(dry_run: bool) -> tuple[int, int]:
    """Normalize rules.ruleset_id values and return (updated, total_rows)."""
    rules = PersistenceService.get_table(
        "rules",
        {
            "id": int,
            "ruleset_id": str,
            "updated_at": str,
        },
    )
    rows = list(rules.rows)
    targets = _canonicalize_rows(rows)

    updated = 0
    now = now_iso_utc()
    for row in rows:
        row_id = int(row.get("id") or 0)
        current = row.get("ruleset_id") or ""
        target = targets.get(row_id, "")
        if current == target:
            continue

        updated += 1
        if not dry_run:
            rules.update(
                updates={"ruleset_id": target, "updated_at": now},
                pk_values=row_id,
            )

    return updated, len(rows)


def _normalize_folders_table(dry_run: bool) -> tuple[int, int, int]:
    """Normalize rule_folders ruleset IDs and de-duplicate case variants.

    Returns (updated, deleted, total_rows). If table is unavailable, returns zeros.
    """
    folders = PersistenceService.get_table(
        "rule_folders",
        {
            "id": int,
            "ruleset_id": str,
            "updated_at": str,
        },
    )

    try:
        rows = list(folders.rows)
    except APIError as exc:
        code = str(getattr(exc, "code", "") or "")
        message = str(getattr(exc, "message", "") or exc)
        if code == "PGRST205" or "rule_folders" in message:
            return 0, 0, 0
        raise

    targets = _canonicalize_rows(rows)
    updated = 0
    deleted = 0
    now = now_iso_utc()

    # Keep the earliest row per normalized key.
    keeper_by_key: dict[str, int] = {}
    for row in sorted(rows, key=lambda item: int(item.get("id") or 0)):
        row_id = int(row.get("id") or 0)
        target = targets.get(row_id, "")
        key = target.lower()

        if not target:
            if row.get("ruleset_id"):
                updated += 1
                if not dry_run:
                    folders.update(updates={"ruleset_id": "", "updated_at": now}, pk_values=row_id)
            continue

        if key in keeper_by_key:
            deleted += 1
            if not dry_run:
                folders.delete(row_id)
            continue

        keeper_by_key[key] = row_id

        current = row.get("ruleset_id") or ""
        if current != target:
            updated += 1
            if not dry_run:
                folders.update(updates={"ruleset_id": target, "updated_at": now}, pk_values=row_id)

    return updated, deleted, len(rows)


def run(dry_run: bool) -> None:
    """Execute one-time normalization against configured backend."""
    rules_updated, rules_total = _normalize_rules_table(dry_run)
    folders_updated, folders_deleted, folders_total = _normalize_folders_table(dry_run)

    mode = "DRY RUN" if dry_run else "APPLIED"
    print(f"[{mode}] Rules normalized: {rules_updated} / {rules_total}")
    if folders_total:
        print(
            f"[{mode}] Folders normalized: {folders_updated} / {folders_total}, "
            f"duplicates removed: {folders_deleted}"
        )
    else:
        print(f"[{mode}] rule_folders table not found or empty; skipped folder normalization")


def main() -> None:
    """CLI entry point for one-time ruleset_id normalization."""
    parser = argparse.ArgumentParser(
        description="Normalize ruleset_id duplicates and whitespace variants"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview updates without writing changes",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply updates to the configured database backend",
    )
    args = parser.parse_args()

    dry_run = True
    if args.apply:
        dry_run = False
    elif args.dry_run:
        dry_run = True

    run(dry_run=dry_run)


if __name__ == "__main__":
    main()
