"""Tests for pipeline stage tracking and the workflow status endpoint.

Two things are load-bearing here and neither is visible in a diff:

**The instrumentation must be inert when nothing is bound.** If ``emit`` ever
stopped being a no-op outside a ``tracking`` block, callers would start
mutating a shared store — so ``test_emit_is_inert_when_untracked`` asserts the
store stays empty across a real call rather than merely asserting the call
still returns.

**A pending engine reports a bare status.** The contract distinguishes "never
started" from "started and stalled at stage 0", and the only thing enforcing
that is the early return in ``EngineRun.snapshot``. A test that just checked
``status == "pending"`` would pass either way, so the assertions here are on the
exact key set.

Generic tracker mechanics (stage arithmetic, binding, per-run keys) are tested
against two synthetic engine codes registered only for this module, rather
than any real engine, so these tests do not drift with which engines exist.

NO LIVE DATABASE for the tracker tests: they build runs by hand. The endpoint
test drives the real ASGI app, which loads settings at import the way
``tests/test_analyze_download.py`` already does, but performs no analysis.

Run: uv run pytest tests/test_pipeline_tracker.py -v
"""

from __future__ import annotations

import pytest

from app.services import pipeline_tracker as pt
from app.services.pipeline_tracker import (
    ENGINE_CODES,
    TOTAL_STAGES,
    EngineSpec,
    Stage,
    Status,
)

TEST_ENGINE_A = "TEST-A"
TEST_ENGINE_B = "TEST-B"


@pytest.fixture(autouse=True)
def _clear_trackers():
    """Each test starts from an empty store so leakage shows up as a failure."""
    pt.TRACKERS.clear()
    yield
    pt.TRACKERS.clear()


@pytest.fixture
def two_test_engines(monkeypatch: pytest.MonkeyPatch):
    """Register two synthetic engines, isolated from the real ENGINE_SPECS."""
    specs = pt.ENGINE_SPECS + (
        EngineSpec(TEST_ENGINE_A, "Test Engine A", Status.PENDING),
        EngineSpec(TEST_ENGINE_B, "Test Engine B", Status.PENDING),
    )
    monkeypatch.setattr(pt, "ENGINE_SPECS", specs)
    monkeypatch.setattr(pt, "ENGINES", {spec.code: spec for spec in specs})
    monkeypatch.setattr(pt, "ENGINE_CODES", tuple(spec.code for spec in specs))


# ---------------------------------------------------------------------------
# Declared status
# ---------------------------------------------------------------------------


def test_untouched_project_reports_every_engine_at_its_declared_status():
    payload = pt.snapshot(42)

    assert payload["project_id"] == 42
    assert payload["timestamp"].endswith("Z")
    assert tuple(payload["engines"]) == ENGINE_CODES


@pytest.mark.parametrize("code", list(ENGINE_CODES))
def test_unrun_engines_report_a_bare_pending(code: str):
    """No stage numbers on an engine that has not started -- see the module docstring."""
    assert pt.snapshot(1)["engines"][code] == {"status": "pending"}


def test_snapshot_of_an_unknown_project_does_not_fill_the_store():
    """Polling ids that were never analysed must not evict real runs."""
    for project_id in range(1, 200):
        pt.snapshot(project_id)

    assert pt.TRACKERS.get(1) is None


# ---------------------------------------------------------------------------
# Stage arithmetic
# ---------------------------------------------------------------------------


def test_stage_numbers_and_progress_match_the_published_contract(two_test_engines):
    """The two worked examples from the endpoint's documented output format."""
    with pt.tracking(1):
        pt.emit(TEST_ENGINE_A, Stage.ENGINE_EXECUTION)
        pt.emit(TEST_ENGINE_B, Stage.IFC_PARSING)

    engines = pt.snapshot(1)["engines"]

    assert engines[TEST_ENGINE_A]["current_stage"] == 3
    assert engines[TEST_ENGINE_A]["stage_name"] == "Engine Execution"
    assert engines[TEST_ENGINE_A]["progress_percent"] == 50

    assert engines[TEST_ENGINE_B]["current_stage"] == 2
    assert engines[TEST_ENGINE_B]["stage_name"] == "IFC Parsing"
    assert engines[TEST_ENGINE_B]["progress_percent"] == 33

    assert engines[TEST_ENGINE_A]["total_stages"] == TOTAL_STAGES == 6


