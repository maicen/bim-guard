#!/usr/bin/env python
"""Run SB-001 (Blue Halo) federated and control seismic sweeps over local models.

WHY THIS EXISTS ALONGSIDE ``run_full_pipeline.py``

    ``scripts/run_full_pipeline.py`` runs the same seismic stage, but prints a
    human summary only. Three numbers a federated trial is actually judged on
    never reach its stdout:

    * **bracing scope** -- how many in-class elements were braced, how many fell
      below ``thresholds.pipe_diameter_mm``, how many were unmeasurable.
      ``phase_6d_seismic.run_seismic_analysis`` computes these and writes them to
      its logger, but deliberately keeps them out of the returned dict so a
      seismic result and a corrosion result stay key-identical downstream
      (``app/modules/phase_6/phase_6d_seismic.py``, "Bracing scope stays in the
      log rather than the result").
    * **cross-model pairs** -- which model a halo came from and which model the
      element intruding on it came from. Carried per-issue in
      ``metadata['source_model']`` / ``metadata['clashing_source_model']``.
    * **geometry_unavailable** -- data-quality issues tagged
      ``metadata['check'] == 'geometry_unavailable'``.

    This driver calls the same ``run_seismic_analysis`` entry point with the same
    arguments ``run_full_pipeline.py`` passes, attaches a log handler to recover
    the scope counters the engine already computed, and aggregates the issue
    metadata. It reimplements no scoping or clash logic -- recomputing the
    threshold test here would risk reporting a number the engine did not produce.

WHY IT DOES NOT USE ``--auto-extra``

    ``--auto-extra`` globs every other ``.ifc`` beside the model. All test models
    live in one flat directory, so it would federate four buildings into one run.
    Building membership is declared in ``BUILDINGS`` below and extras are passed
    explicitly, which needs no copies of 350 MB of IFC on disk.

Usage::

    uv run python scripts/run_seismic_matrix.py --building duplex
    uv run python scripts/run_seismic_matrix.py            # every building

Exit codes: ``0`` every run completed and every archive validated, ``1``
otherwise.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.modules.blue_halo.halo_volume_generator import BraceType  # noqa: E402
from app.modules.comparator.issue_schema import Issue  # noqa: E402
from app.modules.phase_6 import phase_6d_seismic  # noqa: E402
from app.modules.phase_6.phase_6d_seismic import (  # noqa: E402
    DATA_QUALITY,
    DEFAULT_CONFIG_PATH,
    PRIMARY_MODEL_LABEL,
    run_seismic_analysis,
)
from app.services.bcf_exporter import BCFExporter  # noqa: E402

MODEL_DIR = REPO_ROOT / "data" / "test_models"
BCF_ROOT = REPO_ROOT / "docs" / "bcf_exports" / "seismic-2026-09"
DEFAULT_JSON = REPO_ROOT / "docs" / "validation" / "data" / "seismic-federated-2026-09.json"

#: Buildings with more than one discipline model on disk. ``primary`` is the MEP
#: model the federated run is driven from; ``models`` is every discipline of that
#: building. ``building_type`` is the occupancy the model actually is -- note the
#: shipped config sets ``hospital_addition_mm`` to 0, so this currently has no
#: effect on the clearance envelope (reported as an anomaly, not worked around).
BUILDINGS: dict[str, dict] = {
    "clinic": {
        "building_type": "hospital",
        "primary": "Clinic_Plumbing.ifc",
        "models": ["Clinic_HVAC.ifc", "Clinic_Plumbing.ifc", "Clinic_Structural.ifc"],
    },
    "west-riverside": {
        "building_type": "hospital",
        "primary": "west_riverside_hospital_mech_ifc4.ifc",
        "models": [
            "west_riverside_hospital_mech_ifc4.ifc",
            "west_riverside_hospital_plumb_ifc2x3.ifc",
            "west_riverside_hospital_plumb_ifc4.ifc",
            "west_riverside_hospital_str_ifc4.ifc",
        ],
    },
    "duplex": {
        "building_type": "standard",
        "primary": "Duplex_MEP_20110907.ifc",
        "models": [
            "Duplex_A_20110907.ifc",
            "Duplex_MEP_20110907.ifc",
            "Duplex_Plumbing_20121113.ifc",
        ],
    },
    # Three MEP disciplines, no structural model. Meets the "more than one
    # discipline model" test, so it is offered here; not part of the three
    # buildings the September trial named.
    "digitalhub": {
        "building_type": "standard",
        "primary": "DigitalHub_FM-SAN_v2.ifc",
        "models": [
            "DigitalHub_FM-HZG_v2.ifc",
            "DigitalHub_FM-LFT_v2.ifc",
            "DigitalHub_FM-SAN_v2.ifc",
        ],
    },
}

BAND_KEYS = ("critical", "high", "medium", "low")


class _ScopeCapture(logging.Handler):
    """Recover the bracing-scope counters ``run_seismic_analysis`` logs.

    The engine emits exactly one ``"Seismic analysis complete ..."`` record per
    run, with the counters as positional args. Reading them off the record is
    exact; recomputing them here would be a second implementation of the
    threshold rule and could disagree with the engine silently.
    """

    FIELDS = (
        "models", "elements", "in_class", "braced", "below_threshold",
        "unmeasurable", "threshold_mm", "clashes", "data_quality",
        "federated_duplicates",
    )

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.scope: dict | None = None

    def emit(self, record: logging.LogRecord) -> None:
        if not str(record.msg).startswith("Seismic analysis complete"):
            return
        args = record.args or ()
        if len(args) == len(self.FIELDS):
            self.scope = dict(zip(self.FIELDS, args))


def _source_label(raw: str, primary_name: str) -> str:
    """Map the engine's ``"primary model"`` label back to the real filename."""
    if raw == PRIMARY_MODEL_LABEL:
        return primary_name
    return raw or "(unattributed)"


