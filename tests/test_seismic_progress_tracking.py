"""Tests for SB-001's progress reporting, and for the two runs coexisting.

WHAT WENT WRONG, SO IT IS CLEAR WHAT THESE PIN

    A seismic run showed a frozen "Running Engine... 0%" for its whole duration
    while the engine worked correctly and returned thousands of findings. Two
    separate causes, and fixing either alone leaves the bug:

    **Nothing tracked it.** ``analysis_runner`` deliberately skipped binding a
    tracker for the seismic path, because the store used to be keyed by project
    id alone and a second bind would have reset an in-flight corrosion run for
    the same project. The store has been keyed by ``(project_id, run_key)``
    since GRAPH-001, so the conflict is gone -- but the seismic path was never
    revisited.

    **Nothing could read it.** Every reporting call site -- the workflow
    endpoint, the SSE initial frame, the SSE transition frames -- called
    ``snapshot(project_id)``, which reads the *default* key only. So even the
    GRAPH-001 run, tracked correctly under its own key, reported as an engine
    that had never started.

    The tests below therefore assert both halves, and assert them against the
    merge rather than against the seismic tracker directly: reading the seismic
    tracker by name would pass even if the endpoints could not see it, which is
    the failure that shipped.

REGRESSION DIRECTION MATTERS

    The fix must not buy seismic progress with corrosion progress. The
    interleaving tests run one analysis against the other *in both orders* and
    assert the untouched run keeps its own stages and counters -- which is the
    clobbering the original comment was avoiding, and which per-run keys are
    supposed to make structurally impossible.

NO LIVE DATABASE and NO SERVER. Runs are built by hand or driven through
stubbed model loaders; the endpoint test drives the ASGI app in-process.

Run: uv run pytest tests/test_seismic_progress_tracking.py -v
"""

from __future__ import annotations

import pytest

import app.services.analysis_runner as runner
from app.services import pipeline_tracker as pt
from app.services.analysis_cache import ANALYSIS_CACHE
from app.services.pipeline_tracker import (
    CC_ENGINE,
    DEFAULT_RUN_KEY,
    ENGINE_CODES,
    GC_ENGINE,
    GRAPH_ENGINE,
    GRAPH_RUN_KEY,
    RUN_KEY_BY_ENGINE,
    SB_ENGINE,
    SEISMIC_RUN_KEY,
    Stage,
)


@pytest.fixture(autouse=True)
def _clean_state():
    """Each test starts from an empty store and cache, so leakage fails loudly."""
    pt.TRACKERS.clear()
    ANALYSIS_CACHE.clear()
    yield
    pt.TRACKERS.clear()
    ANALYSIS_CACHE.clear()


def empty_result() -> dict:
    """Build an AnalysisResult with no error, so the runner caches it."""
    return {
        "audit_issues": [],
        "issue_stats": {},
        "cost_impact": None,
        "compliance_error": None,
        "compliance_is_demo": False,
    }


# ---------------------------------------------------------------------------
# The engine is registered
# ---------------------------------------------------------------------------


def test_sb001_is_an_engine_the_endpoint_knows_about():
    """``tracker.run`` raises on an unregistered code, so this gates everything."""
    assert SB_ENGINE in ENGINE_CODES
    assert pt.ENGINES[SB_ENGINE].declared_status is pt.Status.PENDING


def test_sb001_owns_its_own_run_key():
    """Sharing the corrosion key is what the reset conflict was about."""
    assert RUN_KEY_BY_ENGINE[SB_ENGINE] == SEISMIC_RUN_KEY
    assert SEISMIC_RUN_KEY != DEFAULT_RUN_KEY
    assert RUN_KEY_BY_ENGINE[GC_ENGINE] == DEFAULT_RUN_KEY


def test_every_engine_is_owned_by_exactly_one_run_key():
    """The merge takes each engine from its owner; an unowned one would vanish."""
    assert set(RUN_KEY_BY_ENGINE) == set(ENGINE_CODES)


# ---------------------------------------------------------------------------
# The merged view -- the half that made a tracked run unreadable
# ---------------------------------------------------------------------------


def test_a_seismic_run_is_visible_without_naming_its_run_key():
    with pt.tracking(1, run_key=SEISMIC_RUN_KEY):
        pt.emit(SB_ENGINE, Stage.ENGINE_EXECUTION, elements_total=900)

    engine = pt.merged_snapshot(1)["engines"][SB_ENGINE]

    assert engine["status"] == "running"
    assert engine["current_stage"] == 3
    assert engine["progress_percent"] == 50
    assert engine["metrics"]["elements_total"] == 900
    assert engine["run_key"] == SEISMIC_RUN_KEY


