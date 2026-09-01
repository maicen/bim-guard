"""Run the end-to-end compliance pipeline over a local IFC model.

Drives the four stages a live trial needs and reports what each one produced:

1. **Parse** -- ``phase_6b_parsing.parse_ifc_file`` reads the model into
   ``ServiceElement`` records.
2. **Galvanic (GC-001)** -- ``phase_6c_corrosion_ui.run_corrosion_analysis``
   scores MEP piping for dissimilar-metal pairs. Only GC-001 is selected, so
   the crevice, MIC and compatibility mechanisms are not assessed at all.
3. **Seismic clearance** -- ``phase_6d_seismic.run_seismic_analysis`` runs Blue
   Halo clash detection against the jurisdiction clearance config.
4. **BCF export** -- both issue sets are handed to
   ``app.services.bcf_exporter.BCFExporter`` and written to ``docs/bcf_exports/``.

WHY SEISMIC WANTS MORE THAN ONE MODEL

    A clearance envelope is a question about a building, not about a file: the
    brace is in the mechanical model and the beam it has to clear is in the
    structural one. Pass every discipline of the same building via ``--extra``
    (or ``--auto-extra``), or the run reports only the clashes a discipline has
    with itself. Corrosion is the opposite case and stays single-model, because
    a second discipline's copy of a pipe run would double every finding.

Usage::

    python scripts/fetch_test_model.py --set clinic
    python scripts/run_full_pipeline.py --model data/test_models/Clinic_Plumbing.ifc --auto-extra

Exit codes: ``0`` success, ``1`` a stage failed, ``2`` usage error.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.modules.module2_producer.halo_volume_generator import BraceType  # noqa: E402
from app.modules.module4_comparator.issue_schema import Issue, RiskBand  # noqa: E402
from app.modules.phase_6.phase_6b_parsing import parse_ifc_file  # noqa: E402
from app.modules.phase_6.phase_6c_corrosion_ui import run_corrosion_analysis  # noqa: E402
from app.modules.phase_6.phase_6d_seismic import (  # noqa: E402
    DEFAULT_CONFIG_PATH,
    run_seismic_analysis,
)
from app.services.bcf_exporter import BCFExporter  # noqa: E402

DEFAULT_MODEL_DIR = REPO_ROOT / "data" / "test_models"

#: The densest MEP piping model available locally. Note it carries essentially
#: no material data - one IfcMaterial entity, "Chrome - DELTA - Polished" - so
#: GC-001 correctly returns zero findings against it. Upstream metadata claiming
#: copper and carbon steel on this model is fabricated; see
#: data/test_models/README.md. Use it to exercise parsing and the seismic path,
#: not to validate galvanic scoring.
DEFAULT_MODEL = DEFAULT_MODEL_DIR / "Clinic_Plumbing.ifc"

BAND_ORDER = (RiskBand.CRITICAL, RiskBand.HIGH, RiskBand.MEDIUM, RiskBand.LOW)


class StageError(RuntimeError):
    """Raised when a pipeline stage cannot complete."""


def _rule(title: str = "") -> None:
    """Print a section rule, optionally titled."""
    if title:
        print()
        print(f"--- {title} " + "-" * max(0, 68 - len(title)))
    else:
        print("-" * 72)


def _resolve_extras(model: Path, extras: Sequence[str], auto: bool) -> list[Path]:
    """Return the sibling discipline models to read alongside *model*."""
    if auto:
        siblings = sorted(
            p for p in model.parent.glob("*.ifc") if p.resolve() != model.resolve()
        )
        return siblings
    resolved = []
    for raw in extras:
        path = Path(raw)
        if not path.is_absolute():
            path = REPO_ROOT / path
        if not path.is_file():
            raise StageError(f"Extra model not found: {raw}")
        resolved.append(path)
    return resolved


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------


def stage_parse(model: Path) -> dict:
    """Parse *model* and report what came back."""
    _rule("Stage 1: parse")
    started = time.perf_counter()
    parsed = parse_ifc_file(model, with_piping=True)
    elapsed = time.perf_counter() - started

    quality = parsed.get("quality", {}) or {}
    if not quality.get("valid", False):
        raise StageError(f"The model could not be parsed: {quality.get('error')}")

    print(f"  file          {model.name} ({model.stat().st_size / 1e6:.1f} MB)")
    print(f"  schema        {parsed.get('schema') or '?'}")
    print(f"  elements      {parsed.get('element_count', 0)}")
    print(f"  piping        {len(parsed.get('piping_elements') or [])}")
    print(f"  sha256        {str(parsed.get('source_sha256') or '')[:16]}...")
    print(f"  parsed in     {elapsed:.1f}s")

    for warning in (quality.get("warnings") or [])[:5]:
        print(f"  warning       {warning}")
    return parsed


def stage_galvanic(parsed: dict, include_low: bool) -> list[Issue]:
    """Run GC-001 over the parsed model and return its issues."""
    _rule("Stage 2: galvanic corrosion (GC-001)")
    started = time.perf_counter()
    result = run_corrosion_analysis(
        parsed, engines=["GC-001"], include_low=include_low, run_id="TRIAL"
    )
    elapsed = time.perf_counter() - started

    error = result.get("compliance_error")
    if error:
        print(f"  engine error  {error}")
    _print_stats(result.get("issue_stats") or {}, elapsed)
    return list(result.get("audit_issues") or [])


def stage_seismic(
    model: Path,
    extras: Sequence[Path],
    *,
    building_type: str,
    brace_type: BraceType,
    seismic_zone: bool,
    config_path: Path,
) -> list[Issue]:
    """Run Blue Halo clearance detection and return its issues."""
    _rule("Stage 3: seismic clearance (Blue Halo)")
    if not Path(config_path).is_file():
        raise StageError(
            f"Clearance config not found: {config_path}. "
            "Pass --seismic-config, or --skip-seismic to leave this stage out."
        )

    print(f"  config        {Path(config_path).as_posix()}")
    print(f"  building      {building_type} | brace {brace_type.value} | zone {seismic_zone}")
    if extras:
        for extra in extras:
            print(f"  cross-model   {extra.name} ({extra.stat().st_size / 1e6:.1f} MB)")
    else:
        print("  cross-model   none - clashes limited to this discipline (see --auto-extra)")

    started = time.perf_counter()
    result = run_seismic_analysis(
        model.read_bytes(),
        extra_models=[(p.name, p.read_bytes()) for p in extras],
        config_path=config_path,
        brace_type=brace_type,
        seismic_zone=seismic_zone,
        building_type=building_type,
        run_id="TRIAL",
    )
    elapsed = time.perf_counter() - started

    error = result.get("compliance_error")
    if error:
        print(f"  engine error  {error}")

    _print_stats(result.get("issue_stats") or {}, elapsed)
    return list(result.get("audit_issues") or [])


def stage_export(issues: Sequence[Issue], output: str, project_name: str) -> Path:
    """Write *issues* to a BCF archive and return the path."""
    _rule("Stage 4: BCF export")
    if not issues:
        print("  nothing to export - no issues were raised")
    started = time.perf_counter()
    path = BCFExporter().export(issues, output, project_name=project_name)
    elapsed = time.perf_counter() - started

    print(f"  topics        {len(issues)}")
    print(f"  archive       {path.relative_to(REPO_ROOT).as_posix()}")
    print(f"  size          {path.stat().st_size / 1024:.1f} KB")
    print(f"  written in    {elapsed:.1f}s")
    return path


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _print_stats(stats: dict[str, Any], elapsed: float) -> None:
    """Print an issue_stats block."""
    if not stats:
        print(f"  findings      0 (ran in {elapsed:.1f}s)")
        return
    print(
        f"  findings      {stats.get('total', 0)}"
        f"  (critical {stats.get('critical', 0)},"
        f" high {stats.get('high', 0)},"
        f" medium {stats.get('medium', 0)},"
        f" low {stats.get('low', 0)})"
    )
    if stats.get("data_quality"):
        print(f"  data quality  {stats['data_quality']} elements could not be assessed")
    print(f"  ran in        {elapsed:.1f}s")


def summarise(issues: Sequence[Issue]) -> None:
    """Print a combined breakdown of every issue raised."""
    _rule("Summary")
    if not issues:
        print("  No issues raised.")
        return

    by_mechanism: dict[str, list[Issue]] = {}
    for issue in issues:
        by_mechanism.setdefault(issue.mechanism or "(unnamed)", []).append(issue)

    print(f"  {'mechanism':<40}{'total':>7}{'crit':>6}{'high':>6}{'med':>6}{'low':>6}")
    print("  " + "-" * 71)
    for mechanism, group in sorted(by_mechanism.items(), key=lambda kv: -len(kv[1])):
        counts = {band: sum(1 for i in group if i.band is band) for band in BAND_ORDER}
        print(
            f"  {mechanism[:39]:<40}{len(group):>7}"
            f"{counts[RiskBand.CRITICAL]:>6}{counts[RiskBand.HIGH]:>6}"
            f"{counts[RiskBand.MEDIUM]:>6}{counts[RiskBand.LOW]:>6}"
        )

    worst = [i for i in issues if i.band in (RiskBand.CRITICAL, RiskBand.HIGH)]
    if worst:
        print()
        print(f"  Top findings ({min(len(worst), 5)} of {len(worst)} critical/high):")
        for issue in sorted(worst, key=lambda i: -i.score)[:5]:
            print(f"    [{issue.band.value:<8}] {issue.id}  {issue.title[:52]}")
            print(f"               element {issue.element_id}  score {issue.score:.2f}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(
        description="Run parse -> GC-001 -> seismic -> BCF over a local IFC model.",
        epilog=(
            "Example: python scripts/run_full_pipeline.py "
            "--model data/test_models/Clinic_Plumbing.ifc --auto-extra"
        ),
    )
    parser.add_argument("--model", default=str(DEFAULT_MODEL), help="IFC model to analyse")
    parser.add_argument(
        "--extra",
        action="append",
        default=[],
        metavar="IFC",
        help="additional discipline model for seismic clash detection (repeatable)",
    )
    parser.add_argument(
        "--auto-extra",
        action="store_true",
        help="use every other .ifc beside --model as a cross-discipline model",
    )
    parser.add_argument("--skip-galvanic", action="store_true", help="do not run GC-001")
    parser.add_argument("--skip-seismic", action="store_true", help="do not run Blue Halo")
    parser.add_argument(
        "--include-low", action="store_true", help="keep Low-band corrosion findings"
    )
    parser.add_argument("--output", default="", help="BCF archive name (default: model stem)")
    parser.add_argument(
        "--building-type", default="hospital", help="occupancy category for clearance rules"
    )
    parser.add_argument(
        "--brace-type",
        default=BraceType.ANGLE_IRON.value,
        choices=[b.value for b in BraceType],
        help="assumed brace hardware",
    )
    parser.add_argument(
        "--no-seismic-zone",
        action="store_true",
        help="treat the site as outside a declared seismic zone",
    )
    parser.add_argument(
        "--seismic-config", default=str(DEFAULT_CONFIG_PATH), help="clearance config JSON"
    )
    args = parser.parse_args(argv)
    if args.skip_galvanic and args.skip_seismic:
        parser.error("--skip-galvanic and --skip-seismic together leave nothing to run")
    return args


def main(argv: list[str] | None = None) -> int:
    """Run the pipeline; see the module docstring for exit codes."""
    args = parse_args(argv)

    model = Path(args.model)
    if not model.is_absolute():
        model = REPO_ROOT / model
    if not model.is_file():
        print(f"error: model not found: {args.model}", file=sys.stderr)
        print("Fetch one first: python scripts/fetch_test_model.py --set clinic", file=sys.stderr)
        return 2

    config_path = Path(args.seismic_config)
    if not config_path.is_absolute():
        config_path = REPO_ROOT / config_path

    print("=" * 72)
    print("BIMGUARD AI - end-to-end pipeline trial")
    print("=" * 72)

    overall = time.perf_counter()
    issues: list[Issue] = []
    try:
        extras = _resolve_extras(model, args.extra, args.auto_extra)
        parsed = stage_parse(model)

        if args.skip_galvanic:
            print("\n--- Stage 2: galvanic corrosion (GC-001) --- skipped")
        else:
            issues += stage_galvanic(parsed, args.include_low)

        if args.skip_seismic:
            print("\n--- Stage 3: seismic clearance (Blue Halo) --- skipped")
        else:
            issues += stage_seismic(
                model,
                extras,
                building_type=args.building_type,
                brace_type=BraceType(args.brace_type),
                seismic_zone=not args.no_seismic_zone,
                config_path=config_path,
            )

        summarise(issues)
        output = args.output or f"{model.stem}_trial"
        path = stage_export(issues, output, project_name=f"BIMGUARD trial - {model.stem}")
    except StageError as exc:
        print(f"\nerror: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nerror: interrupted", file=sys.stderr)
        return 1

    _rule()
    print(f"Done in {time.perf_counter() - overall:.1f}s. {len(issues)} issue(s) exported.")
    print(f"Open {path.relative_to(REPO_ROOT).as_posix()} in Solibri, BIMcollab or BlenderBIM.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
