"""In-memory status for a background IFC model-attach job.

Attaching several (or large) IFC models to a project means, per file, an IFC
preflight parse plus a network upload to Supabase Storage. Doing that inline
inside the request handler routinely ran past the Cloudflare Tunnel's ~100s
idle timeout -- an HTTP 524 the browser reported as a failure even though the
origin kept working and finished the attach anyway. ``POST
/projects/{id}/models`` now hands that loop to a background task and returns
immediately; the frontend polls this store to learn when it is actually done.

Process-local and unpersisted, like ``pipeline_tracker`` and
``analysis_cache``: this is progress about a run in flight, worthless once
that run is over, and never worth a migration.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

#: How long a finished (or abandoned) status is kept around for a client that
#: has not polled it away yet.
_TTL_SECONDS = 30 * 60

_lock = threading.Lock()
_store: dict[int, "AttachStatus"] = {}


@dataclass
class AttachStatus:
    """Progress of one project's in-flight (or just-finished) attach job."""

    total: int
    attached: int = 0
    done: bool = False
    error: str | None = None
    updated_at: float = field(default_factory=time.time)


def start(project_id: int, total: int) -> None:
    """Record that a new attach job for ``project_id`` has begun."""
    with _lock:
        _store[project_id] = AttachStatus(total=total)
        _evict_expired()


def progress(project_id: int, attached: int) -> None:
    """Record that ``attached`` of the job's files have been stored so far."""
    with _lock:
        job = _store.get(project_id)
        if job is not None:
            job.attached = attached
            job.updated_at = time.time()


def finish(project_id: int, error: str | None = None) -> None:
    """Mark the job done, successfully or with ``error``."""
    with _lock:
        job = _store.get(project_id)
        if job is not None:
            job.done = True
            job.error = error
            job.updated_at = time.time()


def get(project_id: int) -> AttachStatus | None:
    """Return the job's current status, or ``None`` if none is on record."""
    with _lock:
        _evict_expired()
        job = _store.get(project_id)
        return AttachStatus(**vars(job)) if job is not None else None


def _evict_expired() -> None:
    now = time.time()
    expired = [pid for pid, job in _store.items() if now - job.updated_at > _TTL_SECONDS]
    for pid in expired:
        _store.pop(pid, None)