def _summarise_issues(issues: list[Issue], primary_name: str) -> dict:
    """Split *issues* into clash bands, geometry gaps and cross-model pairs."""
    clashes = [i for i in issues if i.mechanism != DATA_QUALITY]
    quality = [i for i in issues if i.mechanism == DATA_QUALITY]

    bands = Counter(i.band.value for i in clashes)
    pairs: Counter = Counter()
    cross = 0
    for issue in clashes:
        meta = issue.metadata or {}
        src = _source_label(str(meta.get("source_model", "")), primary_name)
        dst = _source_label(str(meta.get("clashing_source_model", "")), primary_name)
        pairs[(src, dst)] += 1
        if src != dst:
            cross += 1

    geometry_unavailable = sum(
        1 for i in quality if (i.metadata or {}).get("check") == "geometry_unavailable"
    )
    return {
        "clashes_total": len(clashes),
        "clashes_by_band": {k: bands.get(k, 0) for k in BAND_KEYS},
        "cross_model_clashes": cross,
        "same_model_clashes": len(clashes) - cross,
        "cross_model_pairs": [
            {"source_model": s, "clashing_source_model": d, "count": n}
            for (s, d), n in sorted(pairs.items(), key=lambda kv: -kv[1])
        ],
        "data_quality_total": len(quality),
        "geometry_unavailable": geometry_unavailable,
    }


def _validate(path: Path) -> dict:
    """Validate one BCF archive against the vendored BCF 2.1 XSDs."""
    from scripts.regenerate_demo_bcf import _schemas, validate_archive

    topics, violations = validate_archive(path, _schemas())
    return {
        "topics": topics,
        "violations_total": sum(violations.values()),
        "violations": [{"reason": r, "count": c} for r, c in violations.most_common()],
    }


def run_one(
    building: str,
    label: str,
    primary: Path,
    extras: list[Path],
    building_type: str,
    config_path: Path,
) -> dict:
    """Run one seismic analysis and return its full record."""
    print(f"\n=== {building} / {label}")
    print(f"    primary  {primary.name} ({primary.stat().st_size / 1e6:.1f} MB)")
    for extra in extras:
        print(f"    extra    {extra.name} ({extra.stat().st_size / 1e6:.1f} MB)")

    capture = _ScopeCapture()
    # The module's own logger object, not a name lookup: get_logger() namespaces
    # under "bimguard.", so guessing the name silently captures nothing.
    engine_log = phase_6d_seismic.logger
    engine_log.addHandler(capture)
    previous_level = engine_log.level
    engine_log.setLevel(logging.INFO)

    started = time.perf_counter()
    try:
        result = run_seismic_analysis(
            primary.read_bytes(),
            extra_models=[(p.name, p.read_bytes()) for p in extras],
            config_path=config_path,
            brace_type=BraceType.ANGLE_IRON,
            seismic_zone=True,
            building_type=building_type,
            run_id="SEIS",
        )
    finally:
        engine_log.removeHandler(capture)
        engine_log.setLevel(previous_level)
    elapsed = time.perf_counter() - started

    issues: list[Issue] = list(result.get("audit_issues") or [])
    record = {
        "building": building,
        "run": label,
        "federated": bool(extras),
        "primary_model": primary.name,
        "extra_models": [p.name for p in extras],
        "building_type": building_type,
        "wall_clock_s": round(elapsed, 1),
        "compliance_error": result.get("compliance_error"),
        "issue_stats": result.get("issue_stats"),
        "scope": capture.scope,
        **_summarise_issues(issues, primary.name),
    }

    out_dir = BCF_ROOT / building / label
    archive = BCFExporter(export_dir=out_dir).export(
        issues, f"{label}.bcfzip", project_name=f"BIMGUARD SB-001 {building} / {label}"
    )
    record["bcf_archive"] = archive.relative_to(REPO_ROOT).as_posix()
    record["bcf_validation"] = _validate(archive)

    scope = capture.scope or {}
    print(
        f"    scope    elements={scope.get('elements')} in_class={scope.get('in_class')} "
        f"braced={scope.get('braced')} below_threshold={scope.get('below_threshold')} "
        f"unmeasurable={scope.get('unmeasurable')}"
    )
    print(
        f"    clashes  {record['clashes_total']} "
        f"(crit {record['clashes_by_band']['critical']}, "
        f"high {record['clashes_by_band']['high']}, "
        f"med {record['clashes_by_band']['medium']}, "
        f"low {record['clashes_by_band']['low']})  "
        f"cross-model {record['cross_model_clashes']}"
    )
    print(
        f"    quality  geometry_unavailable={record['geometry_unavailable']}  "
        f"bcf topics={record['bcf_validation']['topics']} "
        f"violations={record['bcf_validation']['violations_total']}  "
        f"{elapsed:.1f}s"
    )
    if record["compliance_error"]:
        print(f"    ERROR    {record['compliance_error']}")
    return record


