"""Tests for the overall ``status`` a workflow payload reports.

WHAT WENT WRONG

    The frontend's global pipeline tracker (``activePipelines.svelte.ts``)
    toasts and stops following a run when a status frame's top-level
    ``status`` reads ``"complete"`` or ``"failed"``. No payload ever carried
    either: ``GET /api/status/{id}`` answered only ``"running"`` / ``"idle"``,
    and SSE ``status`` frames had no top-level ``status`` at all -- so a
    finished run was never recognised as finished.

    These tests drive the real drivers (``analysis_runner``, with model loading
    and the kernels stubbed) while an SSE stream is subscribed, and assert what
    the stream and the polled routes actually send -- the boundary the frontend
    consumes.

NO LIVE DATABASE and NO SERVER; the endpoints are driven in-process.

Run: uv run pytest tests/test_workflow_status.py -v
"""

from __future__ import annotations

import asyncio
import json

import pytest

import app.services.analysis_runner as runner
from app.api.events import _sse_generator
from app.services import pipeline_tracker as pt
from app.services.analysis_cache import ANALYSIS_CACHE
from app.services.pipeline_tracker import (
    CC_ENGINE,
    GC_ENGINE,
    GRAPH_ENGINE,
    GRAPH_RUN_KEY,
    SB_ENGINE,
    SEISMIC_RUN_KEY,
    Stage,
)
from app.services.workflow_status import overall_status, status_snapshot


@pytest.fixture(autouse=True)
def _clean_state():
    """Each test starts from an empty store and cache, so leakage fails loudly."""
    pt.TRACKERS.clear()
    ANALYSIS_CACHE.clear()
    yield
    pt.TRACKERS.clear()
    ANALYSIS_CACHE.clear()


def empty_result() -> dict:
    """Build an AnalysisResult with no error."""
    return {
        "audit_issues": [],
        "issue_stats": {},
        "cost_impact": None,
        "compliance_error": None,
        "compliance_is_demo": False,
    }


@pytest.fixture
def stub_drivers(monkeypatch):
    """Serve model bytes and kernel results without storage or IFC parsing."""
    monkeypatch.setattr(runner, "model_bytes", lambda project_id: (b"IFC", None))
    monkeypatch.setattr(
        runner, "model_bytes_all", lambda project_id: ([("primary.ifc", b"IFC")], None)
    )
    monkeypatch.setattr(
        runner,
        "parse_ifc_bytes",
        lambda content, source_ref="", with_piping=False: {
            "quality": {"valid": True},
            "elements": [object(), object()],
        },
    )
    monkeypatch.setattr(runner, "run_corrosion_analysis", lambda parsed, **kw: empty_result())
    monkeypatch.setattr(runner, "run_seismic_analysis", lambda content, **kw: empty_result())


class _ConnectedRequest:
    """The two things ``_sse_generator`` asks of a request: a live client, not a TestClient."""

    headers: dict[str, str] = {}

    async def is_disconnected(self) -> bool:
        return False


#: The event types after which ``_sse_generator`` sends a fresh ``status`` frame.
FRAME_EVENTS = {"stage_transition", "engine_complete", "engine_failed"}


def run_with_stream(project_id: int, drive) -> tuple[list[str], list[dict]]:
    """Run ``drive()`` with an SSE stream subscribed; return live and streamed statuses.

    Returns two things, because the driver is synchronous and runs on the test's
    own thread:

    * **live** -- the overall status at the moment of every event after which
      the SSE generator sends a ``status`` frame. Taken from an event
      subscriber, since a synchronous driver finishes before the generator can
      interleave; this is the sequence a client sees when the run executes on
      a worker thread, as it does under uvicorn.
    * **streamed** -- the ``status`` frames the real ``_sse_generator`` yields:
      the initial one (subscribed before the run) and the frames it sends while
      draining the run's events, read until the first terminal frame. Fails
      the test if none arrives -- which is precisely the bug these tests pin.
    """
    live: list[str] = []

    def record(event: pt.PipelineEvent) -> None:
        if event.project_id == project_id and event.event_type in FRAME_EVENTS:
            live.append(status_snapshot(project_id)["status"])

    async def collect() -> list[dict]:
        gen = _sse_generator(project_id, _ConnectedRequest())
        frames: list[dict] = []
        try:
            frames.append(_parse_status(await gen.__anext__()))
            pt.subscribe_event(record)
            try:
                drive()
            finally:
                pt.unsubscribe_event(record)
            while True:
                chunk = await asyncio.wait_for(gen.__anext__(), timeout=5.0)
                if not chunk.startswith("event: status"):
                    continue
                frames.append(_parse_status(chunk))
                if frames[-1]["status"] in {"complete", "failed"}:
                    return frames
        finally:
            await gen.aclose()

    return live, asyncio.run(collect())


