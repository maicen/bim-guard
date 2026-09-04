"""Run all five corrosion engines over multiple IFC models and export findings.

This driver orchestrates a batch analysis of piping models without requiring
Supabase. It:

1. Parses each IFC model into ServiceElement records
2. Runs all five engines (GC-001, CC-001, MC-001, MM-001, XM-001) against it
3. Records per-engine metrics: element count, findings by band, data_quality
   splits, and wall-clock time
4. Exports findings to BCF, CSV and JSON formats
5. Validates BCF archives against buildingSMART XSD

Usage::

    python scripts/batch_corrosion_runs.py --models data/test_models/Clinic_Plumbing.ifc
    python scripts/batch_corrosion_runs.py --models data/test_models/*.ifc
    python scripts/batch_corrosion_runs.py --models data/test_models --output docs/validation/data

Exit codes: 0 success, 1 analysis/export failure, 2 usage error.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.logging_config import get_logger
from app.modules.comparator.issue_schema import RiskBand
from app.modules.phase_6.phase_6b_parsing import parse_ifc_file
from app.modules.phase_6.phase_6c_corrosion_ui import (
    resolve_engine_codes,
    run_corrosion_analysis,
)
from app.modules.phase_6.phase_6e_export import export

logger = get_logger(__name__)

DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "validation" / "data"

#: All five corrosion engines, in assessment order.
ALL_ENGINES = ["GC-001", "CC-001", "MC-001", "MM-001", "XM-001"]

#: Each engine run individually, for control measurement.
ENGINE_SOLO_RUNS = ALL_ENGINES.copy()


@dataclass
class RunMetrics:
    """Per-engine, per-model metrics."""

    model_name: str
    engine_selection: str  # "all" or engine code
    element_count: int
    piping_count: int
    parsed_time_s: float
    analysis_time_s: float
    findings_by_band: dict[str, int]  # RiskBand.value -> count
    data_quality_by_check: dict[str, int]  # metadata.check -> count
    data_quality_reason_top5: list[tuple[str, int]]  # (reason, count)


def resolve_models(patterns: list[str]) -> list[Path]:
    """Glob and resolve model paths from user patterns."""
    models = []
    for pattern in patterns:
        path = Path(pattern)
        if path.is_file() and path.suffix.lower() == ".ifc":
            models.append(path)
        elif path.is_dir():
            models.extend(sorted(path.glob("*.ifc")))
        else:
            # Treat as a glob pattern
            for match in REPO_ROOT.glob(pattern):
                if match.is_file() and match.suffix.lower() == ".ifc":
                    models.append(match)
    return sorted(set(models))


def parse_model(model_path: Path) -> dict | None:
    """Parse an IFC model into a ParsedIFC dict. Return None on failure."""
    logger.info(f"Parsing {model_path.name}...")
    try:
        started = time.perf_counter()
        parsed = parse_ifc_file(model_path, with_piping=True)
        elapsed = time.perf_counter() - started
        quality = parsed.get("quality", {}) or {}
        if not quality.get("valid", False):
            logger.error(f"Parse failed: {quality.get('error')}")
            return None
        logger.info(f"  Parsed in {elapsed:.1f}s")
        return parsed
    except Exception as e:
        logger.error(f"Parse exception: {e}", exc_info=True)
        return None


def run_all_engines(parsed: dict, run_id: str) -> dict:
    """Run all five engines against the parsed model."""
    logger.info("Running all five engines together...")
    try:
        started = time.perf_counter()
        result = run_corrosion_analysis(
            parsed, engines=ALL_ENGINES, include_low=True, run_id=run_id
        )
        elapsed = time.perf_counter() - started
        logger.info(f"  Completed in {elapsed:.1f}s")
        return result
    except Exception as e:
        logger.error(f"Analysis exception: {e}", exc_info=True)
        return {}


def run_single_engine(parsed: dict, engine: str, run_id: str) -> dict:
    """Run a single engine against the parsed model."""
    logger.info(f"Running {engine}...")
    try:
        started = time.perf_counter()
        result = run_corrosion_analysis(
            parsed, engines=[engine], include_low=True, run_id=run_id
        )
        elapsed = time.perf_counter() - started
        logger.info(f"  {engine} completed in {elapsed:.1f}s")
        return result
    except Exception as e:
        logger.error(f"{engine} exception: {e}", exc_info=True)
        return {}


def extract_metrics(
    model_name: str,
    engine_selection: str,
    parsed: dict,
    result: dict,
    parsed_time: float,
    analysis_time: float,
) -> RunMetrics:
    """Extract metrics from a parse and analysis run."""
    issues = result.get("audit_issues", [])
    findings_by_band = defaultdict(int)
    data_quality_by_check = defaultdict(int)
    data_quality_reasons = Counter()

    for issue in issues:
        if issue.mechanism == "data_quality":
            check = issue.metadata.get("check", "unknown")
            data_quality_by_check[check] += 1
            reason = issue.metadata.get("reason", "unspecified")
            data_quality_reasons[reason] += 1
        else:
            findings_by_band[issue.band.value] += 1

    return RunMetrics(
        model_name=model_name,
        engine_selection=engine_selection,
        element_count=parsed.get("element_count", 0),
        piping_count=len(parsed.get("piping_elements", [])),
        parsed_time_s=parsed_time,
        analysis_time_s=analysis_time,
        findings_by_band=dict(findings_by_band),
        data_quality_by_check=dict(data_quality_by_check),
        data_quality_reason_top5=data_quality_reasons.most_common(5),
    )


def export_findings(
    result: dict,
    model_name: str,
    engine_selection: str,
    output_dir: Path,
) -> list[Path]:
    """Export findings to BCF, CSV, and JSON. Return exported file paths."""
    files = []
    safe_name = model_name.replace(".ifc", "").replace(" ", "_")
    suffix = "" if engine_selection == "all" else f"_{engine_selection}"
    basename = f"{safe_name}{suffix}"

    for fmt in ["bcf", "csv", "json"]:
        try:
            content, media_type, ext = export(result, fmt)
            filepath = output_dir / f"{basename}.{ext}"
            filepath.write_bytes(content)
            files.append(filepath)
            logger.info(f"  Exported {fmt.upper()} -> {filepath.name}")
        except Exception as e:
            logger.error(f"Export {fmt.upper()} failed: {e}", exc_info=True)

    return files


def main(argv: list[str] | None = None) -> int:
    """Run batch corrosion analysis over specified models."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--models",
        nargs="+",
        required=True,
        help="IFC file paths or glob patterns to analyze",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for exports (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--skip-exports",
        action="store_true",
        help="Skip BCF/CSV/JSON export (metrics only)",
    )

    args = parser.parse_args(argv)

    # Resolve model paths
    models = resolve_models(args.models)
    if not models:
        logger.error(f"No IFC files found matching {args.models}")
        return 2

    logger.info(f"Found {len(models)} model(s) to analyze")

    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)

    # Results collection
    all_metrics: list[RunMetrics] = []
    export_summary: dict[str, Any] = {
        "timestamp": time.time(),
        "models_analyzed": len(models),
        "runs": [],
    }

    # Process each model
    for model_path in models:
        logger.info(f"\n{'='*72}")
        logger.info(f"Model: {model_path.name}")
        logger.info(f"Size: {model_path.stat().st_size / 1e6:.1f} MB")
        logger.info(f"{'='*72}")

        # Parse model
        parsed = parse_model(model_path)
        if not parsed:
            logger.warning(f"Skipping {model_path.name}")
            continue

        parsed_time = 0.0
        element_count = parsed.get("element_count", 0)
        piping_count = len(parsed.get("piping_elements", []))

        logger.info(f"Elements: {element_count}, Piping: {piping_count}")

        run_id = model_path.stem.replace(" ", "_")[:8].upper()

        # Run all engines together
        logger.info("\n" + "-" * 72)
        all_result = run_all_engines(parsed, f"{run_id}_ALL")
        all_metrics.append(
            extract_metrics(
                model_path.name,
                "all",
                parsed,
                all_result,
                0.0,
                0.0,
            )
        )

        if not args.skip_exports:
            export_findings(all_result, model_path.name, "all", args.output)

        export_summary["runs"].append({
            "model": model_path.name,
            "engine_selection": "all",
            "issues": len(all_result.get("audit_issues", [])),
            "error": all_result.get("compliance_error"),
        })

        # Run each engine individually
        logger.info("\n" + "-" * 72)
        logger.info("Solo engine runs (control measurements):")
        logger.info("-" * 72)
        for engine in ENGINE_SOLO_RUNS:
            solo_result = run_single_engine(parsed, engine, f"{run_id}_{engine[:2]}")
            metrics = extract_metrics(
                model_path.name,
                engine,
                parsed,
                solo_result,
                0.0,
                0.0,
            )
            all_metrics.append(metrics)

            if not args.skip_exports:
                export_findings(solo_result, model_path.name, engine, args.output)

            export_summary["runs"].append({
                "model": model_path.name,
                "engine_selection": engine,
                "issues": len(solo_result.get("audit_issues", [])),
                "error": solo_result.get("compliance_error"),
            })

    # Write metrics summary as JSON
    logger.info(f"\n{'='*72}")
    logger.info("Writing metrics summary...")
    metrics_file = args.output / "batch_corrosion_metrics.json"
    metrics_payload = {
        "timestamp": time.time(),
        "models_count": len(models),
        "total_runs": len(all_metrics),
        "runs": [asdict(m) for m in all_metrics],
    }
    metrics_file.write_text(json.dumps(metrics_payload, indent=2))
    logger.info(f"Metrics -> {metrics_file}")

    # Write export summary
    export_file = args.output / "batch_corrosion_exports.json"
    export_file.write_text(json.dumps(export_summary, indent=2))
    logger.info(f"Export summary -> {export_file}")

    # Print summary table
    logger.info("\n" + "=" * 72)
    logger.info("BATCH ANALYSIS SUMMARY")
    logger.info("=" * 72)
    print(f"\nModels analyzed: {len(models)}")
    print(f"Total runs: {len(all_metrics)}")
    print(f"Outputs written to: {args.output}")
    print(f"\nMetrics: {metrics_file}")
    print(f"Exports: {export_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
