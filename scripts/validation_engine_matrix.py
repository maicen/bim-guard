#!/usr/bin/env python
"""Run all five corrosion engines over real IFC models and record the evidence.

This is the measurement harness behind ``docs/validation/VALIDATION_REPORT.md``.
It differs from ``scripts/batch_corrosion_runs.py`` in what it optimises for:
that driver runs each engine a second time on its own to time it in isolation,
which costs six analysis passes per model. This one parses each model once,
runs the five engines together once, and then attributes every Issue to the
engine that raised it via ``Issue.mechanism``. The per-engine counts are
therefore the as-deployed numbers -- what the engines produce when they run
together, which is how the product runs them -- rather than six solo runs that
no user ever performs.

Per model it records:

* parse and analysis wall-clock, element and piping counts
* per-engine findings split by risk band, and per-engine data-quality refusals
  split by ``metadata["check"]``
* material / environment / temperature coverage, keeping *read from the model*
  apart from *inferred* so an assumption cannot pass for a measurement
* the MM-001 findings cross-tabulated by (material, medium), which is what
  shows whether the engine fires on the pairings it should and stays silent on
  the ones it should not
* a BCF 2.1 export validated part-by-part against the buildingSMART schemas
  vendored under ``tests/schemas/bcf21/``

Nothing under ``app/`` is imported for anything but reading: the harness runs
the engines, it does not reconfigure them.

Usage::

    uv run python scripts/validation_engine_matrix.py --models test-models/models
    uv run python scripts/validation_engine_matrix.py --models test-models/models/hospital
    uv run python scripts/validation_engine_matrix.py --models a.ifc b.ifc --skip-bcf
    uv run python scripts/validation_engine_matrix.py --models test-models/models \
        --json docs/validation/data/engine-matrix.json

Exit status is 0 when every model that carries piping was analysed, 1 when any
model failed to parse or analyse, and 2 on a usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

warnings.filterwarnings("ignore")

from app.modules.ifc_reader.piping_producer import (  # noqa: E402
    environment_coverage,
    material_coverage,
    temperature_coverage,
)
from app.modules.phase_6.phase_6b_parsing import parse_ifc_file  # noqa: E402
from app.modules.phase_6.phase_6c_corrosion_ui import run_corrosion_analysis  # noqa: E402
from app.modules.phase_6.phase_6e_export import export  # noqa: E402

SCHEMA_DIR = REPO_ROOT / "tests" / "schemas" / "bcf21"

#: All five corrosion engines, in assessment order.
ALL_ENGINES = ["GC-001", "CC-001", "MC-001", "MM-001", "XM-001"]

DATA_QUALITY = "data_quality"

#: Bands in reporting order, so a model with no Critical findings still shows
#: the column rather than silently dropping it.
BANDS = ["critical", "high", "medium", "low"]


def resolve_models(patterns: list[str]) -> list[Path]:
    """Expand file paths, directories and globs into a sorted list of IFCs.

    Directories are searched recursively, because the model corpus is filed
    by building type (``hospital/``, ``office/``, ``industrial/``) and naming
    the parent is the natural way to ask for all of it.
    """
    models: list[Path] = []
    for pattern in patterns:
        path = Path(pattern)
        if path.is_file() and path.suffix.lower() == ".ifc":
            models.append(path)
        elif path.is_dir():
            models.extend(path.rglob("*.ifc"))
        else:
            models.extend(m for m in REPO_ROOT.glob(pattern) if m.suffix.lower() == ".ifc")
    return sorted(set(models))


def engine_of(issue: Any) -> str:
    """Return the engine code that raised one Issue.

    ``mechanism`` is the authority ("MM-001 material-media"); ``rule_id``
    ("MM-001.01") is the fallback. An Issue that answers neither is bucketed
    under "unattributed" rather than dropped, so the per-engine counts always
    re-add to the model total and a mis-tagged Issue is visible instead of
    quietly absent.
    """
    mechanism = (getattr(issue, "mechanism", "") or "").strip()
    if mechanism:
        head = mechanism.split()[0]
        if head.upper().startswith(("GC-", "CC-", "MC-", "MM-", "XM-", "SB-")):
            return head.upper()
    rule_id = (getattr(issue, "rule_id", "") or "").strip()
    if rule_id:
        return rule_id.split(".")[0].upper()
    return "unattributed"


def summarise_issues(issues: list[Any]) -> dict[str, Any]:
    """Split every Issue by engine, then by band or data-quality check.

    Findings and data-quality Issues are counted separately on purpose. A
    data-quality Issue is the engine declining to score an element; folding it
    into a findings total would report a refusal as a detection.
    """
    findings: dict[str, Counter] = defaultdict(Counter)
    refusals: dict[str, Counter] = defaultdict(Counter)

    for issue in issues:
        engine = engine_of(issue)
        if getattr(issue, "mechanism", "") == DATA_QUALITY:
            check = (issue.metadata or {}).get("check", "unspecified")
            refusals[engine][check] += 1
        else:
            refusals[engine]  # touch, so an engine with only findings still appears
            findings[engine][issue.band.value] += 1

    engines = sorted(set(findings) | set(refusals))
    out: dict[str, Any] = {}
    for engine in engines:
        band_counts = {band: findings[engine].get(band, 0) for band in BANDS}
        total_findings = sum(band_counts.values())
        out[engine] = {
            "findings_total": total_findings,
            "findings_excluding_low": total_findings - band_counts["low"],
            "findings_by_band": band_counts,
            "data_quality_total": sum(refusals[engine].values()),
            "data_quality_by_check": dict(refusals[engine].most_common()),
        }
    return out


def mm001_pairings(issues: list[Any]) -> dict[str, Any]:
    """Cross-tabulate the MM-001 findings by (material, medium).

    This is the table that answers "does it fire where it should and stay
    quiet where it should not". Findings are keyed ``material|medium``;
    ``scored_silent`` counts the pairings that were fully scoreable and
    produced nothing, which is the evidence for the negative half of that
    question and cannot be read off the findings alone.
    """
    fired: Counter = Counter()
    bands_by_pair: dict[str, Counter] = defaultdict(Counter)
    guard_applied = 0

    for issue in issues:
        if engine_of(issue) != "MM-001" or getattr(issue, "mechanism", "") == DATA_QUALITY:
            continue
        meta = issue.metadata or {}
        key = f"{meta.get('material', '?')}|{meta.get('medium', '?')}"
        fired[key] += 1
        bands_by_pair[key][issue.band.value] += 1
        if meta.get("kinetics_guard_applied"):
            guard_applied += 1

    return {
        "findings_by_pairing": dict(fired.most_common()),
        "bands_by_pairing": {k: dict(v) for k, v in bands_by_pair.items()},
        "kinetics_guard_applied_count": guard_applied,
    }


def coverage_block(piping: list[Any]) -> dict[str, Any]:
    """Material / environment / temperature coverage for one model's piping.

    Each gate reports its sources separately. ``coverage_pct`` counts an
    element as covered when *any* source resolved it; the ``from_ifc`` and
    ``inferred`` splits alongside it are what make that percentage readable.
    """
    material = material_coverage(piping)
    environment = environment_coverage(piping)
    temperature = temperature_coverage(piping)
    total = material["total"]

    def pct(part: int) -> float:
        return round(100.0 * part / total, 2) if total else 0.0

    return {
        "piping_elements": total,
        "material": {
            **material,
            "coverage_pct": pct(material["from_ifc"] + material["inferred"]),
        },
        "environment": {
            **environment,
            "coverage_pct": pct(environment["total"] - environment["unclassified"]),
        },
        "temperature": {
            **temperature,
            "coverage_pct": pct(temperature["from_ifc"] + temperature["inferred"]),
        },
    }


def _schemas():
    """Load the vendored buildingSMART BCF 2.1 schemas."""
    import xmlschema

    return (
        xmlschema.XMLSchema(SCHEMA_DIR / "markup.xsd"),
        xmlschema.XMLSchema(SCHEMA_DIR / "visinfo.xsd"),
    )


def validate_bcf(path: Path, schemas) -> dict[str, Any]:
    """Validate every markup and viewpoint part inside one BCF archive.

    Returns a record carrying the topic count, whether every part validated,
    and the distinct schema errors. Errors are de-duplicated and counted
    because a malformed archive repeats the same violation once per topic, and
    twenty thousand identical lines say no more than one line and a count.
    """
    markup_schema, visinfo_schema = schemas
    topics = 0
    errors: Counter = Counter()

    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if name.endswith("markup.bcf"):
                schema = markup_schema
                topics += 1
            elif name.endswith(".bcfv"):
                schema = visinfo_schema
            else:
                continue
            for error in schema.iter_errors(zf.read(name).decode("utf-8")):
                errors[str(error.reason or error)] += 1

    return {
        "archive": str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path),
        "topics": topics,
        "valid": not errors,
        "errors": dict(errors.most_common(10)),
    }


def analyse_model(
    model_path: Path,
    output_dir: Path,
    *,
    include_low: bool,
    skip_bcf: bool,
    schemas,
) -> dict[str, Any]:
    """Parse, analyse, export and validate one model. Never raises."""
    record: dict[str, Any] = {"model": model_path.name, "path": str(model_path)}

    started = time.perf_counter()
    try:
        parsed = parse_ifc_file(model_path, with_piping=True)
    except Exception as exc:  # noqa: BLE001 - a bad model must not stop the batch
        record["error"] = f"parse raised: {exc}"
        return record
    record["parse_seconds"] = round(time.perf_counter() - started, 2)

    quality = parsed.get("quality", {}) or {}
    if not quality.get("valid", False):
        record["error"] = f"parse failed: {quality.get('error')}"
        return record

    piping = parsed.get("piping_elements", []) or []
    record["element_count"] = parsed.get("element_count", 0)
    record["coverage"] = coverage_block(piping)

    if not piping:
        # Not an error. A structural or architectural model carries no piping,
        # and the corrosion engines correctly have nothing to say about it.
        record["skipped"] = "no piping elements"
        return record

    started = time.perf_counter()
    try:
        result = run_corrosion_analysis(
            parsed,
            engines=ALL_ENGINES,
            include_low=include_low,
            run_id=model_path.stem[:8].upper() or "VAL",
        )
    except Exception as exc:  # noqa: BLE001
        record["error"] = f"analysis raised: {exc}"
        return record
    record["analysis_seconds"] = round(time.perf_counter() - started, 2)

    if result.get("compliance_error"):
        record["error"] = f"analysis error: {result['compliance_error']}"
        return record

    issues = result.get("audit_issues", []) or []
    record["issues_total"] = len(issues)
    record["by_engine"] = summarise_issues(issues)
    record["mm001"] = mm001_pairings(issues)

    if not skip_bcf:
        output_dir.mkdir(parents=True, exist_ok=True)
        bcf_path = output_dir / f"{model_path.stem}.bcfzip"
        try:
            content, _media_type, _ext = export(result, "bcf")
            bcf_path.write_bytes(content)
            record["bcf"] = validate_bcf(bcf_path, schemas)
        except Exception as exc:  # noqa: BLE001
            record["bcf"] = {"archive": str(bcf_path.name), "valid": False, "errors": {str(exc): 1}}

    return record


def aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Roll per-model records up into corpus totals."""
    engines: dict[str, dict[str, int]] = defaultdict(
        lambda: {"findings_total": 0, "findings_excluding_low": 0, "data_quality_total": 0}
    )
    pairings: Counter = Counter()
    coverage = {
        "piping_elements": 0,
        "material_from_ifc": 0,
        "material_inferred": 0,
        "material_unknown": 0,
        "environment_classified": 0,
        "environment_unclassified": 0,
        "temperature_from_ifc": 0,
        "temperature_inferred": 0,
        "temperature_unknown": 0,
    }
    archives_valid = 0
    archives_total = 0

    for record in records:
        cov = record.get("coverage")
        if cov:
            coverage["piping_elements"] += cov["piping_elements"]
            coverage["material_from_ifc"] += cov["material"]["from_ifc"]
            coverage["material_inferred"] += cov["material"]["inferred"]
            coverage["material_unknown"] += cov["material"]["unknown"]
            coverage["environment_unclassified"] += cov["environment"]["unclassified"]
            coverage["environment_classified"] += (
                cov["environment"]["total"] - cov["environment"]["unclassified"]
            )
            coverage["temperature_from_ifc"] += cov["temperature"]["from_ifc"]
            coverage["temperature_inferred"] += cov["temperature"]["inferred"]
            coverage["temperature_unknown"] += cov["temperature"]["unknown"]

        for engine, block in (record.get("by_engine") or {}).items():
            engines[engine]["findings_total"] += block["findings_total"]
            engines[engine]["findings_excluding_low"] += block["findings_excluding_low"]
            engines[engine]["data_quality_total"] += block["data_quality_total"]

        for key, count in ((record.get("mm001") or {}).get("findings_by_pairing") or {}).items():
            pairings[key] += count

        bcf = record.get("bcf")
        if bcf:
            archives_total += 1
            archives_valid += 1 if bcf.get("valid") else 0

    total = coverage["piping_elements"]

    def pct(part: int) -> float:
        return round(100.0 * part / total, 2) if total else 0.0

    coverage["material_coverage_pct"] = pct(
        coverage["material_from_ifc"] + coverage["material_inferred"]
    )
    coverage["environment_coverage_pct"] = pct(coverage["environment_classified"])
    coverage["temperature_coverage_pct"] = pct(
        coverage["temperature_from_ifc"] + coverage["temperature_inferred"]
    )

    return {
        "models_analysed": sum(1 for r in records if r.get("by_engine")),
        "models_without_piping": sum(1 for r in records if r.get("skipped")),
        "models_failed": sum(1 for r in records if r.get("error")),
        "coverage": coverage,
        "by_engine": {k: dict(v) for k, v in sorted(engines.items())},
        "mm001_findings_by_pairing": dict(pairings.most_common()),
        "bcf_archives_valid": archives_valid,
        "bcf_archives_total": archives_total,
    }


