"""Tests for the Digital Inspector's progress reporting, and for it coexisting with the analyses.

WHAT WENT WRONG, SO IT IS CLEAR WHAT THESE PIN

    ``app.digital_inspector.runner`` reported progress under the engine code
    ``"DIGITAL-INSPECTOR"`` -- a private string literal -- and nothing registered
    that code in ``pipeline_tracker.ENGINE_SPECS``. ``tracker.run`` raises
    ``KeyError`` on an unregistered code, and ``run_inspection`` binds a tracker
    itself before its first ``emit``, so every ``POST /api/projects/{id}/inspect``
    died on that line, outside the ``try`` that would have reported the failure.
    Nothing called ``run_inspection``, which is how it shipped.

    Two things had to change together, and both are pinned here:

    **The code had to be registered.** That is the crash.

    **It had to get its own run key.** The runner bound ``tracking(project_id)``
    under the default key with ``reset=True``, so an inspector question asked
    while a corrosion analysis was running would have discarded that analysis's
    in-flight stages -- the conflict per-run keys exist to prevent, and the reason
    SB-001 and GRAPH-001 each own a key. The frontend also scopes its progress
    average by run key, so an inspector run sharing "default" would have been
    averaged into the corrosion progress bar.

WHAT THE RUNNER ACTUALLY REPORTS

    It is a driver around an LLM agent, not a compliance kernel, and it reports no
    ``Stage`` transitions. It records ``query_chars`` when a question starts, then
    finishes with ``complete(tool_calls=...)`` or ``fail(...)``. The event-sequence
    tests pin exactly that, so if the runner later starts reporting stages the
    registry comment in ``pipeline_tracker`` and these tests get updated together
    instead of drifting apart.

NO LIVE DATABASE, NO SERVER, NO LLM. The agent graph is replaced by a stub that
returns canned messages; the endpoint test drives the ASGI app in-process.

Run: uv run pytest tests/test_digital_inspector_progress_tracking.py -v
"""

from __future__ import annotations

import asyncio

import pytest
from langchain_core.messages import AIMessage, ToolMessage

import app.digital_inspector.graph as inspector_graph
import app.digital_inspector.runner as inspector_runner
from app.services import pipeline_tracker as pt
from app.services.pipeline_tracker import (
    DEFAULT_RUN_KEY,
    DIGITAL_INSPECTOR_ENGINE,
    ENGINE_CODES,
    ENGINES,
    GC_ENGINE,
    GRAPH_RUN_KEY,
    INSPECTOR_RUN_KEY,
    RUN_KEY_BY_ENGINE,
    SEISMIC_RUN_KEY,
    Stage,
)


@pytest.fixture(autouse=True)
def _clean_state():
    """Each test starts from an empty store, so leakage fails loudly."""
    pt.TRACKERS.clear()
    yield
    pt.TRACKERS.clear()


# ---------------------------------------------------------------------------
# The engine is registered
# ---------------------------------------------------------------------------


def test_the_inspector_is_an_engine_the_endpoint_knows_about():
    """``tracker.run`` raises on an unregistered code, so this gates everything."""
    assert DIGITAL_INSPECTOR_ENGINE == "DIGITAL-INSPECTOR"
    assert DIGITAL_INSPECTOR_ENGINE in ENGINE_CODES
    assert ENGINES[DIGITAL_INSPECTOR_ENGINE].declared_status is pt.Status.PENDING


def test_tracker_run_accepts_the_inspector_code_and_still_rejects_a_typo():
    """The crash itself: ``run`` on this code raised ``KeyError``."""
    tracker = pt.PipelineTracker(1, INSPECTOR_RUN_KEY)

    assert tracker.run(DIGITAL_INSPECTOR_ENGINE).code == DIGITAL_INSPECTOR_ENGINE
    assert tracker.peek(DIGITAL_INSPECTOR_ENGINE).code == DIGITAL_INSPECTOR_ENGINE
    # Loud on a typo is the contract that made the original bug visible at all.
    with pytest.raises(KeyError, match="DIGITAL-INSPECTER"):
        tracker.run("DIGITAL-INSPECTER")


