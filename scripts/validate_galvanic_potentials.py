"""Cross-check seeded GC-001 potentials against MIL-STD-889B Table II rank order.

The GC-001 catalog scores couples on a voltage delta; MIL-STD-889B Table II
publishes an ordinal seawater series with no voltages. The two cannot be merged
(see ``scripts/parse_mil_std_889_series.py``), but the ordinal series is an
authoritative check on whether the seeded potentials *rank* correctly.

This harness pulls the seeded ``galvanic_series_entry`` rows from the database,
orders them most-active-first by potential, and compares that ordering against
the Table II rank of each material. Every ordered pair that disagrees is
reported as an inversion.

Mapping our 20 catalog keys onto Table II entries is engineering judgement, not
string matching: Table II names specific alloys and tempers where the catalog
carries generic families. :data:`TABLE_II_MAPPING` records that judgement
explicitly so it can be audited and cited. Where a catalog material has no
Table II counterpart at all it is reported as unmapped rather than forced onto
an approximate neighbour.

Usage::

    python scripts/validate_galvanic_potentials.py

Exit codes: ``0`` no inversions, ``1`` inversions found, ``2`` data unavailable.
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

TABLE_II_JSON = REPO_ROOT / "data" / "reference" / "mil_std_889b_table_ii.json"
RULESET_ID = "BIMGUARD-GC-001"

#: Catalog material key -> regex matching its Table II counterpart entries.
#: A key mapped to ``None`` has no counterpart in Table II and is skipped.
TABLE_II_MAPPING: dict[str, str | None] = {
    "magnesium": r"^Magnesium|^M[gG] Alloy",
    "galv_steel": r"^Zinc \(hot-dip",       # galvanising is a zinc coating
    "zinc": r"^Zinc \(hot-dip",
    "cadmium": r"^Cadmium",
    "aluminium": r"^Al(uminum)? ?(alloy|\(Al\))",
    "carbon_steel": r"^Steel 1010",
    "cast_iron": r"^Iron, cast",
    "ss304_active": r"^Stainless steel 304 \(active\)",
    "ss316_active": r"^Stainless steel 316 \(active\)",
    "ss304_passive": r"^Stainless steel 304 \(passive\)",
    "ss316_passive": r"^Stainless steel 316L? \(passive\)",
    "brass": r"[Bb]rass|Muntz metal",
    "bronze": r"[Bb]ronze",
    "copper": r"^Copper( 110| \(plated)",
    "titanium": r"^Titan(ium|um)",
    "silver_solder": None,   # Table II lists pure Silver only, not silver solder
    "hastelloy_c": None,     # not present in Table II
    "platinum": None,        # not present in Table II
    "gold": r"^Gold$",
    "graphite": r"^Graphite$",
}


def load_table_ii() -> list[dict]:
    """Return the parsed Table II entries."""
    if not TABLE_II_JSON.exists():
        raise FileNotFoundError(
            f"{TABLE_II_JSON} missing - run scripts/parse_mil_std_889_series.py first"
        )
    return json.loads(TABLE_II_JSON.read_text(encoding="utf-8"))["entries"]


def load_seeded_materials() -> list[dict]:
    """Return seeded GC-001 galvanic series entries with their potentials."""
    from app.environment import load_env_file

    load_env_file()
    from app.services.rules_service import RuleService

    materials = []
    for row in RuleService().list_by_ruleset(RULESET_ID):
        if row.get("rule_type") != "galvanic_series_entry":
            continue
        try:
            params = json.loads(row.get("parameters") or "{}")
        except (TypeError, ValueError):
            params = {}
        key = str(params.get("material_key") or row.get("keyword") or "").strip()
        try:
            potential = float(row.get("check_value"))
        except (TypeError, ValueError):
            continue
        if key:
            materials.append(
                {"key": key, "potential": potential, "label": params.get("label") or key}
            )
    return materials


def resolve_rank(key: str, entries: list[dict]) -> tuple[float | None, list[str]]:
    """Return the representative Table II rank for a catalog key and its matches."""
    pattern = TABLE_II_MAPPING.get(key, "__unmapped__")
    if pattern is None or pattern == "__unmapped__":
        return None, []
    regex = re.compile(pattern)
    matched = [e for e in entries if regex.search(e["name"])]
    if not matched:
        return None, []
    # Generic families span several specific alloys; the median rank is the
    # fairest single representative of that span.
    return statistics.median(e["rank"] for e in matched), [e["name"] for e in matched]


def main() -> int:
    """Run the cross-check and report inversions."""
    try:
        entries = load_table_ii()
        materials = load_seeded_materials()
    except Exception as exc:  # noqa: BLE001 - surfaced verbatim to the operator
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not materials:
        print(f"error: no seeded galvanic_series_entry rows for {RULESET_ID}", file=sys.stderr)
        return 2

    for mat in materials:
        rank, matches = resolve_rank(mat["key"], entries)
        mat["rank"] = rank
        mat["matches"] = matches

    # Catalog convention: HIGHER potential = MORE active (anodic).
    # Table II convention: LOWER rank = MORE active (anodic).
    materials.sort(key=lambda m: -m["potential"])

    print("=" * 78)
    print(f"GC-001 seeded potentials vs MIL-STD-889B Table II   ({len(materials)} materials)")
    print("=" * 78)
    print(f"{'#':>3}  {'catalog key':<16} {'V':>6}  {'MIL rank':>9}  matched Table II entries")
    print("-" * 78)
    for i, m in enumerate(materials, 1):
        rank = f"{m['rank']:.1f}" if m["rank"] is not None else "--"
        detail = f"{len(m['matches'])} entr{'y' if len(m['matches']) == 1 else 'ies'}"
        if not m["matches"]:
            detail = "NOT IN TABLE II"
        print(f"{i:>3}  {m['key']:<16} {m['potential']:>6.2f}  {rank:>9}  {detail}")

    ranked = [m for m in materials if m["rank"] is not None]
    unmapped = [m for m in materials if m["rank"] is None]

    inversions = []
    for i in range(len(ranked)):
        for j in range(i + 1, len(ranked)):
            a, b = ranked[i], ranked[j]
            # a is more active than b by potential; Table II must agree.
            if a["rank"] > b["rank"]:
                inversions.append((a, b))

    print()
    print("-" * 78)
    print(f"mapped: {len(ranked)}   unmapped: {len(unmapped)}   "
          f"pairs compared: {len(ranked) * (len(ranked) - 1) // 2}")
    if unmapped:
        print("unmapped (no Table II counterpart): "
              + ", ".join(m["key"] for m in unmapped))
    print()

    if not inversions:
        print("RESULT: no inversions - seeded potentials agree with MIL-STD-889B rank order.")
        return 0

    print(f"RESULT: {len(inversions)} INVERSION(S) - voltage order contradicts MIL-STD-889B:")
    for a, b in inversions:
        print(
            f"  ! {a['key']} ({a['potential']:.2f} V) is ranked MORE active than "
            f"{b['key']} ({b['potential']:.2f} V) by potential,"
        )
        print(
            f"    but Table II puts {a['key']} at rank {a['rank']:.1f} and "
            f"{b['key']} at rank {b['rank']:.1f} (lower rank = more active)."
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