def test_the_default_key_alone_would_still_miss_it():
    """The bug, pinned: reading one key is why a tracked run reported nothing."""
    with pt.tracking(1, run_key=SEISMIC_RUN_KEY):
        pt.emit(SB_ENGINE, Stage.ENGINE_EXECUTION)

    assert pt.snapshot(1)["engines"][SB_ENGINE] == {"status": "pending"}
    assert pt.merged_snapshot(1)["engines"][SB_ENGINE]["status"] == "running"


def test_the_graph_run_was_unreadable_for_the_same_reason_and_is_fixed_too():
    with pt.tracking(2, run_key=GRAPH_RUN_KEY):
        pt.emit(GRAPH_ENGINE, Stage.IFC_PARSING)

    assert pt.merged_snapshot(2)["engines"][GRAPH_ENGINE]["status"] == "running"


def test_merged_view_keeps_the_documented_top_level_shape():
    with pt.tracking(1, run_key=SEISMIC_RUN_KEY):
        pt.emit(SB_ENGINE, Stage.VALIDATION)

    payload = pt.merged_snapshot(1)

    assert set(payload) == {"project_id", "run_key", "timestamp", "engines"}
    assert payload["project_id"] == 1
    assert payload["timestamp"].endswith("Z")
    assert tuple(payload["engines"]) == ENGINE_CODES


def test_an_untouched_project_reports_declared_statuses_under_the_default_key():
    payload = pt.merged_snapshot(99)

    assert payload["run_key"] == DEFAULT_RUN_KEY
    assert payload["engines"][SB_ENGINE] == {"status": "pending"}
    assert payload["engines"][GC_ENGINE] == {"status": "pending"}
    assert payload["engines"]["MC-001"] == {"status": "not_implemented"}


def test_an_untouched_engine_carries_no_run_key():
    """The progress average keys off this to tell "idle" from "in this run"."""
    with pt.tracking(1, run_key=SEISMIC_RUN_KEY):
        pt.emit(SB_ENGINE, Stage.ENGINE_EXECUTION)

    assert "run_key" not in pt.merged_snapshot(1)["engines"][GC_ENGINE]


def test_the_active_run_key_names_the_run_that_reported_last():
    """A finished corrosion run must not claim a later seismic run's progress.

    Ordering cannot come from ``time.monotonic``: its resolution is ~15ms on
    Windows, so two runs inside one request tie and the tie resolves to the
    older run -- naming the corrosion run active while seismic is the one
    actually moving. This asserts the sequence-based ordering instead.
    """
    with pt.tracking(1):
        pt.emit(GC_ENGINE, Stage.ENGINE_EXECUTION)
        pt.complete(GC_ENGINE)
    with pt.tracking(1, run_key=SEISMIC_RUN_KEY):
        pt.emit(SB_ENGINE, Stage.ENGINE_EXECUTION)

        assert pt.merged_snapshot(1)["run_key"] == SEISMIC_RUN_KEY


def test_reading_the_merge_does_not_make_the_reader_the_active_run():
    """Polling must not reorder recency, or a poll would rename the active run."""
    with pt.tracking(1, run_key=SEISMIC_RUN_KEY):
        pt.emit(SB_ENGINE, Stage.ENGINE_EXECUTION)
    with pt.tracking(1):
        pt.emit(GC_ENGINE, Stage.ENGINE_EXECUTION)

    for _ in range(3):
        assert pt.merged_snapshot(1)["run_key"] == DEFAULT_RUN_KEY


def test_an_engine_emitted_under_a_foreign_run_key_is_still_reported():
    """Ownership picks the cell; it must not be the only way to fill one."""
    with pt.tracking(1, run_key=GRAPH_RUN_KEY):
        pt.emit(SB_ENGINE, Stage.RISK_SCORING)

    engine = pt.merged_snapshot(1)["engines"][SB_ENGINE]

    assert engine["status"] == "running"
    assert engine["run_key"] == GRAPH_RUN_KEY


# ---------------------------------------------------------------------------
# The two runs coexisting -- the conflict the original comment avoided
# ---------------------------------------------------------------------------