def test_a_completed_run_reports_100_even_without_reaching_export(two_test_engines):
    """Export happens in a later request, so completion must not require stage 6."""
    with pt.tracking(1):
        pt.emit(TEST_ENGINE_A, Stage.REPORT_ASSEMBLY)
        pt.complete(TEST_ENGINE_A)

    engine = pt.snapshot(1)["engines"][TEST_ENGINE_A]
    assert engine["status"] == "complete"
    assert engine["current_stage"] == 5
    assert engine["progress_percent"] == 100


def test_counters_accumulate_and_metrics_replace(two_test_engines):
    with pt.tracking(1):
        pt.emit(TEST_ENGINE_A, Stage.ENGINE_EXECUTION, elements_total=3)
        for _ in range(3):
            pt.increment(TEST_ENGINE_A, elements_analyzed=1)
        pt.emit(TEST_ENGINE_A, elements_total=4)

    metrics = pt.snapshot(1)["engines"][TEST_ENGINE_A]["metrics"]
    assert metrics["elements_analyzed"] == 3
    assert metrics["elements_total"] == 4
    assert metrics["duration_seconds"] >= 0.0


def test_re_entering_the_current_stage_does_not_restart_its_timing(two_test_engines):
    """An engine that emits one stage repeatedly must record one stage, not N."""
    with pt.tracking(1):
        for _ in range(5):
            pt.emit(TEST_ENGINE_A, Stage.ENGINE_EXECUTION)

    stages = pt.snapshot(1)["engines"][TEST_ENGINE_A]["stages"]
    assert [s["stage"] for s in stages] == [3]


def test_a_failure_keeps_the_stage_it_failed_in(two_test_engines):
    with pt.tracking(1):
        pt.emit(TEST_ENGINE_A, Stage.ENGINE_EXECUTION, elements_total=9)
        pt.fail(TEST_ENGINE_A, "ValueError: bad input")

    engine = pt.snapshot(1)["engines"][TEST_ENGINE_A]
    assert engine["status"] == "failed"
    assert engine["error"] == "ValueError: bad input"
    assert engine["stage_name"] == "Engine Execution"
    assert engine["metrics"]["elements_total"] == 9


def test_an_unknown_engine_code_raises_rather_than_being_recorded():
    with pt.tracking(1) as tracker, pytest.raises(KeyError):
        tracker.run("ZZ-999")


# ---------------------------------------------------------------------------
# Binding
# ---------------------------------------------------------------------------


def test_a_second_run_starts_from_clean_counters(two_test_engines):
    with pt.tracking(1):
        pt.increment(TEST_ENGINE_A, elements_analyzed=10)
    with pt.tracking(1):
        pt.emit(TEST_ENGINE_A, Stage.ENGINE_EXECUTION)
        pt.increment(TEST_ENGINE_A, elements_analyzed=2)

    assert pt.snapshot(1)["engines"][TEST_ENGINE_A]["metrics"]["elements_analyzed"] == 2


def test_binding_unwinds_so_later_calls_are_untracked_again(two_test_engines):
    with pt.tracking(1):
        assert pt.active() is not None
    assert pt.active() is None

    pt.emit(TEST_ENGINE_A, Stage.EXPORT)
    assert pt.snapshot(2)["engines"][TEST_ENGINE_A] == {"status": "pending"}