def test_the_runners_emit_code_is_the_registered_code():
    """The bug was these two drifting apart: a private literal against the registry."""
    assert inspector_runner._TRACKER_CODE == DIGITAL_INSPECTOR_ENGINE
    assert inspector_runner._TRACKER_CODE in ENGINES


def test_the_inspector_owns_its_own_run_key():
    """Sharing the corrosion key is what the reset conflict was about."""
    assert RUN_KEY_BY_ENGINE[DIGITAL_INSPECTOR_ENGINE] == INSPECTOR_RUN_KEY
    assert INSPECTOR_RUN_KEY not in {DEFAULT_RUN_KEY, SEISMIC_RUN_KEY, GRAPH_RUN_KEY}
    assert RUN_KEY_BY_ENGINE[GC_ENGINE] == DEFAULT_RUN_KEY


# ---------------------------------------------------------------------------
# The merged view -- the half that makes a tracked run readable
# ---------------------------------------------------------------------------


def test_an_inspector_run_is_visible_without_naming_its_run_key():
    with pt.tracking(1, run_key=INSPECTOR_RUN_KEY):
        pt.emit(DIGITAL_INSPECTOR_ENGINE, query_chars=27)
        pt.complete(DIGITAL_INSPECTOR_ENGINE, tool_calls=2)

    engine = pt.merged_snapshot(1)["engines"][DIGITAL_INSPECTOR_ENGINE]

    assert engine["status"] == "complete"
    assert engine["progress_percent"] == 100
    assert engine["run_key"] == INSPECTOR_RUN_KEY
    assert engine["metrics"]["query_chars"] == 27
    assert engine["metrics"]["tool_calls"] == 2


def test_the_engine_name_in_the_payload_is_the_registered_label():
    """What the Execution Matrix shows next to the code."""
    with pt.tracking(1, run_key=INSPECTOR_RUN_KEY):
        pt.complete(DIGITAL_INSPECTOR_ENGINE, tool_calls=0)

    engine = pt.merged_snapshot(1)["engines"][DIGITAL_INSPECTOR_ENGINE]

    assert engine["engine_name"] == ENGINES[DIGITAL_INSPECTOR_ENGINE].label == "Digital Inspector agent"


def test_the_default_key_alone_would_miss_it():
    """Reading one key is why a run under any other key once reported nothing."""
    with pt.tracking(1, run_key=INSPECTOR_RUN_KEY):
        pt.complete(DIGITAL_INSPECTOR_ENGINE, tool_calls=1)

    assert pt.snapshot(1)["engines"][DIGITAL_INSPECTOR_ENGINE] == {"status": "pending"}
    assert pt.merged_snapshot(1)["engines"][DIGITAL_INSPECTOR_ENGINE]["status"] == "complete"


def test_an_untouched_project_reports_the_inspector_as_pending():
    payload = pt.merged_snapshot(99)

    assert payload["engines"][DIGITAL_INSPECTOR_ENGINE] == {"status": "pending"}
    assert tuple(payload["engines"]) == ENGINE_CODES


def test_the_active_run_key_names_the_inspector_when_it_reports_last():
    """A finished corrosion run must not claim a later inspector run's progress."""
    with pt.tracking(1):
        pt.emit(GC_ENGINE, Stage.ENGINE_EXECUTION)
        pt.complete(GC_ENGINE)
    with pt.tracking(1, run_key=INSPECTOR_RUN_KEY):
        pt.emit(DIGITAL_INSPECTOR_ENGINE, query_chars=10)
        pt.complete(DIGITAL_INSPECTOR_ENGINE, tool_calls=0)

    assert pt.merged_snapshot(1)["run_key"] == INSPECTOR_RUN_KEY


# ---------------------------------------------------------------------------
# The two runs coexisting -- the conflict a shared default key would recreate
# ---------------------------------------------------------------------------


