"""Run every engine, one at a time and then together, over real IFC models.

WHAT THIS IS FOR

    Seeing what each engine actually produces on real models -- with real
    element names, GUIDs and materials -- rather than a headline count. Six
    piping runs per model ({GC}, {CC}, {MC}, {MM}, {XM}, and all five) plus one
    federated SB-001 seismic run.

PARITY WITH A REAL RUN

    A run started from the app goes
    ``POST /api/analyze/corrosion`` -> ``run_analysis("corrosion", project_id,
    use_cache, engines, include_low)`` (app/services/analysis_runner.py:369) ->
    ``_format_result(...)`` (app/api/analyze.py:175) -> ``AnalysisResultContract``.

    ``run_analysis`` does exactly two things this script cannot: it looks the
    project's model up in Supabase (``model_bytes``, analysis_runner.py:83) and
    it consults the analysis cache. Everything after the bytes are in hand is
    ``_run_corrosion_tracked(content, project_id, engines, include_low)``
    (analysis_runner.py:166, called at :461) -- so that is what this calls,
    handing it a local file's bytes in place of the project's stored model.
    Nothing is uploaded and no project is created.

    The envelope is then built by the API's own ``_format_result``, so it is the
    same object the SPA receives, and it is re-validated through
    ``AnalysisResultContract.model_validate`` before being written out.

    Fields a real run takes from the project record are filled with explicit
    local stand-ins rather than left null: ``project_id=0`` and
    ``project_name="local:<model-stem>"``.

OFFLINE AND READ-ONLY

    No HTTP request is made to any BIM-Guard server, no server is started or
    stopped, and the IFC models are only ever read.

USAGE

    uv run python scripts/showcase_run.py
    uv run python scripts/showcase_run.py --only west_riverside_hospital_plumb_ifc4
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# app.services first: see the note in showcase_inventory.py -- entering the
# import cycle at phase_6c leaves it partially initialised.
from app.services.analysis_runner import _run_corrosion_tracked  # noqa: E402
from app.api.analyze import _format_result  # noqa: E402
from app.modules.contracts import AnalysisResultContract, AuditIssueContract  # noqa: E402
from app.modules.phase_6.phase_6b_parsing import parse_ifc_bytes, sha256_of  # noqa: E402
from app.modules.phase_6.phase_6c_corrosion_ui import (  # noqa: E402
    DATA_QUALITY,
    _hydraulics_gate,
    _material_gate,
    _mic_element,
    resolve_engine_codes,
)
from app.modules.phase_6.phase_6d_seismic import run_seismic_analysis  # noqa: E402
from app.modules.phase_6.phase_6e_export import (  # noqa: E402
    CSV_COLUMNS,
    to_bcf,
    to_csv,
    to_json,
)

MAIN_TREE = Path(r"D:\Zigurat Masters\bim-guard")
MODELS_ROOT = MAIN_TREE / "test-models" / "models"
SYNTHETIC_CONTROL = MAIN_TREE / "data" / "test_hospital_mep_demo.ifc"
SYNTHETIC_SHA256 = "302dcad174e8b94d7196527365d95aae1596861f90457473ca7d74e451f30b54"

OUT_DIR = REPO_ROOT / "docs" / "validation" / "engine-showcase-2026-09-08"
BCF_MARKUP_XSD = REPO_ROOT / "tests" / "schemas" / "bcf21" / "markup.xsd"

#: The five piping engines, run alone and then together.
SINGLE_ENGINES: tuple[str, ...] = ("GC-001", "CC-001", "MC-001", "MM-001", "XM-001")
ALL_FIVE: tuple[str, ...] = SINGLE_ENGINES

#: Project 1540's model, and project 1542's federated pair. Both identified from
#: the repository, not guessed -- see 01_inventory.md for the citations.
PROJECT_1540_MODEL = "west_riverside_hospital_plumb_ifc4.ifc"
PROJECT_1542_FEDERATION = (
    "west_riverside_hospital_plumb_ifc4.ifc",
    "west_riverside_hospital_str_ifc4.ifc",
)

#: A single run is abandoned past this, so one pathological model cannot eat the
#: sweep. Enforced between runs, not inside one: the engines are synchronous.
RUN_BUDGET_SECONDS = 15 * 60


@dataclass
class RunOutcome:
    """One completed (or abandoned) audit."""

    model: str
    engine_set: str
    seconds: float
    summary: dict
    over_budget: bool = False


def _engine_dir(codes: tuple[str, ...]) -> str:
    """Directory name for an engine selection."""
    return "ALL5" if len(codes) == 5 else codes[0]


def _attributed(issues, code: str) -> list:
    """Issues belonging to engine ``code``.

    Attribution is by ``rule_id`` prefix, the same test ``_run_corrosion_tracked``
    uses when it reports per-engine progress (analysis_runner.py:265).
    """
    return [i for i in issues if i.rule_id.startswith(code)]


def _is_dq(issue) -> bool:
    return issue.mechanism == DATA_QUALITY


def coverage(parsed: dict) -> dict:
    """Tri-state coverage for a parsed model, using the audit's own gates."""
    elements = parsed.get("elements", []) or []
    total = len(elements)
    material = sum(1 for e in elements if _material_gate(e) is None)
    hydraulics = sum(1 for e in elements if _hydraulics_gate(_mic_element(e)) is None)
    system = sum(1 for e in elements if (e.system or "").strip() not in ("", "Unassigned"))
    pct = lambda n: round(100.0 * n / total, 2) if total else 0.0  # noqa: E731
    return {
        "elements": total,
        "material_resolved": material,
        "material_pct": pct(material),
        "system_assigned": system,
        "system_pct": pct(system),
        "hydraulics_available": hydraulics,
        "hydraulics_pct": pct(hydraulics),
        "no_material": total - material,
        "no_system": total - system,
        "no_hydraulics": total - hydraulics,
    }


