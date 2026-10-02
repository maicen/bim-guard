"""Events emitted from worker threads reach SSE subscribers promptly."""

from __future__ import annotations

import asyncio
import threading

from app.services.pipeline_tracker import EventBroadcaster, PipelineEvent


def test_broadcast_from_a_worker_thread_wakes_the_subscriber():
    broadcaster = EventBroadcaster()

    async def scenario() -> PipelineEvent:
        q = broadcaster.subscribe(7)
        event = PipelineEvent(event_type="t", source_module="m", project_id=7, payload={})
        threading.Thread(target=broadcaster.broadcast, args=(event,)).start()
        return await asyncio.wait_for(q.get(), timeout=1.0)

    received = asyncio.run(scenario())
    assert received.project_id == 7


def test_unsubscribed_queue_receives_nothing():
    broadcaster = EventBroadcaster()

    async def scenario() -> bool:
        q = broadcaster.subscribe(7)
        broadcaster.unsubscribe(7, q)
        broadcaster.broadcast(PipelineEvent(event_type="t", source_module="m", project_id=7, payload={}))
        await asyncio.sleep(0)
        return q.empty()

    assert asyncio.run(scenario())