def main(argv: list[str] | None = None) -> int:
    """Run the requested buildings and write the aggregated JSON record."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--building", action="append", default=[], choices=sorted(BUILDINGS),
        help="building to run (repeatable; default: clinic, west-riverside, duplex)",
    )
    parser.add_argument(
        "--controls-only", action="store_true", help="skip the federated run"
    )
    parser.add_argument(
        "--federated-only", action="store_true", help="skip the single-model controls"
    )
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON, help="aggregated output path")
    parser.add_argument("--seismic-config", type=Path, default=REPO_ROOT / DEFAULT_CONFIG_PATH)
    args = parser.parse_args(argv)

    targets = args.building or ["clinic", "west-riverside", "duplex"]
    config_path = args.seismic_config
    if not config_path.is_absolute():
        config_path = REPO_ROOT / config_path

    records: list[dict] = []
    # Append to an existing file so buildings can be run one at a time.
    if args.json.is_file():
        try:
            records = json.loads(args.json.read_text(encoding="utf-8")).get("runs", [])
        except (ValueError, AttributeError):
            records = []

    failures = 0
    for building in targets:
        spec = BUILDINGS[building]
        models = [MODEL_DIR / name for name in spec["models"]]
        missing = [p.name for p in models if not p.is_file()]
        if missing:
            print(f"error: {building}: models not on disk: {', '.join(missing)}", file=sys.stderr)
            print("Fetch with: uv run python scripts/fetch_test_model.py --set <set>", file=sys.stderr)
            failures += 1
            continue

        primary = MODEL_DIR / spec["primary"]
        runs: list[tuple[str, Path, list[Path]]] = []
        if not args.controls_only:
            runs.append(("federated", primary, [p for p in models if p != primary]))
        if not args.federated_only:
            for model in models:
                runs.append((f"control-{model.stem}", model, []))

        for label, model, extras in runs:
            # Drop this run's record if the file already carries one, so a
            # re-run replaces rather than duplicates it.
            records = [
                r for r in records
                if not (r.get("building") == building and r.get("run") == label)
            ]
            try:
                record = run_one(
                    building, label, model, extras, spec["building_type"], config_path
                )
            except Exception as exc:  # noqa: BLE001 - one bad run must not lose the rest
                print(f"    FAILED   {type(exc).__name__}: {exc}", file=sys.stderr)
                records.append({
                    "building": building, "run": label, "primary_model": model.name,
                    "failed": f"{type(exc).__name__}: {exc}",
                })
                failures += 1
            else:
                records.append(record)
                if record["compliance_error"] or record["bcf_validation"]["violations_total"]:
                    failures += 1

            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(
                json.dumps(
                    {
                        "generated_by": "scripts/run_seismic_matrix.py",
                        "seismic_config": config_path.relative_to(REPO_ROOT).as_posix(),
                        "runs": sorted(
                            records, key=lambda r: (r.get("building", ""), r.get("run", ""))
                        ),
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

    print(f"\nWrote {args.json.relative_to(REPO_ROOT).as_posix()} ({len(records)} runs)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