def ruleset_versions(issues) -> dict[str, str]:
    """The ruleset_version each engine stamped on this run's findings."""
    seen: dict[str, set[str]] = defaultdict(set)
    for issue in issues:
        version = (issue.metadata or {}).get("ruleset_version") or ""
        code = issue.rule_id.split(".")[0]
        if version:
            seen[code].add(version)
    return {code: ", ".join(sorted(v)) for code, v in sorted(seen.items())}


def null_contract_fields(envelope: AnalysisResultContract) -> list[str]:
    """AuditIssueContract fields that are empty on *every* issue of a run.

    Pydantic gives each field a default, so nothing is literally ``None``; the
    useful question is which fields never carry a value, and that is what this
    reports.
    """
    fields = list(AuditIssueContract.model_fields)
    if not envelope.audit_issues:
        return fields
    unpopulated = []
    for name in fields:
        if all(not getattr(i, name, None) for i in envelope.audit_issues):
            unpopulated.append(name)
    return unpopulated


def validate_bcf(archive: bytes) -> tuple[int, int, list[str]]:
    """Validate every markup.bcf in a BCF archive against BCF 2.1's markup.xsd.

    Returns ``(topics, violations, messages)`` -- the same ``iter_errors`` check
    tests/test_phase_6e_export.py:466-475 performs.
    """
    import xmlschema

    schema = xmlschema.XMLSchema(str(BCF_MARKUP_XSD))
    topics = 0
    messages: list[str] = []
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        for name in zf.namelist():
            if not name.endswith("markup.bcf"):
                continue
            topics += 1
            markup = zf.read(name).decode("utf-8")
            for error in schema.iter_errors(markup):
                messages.append(f"{name}: {error.reason or error}")
    return topics, len(messages), messages[:20]


