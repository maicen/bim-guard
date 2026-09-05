#!/usr/bin/env python
"""Controlled MM-001 cases: prove the engine fires where it should, and only there.

The corpus runs in ``scripts/validation_engine_matrix.py`` measure what MM-001
does on real models. They cannot show *why*, because a real model varies
material, medium, environment and temperature all at once. This harness holds
three of those fixed and moves one, so each verdict has exactly one cause.

Three families of case:

``positive``
    A pairing whose failure mode is documented in the literature. It must
    produce a finding. Galvanised steel sitting in the stagnant water of a
    fire main is the textbook one: zinc depletes, the steel is then bare.

``negative``
    A pairing that is correct engineering practice. It must produce *nothing* --
    not a Low-band finding, not a data-quality refusal. Copper in potable cold
    water is the specification, and flagging it would make the tool unusable on
    the very system it is most often pointed at. Copper in 60 C hot water is
    the sharper case: 60 C is mandated by HSE HSG274 for Legionella control and
    is required by MC-001 in this same codebase, so an MM-001 finding there
    would make the tool contradict itself. The pack's ``kinetics_guard`` is
    what prevents it.

``refusal``
    An element the engine cannot honestly score. It must produce a
    data-quality Issue naming the missing input -- never a silent pass. An
    unassessed element reported as compliant is the failure mode this whole
    tri-state design exists to prevent.

Every expectation below is asserted against the engine's actual output. The
script exits non-zero if any case does not behave as stated, so it is a test of
the claim, not an illustration of it.

Usage::

    uv run python scripts/validation_mm001_controls.py
    uv run python scripts/validation_mm001_controls.py --json docs/validation/data/mm001-controls.json
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

warnings.filterwarnings("ignore")

from app.modules.comparator.material_media import compare, load_rule_pack  # noqa: E402
from app.modules.ifc_reader.piping_producer import (  # noqa: E402
    ENVIRONMENT_SOURCE_DEFAULT,
    MATERIAL_SOURCE_KEY,
    TEMPERATURE_SOURCE_INFERENCE,
)
from app.modules.ifc_reader.piping_schema import (  # noqa: E402
    EnvironmentClass,
    PipingElement,
    PipingSystem,
)

DATA_QUALITY = "data_quality"

#: Expectation vocabulary. "finding" means a banded Issue; "silent" means the
#: engine produced nothing at all; "refusal" means a data-quality Issue.
FINDING = "finding"
SILENT = "silent"
REFUSAL = "refusal"


def element(
    ref: str,
    *,
    material: str | None,
    system: PipingSystem,
    environment: EnvironmentClass,
    temperature_c: float | None,
) -> PipingElement:
    """Build one fully specified piping element for a control case.

    Provenance is stamped the way the producer stamps it, because MM-001 reads
    it back into every finding: a control case that carried no provenance would
    exercise a slightly different path from the real one.
    """
    properties: dict[str, Any] = {}
    if material is not None:
        properties[MATERIAL_SOURCE_KEY] = "ifc_material_association"

    return PipingElement(
        id=ref,
        ifc_class="IfcFlowSegment",
        subtype="pipe_segment",
        name=ref,
        material=material or "Unknown",
        material_confidence="high" if material else None,
        system=system,
        operating_temperature_c=temperature_c,
        temperature_source=TEMPERATURE_SOURCE_INFERENCE if temperature_c is not None else None,
        temperature_confidence="low" if temperature_c is not None else None,
        environment_class=environment,
        environment_source=(
            ENVIRONMENT_SOURCE_DEFAULT
            if environment is not EnvironmentClass.UNCLASSIFIED
            else None
        ),
        environment_confidence="low" if environment is not EnvironmentClass.UNCLASSIFIED else None,
        properties=properties,
    )


#: (ref, expectation, why, element kwargs)
CASES: list[tuple[str, str, str, dict[str, Any]]] = [
    # --- Positive controls: documented failure modes that must be caught -----
    (
        "POS-1-galv-stagnant",
        FINDING,
        "Galvanised steel in the stagnant water of a fire main. Zinc depletes "
        "with no flow to replenish the passive layer, leaving bare steel. "
        "CIBSE Guide G.",
        {
            "material": "GalvanisedSteel",
            "system": PipingSystem.FIRE_SPRINKLER,
            "environment": EnvironmentClass.T1_INDOOR_DAMP,
            "temperature_c": 20.0,
        },
    ),
    (
        "POS-2-galv-hot",
        FINDING,
        "Galvanised steel in domestic hot water. Above ~60 C zinc reverses "
        "polarity against steel and the coating becomes anodic-turned-cathodic. "
        "CIBSE Guide G.",
        {
            "material": "GalvanisedSteel",
            "system": PipingSystem.DOMESTIC_HOT_WATER,
            "environment": EnvironmentClass.T1_INDOOR_DAMP,
            "temperature_c": 60.0,
        },
    ),
    (
        "POS-3-galv-pool",
        FINDING,
        "Galvanised steel in pool circulation water, the most aggressive cell "
        "in the pack. ASTM B117.",
        {
            "material": "GalvanisedSteel",
            "system": PipingSystem.POOL_CIRCULATION,
            "environment": EnvironmentClass.T3_CHLORIDE,
            "temperature_c": 27.0,
        },
    ),
    # --- Negative controls: correct practice that must not be flagged -------
    (
        "NEG-1-copper-potable-cold",
        SILENT,
        "Copper in potable cold water, indoors. This is the specification, not "
        "a defect. CDA Copper Tube Handbook.",
        {
            "material": "Copper_C12200",
            "system": PipingSystem.DOMESTIC_COLD_WATER,
            "environment": EnvironmentClass.T1_INDOOR_DAMP,
            "temperature_c": 12.0,
        },
    ),
    (
        "NEG-2-copper-potable-hot-60c",
        SILENT,
        "Copper in domestic hot water at the 60 C HSE HSG274 mandates for "
        "Legionella control, and that MC-001 requires in this same codebase. "
        "Only the pack's kinetics_guard keeps this Low; without it the "
        "temperature and environment terms alone would band it Medium.",
        {
            "material": "Copper_C12200",
            "system": PipingSystem.DOMESTIC_HOT_WATER,
            "environment": EnvironmentClass.T1_INDOOR_DAMP,
            "temperature_c": 60.0,
        },
    ),
    (
        "NEG-3-copper-chilled",
        SILENT,
        "Copper in chilled water. Benign pairing, benign environment.",
        {
            "material": "Copper_C12200",
            "system": PipingSystem.CHILLED_WATER_FLOW,
            "environment": EnvironmentClass.T1_INDOOR_DAMP,
            "temperature_c": 6.0,
        },
    ),
    (
        "NEG-4-pvc-cold-water",
        SILENT,
        "PVC in cold water. The plastic is immune to the electrochemical "
        "mechanism MM-001 scores, and the pairing is mapped, so the engine "
        "scores it and finds nothing.",
        {
            "material": "PVC",
            "system": PipingSystem.DOMESTIC_COLD_WATER,
            "environment": EnvironmentClass.T1_INDOOR_DAMP,
            "temperature_c": 12.0,
        },
    ),
    # --- Refusal controls: missing inputs must refuse, never pass -----------
    (
        "REF-1-material-unknown",
        REFUSAL,
        "No material identified. The element is unassessed, not compliant.",
        {
            "material": None,
            "system": PipingSystem.DOMESTIC_COLD_WATER,
            "environment": EnvironmentClass.T1_INDOOR_DAMP,
            "temperature_c": 12.0,
        },
    ),
    (
        "REF-2-environment-unclassified",
        REFUSAL,
        "Environment unclassified, so the environment term cannot be "
        "evaluated. Scoring it benign would suppress findings on every "
        "element the producer could not classify.",
        {
            "material": "GalvanisedSteel",
            "system": PipingSystem.FIRE_SPRINKLER,
            "environment": EnvironmentClass.UNCLASSIFIED,
            "temperature_c": 20.0,
        },
    ),
    (
        "REF-3-temperature-missing",
        REFUSAL,
        "No operating temperature. A default here would be a fabricated input "
        "to a compliance verdict.",
        {
            "material": "GalvanisedSteel",
            "system": PipingSystem.FIRE_SPRINKLER,
            "environment": EnvironmentClass.T1_INDOOR_DAMP,
            "temperature_c": None,
        },
    ),
    (
        "REF-4-unmapped-pairing",
        REFUSAL,
        "Titanium in medical oxygen has no cell in the MM-001 matrix. Per "
        "unmapped_pairing_policy an absent cell must not be scored compliant.",
        {
            "material": "Titanium",
            "system": PipingSystem.MEDICAL_GAS_OXYGEN,
            "environment": EnvironmentClass.T1_INDOOR_DAMP,
            "temperature_c": 20.0,
        },
    ),
    (
        "REF-5-unmapped-medium-foul",
        REFUSAL,
        "PVC in foul drainage, with everything else known. The refusal is not "
        "about the element: MM-001's matrix carries eight media and "
        "foul_water is not one of them, so no material can be scored on a "
        "drainage system. Honest, but it bounds what MM-001 can reach -- see "
        "the media-coverage limitation in the validation report.",
        {
            "material": "PVC",
            "system": PipingSystem.FOUL_DRAINAGE,
            "environment": EnvironmentClass.T1_INDOOR_DAMP,
            "temperature_c": 20.0,
        },
    ),
]


def observe(issues: list[Any]) -> str:
    """Classify what the engine actually did with one element."""
    if not issues:
        return SILENT
    if any(getattr(i, "mechanism", "") == DATA_QUALITY for i in issues):
        return REFUSAL
    return FINDING


def run() -> tuple[list[dict[str, Any]], int]:
    """Run every control case. Returns (records, failure count)."""
    pack = load_rule_pack()
    records: list[dict[str, Any]] = []
    failures = 0

    for ref, expected, why, kwargs in CASES:
        el = element(ref, **kwargs)
        issues = compare([el], pack)
        actual = observe(issues)
        passed = actual == expected
        failures += 0 if passed else 1

        issue = issues[0] if issues else None
        records.append(
            {
                "ref": ref,
                "material": kwargs["material"] or "Unknown",
                "system": kwargs["system"].value,
                "medium": (issue.metadata or {}).get("medium") if issue else None,
                "environment": kwargs["environment"].value,
                "temperature_c": kwargs["temperature_c"],
                "expected": expected,
                "actual": actual,
                "passed": passed,
                "band": issue.band.value if issue and actual == FINDING else None,
                "score": round(issue.score, 4) if issue and actual == FINDING else None,
                "check": (issue.metadata or {}).get("check") if issue and actual == REFUSAL else None,
                "kinetics_guard_applied": (
                    (issue.metadata or {}).get("kinetics_guard_applied") if issue else None
                ),
                "title": issue.title if issue else None,
                "rationale": why,
            }
        )

    return records, failures


def print_report(records: list[dict[str, Any]], failures: int) -> None:
    """Print the control matrix."""
    print("=" * 100)
    print("MM-001 CONTROLLED CASES")
    print("=" * 100)
    header = (
        f"{'ref':<28}{'material':<18}{'medium':<16}{'T':>6}  "
        f"{'expected':<9}{'actual':<9}{'band':<9}{'score':>7}"
    )
    print(header)
    print("-" * len(header))
    for r in records:
        temp = "-" if r["temperature_c"] is None else f"{r['temperature_c']:.0f}"
        score = "-" if r["score"] is None else f"{r['score']:.3f}"
        mark = "" if r["passed"] else "  <-- MISMATCH"
        print(
            f"{r['ref']:<28}{r['material']:<18}{str(r['medium'] or '-'):<16}{temp:>6}  "
            f"{r['expected']:<9}{r['actual']:<9}{str(r['band'] or '-'):<9}{score:>7}"
            f"{mark}"
        )
    print("-" * len(header))
    print(f"{len(records) - failures}/{len(records)} control cases behaved as specified")
    if failures:
        print(f"{failures} MISMATCH(ES) -- the engine did not do what the case asserts")


def main(argv: list[str] | None = None) -> int:
    """Run the MM-001 control matrix."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--json", type=Path, default=None, help="Also write the record as JSON")
    args = parser.parse_args(argv)

    records, failures = run()
    print_report(records, failures)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {
                    "cases_total": len(records),
                    "cases_passed": len(records) - failures,
                    "cases_failed": failures,
                    "cases": records,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nWrote {args.json}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
