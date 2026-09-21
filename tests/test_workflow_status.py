"""Tests for the overall ``status`` a workflow payload reports.

WHAT WENT WRONG

    The frontend's global pipeline tracker (``activePipelines.svelte.ts``)
    toasts and stops following a run when a status frame's top-level
    ``status`` reads ``"complete"`` or ``"failed"``. No payload ever carried
    either: ``GET /api/status/{id}`` answered only ``"running"`` / ``"idle"``,
    and SSE ``status`` frames had no top-level ``status`` at all -- so a
    finished run was never recognised as finished.

    These tests drive the pipeline tracker directly against two synthetic
    engine codes (so they do not drift with which real engines exist) while
    an SSE stream is subscribed, and assert what the stream and the polled
    routes actually send -- the boundary the frontend consumes.

NO LIVE DATABASE and NO SERVER; the endpoints are driven in-process.

Run: uv run pytest tests/test_workflow_status.py -v
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.api.events import _sse_generator
from app.services import pipeline_tracker as pt
from app.services.analysis_cache import ANALYSIS_CACHE
from app.services.pipeline_tracker import GRAPH_ENGINE, GRAPH_RUN_KEY, EngineSpec, Stage, Status
from app.services.workflow_status import overall_status, status_snapshot

TEST_ENGINE_A = "TEST-A"
TEST_ENGINE_B = "TEST-B"


@pytest.fixture(autouse=True)
def _clean_state():
    """Each test starts from an empty store and cache, so leakage fails loudly."""
    pt.TRACKERS.clear()
    ANALYSIS_CACHE.clear()
    yield
    pt.TRACKERS.clear()
    ANALYSIS_CACHE.clear()


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
      the SSE generator sends a ``status`` frame.
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


def test_a_run_reports_running_then_complete(two_test_engines):
    def drive():
        with pt.tracking(11):
            pt.emit(TEST_ENGINE_B, Stage.ENGINE_EXECUTION)
            pt.emit(TEST_ENGINE_A, Stage.ENGINE_EXECUTION)
            pt.complete(TEST_ENGINE_A)
            pt.complete(TEST_ENGINE_B)

    live, frames = run_with_stream(11, drive)

    # Subscribed before anything was tracked.
    assert frames[0]["status"] == "idle"
    # Running for every transition until the last engine finishes: TEST-A
    # completes first while TEST-B is still executing, so that frame must
    # still read running -- complete means *every* engine is done.
    assert live[-1] == "complete"
    assert set(live[:-1]) == {"running"}
    # And the stream itself carries the terminal status the frontend waits for.
    assert frames[-1]["status"] == "complete"
    engines = frames[-1]["engines"]
    assert engines[TEST_ENGINE_A]["status"] == engines[TEST_ENGINE_B]["status"] == "complete"


def test_a_failed_run_reports_failed(two_test_engines):
    def drive():
        with pt.tracking(13):
            pt.emit(TEST_ENGINE_A, Stage.ENGINE_EXECUTION)
            pt.fail(TEST_ENGINE_A, "no models")

    live, frames = run_with_stream(13, drive)

    assert live[-1] == "failed"
    assert frames[-1]["status"] == "failed"


def test_the_polled_status_route_agrees_with_the_stream(two_test_engines):
    from starlette.testclient import TestClient

    from app.main import app

    with pt.tracking(14):
        pt.emit(TEST_ENGINE_A, Stage.ENGINE_EXECUTION)
        pt.complete(TEST_ENGINE_A)
        pt.emit(TEST_ENGINE_B, Stage.ENGINE_EXECUTION)
        pt.complete(TEST_ENGINE_B)

    assert TestClient(app).get("/api/analyze/status/14").json()["status"] == "complete"


# ---------------------------------------------------------------------------
# The derivation
# ---------------------------------------------------------------------------


def test_an_untracked_project_is_idle():
    assert status_snapshot(20)["status"] == "idle"


def test_uninstrumented_engines_do_not_hold_a_finished_run_open(two_test_engines):
    """An engine that is registered but never touched must not block ``complete``."""
    with pt.tracking(21):
        pt.emit(TEST_ENGINE_A, Stage.ENGINE_EXECUTION)
        pt.complete(TEST_ENGINE_A)

    snap = status_snapshot(21)
    assert snap["engines"][TEST_ENGINE_B]["status"] == "pending"
    assert snap["status"] == "complete"


def test_a_run_with_one_engine_still_working_is_running(two_test_engines):
    with pt.tracking(22):
        pt.emit(TEST_ENGINE_A, Stage.ENGINE_EXECUTION)
        pt.emit(TEST_ENGINE_B, Stage.ENGINE_EXECUTION)
        pt.complete(TEST_ENGINE_A)

    assert status_snapshot(22)["status"] == "running"


def test_a_later_run_still_working_keeps_the_project_running(two_test_engines):
    """A graph pass after the default run finishes must not read as the project being done."""
    with pt.tracking(23):
        pt.emit(TEST_ENGINE_A, Stage.ENGINE_EXECUTION)
        pt.complete(TEST_ENGINE_A)
    with pt.tracking(23, run_key=GRAPH_RUN_KEY):
        pt.emit(GRAPH_ENGINE, Stage.ENGINE_EXECUTION)

    assert status_snapshot(23)["status"] == "running"


def test_a_stale_failure_in_another_run_does_not_fail_the_active_one(two_test_engines):
    with pt.tracking(24):
        pt.emit(TEST_ENGINE_A, Stage.ENGINE_EXECUTION)
        pt.fail(TEST_ENGINE_A, "old failure")
    with pt.tracking(24, run_key=GRAPH_RUN_KEY):
        pt.emit(GRAPH_ENGINE, Stage.VALIDATION)
        pt.complete(GRAPH_ENGINE)

    snap = status_snapshot(24)
    assert snap["run_key"] == GRAPH_RUN_KEY
    assert snap["status"] == "complete"


def test_any_failure_in_the_active_run_fails_it():
    snap = {
        "run_key": "default",
        "engines": {
            TEST_ENGINE_A: {"status": "complete", "run_key": "default"},
            TEST_ENGINE_B: {"status": "failed", "run_key": "default"},
        },
    }
    assert overall_status(snap) == "failed"