def test_a_seismic_run_does_not_reset_an_in_flight_corrosion_run():
    with pt.tracking(1):
        pt.emit(GC_ENGINE, Stage.ENGINE_EXECUTION, elements_total=40)
        pt.increment(GC_ENGINE, elements_analyzed=12)

        # Mid-corrosion, the user starts a seismic run on the same project.
        with pt.tracking(1, run_key=SEISMIC_RUN_KEY):
            pt.emit(SB_ENGINE, Stage.ENGINE_EXECUTION, elements_total=900)

    engines = pt.merged_snapshot(1)["engines"]

    assert engines[GC_ENGINE]["current_stage"] == 3
    assert engines[GC_ENGINE]["metrics"]["elements_total"] == 40
    assert engines[GC_ENGINE]["metrics"]["elements_analyzed"] == 12
    assert engines[SB_ENGINE]["metrics"]["elements_total"] == 900


def test_a_corrosion_run_does_not_reset_an_in_flight_seismic_run():
    """The same property in the other direction; only one order was ever at risk."""
    with pt.tracking(1, run_key=SEISMIC_RUN_KEY):
        pt.emit(SB_ENGINE, Stage.ENGINE_EXECUTION, elements_total=900)
        pt.increment(SB_ENGINE, elements_assessed=300)

        with pt.tracking(1):
            pt.emit(GC_ENGINE, Stage.VALIDATION)

    engines = pt.merged_snapshot(1)["engines"]

    assert engines[SB_ENGINE]["current_stage"] == 3
    assert engines[SB_ENGINE]["metrics"]["elements_assessed"] == 300
    assert engines[GC_ENGINE]["current_stage"] == 1


def test_a_second_seismic_run_starts_from_clean_counters():
    """``reset=True`` must still apply within the seismic key itself."""
    with pt.tracking(1, run_key=SEISMIC_RUN_KEY):
        pt.increment(SB_ENGINE, elements_assessed=300)
        pt.emit(SB_ENGINE, Stage.ENGINE_EXECUTION)
    with pt.tracking(1, run_key=SEISMIC_RUN_KEY):
        pt.increment(SB_ENGINE, elements_assessed=5)
        pt.emit(SB_ENGINE, Stage.ENGINE_EXECUTION)

    metrics = pt.merged_snapshot(1)["engines"][SB_ENGINE]["metrics"]

    assert metrics["elements_assessed"] == 5


# ---------------------------------------------------------------------------
# The driver
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_models(monkeypatch):
    """Serve model bytes without storage; seismic federates every model."""
    monkeypatch.setattr(
        runner, "model_bytes_all", lambda project_id: ([("primary.ifc", b"IFC")], None)
    )
    monkeypatch.setattr(runner, "model_bytes", lambda project_id: (b"IFC", None))


def test_run_analysis_reports_sb001_through_the_merged_view(monkeypatch, stub_models):
    monkeypatch.setattr(runner, "run_seismic_analysis", lambda content, **kw: empty_result())

    runner.run_analysis("seismic", 5)

    engine = pt.merged_snapshot(5)["engines"][SB_ENGINE]

    assert engine["status"] == "complete"
    assert engine["progress_percent"] == 100
    assert engine["run_key"] == SEISMIC_RUN_KEY
    # Validation is the driver's, so it is recorded even against a stubbed kernel.
    assert [record["stage"] for record in engine["stages"]][0] == int(Stage.VALIDATION)


def test_the_driver_reports_the_findings_the_run_produced(monkeypatch, stub_models):
    from app.modules.comparator.issue_schema import Issue, RiskBand

    def one_finding(content, **kw):
        result = empty_result()
        result["audit_issues"] = [
            Issue(
                id="BGR-1",
                element_id="E1",
                rule_id="BIMGUARD-SB-001",
                title="Clearance intrusion",
                band=RiskBand.HIGH,
                score=8.0,
                mechanism="seismic_clearance",
                mitigation="Reroute",
            )
        ]
        return result

    monkeypatch.setattr(runner, "run_seismic_analysis", one_finding)

    runner.run_analysis("seismic", 5)

    metrics = pt.merged_snapshot(5)["engines"][SB_ENGINE]["metrics"]

    assert metrics["issues"] == 1
    assert metrics["data_quality"] == 0


def test_a_seismic_failure_is_reported_rather_than_left_running(monkeypatch, stub_models):
    def failed(content, **kw):
        result = empty_result()
        result["compliance_error"] = "The seismic clearance config could not be loaded."
        return result

    monkeypatch.setattr(runner, "run_seismic_analysis", failed)

    runner.run_analysis("seismic", 5)

    engine = pt.merged_snapshot(5)["engines"][SB_ENGINE]

    assert engine["status"] == "failed"
    assert "clearance config" in engine["error"]


