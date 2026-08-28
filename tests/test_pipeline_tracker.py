"""Tests for pipeline stage tracking and the workflow status endpoint.

Two things are load-bearing here and neither is visible in a diff:

**The instrumentation must be inert when nothing is bound.** The engines are
called by the CLI demos, the validation sweep and a dozen tests that predate
this feature. If ``emit`` ever stopped being a no-op outside a ``tracking``
block, those callers would start mutating a shared store — so
``test_engines_are_inert_when_untracked`` asserts the store stays empty across a
real engine call rather than merely asserting the call still returns.

**A pending engine reports a bare status.** The contract distinguishes "never
started" from "started and stalled at stage 0", and the only thing enforcing
that is the early return in ``EngineRun.snapshot``. A test that just checked
``status == "pending"`` would pass either way, so the assertions here are on the
exact key set.

NO LIVE DATABASE for the tracker tests: they build runs by hand. The endpoint
test drives the real ASGI app, which loads settings at import the way
``tests/test_analyze_download.py`` already does, but performs no analysis.

Run: uv run pytest tests/test_pipeline_tracker.py -v
"""

from __future__ import annotations

import pytest

from app.services import pipeline_tracker as pt
from app.services.pipeline_tracker import (
    CC_ENGINE,
    ENGINE_CODES,
    GC_ENGINE,
    TOTAL_STAGES,
    Stage,
    Status,
)


@pytest.fixture(autouse=True)
def _clear_trackers():
    """Each test starts from an empty store so leakage shows up as a failure."""
    pt.TRACKERS.clear()
    yield
    pt.TRACKERS.clear()


# ---------------------------------------------------------------------------
# Declared status
# ---------------------------------------------------------------------------


def test_untouched_project_reports_every_engine_at_its_declared_status():
    payload = pt.snapshot(42)

    assert payload["project_id"] == 42
    assert payload["timestamp"].endswith("Z")
    assert tuple(payload["engines"]) == ENGINE_CODES


@pytest.mark.parametrize("code", ["GC-001", "CC-001", "MM-001", "XM-001"])
def test_unrun_engines_report_a_bare_pending(code: str):
    """No stage numbers on an engine that has not started -- see the module docstring."""
    assert pt.snapshot(1)["engines"][code] == {"status": "pending"}


def test_mc001_reports_the_declared_not_implemented_status():
    """The frontend contract declares MC-001 not_implemented.

    Note that an MC-001 engine does exist in this repository; the declared
    status is a contract decision recorded in ``ENGINE_SPECS``, not a claim
    about the codebase. If that decision changes, this assertion is the thing
    that should fail first.
    """
    assert pt.snapshot(1)["engines"]["MC-001"] == {"status": "not_implemented"}


def test_snapshot_of_an_unknown_project_does_not_fill_the_store():
    """Polling ids that were never analysed must not evict real runs."""
    for project_id in range(1, 200):
        pt.snapshot(project_id)

    assert pt.TRACKERS.get(1) is None


# ---------------------------------------------------------------------------
# Stage arithmetic
# ---------------------------------------------------------------------------


def test_stage_numbers_and_progress_match_the_published_contract():
    """The two worked examples from the endpoint's documented output format."""
    with pt.tracking(1):
        pt.emit(GC_ENGINE, Stage.ENGINE_EXECUTION)
        pt.emit(CC_ENGINE, Stage.IFC_PARSING)

    engines = pt.snapshot(1)["engines"]

    assert engines[GC_ENGINE]["current_stage"] == 3
    assert engines[GC_ENGINE]["stage_name"] == "Engine Execution"
    assert engines[GC_ENGINE]["progress_percent"] == 50

    assert engines[CC_ENGINE]["current_stage"] == 2
    assert engines[CC_ENGINE]["stage_name"] == "IFC Parsing"
    assert engines[CC_ENGINE]["progress_percent"] == 33

    assert engines[GC_ENGINE]["total_stages"] == TOTAL_STAGES == 6


def test_a_completed_run_reports_100_even_without_reaching_export():
    """Export happens in a later request, so completion must not require stage 6."""
    with pt.tracking(1):
        pt.emit(GC_ENGINE, Stage.REPORT_ASSEMBLY)
        pt.complete(GC_ENGINE)

    engine = pt.snapshot(1)["engines"][GC_ENGINE]
    assert engine["status"] == "complete"
    assert engine["current_stage"] == 5
    assert engine["progress_percent"] == 100


def test_counters_accumulate_and_metrics_replace():
    with pt.tracking(1):
        pt.emit(GC_ENGINE, Stage.ENGINE_EXECUTION, elements_total=3)
        for _ in range(3):
            pt.increment(GC_ENGINE, elements_analyzed=1)
        pt.emit(GC_ENGINE, elements_total=4)

    metrics = pt.snapshot(1)["engines"][GC_ENGINE]["metrics"]
    assert metrics["elements_analyzed"] == 3
    assert metrics["elements_total"] == 4
    assert metrics["duration_seconds"] >= 0.0


def test_re_entering_the_current_stage_does_not_restart_its_timing():
    """The engines emit stage 3 per element; that must record one stage, not N."""
    with pt.tracking(1):
        for _ in range(5):
            pt.emit(GC_ENGINE, Stage.ENGINE_EXECUTION)

    stages = pt.snapshot(1)["engines"][GC_ENGINE]["stages"]
    assert [s["stage"] for s in stages] == [3]