def test_an_inspector_run_does_not_reset_an_in_flight_corrosion_run():
    with pt.tracking(1):
        pt.emit(GC_ENGINE, Stage.ENGINE_EXECUTION, elements_total=40)
        pt.increment(GC_ENGINE, elements_analyzed=12)

        # Mid-corrosion, someone asks the Digital Inspector about the same project.
        with pt.tracking(1, run_key=INSPECTOR_RUN_KEY):
            pt.emit(DIGITAL_INSPECTOR_ENGINE, query_chars=9)
            pt.complete(DIGITAL_INSPECTOR_ENGINE, tool_calls=0)

    engines = pt.merged_snapshot(1)["engines"]

    assert engines[GC_ENGINE]["current_stage"] == 3
    assert engines[GC_ENGINE]["metrics"]["elements_total"] == 40
    assert engines[GC_ENGINE]["metrics"]["elements_analyzed"] == 12
    assert engines[DIGITAL_INSPECTOR_ENGINE]["status"] == "complete"


def test_a_corrosion_run_does_not_reset_an_in_flight_inspector_run():
    """The same property in the other direction."""
    with pt.tracking(1, run_key=INSPECTOR_RUN_KEY):
        pt.emit(DIGITAL_INSPECTOR_ENGINE, query_chars=5)

        with pt.tracking(1):
            pt.emit(GC_ENGINE, Stage.VALIDATION)

        # Back in the inspector's own context: its earlier metric must have survived.
        pt.complete(DIGITAL_INSPECTOR_ENGINE, tool_calls=1)

    engines = pt.merged_snapshot(1)["engines"]

    assert engines[DIGITAL_INSPECTOR_ENGINE]["status"] == "complete"
    assert engines[DIGITAL_INSPECTOR_ENGINE]["metrics"]["query_chars"] == 5
    assert engines[GC_ENGINE]["current_stage"] == 1


def test_a_second_inspector_run_starts_from_clean_counters():
    """``reset=True`` must still apply within the inspector's own key."""
    with pt.tracking(1, run_key=INSPECTOR_RUN_KEY):
        pt.emit(DIGITAL_INSPECTOR_ENGINE, query_chars=300)
        pt.complete(DIGITAL_INSPECTOR_ENGINE, tool_calls=3)
    with pt.tracking(1, run_key=INSPECTOR_RUN_KEY):
        pt.emit(DIGITAL_INSPECTOR_ENGINE, query_chars=5)
        pt.complete(DIGITAL_INSPECTOR_ENGINE, tool_calls=1)

    metrics = pt.merged_snapshot(1)["engines"][DIGITAL_INSPECTOR_ENGINE]["metrics"]

    assert metrics["query_chars"] == 5
    assert metrics["tool_calls"] == 1


# ---------------------------------------------------------------------------
# The driver
# ---------------------------------------------------------------------------


class StubGraph:
    """Stands in for the compiled LangGraph agent: canned messages, or an error."""

    def __init__(self, messages=None, error: Exception | None = None):
        self._messages = messages or []
        self._error = error

    async def ainvoke(self, state):
        if self._error is not None:
            raise self._error
        return {"messages": self._messages}


def install_graph(monkeypatch, graph: StubGraph) -> None:
    """Make ``run_inspection`` build ``graph`` instead of a real LLM-backed one."""
    monkeypatch.setattr(
        inspector_graph, "build_digital_inspector_graph", lambda organization_id=None: graph
    )


def one_tool_call_then_answer() -> list:
    """Return the transcript of a question that used one tool and then answered."""
    return [
        AIMessage(
            content="",
            tool_calls=[{"id": "call-1", "name": "query_ifc_model", "args": {"project_id": 7}}],
        ),
        ToolMessage(content="{'found': True}", tool_call_id="call-1"),
        AIMessage(content="Tower A is loaded."),
    ]


def inspector_events(project_id: int) -> list[str]:
    """Event types the inspector emitted for ``project_id``, in order."""
    return [
        event.event_type
        for event in pt.get_event_history(project_id)
        if event.source_module == DIGITAL_INSPECTOR_ENGINE
    ]