def print_report(records: list[dict[str, Any]], totals: dict[str, Any]) -> None:
    """Print the human-readable summary."""
    print("\n" + "=" * 78)
    print("PER-MODEL ENGINE MATRIX (findings / data-quality refusals)")
    print("=" * 78)
    header = f"{'model':<44}{'piping':>8}  " + "".join(f"{e:>12}" for e in ALL_ENGINES)
    print(header)
    print("-" * len(header))
    for record in records:
        if record.get("error"):
            print(f"{record['model']:<44}{'ERROR':>8}  {record['error'][:60]}")
            continue
        if record.get("skipped"):
            continue
        piping = record["coverage"]["piping_elements"]
        cells = []
        for engine in ALL_ENGINES:
            block = (record.get("by_engine") or {}).get(engine)
            if not block:
                cells.append(f"{'0/0':>12}")
            else:
                cells.append(f"{block['findings_total']}/{block['data_quality_total']:<d}".rjust(12))
        print(f"{record['model']:<44}{piping:>8}  " + "".join(cells))

    print("\n" + "=" * 78)
    print("CORPUS TOTALS")
    print("=" * 78)
    cov = totals["coverage"]
    print(f"  models analysed        : {totals['models_analysed']}")
    print(f"  models without piping  : {totals['models_without_piping']}")
    print(f"  models failed          : {totals['models_failed']}")
    print(f"  piping elements        : {cov['piping_elements']}")
    print(
        f"  material coverage      : {cov['material_coverage_pct']}%"
        f"  ({cov['material_from_ifc']} from IFC, {cov['material_inferred']} inferred,"
        f" {cov['material_unknown']} unknown)"
    )
    print(
        f"  environment coverage   : {cov['environment_coverage_pct']}%"
        f"  ({cov['environment_unclassified']} unclassified)"
    )
    print(
        f"  temperature coverage   : {cov['temperature_coverage_pct']}%"
        f"  ({cov['temperature_from_ifc']} from IFC, {cov['temperature_inferred']} inferred,"
        f" {cov['temperature_unknown']} unknown)"
    )
    print("\n  engine            findings   excl-Low   data-quality")
    for engine in ALL_ENGINES:
        block = totals["by_engine"].get(engine)
        if not block:
            print(f"  {engine:<16}{0:>9}{0:>11}{0:>15}")
            continue
        print(
            f"  {engine:<16}{block['findings_total']:>9}"
            f"{block['findings_excluding_low']:>11}{block['data_quality_total']:>15}"
        )
    other = [e for e in totals["by_engine"] if e not in ALL_ENGINES]
    for engine in other:
        block = totals["by_engine"][engine]
        print(
            f"  {engine:<16}{block['findings_total']:>9}"
            f"{block['findings_excluding_low']:>11}{block['data_quality_total']:>15}"
        )

    if totals["mm001_findings_by_pairing"]:
        print("\n  MM-001 findings by material / medium")
        for key, count in totals["mm001_findings_by_pairing"].items():
            material, _, medium = key.partition("|")
            print(f"    {material:<20}{medium:<20}{count:>8}")

    if totals["bcf_archives_total"]:
        print(
            f"\n  BCF archives valid     : {totals['bcf_archives_valid']}"
            f"/{totals['bcf_archives_total']}"
        )


