"""Seed the XM-001 cross-material galvanic corrosion rule family (MEP-CORROSION).

Inserts per-pair galvanic couple rules into the ``rules`` table for the
``MEP-CORROSION`` ruleset. Each row names a dissimilar-metal pairing that
recurs in MEP building services, the electrochemical driving voltage across
it, and the mitigation required to break the couple.

Provenance
----------
MIL-STD-889B Table II, *Galvanic series of selected metals in seawater*, is
the ordinal authority for which member of a couple is anodic. The scraped
source is ``docs/scraped_standards/corrosion_mil_std_889_galvanic.md`` and the
machine extract is produced by ``scripts/parse_mil_std_889_series.py``.

Table II is **ordinal only** -- it ranks alloys but publishes no electrode
potentials. The millivolt figures in these rows therefore do NOT come from
MIL-STD-889B. They are read at build time from the seeded ``BIMGUARD-GC-001``
galvanic series (``potential`` values against Ag/AgCl in seawater, sourced
from WorldStainless / Euro Inox 2025 and the AUCSC Basic Corrosion Course
2024). MIL-STD-889B is cited for the *direction* of attack; GC-001 supplies
the *magnitude*. Conflating the two would misattribute the numbers.

Single source of truth
----------------------
No galvanic series is embedded here. :func:`build_rows` reads
``bimguard_corrosion_engine.GALVANIC_SERIES`` -- itself database-backed via
``corrosion_rule_catalog`` -- and computes every ``gap_v`` at build time. A
material key that is not in the live series aborts the run rather than seeding
a couple scored against a potential that does not exist.

Read this before extending the ruleset
--------------------------------------
Four things about this seed are load-bearing and easy to get wrong:

1. **Material keys are canonical series keys, not free text.** The first pair
   is stored as ``["copper", "galv_steel"]``. It is NOT stored as
   ``"galvanized_steel"``: ``resolve_material("galvanized_steel")`` returns
   ``"carbon_steel"`` (0.55 V), because the alias table holds
   ``"galvanized steel"`` with a space and the substring fallback will not
   cross an underscore. Seeding the underscored spelling silently swaps a
   0.54 V couple for a 0.27 V one and drops the band from Critical to Medium.
   The spelling this pair was originally specified under is preserved in
   ``parameters.material_pair_declared`` so the substitution stays auditable.
   :func:`validate_materials` enforces this for every future row.

2. **There is no ``mitigation`` column on ``rules``.** The table's columns are
   fixed (see
   ``supabase/migrations/20260721135500_init_core_public_tables.sql``);
   ``mitigation`` is a field on *findings*, populated by the engines from a
   mitigation catalogue. The mitigation text therefore lives in
   ``parameters.mitigation``, with ``parameters.mitigation_refs`` pointing at
   the existing catalogue codes.

3. **This script never rewrites the shared mitigation catalogue.**
   ``MIT-GC-001`` is already defined, in three places, as "Install dielectric
   isolation gaskets at all contact points between dissimilar metals" -- it
   does not mention clearance. The clearance half of the requirement is the
   existing ``MIT-GC-006``, "Increase separation distance to prevent moisture
   bridge formation". Both codes are referenced; neither is redefined.
   Rewriting ``MIT-GC-001`` in place would silently restate the mitigation on
   every historical GC-001 finding.

4. **The 25 mm clearance is declarative, not enforced.** The approved XM-001
   comparator (``app/modules/module4_comparator/cross_material.py``, pack
   ``data/rulesets/xm_001_cross_material.json``, status APPROVED v1.0) models
   separation *categorically* -- ``direct_contact`` (factor 1.0) and
   ``same_loop`` (factor 0.8) -- and consumes no millimetre geometry at all.
   Nothing in the pipeline reads ``min_clearance_mm`` today. See the warning
   this script prints.

Usage::

    python scripts/seed_galvanic_corrosion_rules.py            # dry run
    python scripts/seed_galvanic_corrosion_rules.py --apply    # write
    python scripts/seed_galvanic_corrosion_rules.py --apply --force

Exit codes: ``0`` success, ``1`` validation or write failure.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

RULESET_ID = "MEP-CORROSION"
MECHANISM = "XM-001"
TARGET = "IfcPipeSegment"

#: Default annular separation required where a couple is not positively
#: isolated by a dielectric break.
DEFAULT_CLEARANCE_MM = 25.0

#: Ordinal authority for anode direction. Carries no potentials -- see the
#: module docstring.
CLAUSE = "MIL-STD-889B Table II (Galvanic series of selected metals in seawater)"

SOURCE_DOC = "docs/scraped_standards/corrosion_mil_std_889_galvanic.md"

#: Where the millivolt figures actually come from.
POTENTIAL_SOURCE = (
    "Potentials read from the seeded BIMGUARD-GC-001 galvanic series "
    "(Ag/AgCl, seawater; WorldStainless / Euro Inox 2025, AUCSC 2024). "
    "MIL-STD-889B Table II is ordinal and supplies anode direction only."
)

#: Existing catalogue codes. Referenced, never redefined -- see docstring (3).
MIT_DIELECTRIC = "MIT-GC-001"
MIT_SEPARATION = "MIT-GC-006"

#: Mitigation text carried on every row of the family.
MITIGATION_TEXT = "MIT-GC-001: Install dielectric isolation or maintain 25mm clearance."

#: The couple family. ``material_pair`` holds canonical GC-001 series keys.
#: ``declared`` preserves any differently-spelled name the pair was specified
#: under, so the canonicalisation stays auditable.
COUPLES = [
    {
        "reference": "XM-001.01",
        "material_pair": ["copper", "galv_steel"],
        "declared": ["copper", "galvanized_steel"],
        "application": "Galvanised steel support bracket / copper pipe",
        "min_clearance_mm": DEFAULT_CLEARANCE_MM,
        "gc_pairing_id": "P-001",
    },
    {
        "reference": "XM-001.02",
        "material_pair": ["carbon_steel", "ss316_passive"],
        "declared": None,
        "application": "Carbon steel structure / SS316 process pipe",
        "min_clearance_mm": DEFAULT_CLEARANCE_MM,
        "gc_pairing_id": "P-002",
    },
    {
        "reference": "XM-001.03",
        "material_pair": ["aluminium", "copper"],
        "declared": None,
        "application": "Aluminium cable tray / copper pipework",
        "min_clearance_mm": DEFAULT_CLEARANCE_MM,
        "gc_pairing_id": "P-003",
    },
    {
        "reference": "XM-001.04",
        "material_pair": ["galv_steel", "ss316_passive"],
        "declared": None,
        "application": "Galvanised unistrut / SS316 process pipe",
        "min_clearance_mm": DEFAULT_CLEARANCE_MM,
        "gc_pairing_id": "P-006",
    },
]


def _series() -> dict:
    """Return the live, database-backed GC-001 galvanic series."""
    from app.engines.bimguard_corrosion_engine import GALVANIC_SERIES

    return GALVANIC_SERIES


def validate_materials(series: dict) -> list[str]:
    """Return one error string per material key absent from the galvanic series.

    Guards the failure mode in the module docstring (1): a key the series does
    not hold would otherwise seed a couple whose voltage cannot be computed
    or -- once resolved through ``resolve_material`` -- one scored against the
    wrong metal entirely.
    """
    errors: list[str] = []
    for couple in COUPLES:
        for key in couple["material_pair"]:
            if key not in series:
                errors.append(
                    f"{couple['reference']}: material {key!r} is not in the "
                    f"GC-001 galvanic series ({len(series)} keys). Use a "
                    f"canonical series key, not an IFC material string."
                )
    return errors


def _anode_cathode(pair: list[str], series: dict) -> tuple[str, str, float]:
    """Return ``(anode, cathode, gap_v)`` for a couple.

    Higher ``potential`` is more active, so that member corrodes
    preferentially. The convention is stated on the seeded GC-001 payload as
    "Lower potential = more noble (cathodic). Higher potential = more active
    (anodic)".
    """
    first, second = pair
    pot_first = float(series[first]["potential"])
    pot_second = float(series[second]["potential"])
    if pot_first >= pot_second:
        anode, cathode = first, second
    else:
        anode, cathode = second, first
    return anode, cathode, round(abs(pot_first - pot_second), 4)


def build_rows() -> list[dict]:
    """Return a rule row per galvanic couple, voltages computed from the series."""
    series = _series()

    errors = validate_materials(series)
    if errors:
        for line in errors:
            print(f"error: {line}", file=sys.stderr)
        raise SystemExit(1)

    rows: list[dict] = []
    for couple in COUPLES:
        pair = couple["material_pair"]
        anode, cathode, gap_v = _anode_cathode(pair, series)
        clearance = float(couple["min_clearance_mm"])

        applies_when = {
            "target_ifc_class": TARGET,
            "material_pair": pair,
            "min_clearance_mm": clearance,
        }

        parameters = {
            "mitigation": MITIGATION_TEXT,
            "mitigation_refs": [MIT_DIELECTRIC, MIT_SEPARATION],
            "mitigation_catalogue_mutated": False,
            "anode": anode,
            "anode_label": series[anode]["label"],
            "cathode": cathode,
            "cathode_label": series[cathode]["label"],
            "gap_v": gap_v,
            "potentials_v": {key: float(series[key]["potential"]) for key in pair},
            "application": couple["application"],
            "gc_pairing_id": couple["gc_pairing_id"],
            "min_clearance_mm": clearance,
            "potential_source": POTENTIAL_SOURCE,
            "series_convention": (
                "higher potential = more active (anodic); lower = more noble"
            ),
            "enforced_today": False,
            "separation_model_note": (
                "XM-001 v1.0 scores separation categorically (direct_contact "
                "1.0 / same_loop 0.8) and reads no millimetre geometry, so "
                "min_clearance_mm is declarative until an evaluator consumes it."
            ),
        }
        if couple["declared"]:
            parameters["material_pair_declared"] = couple["declared"]
            parameters["material_pair_canonicalised"] = True

        rows.append(
            {
                "reference": couple["reference"],
                "rule_type": "material_compatibility",
                "rule_category": "threshold_band",
                "category": "MEP",
                "description": (
                    f"Galvanic couple {series[anode]['label']} (anode) / "
                    f"{series[cathode]['label']} (cathode) -- {gap_v:.2f} V "
                    f"driving potential; isolate or maintain "
                    f"{clearance:.0f} mm clearance"
                ),
                "target_ifc_class": TARGET,
                "property_name": "GalvanicSeparationDistance",
                "operator": ">=",
                "check_value": clearance,
                "unit": "mm",
                "severity": "mandatory",
                "keyword": "galvanic corrosion",
                "compliance_type": "prescriptive",
                "applies_when": applies_when,
                "exceptions": [],
                "parameters": json.dumps(parameters),
                "source_text": f"{CLAUSE}. See {SOURCE_DOC}. {POTENTIAL_SOURCE}",
                "related_refs": ["BIMGUARD-GC-001", "BIMGUARD-XM-001", "MIL-STD-889B"],
                "confidence": 0.9,
                "needs_review": False,
                "extraction_method": "manual",
                "mechanism": MECHANISM,
                "ruleset_id": RULESET_ID,
            }
        )

    return rows


def summarise(rows: list[dict]) -> None:
    """Print the rule family so the modelling can be reviewed before writing."""
    print()
    print("=" * 78)
    print(f"{RULESET_ID} / {MECHANISM} - cross-material galvanic couples")
    print("=" * 78)

    for row in rows:
        params = json.loads(row["parameters"])
        applies_when = row["applies_when"]
        print(f"\n  {row['reference']}  {params['application']}")
        print(f"    pair       : {' + '.join(applies_when['material_pair'])}")
        if params.get("material_pair_canonicalised"):
            print(
                f"    declared as: {' + '.join(params['material_pair_declared'])}"
                "   [canonicalised - see docstring (1)]"
            )
        print(
            f"    anode      : {params['anode']} ({params['anode_label']}) "
            f"corrodes preferentially"
        )
        print(f"    cathode    : {params['cathode']} ({params['cathode_label']})")
        print(f"    driving V  : {params['gap_v']:.2f} V  {params['potentials_v']}")
        print(
            f"    check      : {row['property_name']} {row['operator']} "
            f"{row['check_value']:.0f} {row['unit']}"
        )
        print(f"    mitigation : {params['mitigation']}")
        print(f"    refs       : {', '.join(params['mitigation_refs'])}")
        print(f"    severity   : {row['severity']}   confidence: {row['confidence']}")


def _warn() -> None:
    """Print the enforcement caveats that the rows themselves cannot carry."""
    print(
        "\nWARNING - what is stored is not yet what is enforced:\n"
        "  * min_clearance_mm is declarative. The approved XM-001 comparator\n"
        "    scores separation categorically (direct_contact / same_loop) and\n"
        "    reads no millimetre geometry, so no verdict turns on 25 mm today.\n"
        "  * applies_when.material_pair is stored but not dispatched on;\n"
        "    module4_comparator._evaluate_rule keys off operator and\n"
        f"    check_value alone, so each row matches every {TARGET}.\n"
        "  * The shared mitigation catalogue was NOT modified. MIT-GC-001 keeps\n"
        "    its existing dielectric-gasket wording; the clearance half of the\n"
        "    requirement is MIT-GC-006. Both are referenced from parameters.\n"
        "  Wire an evaluator before this ruleset drives verdicts."
    )


def main() -> int:
    """Build, summarise and -- only with ``--apply`` -- write the rule family."""
    parser = argparse.ArgumentParser(
        description="Seed XM-001 cross-material galvanic corrosion rules."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write to the live database (default: dry run, no mutation)",
    )
    parser.add_argument(
        "--force", action="store_true", help="rewrite rows whose reference exists"
    )
    args = parser.parse_args()

    rows = build_rows()
    summarise(rows)

    if not args.apply:
        print(
            f"\nDRY RUN - nothing written. {len(rows)} rules would be inserted "
            f"into ruleset {RULESET_ID}."
        )
        print("Re-run with --apply to write to the live database.")
        _warn()
        return 0

    from app.environment import load_env_file

    load_env_file()
    from app.services.rules_service import RuleService

    service = RuleService()
    existing = {row["reference"]: row for row in service.list_by_ruleset(RULESET_ID)}

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
    if skipped:
        print("  (existing references left untouched; use --force to rewrite)")
    _warn()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