# ---------------------------------------------------------------------------
# Per-run keys
# ---------------------------------------------------------------------------
#
# A second, genuinely concurrent analysis path for the same project (e.g. the
# graph engine's GRAPH-001, run alongside the architecture analysis) must not
# reset the default run's in-flight progress. These tests exercise the store
# keying that makes that true, independent of any specific engine.


def test_a_second_run_key_gets_its_own_tracker(two_test_engines):
    with pt.tracking(1):
        pt.emit(TEST_ENGINE_A, Stage.ENGINE_EXECUTION, elements_total=5)
    with pt.tracking(1, run_key="graph"):
        pt.emit(TEST_ENGINE_A, Stage.IFC_PARSING, elements_total=1)

    default_engine = pt.snapshot(1)["engines"][TEST_ENGINE_A]
    graph_engine = pt.snapshot(1, run_key="graph")["engines"][TEST_ENGINE_A]

    assert default_engine["current_stage"] == 3
    assert default_engine["metrics"]["elements_total"] == 5
    assert graph_engine["current_stage"] == 2
    assert graph_engine["metrics"]["elements_total"] == 1


def test_resetting_a_second_run_key_does_not_touch_the_default_run(two_test_engines):
    with pt.tracking(1):
        pt.emit(TEST_ENGINE_A, Stage.ENGINE_EXECUTION, elements_total=5)

    # A second concurrent path for the same project, its own run_key, reset
    # on entry (the default) -- must not discard the default run above.
    with pt.tracking(1, run_key="graph"):
        pass

    assert pt.snapshot(1)["engines"][TEST_ENGINE_A]["metrics"]["elements_total"] == 5


def test_snapshot_reports_which_run_key_it_belongs_to():
    with pt.tracking(1, run_key="graph"):
        pass

    assert pt.snapshot(1, run_key="graph")["run_key"] == "graph"
    assert pt.snapshot(1)["run_key"] == "default"


def test_discarding_one_run_key_leaves_other_run_keys_for_the_same_project(two_test_engines):
    with pt.tracking(1):
        pt.emit(TEST_ENGINE_A, Stage.ENGINE_EXECUTION)
    with pt.tracking(1, run_key="graph"):
        pt.emit(TEST_ENGINE_A, Stage.ENGINE_EXECUTION)

    assert pt.TRACKERS.discard(1, run_key="graph") is True
    assert pt.TRACKERS.get(1, run_key="graph") is None
    assert pt.TRACKERS.get(1) is not None


def test_emit_is_inert_when_untracked():
    """Instrumentation calls outside a ``tracking`` block must not mutate the store."""
    pt.emit(pt.GRAPH_ENGINE, Stage.ENGINE_EXECUTION)

    assert pt.active() is None
    assert pt.TRACKERS.get(1) is None


# ---------------------------------------------------------------------------
# The endpoint
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    from starlette.testclient import TestClient

    from app.main import app

    return TestClient(app)


def test_endpoint_returns_the_documented_shape(client):
    response = client.get("/api/workflow/1234")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"

    payload = response.json()
    assert payload["project_id"] == 1234
    assert set(payload) == {"project_id", "run_key", "timestamp", "engines"}
    assert payload["run_key"] == "default"
    assert tuple(payload["engines"]) == ENGINE_CODES


def test_endpoint_reports_a_run_recorded_by_this_process(client):
    with pt.tracking(4321, run_key="graph"):
        pt.emit(pt.GRAPH_ENGINE, Stage.ENGINE_EXECUTION, elements_total=47)
        pt.increment(pt.GRAPH_ENGINE, elements_analyzed=23)

    engine = client.get("/api/workflow/4321").json()["engines"][pt.GRAPH_ENGINE]

    assert engine["status"] == "running"
    assert engine["current_stage"] == 3
    assert engine["progress_percent"] == 50
    assert engine["metrics"]["elements_analyzed"] == 23
    assert engine["metrics"]["elements_total"] == 47


