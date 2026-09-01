"""Seed NFPA 13 Sec. 18.5 pipe penetration clearance rules (BIMGUARD-PC-001).

NFPA 13 requires annular clearance around pipe passing through walls, floors,
platforms and foundations, so that a sprinkler system can move relative to the
structure during a seismic event without the penetration acting as a restraint.
The requirement is banded by nominal pipe size, and is waived where the
construction is frangible or where flexible couplings already accommodate the
movement.

Provenance
----------
FEMA E-74 Sec. 6.4 (page 6-314) establishes the delegation chain rather than
the dimensions:

    ASCE/SEI 7-10 specifies that fire protection piping conform to NFPA 13...
    The 2010 edition of NFPA 13 contains prescriptive details and requirements
    for many aspects of the piping installation, such as hanger size and
    spacing, clearances between the system and other structural or
    nonstructural components...

That ingested extract is at ``docs/scraped_standards/seismic_fema_e74_official.md``.
The dimensions themselves come from NFPA 13 Sec. 18.5, which is copyrighted and
was not machine-ingested; they are recorded here on the authority of the
operator's library copy.

**Confidence.** The two base clearances (50 mm / 100 mm and their size bands)
are corroborated. The exemption *parameters* -- in particular the distance
within which a flexible coupling waives the requirement -- could not be
verified against the standard text and are seeded with ``needs_review`` set.
Check them against the library copy before the ruleset drives any verdict.

Enforcement status
------------------
The clearance rows use the same shape as the existing ``BIMGUARD-SB-001``
spatial clearance rule, so the comparator evaluates them today. The size
banding and the exemptions are carried in ``applies_when`` / ``exceptions`` /
``parameters``, which nothing in the pipeline currently reads:
``module4_comparator._evaluate_rule`` dispatches on ``operator`` and
``check_value`` alone. Until an evaluator honours them, the bands and
exemptions are **declarative, not enforced** -- see the warning this script
prints.

Usage::

    python scripts/seed_nfpa13_clearances.py [--dry-run] [--force]

Exit codes: ``0`` success, ``1`` write failure.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

RULESET_ID = "BIMGUARD-PC-001"
MECHANISM = "SEISMIC"
TARGET = "IfcPipeSegment"

#: Clause the dimensions come from, repeated into every row's source_text.
CLAUSE = "NFPA 13 Sec. 18.5 (Clearance)"

#: Delegation evidence, ingested and version-controlled.
DELEGATION = (
    "FEMA E-74 Sec. 6.4 p.6-314 delegates clearance requirements to NFPA 13; "
    "see docs/scraped_standards/seismic_fema_e74_official.md"
)

#: mm per inch, for the imperial figures the standard is written in.
MM_PER_INCH = 25.4


def _nominal(inches: float) -> float:
    """Return a nominal pipe size in mm, rounded to the metric designation."""
    return round(inches * MM_PER_INCH, 1)


#: The two base clearance bands. ``diameter_min_mm`` is inclusive,
#: ``diameter_max_mm`` inclusive; ``None`` means unbounded above.
CLEARANCE_BANDS = [
    {
        "reference": "PC-001.01",
        "clearance_mm": 50.0,
        "clearance_in": 2.0,
        "diameter_min_mm": _nominal(1.0),
        "diameter_max_mm": _nominal(3.5),
        "band_label": 'nominal 1" through 3-1/2"',
    },
    {
        "reference": "PC-001.02",
        "clearance_mm": 100.0,
        "clearance_in": 4.0,
        "diameter_min_mm": _nominal(4.0),
        "diameter_max_mm": None,
        "band_label": 'nominal 4" and larger',
    },
]

#: Conditions under which the clearance requirement is waived. Modelled as
#: their own rows so each carries its own citation, confidence and review
#: state, and so the UI can list them beside the requirement they modify.
EXEMPTIONS = [
    {
        "reference": "PC-001.03",
        "exemption_key": "breakaway_gypsum",
        "label": "Breakaway or frangible construction",
        "rationale": (
            "Gypsum board and equivalent breakaway construction fails locally "
            "before it can restrain the pipe, so the annular gap is not needed "
            "to accommodate differential movement."
        ),
        "predicate": {
            "host_material_any_of": [
                "gypsum",
                "gypsum board",
                "plasterboard",
                "drywall",
            ],
            "host_is_breakaway": True,
        },
        "verified": True,
        "note": "Construction class is qualitative; no numeric threshold to verify.",
    },
    {
        "reference": "PC-001.04",
        "exemption_key": "flexible_coupling_adjacent",
        "label": "Flexible couplings adjacent to the penetration",
        "rationale": (
            "A flexible coupling close to the penetration accommodates the "
            "differential movement the clearance would otherwise provide for."
        ),
        "predicate": {
            "flexible_coupling_within_mm": 300.0,
            "measured_from": "each face of the penetrated element",
        },
        "verified": False,
        "note": (
            "UNVERIFIED: the 300 mm (1 ft) proximity threshold could not be "
            "confirmed against NFPA 13 text and must be checked against the "
            "library copy before this exemption is enforced."
        ),
    },
    {
        "reference": "PC-001.05",
        "exemption_key": "below_scope_diameter",
        "label": "Pipe below the smallest banded size",
        "rationale": (
            "The clearance bands start at nominal 1 in.; smaller pipe is "
            "outside the scope of the requirement rather than exempted by a "
            "condition of the installation."
        ),
        "predicate": {"nominal_diameter_below_mm": _nominal(1.0)},
        "verified": True,
        "note": "Scope floor implied by the bands, not a conditional waiver.",
    },
]


def build_rows() -> list[dict]:
    """Return every rule row for the ruleset, bands first then exemptions."""
    rows: list[dict] = []

    exemption_refs = [e["reference"] for e in EXEMPTIONS]

    for band in CLEARANCE_BANDS:
        upper = band["diameter_max_mm"]
        applies_when = {
            "target_ifc_class": TARGET,
            "penetrates": ["IfcWall", "IfcSlab", "IfcFooting", "IfcPlate"],
            "nominal_diameter_mm": {
                "min": band["diameter_min_mm"],
                **({"max": upper} if upper is not None else {}),
            },
        }
        parameters = {
            "clearance_mm": band["clearance_mm"],
            "clearance_in": band["clearance_in"],
            "band_label": band["band_label"],
            "diameter_min_mm": band["diameter_min_mm"],
            "diameter_max_mm": upper,
            "geometry": "annular gap measured radially from the pipe outside surface",
            "exemption_refs": exemption_refs,
            "enforced_today": True,
            "banding_enforced_today": False,
        }
        bound = (
            f"{band['diameter_min_mm']:.1f} mm and above"
            if upper is None
            else f"{band['diameter_min_mm']:.1f}-{upper:.1f} mm"
        )
        rows.append(
            {
                "reference": band["reference"],
                "rule_type": "spatial_clearance",
                "rule_category": "property_check",
                "category": "seismic",
                "description": (
                    f"Annular clearance {band['clearance_mm']:.0f} mm "
                    f"({band['clearance_in']:.0f} in.) around pipe penetrations, "
                    f"{band['band_label']} ({bound})"
                ),
                "target_ifc_class": TARGET,
                "property_name": "AnnularClearance",
                "operator": ">=",
                "check_value": band["clearance_mm"],
                "unit": "mm",
                "severity": "mandatory",
                "keyword": "annular clearance",
                "compliance_type": "prescriptive",
                "applies_when": applies_when,
                "exceptions": exemption_refs,
                "parameters": json.dumps(parameters),
                "source_text": f"{CLAUSE}. {DELEGATION}",
                "related_refs": ["FEMA-E-74-6.4", "ASCE-7-10-13.6"],
                "confidence": 0.9,
                "needs_review": False,
                "extraction_method": "manual",
                "mechanism": MECHANISM,
                "ruleset_id": RULESET_ID,
            }
        )

    for item in EXEMPTIONS:
        parameters = {
            "exemption_key": item["exemption_key"],
            "predicate": item["predicate"],
            "rationale": item["rationale"],
            "waives": [b["reference"] for b in CLEARANCE_BANDS],
            "verified_against_standard": item["verified"],
            "note": item["note"],
            "enforced_today": False,
        }
        rows.append(
            {
                "reference": item["reference"],
                "rule_type": "exemption",
                "rule_category": "property_check",
                "category": "seismic",
                "description": f"Clearance exemption — {item['label']}",
                "target_ifc_class": TARGET,
                "property_name": "AnnularClearance",
                "operator": "exempt",
                "severity": "advisory",
                "keyword": item["exemption_key"],
                "compliance_type": "exemption",
                "applies_when": item["predicate"],
                "exceptions": [],
                "parameters": json.dumps(parameters),
                "source_text": f"{CLAUSE} — exemption. {DELEGATION}",
                "related_refs": [b["reference"] for b in CLEARANCE_BANDS],
                "confidence": 0.9 if item["verified"] else 0.4,
                "needs_review": not item["verified"],
                "extraction_method": "manual",
                "mechanism": MECHANISM,
                "ruleset_id": RULESET_ID,
            }
        )

    return rows


def summarise(rows: list[dict]) -> None:
    """Print the rule structure so the modelling can be reviewed."""
    print()
    print("=" * 78)
    print(f"{RULESET_ID} — NFPA 13 Sec. 18.5 pipe penetration clearance")
    print("=" * 78)

    print("\nREQUIREMENTS (evaluated by the comparator today)")
    for row in rows:
        if row["rule_type"] != "spatial_clearance":
            continue
        params = json.loads(row["parameters"])
        band = row["applies_when"]["nominal_diameter_mm"]
        upper = f"{band['max']:.1f}" if "max" in band else "unbounded"
        print(f"\n  {row['reference']}  {params['band_label']}")
        print(f"    check      : {row['property_name']} {row['operator']} "
              f"{row['check_value']:.0f} {row['unit']}  "
              f"({params['clearance_in']:.0f} in.)")
        print(f"    applies to : {row['target_ifc_class']}, nominal diameter "
              f"{band['min']:.1f}-{upper} mm")
        print(f"    penetrating: {', '.join(row['applies_when']['penetrates'])}")
        print(f"    waived by  : {', '.join(row['exceptions'])}")
        print(f"    severity   : {row['severity']}   confidence: {row['confidence']}")

    print("\nEXEMPTIONS (declarative — see warning below)")
    for row in rows:
        if row["rule_type"] != "exemption":
            continue
        params = json.loads(row["parameters"])
        flag = "" if params["verified_against_standard"] else "   [NEEDS REVIEW]"
        print(f"\n  {row['reference']}  {params['exemption_key']}{flag}")
        print(f"    waives    : {', '.join(params['waives'])}")
        print(f"    predicate : {json.dumps(params['predicate'])}")
        print(f"    rationale : {params['rationale'][:96]}...")
        if not params["verified_against_standard"]:
            print(f"    WARNING   : {params['note']}")


def main() -> int:
    """Seed the ruleset and report what was written."""
    parser = argparse.ArgumentParser(description="Seed NFPA 13 clearance rules.")
    parser.add_argument("--dry-run", action="store_true", help="build but do not write")
    parser.add_argument(
        "--force", action="store_true", help="rewrite rows whose reference exists"
    )
    args = parser.parse_args()

    rows = build_rows()
    summarise(rows)

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0

    from app.environment import load_env_file

    load_env_file()
    from app.services.rules_service import RuleService

    service = RuleService()
    existing = {
        row["reference"]: row for row in service.list_by_ruleset(RULESET_ID)
    }

    written = skipped = replaced = 0
    for row in rows:
        current = existing.get(row["reference"])
        if current and not args.force:
            skipped += 1
            continue
        if current and args.force:
            service.delete_rule(current["id"])
            replaced += 1
        try:
            service.create_rule(**row)
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            print(f"error writing {row['reference']}: {exc}", file=sys.stderr)
            return 1
        written += 1

    print(f"\nwrote {written} rules ({replaced} replaced), skipped {skipped}")
    print(
        "\nWARNING: applies_when and exceptions are stored but not evaluated.\n"
        "  module4_comparator._evaluate_rule dispatches on operator and\n"
        "  check_value only, so today BOTH clearance rules match every\n"
        f"  {TARGET} regardless of diameter, and no exemption suppresses a\n"
        "  finding. Wire an evaluator before this ruleset drives verdicts."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
