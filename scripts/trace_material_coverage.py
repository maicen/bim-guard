#!/usr/bin/env python
"""Audit piping material coverage across IFC models.

Reports, per model and overall, how many piping elements resolve a material
and where each answer came from:

    from IFC    read from the file - an IfcRelAssociatesMaterial association
                or a Material/MaterialName property. Authoritative.
    inferred    deduced from the element's piping system by
                piping_producer.infer_material_from_system. A design
                convention, not a reading of this model.
    unknown     neither source resolved anything. Stays Undetermined:
                MM-001 and XM-001 raise a data-quality finding rather than
                scoring a couple.

The two columns are kept apart on purpose. A headline coverage number that
merges them would let an assumption pass for a measurement, and both feed the
same galvanic scoring.

Usage:
    uv run python scripts/trace_material_coverage.py
    uv run python scripts/trace_material_coverage.py --models-dir data/test_models
    uv run python scripts/trace_material_coverage.py --no-inference   # file only
    uv run python scripts/trace_material_coverage.py --json docs/validation/data/material-coverage.json
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


def _percent(part: int, whole: int) -> float:
    return (100.0 * part / whole) if whole else 0.0


def audit_model(path: Path, *, inference: bool) -> dict | None:
    """Return coverage counts for one model, or None when it holds no piping."""
    model = ifcopenshell.open(str(path))
    elements = pp.produce_piping_elements_from_model(model, material_inference=inference)
    if not elements:
        return None

    counts = pp.material_coverage(elements)
    systems_missing: Counter = Counter()
    raw_rejected: Counter = Counter()
    for element in elements:
        if (element.properties or {}).get(pp.MATERIAL_SOURCE_KEY):
            continue
        systems_missing[element.system.value] += 1
        if element.material_raw:
            raw_rejected[element.material_raw] += 1

    counts["name"] = path.name
    counts["resolved"] = counts["from_ifc"] + counts["inferred"]
    counts["systems_missing"] = systems_missing.most_common(5)
    counts["raw_rejected"] = raw_rejected.most_common(5)
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--models-dir", type=Path, default=DEFAULT_MODELS_DIR,
        help=f"Directory searched recursively for .ifc files (default: {DEFAULT_MODELS_DIR})",
    )
    parser.add_argument(
        "--no-inference", action="store_true",
        help="Report the file-only baseline, with the system fallback disabled.",
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

    systems: Counter = Counter()
    rejected: Counter = Counter()
    for result in results:
        systems.update(dict(result["systems_missing"]))
        rejected.update(dict(result["raw_rejected"]))

    if systems:
        print("\nSystems of still-unknown elements (inference targets):")
        for system, count in systems.most_common(10):
            print(f"  {system:<28}{count:>8}")
    if rejected:
        print("\nMaterial text present but unrecognised (normaliser targets):")
        for raw, count in rejected.most_common(10):
            print(f"  {raw[:40]!r:<44}{count:>8}")

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