def test_a_failure_keeps_the_stage_it_failed_in():
    with pt.tracking(1):
        pt.emit(GC_ENGINE, Stage.ENGINE_EXECUTION, elements_total=9)
        pt.fail(GC_ENGINE, "ValueError: bad material")

    engine = pt.snapshot(1)["engines"][GC_ENGINE]
    assert engine["status"] == "failed"
    assert engine["error"] == "ValueError: bad material"
    assert engine["stage_name"] == "Engine Execution"
    assert engine["metrics"]["elements_total"] == 9


def test_an_unknown_engine_code_raises_rather_than_being_recorded():
    with pt.tracking(1) as tracker, pytest.raises(KeyError):
        tracker.run("ZZ-999")


# ---------------------------------------------------------------------------
# Binding
# ---------------------------------------------------------------------------


def test_a_second_run_starts_from_clean_counters():
    with pt.tracking(1):
        pt.increment(GC_ENGINE, elements_analyzed=10)
    with pt.tracking(1):
        pt.emit(GC_ENGINE, Stage.ENGINE_EXECUTION)
        pt.increment(GC_ENGINE, elements_analyzed=2)

    assert pt.snapshot(1)["engines"][GC_ENGINE]["metrics"]["elements_analyzed"] == 2


def test_binding_unwinds_so_later_calls_are_untracked_again():
    with pt.tracking(1):
        assert pt.active() is not None
    assert pt.active() is None

    pt.emit(GC_ENGINE, Stage.EXPORT)
    assert pt.snapshot(2)["engines"][GC_ENGINE] == {"status": "pending"}


# ---------------------------------------------------------------------------
# The engines themselves
# ---------------------------------------------------------------------------


def gc_element():
    """A carbon-steel-to-copper pair, chosen only because it assesses cleanly."""
    from app.engines.bimguard_corrosion_engine import GCElement

    return GCElement(
        global_id_anode="GUID-A",
        global_id_cathode="GUID-B",
        material_anode="carbon steel",
        material_cathode="copper",
        anode_area_m2=0.5,
        cathode_area_m2=2.0,
        zone_category="plant room",
    )


def cc_element():
    """A single flanged stainless element."""
    from app.engines.bimguard_crevice_engine import CCElement

    return CCElement(
        global_id="GUID-C",
        element_type="IfcPipeSegment",
        material="stainless steel 316",
        joint_description="flanged joint with gasket",
        operating_temp_c=45.0,
        zone_category="plant room",
    )


def test_engines_are_inert_when_untracked():
    """The property the pre-existing engine callers depend on.

    Asserts the store stays empty, not merely that the call returns: a leak
    would still return a result while quietly writing into shared state.
    """
    from app.engines.bimguard_corrosion_engine import assess_galvanic_batch
    from app.engines.bimguard_crevice_engine import assess_crevice_batch

    assert assess_galvanic_batch([gc_element()])
    assert assess_crevice_batch([cc_element()])

    assert pt.active() is None
    assert pt.TRACKERS.get(1) is None


def test_the_batch_entry_points_report_totals_and_close_scoring():
    from app.engines.bimguard_corrosion_engine import assess_galvanic_batch
    from app.engines.bimguard_crevice_engine import assess_crevice_batch

    with pt.tracking(1):
        assess_galvanic_batch([gc_element(), gc_element()])
        assess_crevice_batch([cc_element()])

    engines = pt.snapshot(1)["engines"]

    gc = engines[GC_ENGINE]
    assert gc["status"] == Status.RUNNING.value
    assert gc["stage_name"] == "Risk Scoring"
    assert gc["metrics"]["elements_total"] == 2
    assert gc["metrics"]["elements_analyzed"] == 2

    cc = engines[CC_ENGINE]
    assert cc["metrics"]["elements_total"] == 1
    assert cc["metrics"]["elements_analyzed"] == 1

    # Every element lands in exactly one band bucket.
    assert sum(v for k, v in gc["metrics"].items() if k.startswith("band_")) == 2


def test_a_single_element_call_still_reports_execution():
    """The Phase 6 pipeline loops the per-element functions, not the batches."""
    from app.engines.bimguard_corrosion_engine import assess_galvanic_risk

    with pt.tracking(1):
        assess_galvanic_risk(gc_element())

    gc = pt.snapshot(1)["engines"][GC_ENGINE]
    assert gc["current_stage"] == int(Stage.ENGINE_EXECUTION)
    assert gc["metrics"]["elements_analyzed"] == 1


def test_the_export_writers_report_stage_six(tmp_path):
    from app.engines.bimguard_corrosion_engine import (
        assess_galvanic_batch,
        export_gc_asset_register,
    )

    with pt.tracking(1):
        results = assess_galvanic_batch([gc_element()])
        export_gc_asset_register(results, str(tmp_path / "register.csv"))

    gc = pt.snapshot(1)["engines"][GC_ENGINE]
    assert gc["current_stage"] == int(Stage.EXPORT)
    assert gc["stage_name"] == "Export"
    assert gc["metrics"]["csv_rows"] == 1


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
    assert set(payload) == {"project_id", "timestamp", "engines"}
    assert tuple(payload["engines"]) == ENGINE_CODES


def test_endpoint_reports_a_run_recorded_by_this_process(client):
    with pt.tracking(4321):
        pt.emit(GC_ENGINE, Stage.ENGINE_EXECUTION, elements_total=47)
        pt.increment(GC_ENGINE, elements_analyzed=23)

    engine = client.get("/api/workflow/4321").json()["engines"][GC_ENGINE]

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