def test_run_inspection_no_longer_raises_and_reports_through_the_merged_view(monkeypatch):
    """The regression itself: this call used to die with ``KeyError`` on its first emit."""
    install_graph(monkeypatch, StubGraph(one_tool_call_then_answer()))
    query = "Which rules apply to this model?"

    response = asyncio.run(inspector_runner.run_inspection(5, query))

    assert response.answer == "Tower A is loaded."
    assert [call.tool_name for call in response.tool_calls] == ["query_ifc_model"]

    engine = pt.merged_snapshot(5)["engines"][DIGITAL_INSPECTOR_ENGINE]

    assert engine["status"] == "complete"
    assert engine["progress_percent"] == 100
    assert engine["run_key"] == INSPECTOR_RUN_KEY
    assert engine["engine_name"] == "Digital Inspector agent"
    assert engine["metrics"]["query_chars"] == len(query)
    assert engine["metrics"]["tool_calls"] == 1


def test_a_question_answered_without_tools_reports_zero_tool_calls(monkeypatch):
    install_graph(monkeypatch, StubGraph([AIMessage(content="Nothing to check.")]))

    asyncio.run(inspector_runner.run_inspection(5, "hi"))

    engine = pt.merged_snapshot(5)["engines"][DIGITAL_INSPECTOR_ENGINE]

    assert engine["status"] == "complete"
    assert engine["metrics"]["tool_calls"] == 0


def test_a_graph_failure_is_reported_as_failed_and_still_raised(monkeypatch):
    install_graph(monkeypatch, StubGraph(error=RuntimeError("llm unreachable")))

    with pytest.raises(RuntimeError, match="llm unreachable"):
        asyncio.run(inspector_runner.run_inspection(5, "hi"))

    engine = pt.merged_snapshot(5)["engines"][DIGITAL_INSPECTOR_ENGINE]

    assert engine["status"] == "failed"
    assert engine["error"]
    assert engine["run_key"] == INSPECTOR_RUN_KEY


def test_the_driver_does_not_reset_an_in_flight_corrosion_run(monkeypatch):
    """Through the real runner, so a regression to the default key is caught here.

    ``run_inspection`` binds its own tracker. Under the default key that bind's
    ``reset=True`` discards the corrosion tracker for the project, and GC-001
    would read as ``pending`` again.
    """
    install_graph(monkeypatch, StubGraph(one_tool_call_then_answer()))

    with pt.tracking(5):
        pt.emit(GC_ENGINE, Stage.ENGINE_EXECUTION, elements_total=40)

        asyncio.run(inspector_runner.run_inspection(5, "what is running?"))

    engines = pt.merged_snapshot(5)["engines"]

    assert engines[GC_ENGINE]["status"] == "running"
    assert engines[GC_ENGINE]["current_stage"] == 3
    assert engines[GC_ENGINE]["metrics"]["elements_total"] == 40
    assert engines[DIGITAL_INSPECTOR_ENGINE]["status"] == "complete"


def test_what_the_runner_emits_is_a_start_metric_then_completion_and_no_stages(monkeypatch):
    """The real emit sequence, so the registry's description of it stays honest."""
    install_graph(monkeypatch, StubGraph(one_tool_call_then_answer()))

    asyncio.run(inspector_runner.run_inspection(6001, "hello"))

    assert inspector_events(6001) == ["metric_increment", "engine_complete"]


def test_a_failed_run_emits_a_start_metric_then_failure(monkeypatch):
    install_graph(monkeypatch, StubGraph(error=RuntimeError("boom")))

    with pytest.raises(RuntimeError):
        asyncio.run(inspector_runner.run_inspection(6002, "hello"))

    assert inspector_events(6002) == ["metric_increment", "engine_failed"]


# ---------------------------------------------------------------------------
# The endpoint
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    from starlette.testclient import TestClient

    from app.main import app

    return TestClient(app)


def test_the_workflow_endpoint_reports_an_inspector_run(client):
    """In-process ASGI; no server is contacted."""
    with pt.tracking(8766, run_key=INSPECTOR_RUN_KEY):
        pt.emit(DIGITAL_INSPECTOR_ENGINE, query_chars=11)
        pt.complete(DIGITAL_INSPECTOR_ENGINE, tool_calls=2)

    payload = client.get("/api/workflow/8766").json()

    assert payload["run_key"] == INSPECTOR_RUN_KEY
    engine = payload["engines"][DIGITAL_INSPECTOR_ENGINE]
    assert engine["status"] == "complete"
    assert engine["engine_name"] == "Digital Inspector agent"
    assert engine["metrics"]["tool_calls"] == 2
