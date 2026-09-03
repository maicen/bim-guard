"""
scripts/inspect_ifc_properties.py
------------------------------------
Diagnostic tool: runs the same IFCReader.extract_for_compliance()
lookup Module 4 uses during a real analysis, and reports per rule whether
the expected IFC class and property were actually found in a file. For
anything reported missing, also lists nearby property names so a near-miss
(e.g. a property exported under a slightly different name) is visible
instead of just "missing".

Run this against a fresh Revit/IFC export before wiring it into the app,
to catch export-setting and rule property_name mismatches early.

Usage:
    uv run python scripts/inspect_ifc_properties.py path/to/model.ifc
    uv run python scripts/inspect_ifc_properties.py path/to/model.ifc --target IfcStairFlight
    uv run python scripts/inspect_ifc_properties.py path/to/model.ifc --theme MEP
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ifcopenshell
import ifcopenshell.util.element

from app.modules.ifc_reader import IFCReader
from app.services.rules_service import RuleService


def _load_reader(ifc_path: Path) -> IFCReader:
    # Bypass load_ifc_file()'s quality-score auto-improve step on purpose --
    # this is a read-only diagnostic and must not write an "_improved" file.
    reader = IFCReader()
    reader.ifc_file = ifcopenshell.open(str(ifc_path))
    return reader


def _actual_property_names(reader: IFCReader, target: str) -> set[str]:
    """Union of every pset/qto/direct-attribute name found across all elements of a class."""
    try:
        elements = reader.ifc_file.by_type(target)
    except Exception:
        elements = []

    names: set[str] = set()
    for el in elements:
        try:
            psets = ifcopenshell.util.element.get_psets(el, psets_only=False)
        except Exception:
            psets = {}
        for props in psets.values():
            if isinstance(props, dict):
                names.update(props.keys())
        names.update(reader.get_direct_attributes(el).keys())
    return names


def inspect(ifc_path: Path, target_filter: str | None, theme_filter: str | None) -> None:
    rules = [
        r
        for r in RuleService().list_rules()
        if (r.get("target_ifc_class") or "").strip() and (r.get("property_name") or "").strip()
    ]
    if target_filter:
        rules = [r for r in rules if r.get("target_ifc_class") == target_filter]
    if theme_filter:
        rules = [r for r in rules if RuleService.infer_theme(r) == theme_filter]

    if not rules:
        print("No rules with both target_ifc_class and property_name to check against.")
        return

    reader = _load_reader(ifc_path)
    results = reader.extract_for_compliance(rules)

    actual_cache: dict[str, set[str]] = {}
    seen_targets: set[str] = set()
    tally = {"OK": 0, "NEAR-MISS": 0, "MISSING": 0, "NO_ELEMENTS": 0}

    for result in sorted(results, key=lambda r: (r["target_ifc_class"], r["property_name"])):
        target = result["target_ifc_class"]
        prop = result["property_name"]
        elements = result["elements"]

        if target not in seen_targets:
            seen_targets.add(target)
            print(f"\n=== {target} ===")
            if not elements:
                print("  NO ELEMENTS of this class found in the file.")
                print("  -> Check Revit's IFC class mapping for this category.")

        if not elements:
            tally["NO_ELEMENTS"] += 1
            continue

        found_any = any(el["found"] for el in elements)
        if found_any:
            pset_used = next(el["found_pset"] for el in elements if el["found"])
            print(f"  [OK]        {prop}  (in {pset_used})")
            tally["OK"] += 1
            continue

        if target not in actual_cache:
            actual_cache[target] = _actual_property_names(reader, target)
        suggestion = difflib.get_close_matches(prop, actual_cache[target], n=1, cutoff=0.6)
        if suggestion:
            print(f"  [NEAR-MISS] {prop}  -- found similar property: '{suggestion[0]}'")
            tally["NEAR-MISS"] += 1
        else:
            print(f"  [MISSING]   {prop}  -- not present under any pset/attribute on {len(elements)} element(s)")
            tally["MISSING"] += 1

    print(
        f"\n{'-' * 40}\n"
        f"OK {tally['OK']} | NEAR-MISS {tally['NEAR-MISS']} | "
        f"MISSING {tally['MISSING']} | NO_ELEMENTS (class) {tally['NO_ELEMENTS']}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check whether an IFC export actually contains the properties your rules expect."
    )
    parser.add_argument("ifc_path", type=Path, help="Path to the .ifc file to inspect")
    parser.add_argument("--target", help="Limit to a single IFC class, e.g. IfcStairFlight")
    parser.add_argument("--theme", choices=["Architecture", "MEP"], help="Limit to rules of one theme")
    args = parser.parse_args()

    if not args.ifc_path.exists():
        parser.error(f"File not found: {args.ifc_path}")

    inspect(args.ifc_path, args.target, args.theme)


if __name__ == "__main__":
    main()