def test_a_cached_seismic_result_does_not_report_a_run_that_did_not_happen(
    monkeypatch, stub_models
):
    """A cache hit runs no engine, so it must report no stages."""
    monkeypatch.setattr(runner, "run_seismic_analysis", lambda content, **kw: empty_result())
    runner.run_analysis("seismic", 5)
    pt.TRACKERS.clear()

    assert runner.run_analysis("seismic", 5)["cached"] is True
    assert pt.merged_snapshot(5)["engines"][SB_ENGINE] == {"status": "pending"}


def test_the_corrosion_path_still_tracks_gc_and_cc_under_the_default_key(monkeypatch):
    """The regression guard: seismic tracking must not have cost corrosion its own."""
    monkeypatch.setattr(runner, "model_bytes", lambda project_id: (b"IFC", None))
    monkeypatch.setattr(
        runner,
        "parse_ifc_bytes",
        lambda content, source_ref="", with_piping=False: {
            "quality": {"valid": True},
            "elements": [object(), object()],
        },
    )
    monkeypatch.setattr(
        runner, "run_corrosion_analysis", lambda parsed, **kw: empty_result()
    )

    runner.run_analysis("corrosion", 6)

    engines = pt.merged_snapshot(6)["engines"]

    for code in (GC_ENGINE, CC_ENGINE):
        assert engines[code]["status"] == "complete"
        assert engines[code]["progress_percent"] == 100
        assert engines[code]["run_key"] == DEFAULT_RUN_KEY
        assert engines[code]["metrics"]["elements_total"] == 2
    assert pt.merged_snapshot(6)["run_key"] == DEFAULT_RUN_KEY


# ---------------------------------------------------------------------------
# The kernel
# ---------------------------------------------------------------------------

ifcopenshell = pytest.importorskip("ifcopenshell", reason="Blue Halo needs ifcopenshell")


def minimal_ifc() -> bytes:
    """Two braced-class elements with no geometry representations."""
    model = ifcopenshell.file(schema="IFC4")
    model.create_entity("IfcPipeSegment", GlobalId=ifcopenshell.guid.new(), Name="CHW-01")
    model.create_entity("IfcDuctSegment", GlobalId=ifcopenshell.guid.new(), Name="SA-01")
    return model.to_string().encode("utf-8")


def test_the_kernel_is_inert_when_nothing_is_bound():
    """The CLI demos, the sweep and the direct tests all call it untracked."""
    from app.modules.phase_6.phase_6d_seismic import run_seismic_analysis

    run_seismic_analysis(minimal_ifc())

    assert pt.TRACKERS.for_project(1) == []


def test_the_kernel_reports_the_stages_it_owns():
    """Parsing and execution are the kernel's; the driver cannot see inside it."""
    from app.modules.phase_6.phase_6d_seismic import run_seismic_analysis

    with pt.tracking(1, run_key=SEISMIC_RUN_KEY):
        run_seismic_analysis(minimal_ifc())

    engine = pt.merged_snapshot(1)["engines"][SB_ENGINE]
    reached = [record["stage"] for record in engine["stages"]]

    assert int(Stage.IFC_PARSING) in reached
    assert int(Stage.ENGINE_EXECUTION) in reached
    assert int(Stage.RISK_SCORING) in reached
    assert engine["metrics"]["models_read"] == 1


def test_the_kernel_reports_a_config_failure_against_sb001():
    from app.modules.phase_6.phase_6d_seismic import run_seismic_analysis

    with pt.tracking(1, run_key=SEISMIC_RUN_KEY):
        result = run_seismic_analysis(minimal_ifc(), config_path="no/such/config.json")

    assert result["compliance_error"]
    assert pt.merged_snapshot(1)["engines"][SB_ENGINE]["status"] == "failed"


# ---------------------------------------------------------------------------
# The endpoint
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    from starlette.testclient import TestClient

    from app.main import app

    return TestClient(app)


def test_the_workflow_endpoint_reports_a_seismic_run(client):
    """In-process ASGI; no server is contacted."""
    with pt.tracking(8765, run_key=SEISMIC_RUN_KEY):
        pt.emit(SB_ENGINE, Stage.ENGINE_EXECUTION, elements_total=900)
        pt.increment(SB_ENGINE, elements_assessed=450)

    payload = client.get("/api/workflow/8765").json()

    assert payload["run_key"] == SEISMIC_RUN_KEY
    engine = payload["engines"][SB_ENGINE]
    assert engine["status"] == "running"
    assert engine["progress_percent"] == 50
    assert engine["metrics"]["elements_assessed"] == 450
