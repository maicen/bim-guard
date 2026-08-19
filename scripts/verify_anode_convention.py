"""
Determine the sign convention of the GC-001 galvanic series.

Two engines read that series with opposite conventions for which end is the
anode, so one of them names the wrong corroding material. See
docs/defects/defect_report_anode_convention.md.

This script settles it from the data. It needs database access, since the
series lives only in the Supabase static asset 'ruleset:BIMGUARD-GC-001'.

    uv run python scripts/verify_anode_convention.py

Two independent checks are run:

    1. The `noble` flag. Every entry carries one alongside potential_v, so
       whether noble materials hold higher or lower potentials settles the
       convention outright — no physics argument required.

    2. Zinc against copper. Zinc sacrifices to copper; that is what
       galvanising is. Whichever sign reading names zinc as anode is correct.

Both should agree. If they disagree, the series itself is inconsistent and
that is a bigger problem than the convention.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Run directly from scripts/ without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MORE_NEGATIVE = "more_negative_is_anodic"
MORE_POSITIVE = "more_positive_is_anodic"

# Substrings identifying the physics-anchor pair, matched case-insensitively
# against series keys and labels.
ANODE_ANCHOR = ("zinc", "galvanis", "galvaniz")
CATHODE_ANCHOR = ("copper", "cu_", "c12200")


def _potential(entry: object) -> float | None:
    """Extract potential_v from a series entry of either shape."""
    if isinstance(entry, (int, float)):
        return float(entry)
    if isinstance(entry, dict):
        value = entry.get("potential_v")
        return float(value) if value is not None else None
    return None


def _noble(entry: object) -> bool | None:
    """Extract the noble flag from a series entry, if present."""
    if isinstance(entry, dict) and isinstance(entry.get("noble"), bool):
        return entry["noble"]
    return None


def _find(series: dict, needles: tuple[str, ...]) -> tuple[str, object] | None:
    """Find the first entry whose key or label matches any needle."""
    for key, entry in series.items():
        label = entry.get("label", "") if isinstance(entry, dict) else ""
        haystack = f"{key} {label}".lower()
        if any(needle in haystack for needle in needles):
            return key, entry
    return None


def check_noble_flag(series: dict) -> str | None:
    """Infer the convention from the noble flag. Returns None if unusable."""
    noble_potentials = []
    active_potentials = []
    for entry in series.values():
        noble = _noble(entry)
        potential = _potential(entry)
        if noble is None or potential is None:
            continue
        (noble_potentials if noble else active_potentials).append(potential)

    if not noble_potentials or not active_potentials:
        print("  noble-flag check: UNUSABLE - entries lack noble flags or potentials")
        return None

    noble_mean = sum(noble_potentials) / len(noble_potentials)
    active_mean = sum(active_potentials) / len(active_potentials)
    print(f"  noble  (cathodic) n={len(noble_potentials):2d} mean potential {noble_mean:+.3f} V")
    print(f"  active (anodic)   n={len(active_potentials):2d} mean potential {active_mean:+.3f} V")

    if active_mean < noble_mean:
        print("  -> active materials sit LOWER: more negative is anodic")
        return MORE_NEGATIVE
    if active_mean > noble_mean:
        print("  -> active materials sit HIGHER: more positive is anodic")
        return MORE_POSITIVE
    print("  noble-flag check: INCONCLUSIVE - means are equal")
    return None


def check_zinc_copper(series: dict) -> str | None:
    """Infer the convention from the zinc/copper anchor pair."""
    anode = _find(series, ANODE_ANCHOR)
    cathode = _find(series, CATHODE_ANCHOR)
    if anode is None or cathode is None:
        print("  zinc/copper check: UNUSABLE - anchor materials not found in series")
        return None

    anode_key, anode_entry = anode
    cathode_key, cathode_entry = cathode
    anode_v = _potential(anode_entry)
    cathode_v = _potential(cathode_entry)
    if anode_v is None or cathode_v is None:
        print("  zinc/copper check: UNUSABLE - anchor entries carry no potential")
        return None

    print(f"  {anode_key:24s} {anode_v:+.3f} V   (known anode - galvanising sacrifices)")
    print(f"  {cathode_key:24s} {cathode_v:+.3f} V   (known cathode)")

    if anode_v < cathode_v:
        print("  -> the known anode sits LOWER: more negative is anodic")
        return MORE_NEGATIVE
    print("  -> the known anode sits HIGHER: more positive is anodic")
    return MORE_POSITIVE


def main() -> int:
    """Run both checks and report the convention."""
    try:
        from app.services.corrosion_rule_catalog import load_gc_catalog
    except ImportError as exc:
        print(f"Cannot import the catalogue loader: {exc}")
        return 2

    try:
        catalogue = load_gc_catalog()
    except Exception as exc:
        print(f"Cannot read the GC-001 catalogue: {type(exc).__name__}: {exc}")
        print()
        print("This script needs database access. The galvanic series lives only in")
        print("the Supabase static asset 'ruleset:BIMGUARD-GC-001'; it is in no")
        print("repository file. Set SUPABASE_URL and the service key, then re-run.")
        return 2

    series = catalogue.get("galvanic_series") or {}
    materials = series.get("materials", series)
    if not materials:
        print("The catalogue returned an empty galvanic series.")
        return 2

    print(f"GC-001 galvanic series: {len(materials)} entries")
    print()
    print("Check 1 - noble flag")
    by_flag = check_noble_flag(materials)
    print()
    print("Check 2 - zinc/copper physics anchor")
    by_anchor = check_zinc_copper(materials)
    print()

    verdicts = [v for v in (by_flag, by_anchor) if v is not None]
    if not verdicts:
        print("INCONCLUSIVE - neither check could run. Inspect the series by hand.")
        return 1
    if len(set(verdicts)) > 1:
        print("CHECKS DISAGREE - the series is internally inconsistent.")
        print("That is a larger problem than the convention. Do not proceed.")
        return 1

    convention = verdicts[0]
    print(f"CONVENTION: {convention}")
    print()
    if convention == MORE_NEGATIVE:
        print("  galvanic.py:190                  CORRECT (more negative = anode)")
        print("  bimguard_corrosion_engine.py:353 WRONG   - the LIVE engine")
        print()
        print("  Every galvanic BCF issue names the wrong victim. See the defect")
        print("  report for the one-line fix and its regression test.")
    else:
        print("  bimguard_corrosion_engine.py:353 CORRECT (more positive = anode)")
        print("  galvanic.py:190                  WRONG   - dormant, Path B")
        print()
        print("  No user-facing defect: the wrong engine is not wired up. Fix before")
        print("  Path B is enabled.")
    print()
    print(f"Set series_convention in xm_001_cross_material.json to: {convention}")
    print("Paste the values above into the defect report as evidence.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