def run_corrosion(
    model_path: Path, content: bytes, parsed: dict, codes: tuple[str, ...], out_root: Path
) -> RunOutcome:
    """One corrosion audit, exported and summarised."""
    engine_dir = _engine_dir(codes)
    run_dir = out_root / model_path.stem / engine_dir
    run_dir.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    raw = _run_corrosion_tracked(content, 0, list(codes), include_low=True)
    elapsed = time.monotonic() - started

    issues = raw.get("audit_issues", []) or []
    canonical = resolve_engine_codes(list(codes))

    # --- the envelope, built by the API's own formatter -------------------
    envelope = _format_result("corrosion", 0, raw)
    envelope.duration_seconds = round(elapsed, 3)
    envelope.elements_evaluated = parsed.get("element_count", 0)
    envelope.unique_elements_evaluated = len({i.element_id for i in issues})
    envelope.rules_with_elements = len({i.rule_id for i in issues})
    verdicts = [i for i in issues if not _is_dq(i)]
    envelope.pass_rate = (
        round(1.0 - len({i.element_id for i in verdicts}) / parsed["element_count"], 4)
        if parsed.get("element_count")
        else None
    )
    # Everything a real run takes from the project record, with explicit local
    # stand-ins, plus the run provenance AnalysisResultContract has no dedicated
    # field for. `summary` is a real contract field (contracts.py:988).
    envelope.summary = {
        "project_id": 0,
        "project_name": f"local:{model_path.stem}",
        "organisation": "local:showcase",
        "model_id": None,
        "uploaded_file_id": None,
        "model_file_name": model_path.name,
        "model_path": str(model_path),
        "model_sha256": parsed.get("source_sha256", ""),
        "ifc_schema": parsed.get("schema", ""),
        "engines_requested": list(codes),
        "engines_canonical": list(canonical),
        "include_low": True,
        "run_started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - elapsed)),
        "run_seconds": round(elapsed, 3),
        "ruleset_versions": ruleset_versions(issues),
        "coverage": coverage(parsed),
    }

    # Prove the envelope is contract-valid, not merely contract-shaped.
    revalidated = AnalysisResultContract.model_validate(envelope.model_dump())
    (run_dir / "result.json").write_text(
        json.dumps(revalidated.model_dump(), indent=2, default=str), encoding="utf-8"
    )

    # --- exports, through the 6E functions --------------------------------
    csv_text = to_csv(raw)
    (run_dir / "findings.csv").write_text(csv_text, encoding="utf-8")
    (run_dir / "findings.json").write_text(to_json(raw), encoding="utf-8")
    (run_dir / "sample_50.csv").write_text(
        "\n".join(csv_text.splitlines()[:51]) + "\n", encoding="utf-8"
    )

    bcf_topics = bcf_violations = None
    bcf_messages: list[str] = []
    if len(codes) == 5:
        archive = to_bcf(raw)
        (run_dir / "findings.bcf").write_bytes(archive)
        bcf_topics, bcf_violations, bcf_messages = validate_bcf(archive)

    # --- summary ----------------------------------------------------------
    bands = Counter(i.band.value for i in verdicts)
    dq = [i for i in issues if _is_dq(i)]
    dq_status = Counter((i.metadata or {}).get("check", "") for i in dq)
    per_engine = {}
    for code in SINGLE_ENGINES:
        mine = _attributed(issues, code)
        per_engine[code] = {
            "verdicts": sum(1 for i in mine if not _is_dq(i)),
            "data_quality": sum(1 for i in mine if _is_dq(i)),
        }

    summary = {
        "model": model_path.name,
        "model_stem": model_path.stem,
        "model_path": str(model_path),
        "model_sha256": parsed.get("source_sha256", ""),
        "engine_set": engine_dir,
        "engines_requested": list(codes),
        "engines_canonical": list(canonical),
        "include_low": True,
        "element_count": parsed.get("element_count", 0),
        "wall_clock_seconds": round(elapsed, 2),
        "findings_total": len(issues),
        "verdicts_total": len(verdicts),
        "data_quality_total": len(dq),
        "bands": {
            "critical": bands.get("critical", 0),
            "high": bands.get("high", 0),
            "medium": bands.get("medium", 0),
            "low": bands.get("low", 0),
        },
        "data_quality_status": dict(sorted(dq_status.items())),
        "per_engine": per_engine,
        "rows_missing_ruleset_version": sum(
            1 for i in issues if not (i.metadata or {}).get("ruleset_version")
        ),
        "ruleset_versions": ruleset_versions(issues),
        "coverage": coverage(parsed),
        "parity": {
            "model_validate_ok": True,
            "csv_header": csv_text.splitlines()[0].split(","),
            "csv_header_matches_exporter_columns": csv_text.splitlines()[0].split(",")
            == list(CSV_COLUMNS),
            "contract_fields_unpopulated_on_every_issue": null_contract_fields(envelope),
        },
        "bcf": (
            None
            if bcf_topics is None
            else {"topics": bcf_topics, "xsd_violations": bcf_violations, "examples": bcf_messages}
        ),
        "compliance_error": raw.get("compliance_error"),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return RunOutcome(model_path.name, engine_dir, elapsed, summary)


def run_seismic(models: list[Path], out_root: Path) -> RunOutcome:
    """The federated SB-001 run."""
    run_dir = out_root / "SEISMIC-1542-federation" / "SB-001"
    run_dir.mkdir(parents=True, exist_ok=True)

    payloads = [(p.name, p.read_bytes()) for p in models]
    started = time.monotonic()
    raw = run_seismic_analysis(
        payloads[0][1], primary_label=payloads[0][0], extra_models=payloads[1:]
    )
    elapsed = time.monotonic() - started

    issues = raw.get("audit_issues", []) or []
    verdicts = [i for i in issues if not _is_dq(i)]
    dq = [i for i in issues if _is_dq(i)]

    envelope = _format_result("seismic", 0, raw)
    envelope.duration_seconds = round(elapsed, 3)
    envelope.unique_elements_evaluated = len({i.element_id for i in issues})
    envelope.rules_with_elements = len({i.rule_id for i in issues})
    envelope.summary = {
        "project_id": 0,
        "project_name": "local:west-riverside-federation",
        "organisation": "local:showcase",
        "model_id": None,
        "uploaded_file_id": None,
        "model_file_name": payloads[0][0],
        "federated_models": [name for name, _ in payloads],
        "model_sha256": {name: sha256_of(data) for name, data in payloads},
        "engines_requested": ["SB-001"],
        "engines_canonical": ["SB-001"],
        "include_low": True,
        "run_seconds": round(elapsed, 3),
        "ruleset_versions": ruleset_versions(issues),
    }
    revalidated = AnalysisResultContract.model_validate(envelope.model_dump())
    (run_dir / "result.json").write_text(
        json.dumps(revalidated.model_dump(), indent=2, default=str), encoding="utf-8"
    )

    csv_text = to_csv(raw)
    (run_dir / "findings.csv").write_text(csv_text, encoding="utf-8")
    (run_dir / "findings.json").write_text(to_json(raw), encoding="utf-8")
    (run_dir / "sample_50.csv").write_text(
        "\n".join(csv_text.splitlines()[:51]) + "\n", encoding="utf-8"
    )
    archive = to_bcf(raw)
    (run_dir / "findings.bcf").write_bytes(archive)
    topics, violations, messages = validate_bcf(archive)

    bands = Counter(i.band.value for i in verdicts)
    summary = {
        "model": " + ".join(name for name, _ in payloads),
        "model_stem": "SEISMIC-1542-federation",
        "model_path": [str(p) for p in models],
        "engine_set": "SB-001",
        "engines_requested": ["SB-001"],
        "engines_canonical": ["SB-001"],
        "include_low": True,
        "element_count": envelope.element_count,
        "wall_clock_seconds": round(elapsed, 2),
        "findings_total": len(issues),
        "verdicts_total": len(verdicts),
        "data_quality_total": len(dq),
        "bands": {
            "critical": bands.get("critical", 0),
            "high": bands.get("high", 0),
            "medium": bands.get("medium", 0),
            "low": bands.get("low", 0),
        },
        "data_quality_status": dict(
            sorted(Counter((i.metadata or {}).get("check", "") for i in dq).items())
        ),
        "rows_missing_ruleset_version": sum(
            1 for i in issues if not (i.metadata or {}).get("ruleset_version")
        ),
        "ruleset_versions": ruleset_versions(issues),
        "parity": {
            "model_validate_ok": True,
            "csv_header": csv_text.splitlines()[0].split(","),
            "csv_header_matches_exporter_columns": csv_text.splitlines()[0].split(",")
            == list(CSV_COLUMNS),
            "contract_fields_unpopulated_on_every_issue": null_contract_fields(envelope),
        },
        "bcf": {"topics": topics, "xsd_violations": violations, "examples": messages},
        "compliance_error": raw.get("compliance_error"),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return RunOutcome(summary["model"], "SB-001", elapsed, summary)


def consistency(model_stem: str, out_root: Path) -> dict:
    """Compare each single-engine run against that engine's share of the five.

    A difference means running an engine alone is not the same as running it in
    company, which would make the analyse page's chips lie. Reported, never
    repaired.
    """
    checks = {}
    all5_dir = out_root / model_stem / "ALL5"
    if not (all5_dir / "findings.json").exists():
        return checks
    all5 = json.loads((all5_dir / "findings.json").read_text(encoding="utf-8"))
    all5_rows = (all5.get("findings") or []) + (all5.get("data_quality") or [])

    for code in SINGLE_ENGINES:
        solo_path = out_root / model_stem / code / "findings.json"
        if not solo_path.exists():
            continue
        solo = json.loads(solo_path.read_text(encoding="utf-8"))
        solo_rows = (solo.get("findings") or []) + (solo.get("data_quality") or [])
        solo_keys = {
            (r["element_id"], r["rule_id"]) for r in solo_rows if r["rule_id"].startswith(code)
        }
        all5_keys = {
            (r["element_id"], r["rule_id"]) for r in all5_rows if r["rule_id"].startswith(code)
        }
        only_solo = sorted(k[0] for k in solo_keys - all5_keys)[:3]
        only_all5 = sorted(k[0] for k in all5_keys - solo_keys)[:3]
        checks[code] = {
            "alone": len(solo_keys),
            "within_all_five": len(all5_keys),
            "match": len(solo_keys) == len(all5_keys) and not only_solo and not only_all5,
            "example_guids_only_when_alone": only_solo,
            "example_guids_only_within_all_five": only_all5,
        }
    return checks


def select_models(inventory_path: Path) -> list[Path]:
    """The five piping models, per the selection rule stated in the report."""
    data = json.loads(inventory_path.read_text(encoding="utf-8"))
    real = [
        r
        for r in data
        if r["valid"] and r["element_count"] > 0 and r["name"] != PROJECT_1540_MODEL
    ]
    real.sort(
        key=lambda r: (r["material_ok"] / r["element_count"], r["element_count"]), reverse=True
    )
    chosen = [Path(r["path"]) for r in real[:3]]
    chosen.append(MODELS_ROOT / "hospital" / PROJECT_1540_MODEL)
    chosen.append(SYNTHETIC_CONTROL)
    return chosen


def main(argv: list[str] | None = None) -> int:
    """Run the sweep and write every artefact."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--only", default="", help="Restrict to model stems containing this")
    parser.add_argument("--skip-seismic", action="store_true")
    args = parser.parse_args(argv)

    out_root = args.out_dir / "runs"
    out_root.mkdir(parents=True, exist_ok=True)

    inventory = args.out_dir / "01_inventory.json"
    if not inventory.exists():
        print(f"Run showcase_inventory.py first: {inventory} is missing", file=sys.stderr)
        return 2

    models = select_models(inventory)
    if args.only:
        models = [m for m in models if args.only in m.stem]

    if SYNTHETIC_CONTROL in models:
        digest = sha256_of(SYNTHETIC_CONTROL.read_bytes())
        print(f"synthetic control sha256 {'MATCH' if digest == SYNTHETIC_SHA256 else 'MISMATCH'}")

    outcomes: list[RunOutcome] = []
    abandoned: list[str] = []
    for model in models:
        print(f"\n=== {model.name} ===", flush=True)
        content = model.read_bytes()
        parsed = parse_ifc_bytes(content, source_ref=str(model), with_piping=True)
        if not parsed.get("quality", {}).get("valid"):
            print(f"  unreadable: {parsed.get('quality', {}).get('error')}", flush=True)
            continue
        print(f"  {parsed['element_count']:,} elements", flush=True)

        for codes in [(c,) for c in SINGLE_ENGINES] + [ALL_FIVE]:
            label = _engine_dir(codes)
            print(f"  {label:6s} ...", end="", flush=True)
            outcome = run_corrosion(model, content, parsed, codes, out_root)
            outcomes.append(outcome)
            flag = ""
            if outcome.seconds > RUN_BUDGET_SECONDS:
                outcome.over_budget = True
                abandoned.append(f"{model.name}/{label}")
                flag = "  OVER BUDGET"
            s = outcome.summary
            print(
                f" {s['findings_total']:,} findings "
                f"({s['verdicts_total']:,} verdicts / {s['data_quality_total']:,} DQ) "
                f"in {outcome.seconds:.1f}s{flag}",
                flush=True,
            )
            if outcome.over_budget:
                print("  budget exceeded; skipping the rest of this model", flush=True)
                break

    if not args.skip_seismic:
        federation = [MODELS_ROOT / "hospital" / name for name in PROJECT_1542_FEDERATION]
        if all(p.exists() for p in federation):
            print("\n=== SB-001 federated (project 1542's pair) ===", flush=True)
            outcome = run_seismic(federation, out_root)
            outcomes.append(outcome)
            s = outcome.summary
            print(
                f"  {s['findings_total']:,} findings in {outcome.seconds:.1f}s; "
                f"BCF {s['bcf']['topics']} topics, {s['bcf']['xsd_violations']} violations",
                flush=True,
            )
        else:
            print("Federation models missing; seismic skipped", file=sys.stderr)

    # Consistency, per model
    checks = {}
    for model in models:
        result = consistency(model.stem, out_root)
        if result:
            checks[model.stem] = result
    (args.out_dir / "02_consistency.json").write_text(
        json.dumps(checks, indent=2), encoding="utf-8"
    )

    total_missing = sum(o.summary["rows_missing_ruleset_version"] for o in outcomes)
    print(f"\nRuns completed: {len(outcomes)}")
    print(f"Rows missing ruleset_version across all runs: {total_missing}")
    if abandoned:
        print("Abandoned over the 15-minute budget: " + ", ".join(abandoned))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