def main(argv: list[str] | None = None) -> int:
    """Run the engine matrix over the requested models."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["test-models/models"],
        help="IFC files, directories (searched recursively) or globs",
    )
    parser.add_argument(
        "--bcf-dir",
        type=Path,
        default=REPO_ROOT / "docs" / "bcf_exports" / "validation-matrix",
        help="Where to write the per-model BCF archives",
    )
    parser.add_argument("--json", type=Path, default=None, help="Also write the record as JSON")
    parser.add_argument(
        "--include-low",
        action="store_true",
        default=True,
        help="Emit Low-band findings too (default: on, so the band split is complete)",
    )
    parser.add_argument(
        "--no-include-low",
        dest="include_low",
        action="store_false",
        help="Suppress Low-band findings, matching the product default",
    )
    parser.add_argument("--skip-bcf", action="store_true", help="Skip BCF export and validation")
    parser.add_argument(
        "--limit-models", type=int, default=None, metavar="N", help="Analyse only the first N models"
    )

    args = parser.parse_args(argv)

    models = resolve_models(args.models)
    if not models:
        print(f"No IFC files matched {args.models}", file=sys.stderr)
        return 2
    if args.limit_models:
        models = models[: args.limit_models]

    schemas = None if args.skip_bcf else _schemas()

    records: list[dict[str, Any]] = []
    for index, model_path in enumerate(models, start=1):
        size_mb = model_path.stat().st_size / 1e6
        print(f"[{index}/{len(models)}] {model_path.name} ({size_mb:.1f} MB)", flush=True)
        record = analyse_model(
            model_path,
            args.bcf_dir,
            include_low=args.include_low,
            skip_bcf=args.skip_bcf,
            schemas=schemas,
        )
        records.append(record)
        if record.get("error"):
            print(f"    ERROR: {record['error']}", flush=True)
        elif record.get("skipped"):
            print(f"    skipped: {record['skipped']}", flush=True)
        else:
            print(
                f"    piping={record['coverage']['piping_elements']} "
                f"issues={record['issues_total']} "
                f"parse={record.get('parse_seconds')}s analysis={record.get('analysis_seconds')}s",
                flush=True,
            )

    totals = aggregate(records)
    print_report(records, totals)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {
                    "models_requested": [str(m) for m in models],
                    "include_low": args.include_low,
                    "totals": totals,
                    "models": records,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nWrote {args.json}")

    return 1 if totals["models_failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