@pytest.mark.parametrize("project_id", [0, -1])
def test_endpoint_rejects_a_non_positive_project_id(client, project_id: int):
    response = client.get(f"/api/workflow/{project_id}")

    assert response.status_code == 400
    assert "error" in response.json()


# ---------------------------------------------------------------------------
# Dynamic Engine Registration & Explicit Progress Callback
# ---------------------------------------------------------------------------


def test_register_and_unregister_engine_dynamically():
    code = "CUSTOM-TEST-001"
    try:
        spec = pt.register_engine(code, label="Custom Extraction Engine", run_key="custom")
        assert spec.code == code
        assert code in pt.ENGINES
        assert code in pt.ENGINE_CODES
        assert pt.RUN_KEY_BY_ENGINE[code] == "custom"

        with pt.tracking(999, run_key="custom") as tracker:
            tracker.run(code).stage(Stage.ENGINE_EXECUTION, clauses_total=10)

        snapshot = pt.snapshot(999, run_key="custom")
        assert snapshot["engines"][code]["status"] == "running"
        assert snapshot["engines"][code]["engine_name"] == "Custom Extraction Engine"
        assert snapshot["engines"][code]["metrics"]["clauses_total"] == 10
    finally:
        pt.unregister_engine(code)

    assert code not in pt.ENGINES
    assert code not in pt.ENGINE_CODES


def test_auto_register_via_emit_and_tracker_run():
    code = "AUTO-TASK-001"
    with pt.tracking(777):
        pt.emit(code, Stage.VALIDATION, auto_register=True, items=5)
        pt.increment(code, auto_register=True, processed=2)

    snapshot = pt.snapshot(777)
    assert code in snapshot["engines"]
    assert snapshot["engines"][code]["status"] == "running"
    assert snapshot["engines"][code]["metrics"]["items"] == 5
    assert snapshot["engines"][code]["metrics"]["processed"] == 2


def test_pipeline_progress_callback_explicit_protocol():
    callback = pt.create_progress_callback(
        project_id=888,
        code="DOC-EXTRACT-001",
        label="Document Clause Extractor",
        run_key="extraction",
        total_stages=3,
    )

    callback.stage(1, name="Text Parsing", chunks=12)
    callback.set_progress(35, items_completed=4)
    callback.increment(items_completed=1)

    snap = pt.merged_snapshot(888)
    assert "DOC-EXTRACT-001" in snap["engines"]
    eng = snap["engines"]["DOC-EXTRACT-001"]
    assert eng["status"] == "running"
    assert eng["stage_name"] == "Text Parsing"
    assert eng["total_stages"] == 3
    assert eng["progress_percent"] == 35
    assert eng["metrics"]["chunks"] == 12
    assert eng["metrics"]["items_completed"] == 5

    callback.complete(final_clauses=5)
    snap_after = pt.merged_snapshot(888)
    assert snap_after["engines"]["DOC-EXTRACT-001"]["status"] == "complete"
    assert snap_after["engines"]["DOC-EXTRACT-001"]["progress_percent"] == 100
    assert snap_after["engines"]["DOC-EXTRACT-001"]["metrics"]["final_clauses"] == 5


def test_pipeline_progress_callback_callable_adapter():
    callback = pt.create_progress_callback(
        project_id=666,
        code="MODEL-ATTACH-001",
        label="IFC Model Attach",
    )

    # Use as standard callable adapter
    callback(Stage.IFC_PARSING, progress_percent=33, models_total=3)
    snap = pt.snapshot(666)
    assert snap["engines"]["MODEL-ATTACH-001"]["current_stage"] == 2
    assert snap["engines"]["MODEL-ATTACH-001"]["progress_percent"] == 33

    # Mark failed via callable
    callback(error="Network timeout parsing IFC")
    snap_failed = pt.snapshot(666)
    assert snap_failed["engines"]["MODEL-ATTACH-001"]["status"] == "failed"
    assert snap_failed["engines"]["MODEL-ATTACH-001"]["error"] == "Network timeout parsing IFC"

