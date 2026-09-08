"""In-process progress tracking for document rule-draft extraction.

Deliberately separate from `pipeline_tracker`: that tracker is a fixed
corrosion-engine registry (GC-001/CC-001/...) keyed by project_id, and
`RuleExtractionService.ingest_with_llamaindex` used to (incorrectly) bind
it under a document_id with an unregistered engine code, which crashed on
every call -- see the fix in that method. Document extraction has no
"engine" concept at all, just "how many of N clause-nodes are done", so
this is a much smaller, dedicated structure rather than another attempt to
fit that shape onto the corrosion registry.

Polled via `GET /api/documents/{id}/rules/extract-progress` while
`POST /api/documents/{id}/rules/extract-drafts` is in flight.
"""

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Literal, Optional

Status = Literal["running", "complete", "failed"]

#: Most documents tracked at once, evicting least-recently-started.
MAX_ENTRIES = 64

#: How long a finished (or abandoned) entry stays readable after its last
#: update -- long enough for a client to poll to completion, short enough
#: that it doesn't linger for the life of the process.
TTL_SECONDS = 900.0


@dataclass
class ExtractionProgress:
    """One document's extraction run: how far it has gotten, and how."""

    document_id: int
    total: int
    completed: int = 0
    status: Status = "running"
    error: Optional[str] = None
    updated_at: float = field(default_factory=time.monotonic)


class _ProgressStore:
    """A bounded, expiring, thread-safe map of document id to progress."""

    def __init__(self, max_entries: int = MAX_ENTRIES, ttl_seconds: float = TTL_SECONDS):
        self._entries: "OrderedDict[int, ExtractionProgress]" = OrderedDict()
        self._max = max_entries
        self._ttl = ttl_seconds
        self._lock = threading.Lock()

    def start(self, document_id: int, total: int) -> None:
        with self._lock:
            self._entries[document_id] = ExtractionProgress(document_id=document_id, total=total)
            self._entries.move_to_end(document_id)
            while len(self._entries) > self._max:
                self._entries.popitem(last=False)

    def increment(self, document_id: int) -> None:
        with self._lock:
            entry = self._entries.get(document_id)
            if entry is None:
                return
            entry.completed += 1
            entry.updated_at = time.monotonic()

    def complete(self, document_id: int) -> None:
        with self._lock:
            entry = self._entries.get(document_id)
            if entry is None:
                return
            entry.status = "complete"
            entry.updated_at = time.monotonic()

    def fail(self, document_id: int, error: str) -> None:
        with self._lock:
            entry = self._entries.get(document_id)
            if entry is None:
                return
            entry.status = "failed"
            entry.error = error
            entry.updated_at = time.monotonic()

    def get(self, document_id: int) -> Optional[ExtractionProgress]:
        with self._lock:
            entry = self._entries.get(document_id)
            if entry is None:
                return None
            if (time.monotonic() - entry.updated_at) > self._ttl:
                del self._entries[document_id]
                return None
            return entry

    def clear(self) -> None:
        """Empty the store. For tests."""
        with self._lock:
            self._entries.clear()


#: Process-wide store. Per-process by design, matching pipeline_tracker --
#: a document extraction is expected to be polled from the same process
#: that runs it, not shared across a multi-worker deployment.
STORE = _ProgressStore()


def start(document_id: int, total: int) -> None:
    """Begin tracking a new extraction run for `document_id`, resetting any prior one."""
    STORE.start(document_id, total)


def increment(document_id: int) -> None:
    """Record one more node finished (success or handled failure). No-op if untracked."""
    STORE.increment(document_id)


def complete(document_id: int) -> None:
    """Mark the run finished. No-op if untracked."""
    STORE.complete(document_id)


def fail(document_id: int, error: str) -> None:
    """Mark the run failed outright (not a per-node failure, which increment() covers)."""
    STORE.fail(document_id, error)


def snapshot(document_id: int) -> Optional[ExtractionProgress]:
    """Return the current progress for `document_id`, or None if never started/expired."""
    return STORE.get(document_id)
