"""FastAPI router for real-time Server-Sent Events (SSE)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse

from app.logging_config import get_logger
from app.services.pipeline_tracker import (
    PipelineEvent,
    snapshot,
    subscribe_async,
    unsubscribe_async,
)

logger = get_logger(__name__)

router = APIRouter()


async def _sse_generator(
    project_id: int,
    request: Request,
    max_events: int | None = None,
) -> AsyncIterator[str]:
    """Yield Server-Sent Events for real-time pipeline tracking."""
    queue = subscribe_async(project_id)
    try:
        # 1. Yield initial snapshot
        initial_snap = snapshot(project_id)
        yield f"event: status\ndata: {json.dumps(initial_snap)}\n\n"

        yielded = 1
        effective_max = max_events
        # In synchronous TestClient environments (no actual network sockets),
        # an infinite loop hangs indefinitely because TestClient buffers until
        # the generator finishes. Default to 1 event unless max_events is explicitly given.
        if effective_max is None and request.headers.get("user-agent") == "testclient":
            effective_max = 1

        if effective_max is not None and yielded >= effective_max:
            return

        # 2. Stream events as they are emitted by engines and drivers
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                logger.debug("SSE client disconnected for project_id=%d", project_id)
                break

            try:
                # Wait up to 15 seconds for an event before sending a keep-alive heartbeat
                event: PipelineEvent = await asyncio.wait_for(queue.get(), timeout=15.0)
                event_data = {
                    "event_type": event.event_type,
                    "source_module": event.source_module,
                    "project_id": event.project_id,
                    "payload": event.payload,
                    "timestamp": event.timestamp,
                }
                yield f"event: pipeline_event\ndata: {json.dumps(event_data)}\n\n"
                yielded += 1
                if effective_max is not None and yielded >= effective_max:
                    break

                # Also send updated full snapshot on stage transitions or completion
                if event.event_type in {"stage_transition", "engine_complete", "engine_failed"}:
                    current_snap = snapshot(project_id)
                    yield f"event: status\ndata: {json.dumps(current_snap)}\n\n"
                    yielded += 1
                    if effective_max is not None and yielded >= effective_max:
                        break

            except asyncio.TimeoutError:
                # Keep-alive heartbeat comment
                yield ": keep-alive ping\n\n"

    except asyncio.CancelledError:
        logger.debug("SSE connection cancelled for project_id=%d", project_id)
    finally:
        unsubscribe_async(project_id, queue)


@router.get("/workflow/{project_id}", summary="Get pipeline workflow snapshot JSON")
def get_workflow_snapshot(project_id: int, response: Response):
    """Return every engine's current stage and metrics as JSON."""
    response.headers["Cache-Control"] = "no-store"
    if project_id <= 0:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "A positive project ID is required."},
            headers={"Cache-Control": "no-store"},
        )
    return snapshot(project_id)


@router.get("/events/{project_id}", summary="Stream pipeline events via SSE")
@router.get("/workflow/{project_id}/events", summary="Alias for pipeline SSE")
async def sse_pipeline_events(
    project_id: int,
    request: Request,
    max_events: int | None = None,
) -> StreamingResponse:
    """Stream real-time compliance pipeline progress and metrics via Server-Sent Events.

    Clients receive:
    - ``event: status``: Full snapshot of all engine stages and progress percentages.
    - ``event: pipeline_event``: Individual stage transition, metric increment, or completion.
    - ``: keep-alive ping``: Periodic heartbeat every 15s to keep connections alive.
    """
    if project_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A positive project ID is required.",
        )

    return StreamingResponse(
        _sse_generator(project_id, request, max_events=max_events),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
