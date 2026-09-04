#!/usr/bin/env python
"""Audit piping environment classification across IFC models.

Reports, per model and overall, which EN ISO 15329 environment class each
piping element carries and where the answer came from:

    ifc_property     read from an EnvironmentClass-style property on the
                     element. Authoritative; rare in MEP models.
    spatial_names    inferred by piping_producer.classify_environment from
                     the space / storey / system names ("Pool Hall",
                     "Basement Plant Room"). A heuristic on naming.
    default_indoor   nothing to go on, so T1_indoor_damp was applied as the
                     safe indoor default. MEP discipline models carry no
                     atmospheric metadata (most have no IfcSpace at all and
                     storey names are floor ids), so this is the common case.
    unclassified     no default applied (older producer output, or fixtures).

The columns are kept apart on purpose: a default is not a measurement, and a
headline "100 % classified" that hid the split would let an assumption pass
for one. EnvironmentClass describes the atmosphere around the pipe (rooftop,
coastal, indoor), not what flows inside it; the media axis is
piping_producer.media_for_system and is not reported here.

Usage:
    uv run python scripts/trace_environment_coverage.py
    uv run python scripts/trace_environment_coverage.py --models-dir data/test_models
    uv run python scripts/trace_environment_coverage.py --no-default   # reading only, no T1 default
    uv run python scripts/trace_environment_coverage.py --json docs/validation/data/environment-coverage.json
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
from app.modules.ifc_reader.piping_schema import EnvironmentClass  # noqa: E402

DEFAULT_MODELS_DIR = Path("test-models/models")
SOURCES = ("ifc_property", "spatial_names", "default_indoor", "unclassified")


def _percent(part: int, whole: int) -> float:
    return (100.0 * part / whole) if whole else 0.0


def _source_of(element) -> str:
    """Normalise an element's environment provenance onto the SOURCES buckets."""
    if element.environment_class is EnvironmentClass.UNCLASSIFIED:
        return "unclassified"
    source = getattr(element, "environment_source", None) or ""
    if source == getattr(pp, "ENVIRONMENT_SOURCE_IFC", "ifc_property"):
        return "ifc_property"
    if source == getattr(pp, "ENVIRONMENT_SOURCE_DEFAULT", "default_indoor"):
        return "default_indoor"
    return "spatial_names"


def audit_model(path: Path, *, default: bool = True) -> dict | None:
    """Return environment coverage counts for one model, or None without piping."""
    model = ifcopenshell.open(str(path))
    elements = pp.produce_piping_elements_from_model(model, environment_default=default)
    if not elements:
        return None

    by_source: Counter = Counter(_source_of(e) for e in elements)
    by_class: Counter = Counter(e.environment_class.value for e in elements)
    by_confidence: Counter = Counter(
        getattr(e, "environment_confidence", None) or "n/a" for e in elements
    )
    return {
        "name": path.name,
        "total": len(elements),
        "classified": len(elements) - by_source["unclassified"],
        "by_source": {s: by_source[s] for s in SOURCES},
        "by_class": dict(by_class.most_common()),
        "by_confidence": dict(by_confidence.most_common()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--models-dir", type=Path, default=DEFAULT_MODELS_DIR)
    parser.add_argument(
        "--no-default", action="store_true",
        help="report the reading alone, with the T1 indoor default switched off",
    )
    parser.add_argument("--json", type=Path, default=None, help="also write the report as JSON")
    args = parser.parse_args()

    paths = sorted(args.models_dir.rglob("*.ifc"))
    if not paths:
        print(f"no .ifc files under {args.models_dir}")
        return 1

    default = not args.no_default
    print(f"Models dir : {args.models_dir}")
    print(f"T1 default : {'ON' if default else 'OFF (reading only)'}\n")

    reports: list[dict] = []
    print(f"{'model':<52} {'elements':>8} {'ifc':>6} {'spatial':>8} {'default':>8} {'unclass':>8} {'cover%':>7}")
    print("-" * 102)
    for path in paths:
        try:
            report = audit_model(path, default=default)
        except Exception as exc:  # a broken model must not sink the audit
            print(f"{path.name:<52} ERROR {type(exc).__name__}: {exc}")
            continue
        if report is None:
            continue
        reports.append(report)
        s = report["by_source"]
        print(
            f"{report['name']:<52} {report['total']:>8} {s['ifc_property']:>6} "
            f"{s['spatial_names']:>8} {s['default_indoor']:>8} {s['unclassified']:>8} "
            f"{_percent(report['classified'], report['total']):>6.1f}%"
        )

    total = sum(r["total"] for r in reports)
    totals_by_source = {s: sum(r["by_source"][s] for r in reports) for s in SOURCES}
    totals_by_class: Counter = Counter()
    for r in reports:
        totals_by_class.update(r["by_class"])
    classified = total - totals_by_source["unclassified"]

    print("-" * 102)
    print(f"{'TOTAL':<52} {total:>8} {totals_by_source['ifc_property']:>6} "
          f"{totals_by_source['spatial_names']:>8} {totals_by_source['default_indoor']:>8} "
          f"{totals_by_source['unclassified']:>8} {_percent(classified, total):>6.1f}%")
    print("\nby environment class:")
    for cls, count in totals_by_class.most_common():
        print(f"  {cls:<20} {count:>8} ({_percent(count, total):.1f}%)")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {
                    "models_dir": str(args.models_dir),
                    "default_enabled": default,
                    "totals": {
                        "total": total,
                        "classified": classified,
                        "coverage_pct": round(_percent(classified, total), 2),
                        "by_source": totals_by_source,
                        "by_class": dict(totals_by_class.most_common()),
                    },
                    "models": reports,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
