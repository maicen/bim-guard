#!/usr/bin/env python
"""Audit piping operating-temperature coverage across IFC models.

Reports, per model and overall, how many piping elements carry an operating
temperature and where the answer came from:

    from IFC    read from an OperatingTemperature-style property on the
                element. Authoritative; absent from every model measured here.
    inferred    the design temperature for that piping system, from
                piping_producer.infer_temperature_from_system. A statement
                about ordinary MEP practice, not a reading of this model.
    unknown     neither source resolved one. Stays Undetermined: MM-001
                raises temperature_missing rather than scoring the element.

The two sources are kept apart on purpose. Temperature is not a mild input -
MM-001's stress bands step at 10, 25, 40, 60, 80 and 100 C, and the 60 C edge
is the zinc polarity reversal on galvanised steel, a step change rather than a
gradient. A headline number merging a design assumption with a stated value
would hide which side of that edge a verdict rests on.

The band histogram below shows where the resolved temperatures land, so a
reviewer can see at a glance whether an inference is doing real work or just
parking elements in the ambient band.

Usage:
    uv run python scripts/trace_temperature_coverage.py
    uv run python scripts/trace_temperature_coverage.py --models-dir data/test_models
    uv run python scripts/trace_temperature_coverage.py --no-inference   # file only
    uv run python scripts/trace_temperature_coverage.py --json docs/validation/data/temperature-coverage.json
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from collections import Counter
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

warnings.filterwarnings("ignore")

import ifcopenshell  # noqa: E402

from app.modules.ifc_reader import piping_producer as pp  # noqa: E402

DEFAULT_MODELS_DIR = Path("test-models/models")

#: The MM-001 temperature_stress bands, for the histogram. Lower bound
#: inclusive, upper exclusive, mirroring the pack.
_BANDS: tuple[tuple[float | None, float | None, str], ...] = (
    (None, 10.0, "<10 chilled/cold"),
    (10.0, 25.0, "10-25 ambient"),
    (25.0, 40.0, "25-40 tempered"),
    (40.0, 60.0, "40-60 below zinc edge"),
    (60.0, 80.0, "60-80 DHW / zinc reversal"),
    (80.0, 100.0, "80-100 LTHW flow"),
    (100.0, None, ">=100 steam/HTHW"),
)


def _band_label(temperature: float) -> str:
    for low, high, label in _BANDS:
        if (low is None or temperature >= low) and (high is None or temperature < high):
            return label
    return "unbanded"


def _percent(part: int, whole: int) -> float:
    return (100.0 * part / whole) if whole else 0.0


def audit_model(path: Path, *, inference: bool) -> dict | None:
    """Return temperature coverage counts for one model, or None if no piping."""
    model = ifcopenshell.open(str(path))
    elements = pp.produce_piping_elements_from_model(model, temperature_inference=inference)
    if not elements:
        return None

    counts = pp.temperature_coverage(elements)
    bands: Counter = Counter()
    systems_missing: Counter = Counter()
    for element in elements:
        if element.operating_temperature_c is None:
            systems_missing[element.system.value] += 1
        else:
            bands[_band_label(element.operating_temperature_c)] += 1

    counts["name"] = path.name
    counts["resolved"] = counts["from_ifc"] + counts["inferred"]
    counts["bands"] = dict(bands)
    counts["systems_missing"] = systems_missing.most_common(5)
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--models-dir", type=Path, default=DEFAULT_MODELS_DIR,
        help=f"Directory searched recursively for .ifc files (default: {DEFAULT_MODELS_DIR})",
    )
    parser.add_argument(
        "--no-inference", action="store_true",
        help="Report the file-only baseline, with the design-temperature fallback off.",
    )
    parser.add_argument("--json", type=Path, help="Also write the results to this JSON path.")
    args = parser.parse_args()

    if not args.models_dir.exists():
        print(f"No such directory: {args.models_dir}", file=sys.stderr)
        return 2

    paths = sorted(args.models_dir.rglob("*.ifc"))
    if not paths:
        print(f"No .ifc files under {args.models_dir}", file=sys.stderr)
        return 2

    inference = not args.no_inference
    print(f"Models dir : {args.models_dir}")
    print(f"Inference  : {'ON' if inference else 'OFF (file only)'}")
    print()
    header = f"{'model':<46}{'total':>8}{'IFC':>8}{'infer':>8}{'unknown':>9}{'covered':>10}"
    print(header)
    print("-" * len(header))

    results: list[dict] = []
    for path in paths:
        try:
            counts = audit_model(path, inference=inference)
        except Exception as exc:  # noqa: BLE001 - a bad model must not stop the audit
            print(f"{path.name:<46}  ERROR {type(exc).__name__}: {exc}")
            continue
        if counts is None:
            continue
        results.append(counts)
        print(
            f"{counts['name'][:45]:<46}{counts['total']:>8}{counts['from_ifc']:>8}"
            f"{counts['inferred']:>8}{counts['unknown']:>9}"
            f"{_percent(counts['resolved'], counts['total']):>9.1f}%"
        )

    if not results:
        print("\nNo model contained piping elements.")
        return 1

    total = sum(r["total"] for r in results)
    from_ifc = sum(r["from_ifc"] for r in results)
    inferred = sum(r["inferred"] for r in results)
    unknown = sum(r["unknown"] for r in results)
    resolved = from_ifc + inferred

    print("-" * len(header))
    print(
        f"{'TOTAL':<46}{total:>8}{from_ifc:>8}{inferred:>8}{unknown:>9}"
        f"{_percent(resolved, total):>9.1f}%"
    )
    print()
    print(f"  read from IFC        {from_ifc:>7}  ({_percent(from_ifc, total):.1f}%)")
    print(f"  inferred from system {inferred:>7}  ({_percent(inferred, total):.1f}%)")
    print(f"  still unknown        {unknown:>7}  ({_percent(unknown, total):.1f}%)")

    bands: Counter = Counter()
    systems: Counter = Counter()
    for result in results:
        bands.update(result["bands"])
        systems.update(dict(result["systems_missing"]))

    if bands:
        print("\nMM-001 stress band of resolved temperatures:")
        for _, _, label in _BANDS:
            if bands.get(label):
                print(f"  {label:<28}{bands[label]:>8}  ({_percent(bands[label], resolved):.1f}%)")
    if systems:
        print("\nSystems of still-unknown elements:")
        for system, count in systems.most_common(10):
            print(f"  {system:<28}{count:>8}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {
                    "models_dir": str(args.models_dir),
                    "inference_enabled": inference,
                    "totals": {
                        "total": total, "from_ifc": from_ifc,
                        "inferred": inferred, "unknown": unknown,
                        "coverage_pct": round(_percent(resolved, total), 2),
                    },
                    "bands": dict(bands),
                    "models": results,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nWrote {args.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