def _parse_status(chunk: str) -> dict:
    assert chunk.startswith("event: status\n"), chunk
    return json.loads(chunk.split("data: ", 1)[1])


# ---------------------------------------------------------------------------
# End to end: a run driven to completion through the SSE stream
# ---------------------------------------------------------------------------


def test_a_corrosion_run_reports_running_then_complete(stub_drivers):
    live, frames = run_with_stream(11, lambda: runner.run_analysis("corrosion", 11))

    # Subscribed before anything was tracked.
    assert frames[0]["status"] == "idle"
    # Running for every transition until the last engine finishes. GC-001
    # completes first while CC-001 is still assembling its report, so that
    # frame must still read running -- complete means *every* engine is done.
    assert live[-1] == "complete"
    assert set(live[:-1]) == {"running"}
    # And the stream itself carries the terminal status the frontend waits for.
    assert frames[-1]["status"] == "complete"
    engines = frames[-1]["engines"]
    assert engines[GC_ENGINE]["status"] == engines[CC_ENGINE]["status"] == "complete"


def test_a_seismic_run_reports_running_then_complete(stub_drivers):
    live, frames = run_with_stream(12, lambda: runner.run_analysis("seismic", 12))

    assert live[-1] == "complete"
    assert set(live[:-1]) == {"running"}
    assert frames[-1]["status"] == "complete"
    assert frames[-1]["run_key"] == SEISMIC_RUN_KEY


def test_a_failed_run_reports_failed(stub_drivers, monkeypatch):
    monkeypatch.setattr(
        runner,
        "run_seismic_analysis",
        lambda content, **kw: {**empty_result(), "compliance_error": "no models"},
    )

    live, frames = run_with_stream(13, lambda: runner.run_analysis("seismic", 13))

    assert live[-1] == "failed"
    assert frames[-1]["status"] == "failed"


def test_the_polled_status_route_agrees_with_the_stream(stub_drivers):
    from starlette.testclient import TestClient

    from app.main import app

    runner.run_analysis("corrosion", 14)

    assert TestClient(app).get("/api/analyze/status/14").json()["status"] == "complete"


# ---------------------------------------------------------------------------
# The derivation
# ---------------------------------------------------------------------------


def test_an_untracked_project_is_idle():
    assert status_snapshot(20)["status"] == "idle"


def test_uninstrumented_engines_do_not_hold_a_finished_run_open():
    """MM-001 / XM-001 / MC-001 are never tracked; they must not block ``complete``."""
    with pt.tracking(21):
        for code in (GC_ENGINE, CC_ENGINE):
            pt.emit(code, Stage.ENGINE_EXECUTION)
            pt.complete(code)

    snap = status_snapshot(21)
    assert snap["engines"]["MM-001"]["status"] == "pending"
    assert snap["status"] == "complete"


def test_a_run_with_one_engine_still_working_is_running():
    with pt.tracking(22):
        pt.emit(GC_ENGINE, Stage.ENGINE_EXECUTION)
        pt.emit(CC_ENGINE, Stage.ENGINE_EXECUTION)
        pt.complete(GC_ENGINE)

    assert status_snapshot(22)["status"] == "running"


def test_a_later_run_still_working_keeps_the_project_running():
    """A graph pass after corrosion finishes must not read as the project being done."""
    with pt.tracking(23):
        pt.emit(GC_ENGINE, Stage.ENGINE_EXECUTION)
        pt.complete(GC_ENGINE)
    with pt.tracking(23, run_key=GRAPH_RUN_KEY):
        pt.emit(GRAPH_ENGINE, Stage.ENGINE_EXECUTION)

    assert status_snapshot(23)["status"] == "running"


def test_a_stale_failure_in_another_run_does_not_fail_the_active_one():
    with pt.tracking(24):
        pt.emit(GC_ENGINE, Stage.ENGINE_EXECUTION)
        pt.fail(GC_ENGINE, "old corrosion failure")
    with pt.tracking(24, run_key=SEISMIC_RUN_KEY):
        pt.emit(SB_ENGINE, Stage.VALIDATION)
        pt.complete(SB_ENGINE)

    snap = status_snapshot(24)
    assert snap["run_key"] == SEISMIC_RUN_KEY
    assert snap["status"] == "complete"


def test_any_failure_in_the_active_run_fails_it():
    snap = {
        "run_key": "default",
        "engines": {
            GC_ENGINE: {"status": "complete", "run_key": "default"},
            CC_ENGINE: {"status": "failed", "run_key": "default"},
        },
    }
    assert overall_status(snap) == "failed"
