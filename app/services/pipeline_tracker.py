"""Live stage and metric tracking for the corrosion engine pipeline.

A run of the corrosion engines over a large IFC model takes seconds to tens of
seconds, and until now nothing outside the process could see how far it had got.
This module records that progress as it happens so
``GET /api/workflow/{project_id}`` can report it, and so the logs carry a timed
breakdown of where a slow run actually spent its time.

SIX STAGES, AND WHO OWNS EACH
    Every engine moves through the same six stages (:class:`Stage`). They are
    split between the driver and the engines because that is where the work
    genuinely happens -- nothing here pretends an engine parses IFC:

    * **1 Validation, 2 IFC Parsing** belong to the driver
      (:mod:`app.services.analysis_runner`): it holds the model bytes and calls
      the parser.
    * **3 Engine Execution, 4 Risk Scoring** belong to the engines themselves.
    * **5 Report Assembly** belongs to the driver: it turns engine results into
      Issues and statistics.
    * **6 Export** belongs to the engines' BCF and CSV writers.

INSTRUMENTATION IS AMBIENT, NOT A PARAMETER
    The engines are pure functions reached from several call sites -- the app,
    the CLI demos, the validation sweep, the test suite. Threading a tracker
    through every signature would have changed all of them and broken the tests
    that call the engines directly.

    Instead a tracker is bound to the current context (:func:`tracking`) and the
    engines call :func:`emit` / :func:`increment`, which are **no-ops when
    nothing is bound**. An untracked call path therefore behaves exactly as it
    did before this module existed, which is what makes the instrumentation safe
    to add to code with a validation history behind it.

    ``contextvars`` rather than a module global: uvicorn serves sync routes from
    a threadpool that copies the context per request, so two projects analysed
    concurrently cannot write into each other's tracker.

DECLARED STATUS FOR ENGINES THAT HAVE NOT RUN
    An engine nobody has tracked reports only its declared status --
    ``{"status": "pending"}`` -- rather than a stage-zero shape that would read
    as "started and got nowhere". See :data:`ENGINE_SPECS` for what each engine's
    declared status means and why MC-001's differs from the others.

STORAGE
    Process-local, bounded and expiring, mirroring
    :mod:`app.services.analysis_cache`: progress is derived data about a run in
    flight, worthless once the run is over, and never worth a migration. Under
    multiple uvicorn workers a poll can land on a worker that did not run the
    analysis and will see ``pending`` -- a reporting gap, never a correctness
    one, since nothing reads this back into the analysis.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections import OrderedDict
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, IntEnum
from typing import Any, Callable, Optional

from app.logging_config import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------


class Stage(IntEnum):
    """One step of the pipeline, numbered as the API reports it.

    The values are the wire format's ``current_stage``: 1-based, so
    ``progress_percent`` reaches 100 only when the last stage is done rather
    than sitting a stage short of it.
    """

    VALIDATION = 1
    IFC_PARSING = 2
    ENGINE_EXECUTION = 3
    RISK_SCORING = 4
    REPORT_ASSEMBLY = 5
    EXPORT = 6

    @property
    def label(self) -> str:
        """Human-readable stage name, reported as ``stage_name``."""
        return STAGE_NAMES[self]


#: Display name per stage. Kept beside :class:`Stage` rather than derived from
#: the member name so wording can change without renaming the enum members the
#: engines reference.
STAGE_NAMES: dict["Stage", str] = {
    Stage.VALIDATION: "Validation",
    Stage.IFC_PARSING: "IFC Parsing",
    Stage.ENGINE_EXECUTION: "Engine Execution",
    Stage.RISK_SCORING: "Risk Scoring",
    Stage.REPORT_ASSEMBLY: "Report Assembly",
    Stage.EXPORT: "Export",
}

#: How many stages a run has. Reported on every engine so a client can compute
#: progress itself rather than having to trust ``progress_percent``.
TOTAL_STAGES: int = len(Stage)


class Status(str, Enum):
    """Lifecycle state of one engine within one project's run.

    A ``str`` enum so members serialise to the exact wire strings without a
    conversion step at the boundary.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    NOT_IMPLEMENTED = "not_implemented"


# ---------------------------------------------------------------------------
# Engine registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EngineSpec:
    """One engine the workflow endpoint reports on.

    Attributes:
        code: Ruleset code, e.g. ``"GC-001"``. The key in the API payload.
        label: Human name, for logs and for clients that want more than a code.
        declared_status: What the engine reports before anything tracks it.
    """

    code: str
    label: str
    declared_status: Status


#: Every engine the endpoint reports, in payload order.
#:
#: ``declared_status`` is what an engine reports until a run touches it, and the
#: values in use here mean three different things:
#:
#: ``GC-001`` / ``CC-001``
#:     Implemented and instrumented. ``pending`` means "no run yet".
#: ``MM-001`` / ``XM-001``
#:     Path B comparators. ``FEATURE_PATH_B_MM`` / ``FEATURE_PATH_B_XM`` in
#:     :mod:`app.modules.config` gate them only in
#:     ``module4_comparator.compliance_orchestrator``, which no API route calls.
#:     On the live path they are ``NETWORK_MECHANISMS`` in
#:     ``phase_6c_corrosion_ui`` and run whenever selected -- which the analyse
#:     page now does by default. ``pending`` here means "not instrumented",
#:     exactly as it does for MC-001 below, not "not running".
#: ``MC-001``
#:     Declared ``not_implemented`` because the frontend contract for this
#:     endpoint specifies it. **Note that this repository does ship an MC-001
#:     engine** -- :mod:`app.engines.bimguard_mic_engine`, wired into
#:     ``phase_6c_corrosion_ui.MECHANISMS`` and running on every corrosion
#:     analysis. To report it as a live engine, change this one value to
#:     ``Status.PENDING`` and instrument it exactly as GC-001 is. Tracking always
#:     wins over the declared status, so a tracked MC-001 run would report
#:     ``running`` / ``complete`` regardless of this value.
ENGINE_SPECS: tuple[EngineSpec, ...] = (
    EngineSpec("GC-001", "Galvanic corrosion", Status.PENDING),
    EngineSpec("CC-001", "Crevice corrosion", Status.PENDING),
    EngineSpec("MM-001", "Material / media comparator", Status.PENDING),
    EngineSpec("XM-001", "Cross-material comparator", Status.PENDING),
    EngineSpec("MC-001", "Microbially influenced corrosion", Status.NOT_IMPLEMENTED),
)

#: Lookup by code, built once.
ENGINES: dict[str, EngineSpec] = {spec.code: spec for spec in ENGINE_SPECS}

#: Codes in payload order, for callers that iterate without touching the specs.
ENGINE_CODES: tuple[str, ...] = tuple(spec.code for spec in ENGINE_SPECS)

#: Ruleset codes for the two instrumented engines. The engines import these
#: rather than repeating the literal, so a code change cannot leave one call
#: site emitting under a name the endpoint does not know.
GC_ENGINE = "GC-001"
CC_ENGINE = "CC-001"


# ---------------------------------------------------------------------------
# Per-engine state
# ---------------------------------------------------------------------------


@dataclass
class StageRecord:
    """A stage an engine has entered, and how long it lasted.

    Attributes:
        stage: The stage number, matching :class:`Stage`.
        name: The stage's display name.
        duration_seconds: Wall time in the stage. ``None`` while it is current.
    """

    stage: int
    name: str
    duration_seconds: Optional[float] = None

    def as_dict(self) -> dict[str, Any]:
        """Render for the API payload."""
        return {
            "stage": self.stage,
            "name": self.name,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class EngineRun:
    """Live progress of one engine over one project.

    Every mutator is guarded by the owning tracker's lock, passed in at
    construction: a poll and an engine emitting a metric are genuinely
    concurrent under uvicorn, and a half-updated snapshot would report a stage
    from one moment with counters from another.
    """

    code: str
    label: str
    lock: threading.RLock
    status: Status = Status.PENDING
    current_stage: Optional[Stage] = None
    metrics: dict[str, Any] = field(default_factory=dict)
    stages: list[StageRecord] = field(default_factory=list)
    error: Optional[str] = None
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    stage_started_at: Optional[float] = None

    # -- mutation ----------------------------------------------------------

    def stage(self, stage: Stage, **metrics: Any) -> "EngineRun":
        """Enter ``stage``, closing the previous one and merging ``metrics``.

        Re-entering the stage already current is deliberately a no-op for the
        stage itself, though the metrics still merge. The engines call this once
        per element so a run whose driver never announced execution still
        reports it; without the guard the recorded stage duration would reset on
        every element and always read as near zero.

        Returns:
            ``self``, so a caller can chain a metric update onto a transition.
        """
        with self.lock:
            now = time.monotonic()
            if self.started_at is None:
                self.started_at = now
            if self.current_stage is not stage:
                self._close_stage(now)
                self.current_stage = stage
                self.stage_started_at = now
                self.stages.append(StageRecord(stage=int(stage), name=stage.label))
            if self.status is not Status.RUNNING:
                self.status = Status.RUNNING
                self.finished_at = None
                self.error = None
            self._merge(metrics)
            return self

    def record(self, **metrics: Any) -> "EngineRun":
        """Merge metric values, replacing any existing key."""
        with self.lock:
            self._merge(metrics)
            return self

    def increment(self, **counters: int) -> "EngineRun":
        """Add to counter metrics, starting them at zero when absent.

        Separate from :meth:`record` because a per-element counter cannot be
        computed by the caller without reading the tracker first, and a
        read-then-write from two threads loses increments.
        """
        with self.lock:
            for key, amount in counters.items():
                self.metrics[key] = self.metrics.get(key, 0) + amount
            return self

    def complete(self, **metrics: Any) -> "EngineRun":
        """Mark the run finished successfully and freeze its duration."""
        with self.lock:
            now = time.monotonic()
            if self.started_at is None:
                self.started_at = now
            self._close_stage(now)
            self._merge(metrics)
            self.status = Status.COMPLETE
            self.finished_at = now
            if self.current_stage is None:
                self.current_stage = Stage.EXPORT
            logger.info(
                "Pipeline engine complete engine=%s duration_seconds=%.3f metrics=%s",
                self.code,
                now - self.started_at,
                self.metrics,
            )
            return self

    def fail(self, reason: str) -> "EngineRun":
        """Mark the run failed, keeping the stage it failed in and its metrics.

        The stage survives because "failed during Engine Execution" and "failed
        during Export" are different problems, and a status alone cannot tell
        them apart.
        """
        with self.lock:
            now = time.monotonic()
            if self.started_at is None:
                self.started_at = now
            self._close_stage(now)
            self.status = Status.FAILED
            self.error = reason
            self.finished_at = now
            logger.warning("Pipeline engine failed engine=%s reason=%s", self.code, reason)
            return self

    # -- reading -----------------------------------------------------------

    def duration_seconds(self) -> float:
        """Seconds since the run started; frozen once it has finished."""
        with self.lock:
            if self.started_at is None:
                return 0.0
            end = self.finished_at if self.finished_at is not None else time.monotonic()
            return round(end - self.started_at, 3)

    def progress_percent(self) -> int:
        """Whole-percent progress through the six stages.

        A completed run reports 100 even if it never entered Export, because a
        run that finished is finished -- an engine with nothing to export would
        otherwise sit at 83% forever.
        """
        with self.lock:
            if self.status is Status.COMPLETE:
                return 100
            if self.current_stage is None:
                return 0
            return round(int(self.current_stage) * 100 / TOTAL_STAGES)

    def snapshot(self) -> dict[str, Any]:
        """Render this engine for the API payload.

        An engine nothing has tracked renders as its declared status alone --
        no stage numbers, no empty metrics -- so a client cannot mistake "not
        started" for "started and stalled at stage 0".
        """
        with self.lock:
            if self.current_stage is None and self.status is Status.PENDING:
                return {"status": ENGINES[self.code].declared_status.value}

            stage = self.current_stage or Stage.VALIDATION
            payload: dict[str, Any] = {
                "status": self.status.value,
                "engine_name": self.label,
                "current_stage": int(stage),
                "total_stages": TOTAL_STAGES,
                "stage_name": stage.label,
                "progress_percent": self.progress_percent(),
                "metrics": {
                    **self.metrics,
                    "duration_seconds": self.duration_seconds(),
                },
                "stages": [record.as_dict() for record in self.stages],
            }
            if self.error is not None:
                payload["error"] = self.error
            return payload

    # -- internals ---------------------------------------------------------

    def _merge(self, metrics: dict[str, Any]) -> None:
        """Merge non-``None`` metric values. Caller holds the lock.

        ``None`` is dropped rather than stored so a caller can pass an optional
        value straight through without first checking it, and without blanking a
        metric an earlier call established.
        """
        for key, value in metrics.items():
            if value is not None:
                self.metrics[key] = value

    def _close_stage(self, now: float) -> None:
        """Stamp the current stage's duration. Caller holds the lock."""
        if self.stages and self.stage_started_at is not None:
            self.stages[-1].duration_seconds = round(now - self.stage_started_at, 3)
        self.stage_started_at = None


# ---------------------------------------------------------------------------
# Per-project tracker
# ---------------------------------------------------------------------------


class PipelineTracker:
    """Every engine's progress for one project's analysis run.

    One lock for the whole tracker rather than one per engine: a snapshot has to
    read all five engines, and five separate locks would let a run advance
    between two of the reads and produce a payload describing no moment that
    ever existed.
    """

    def __init__(self, project_id: int):
        self.project_id = project_id
        self._lock = threading.RLock()
        self._runs: dict[str, EngineRun] = {
            spec.code: EngineRun(code=spec.code, label=spec.label, lock=self._lock)
            for spec in ENGINE_SPECS
        }
        self.created_at = time.monotonic()
        self.updated_at = self.created_at

    def run(self, code: str) -> EngineRun:
        """Return the :class:`EngineRun` for ``code``.

        Raises:
            KeyError: If ``code`` is not a registered engine. Loudly, because a
                typo'd code would otherwise create a run nothing ever reports.
        """
        with self._lock:
            self.updated_at = time.monotonic()
            try:
                return self._runs[code]
            except KeyError:
                raise KeyError(
                    f"Unknown engine {code!r}; expected one of {', '.join(ENGINE_CODES)}"
                ) from None

    def touched(self) -> bool:
        """Whether any engine on this project has reported anything yet."""
        with self._lock:
            return any(run.current_stage is not None for run in self._runs.values())

    def snapshot(self) -> dict[str, Any]:
        """Render the full payload for ``GET /api/workflow/{project_id}``."""
        with self._lock:
            return {
                "project_id": self.project_id,
                "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "engines": {code: run.snapshot() for code, run in self._runs.items()},
            }


# ---------------------------------------------------------------------------
# Process-wide store
# ---------------------------------------------------------------------------

#: Most projects tracked at once, evicting least-recently-updated. A tracker is
#: a handful of small dicts, so this bounds the store well under a megabyte.
MAX_TRACKERS: int = 32

#: How long a tracker stays readable after its last update. Long enough for a
#: client to poll to the end of a run and read the final state; short enough
#: that a finished run does not linger for the life of the process.
TTL_SECONDS: float = 900.0


class _TrackerStore:
    """A bounded, expiring, thread-safe map of project id to tracker."""

    def __init__(self, max_trackers: int = MAX_TRACKERS, ttl_seconds: float = TTL_SECONDS):
        self._trackers: OrderedDict[int, PipelineTracker] = OrderedDict()
        self._max = max_trackers
        self._ttl = ttl_seconds
        self._lock = threading.Lock()

    def get(self, project_id: int) -> Optional[PipelineTracker]:
        """Return the tracker for ``project_id``, or ``None`` if absent or expired."""
        with self._lock:
            tracker = self._trackers.get(project_id)
            if tracker is None:
                return None
            if (time.monotonic() - tracker.updated_at) > self._ttl:
                del self._trackers[project_id]
                logger.debug("Pipeline tracker expired project_id=%d", project_id)
                return None
            self._trackers.move_to_end(project_id)
            return tracker

    def get_or_create(self, project_id: int) -> PipelineTracker:
        """Return the tracker for ``project_id``, creating one if needed."""
        existing = self.get(project_id)
        if existing is not None:
            return existing
        with self._lock:
            tracker = PipelineTracker(project_id)
            self._trackers[project_id] = tracker
            self._trackers.move_to_end(project_id)
            while len(self._trackers) > self._max:
                evicted, _ = self._trackers.popitem(last=False)
                logger.debug("Pipeline tracker evicted project_id=%d", evicted)
            return tracker

    def discard(self, project_id: int) -> bool:
        """Drop one project's tracker. Returns whether one was there."""
        with self._lock:
            return self._trackers.pop(project_id, None) is not None

    def clear(self) -> None:
        """Empty the store. For tests and for a deliberate operational reset."""
        with self._lock:
            self._trackers.clear()


#: Process-wide store. Per-process by design -- see the module docstring.
TRACKERS = _TrackerStore()


def tracker_for(project_id: int) -> PipelineTracker:
    """Return (creating if needed) the tracker for ``project_id``."""
    return TRACKERS.get_or_create(project_id)


def snapshot(project_id: int) -> dict[str, Any]:
    """Return the workflow payload for ``project_id``.

    A project nothing has ever analysed is not an error: it reports every engine
    at its declared status, which is the truthful answer to "how far has this
    got" for a run that has not started. Building a throwaway tracker for that
    case keeps an unbounded stream of polls for unknown ids from filling the
    store with empty entries.
    """
    tracker = TRACKERS.get(project_id)
    if tracker is None:
        return PipelineTracker(project_id).snapshot()
    return tracker.snapshot()


# ---------------------------------------------------------------------------
# Ambient binding
# ---------------------------------------------------------------------------

#: The tracker the current context writes to, or ``None``. Holds the tracker
#: rather than a single engine run because GC-001 and CC-001 interleave -- the
#: analysis loops elements on the outside and mechanisms on the inside -- so a
#: single "current engine" would be wrong on every other call.
_ACTIVE: ContextVar[Optional[PipelineTracker]] = ContextVar(
    "bimguard_pipeline_tracker", default=None
)


def active() -> Optional[PipelineTracker]:
    """Return the tracker bound to this context, or ``None``."""
    return _ACTIVE.get()


@contextmanager
def tracking(project_id: int, *, reset: bool = True) -> Iterator[PipelineTracker]:
    """Bind a tracker for ``project_id`` for the duration of the block.

    Args:
        project_id: Project being analysed.
        reset: Start from a clean tracker. On by default: a second analysis of
            the same project is a new run, and inheriting the previous run's
            counters would report an element count that never happened.

    Yields:
        The bound :class:`PipelineTracker`.
    """
    if reset:
        TRACKERS.discard(project_id)
    tracker = tracker_for(project_id)
    token = _ACTIVE.set(tracker)
    try:
        yield tracker
    finally:
        _ACTIVE.reset(token)


def emit(code: str, stage: Optional[Stage] = None, **metrics: Any) -> None:
    """Report a stage transition and/or metrics for ``code``.

    **A no-op when no tracker is bound**, which is what lets the engines carry
    these calls without changing how they behave for the CLI demos, the
    validation sweep, or the tests that call them directly.

    Args:
        code: Ruleset code, e.g. ``"GC-001"``.
        stage: Stage being entered, or ``None`` to record metrics only.
        **metrics: Metric values to merge; ``None`` values are ignored.
    """
    tracker = _ACTIVE.get()
    if tracker is None:
        return
    run = tracker.run(code)
    if stage is not None:
        run.stage(stage, **metrics)
        emit_event(
            event_type="stage_transition",
            source_module=code,
            project_id=tracker.project_id,
            payload={
                "stage": stage.value,
                "stage_name": stage.label,
                "metrics": metrics,
            },
        )
    elif metrics:
        run.record(**metrics)
        emit_event(
            event_type="metric_increment",
            source_module=code,
            project_id=tracker.project_id,
            payload={"metrics": metrics},
        )


def increment(code: str, **counters: int) -> None:
    """Add to ``code``'s counter metrics. A no-op when nothing is bound."""
    tracker = _ACTIVE.get()
    if tracker is None:
        return
    tracker.run(code).increment(**counters)


def complete(code: str, **metrics: Any) -> None:
    """Mark ``code`` finished. A no-op when nothing is bound."""
    tracker = _ACTIVE.get()
    if tracker is None:
        return
    tracker.run(code).complete(**metrics)
    emit_event(
        event_type="engine_complete",
        source_module=code,
        project_id=tracker.project_id,
        payload={"status": "complete", "metrics": metrics},
    )


def fail(code: str, reason: str) -> None:
    """Mark ``code`` failed. A no-op when nothing is bound."""
    tracker = _ACTIVE.get()
    if tracker is None:
        return
    tracker.run(code).fail(reason)
    emit_event(
        event_type="engine_failed",
        source_module=code,
        project_id=tracker.project_id,
        payload={"status": "failed", "reason": reason},
    )


# ---------------------------------------------------------------------------
# Event-driven messaging infrastructure
# ---------------------------------------------------------------------------


@dataclass
class PipelineEvent:
    """Event payload emitted during pipeline execution."""

    event_type: str
    source_module: str
    project_id: int
    payload: dict[str, Any]
    timestamp: str = field(
        default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    )


_EVENT_SUBSCRIBERS: list[Callable[[PipelineEvent], None]] = []
_EVENT_HISTORY: list[PipelineEvent] = []


def subscribe_event(handler: Callable[[PipelineEvent], None]) -> None:
    """Register a callback for pipeline events."""
    if handler not in _EVENT_SUBSCRIBERS:
        _EVENT_SUBSCRIBERS.append(handler)


def unsubscribe_event(handler: Callable[[PipelineEvent], None]) -> None:
    """Remove a registered pipeline event callback."""
    if handler in _EVENT_SUBSCRIBERS:
        _EVENT_SUBSCRIBERS.remove(handler)


def emit_event(
    event_type: str, source_module: str, project_id: int, payload: dict[str, Any]
) -> PipelineEvent:
    """Publish an event to all active pipeline subscribers."""
    event = PipelineEvent(
        event_type=event_type,
        source_module=source_module,
        project_id=project_id,
        payload=payload,
    )
    _EVENT_HISTORY.append(event)
    for subscriber in list(_EVENT_SUBSCRIBERS):
        try:
            subscriber(event)
        except Exception as exc:
            logger.warning("Error in event subscriber %r: %s", subscriber, exc)
    return event


def get_event_history(project_id: int | None = None) -> list[PipelineEvent]:
    """Return historical pipeline events."""
    if project_id is None:
        return list(_EVENT_HISTORY)
    return [event for event in _EVENT_HISTORY if event.project_id == project_id]


class EventBroadcaster:
    """Thread-safe bridge between synchronous engine emits and async SSE queues."""

    def __init__(self) -> None:
        self._subscribers: dict[int, set[asyncio.Queue]] = {}
        self._lock = threading.Lock()

    def subscribe(self, project_id: int) -> asyncio.Queue:
        """Register an asyncio.Queue to receive events for project_id."""
        q: asyncio.Queue = asyncio.Queue()
        with self._lock:
            if project_id not in self._subscribers:
                self._subscribers[project_id] = set()
            self._subscribers[project_id].add(q)
        return q

    def unsubscribe(self, project_id: int, q: asyncio.Queue) -> None:
        """Remove a previously registered asyncio.Queue."""
        with self._lock:
            if project_id in self._subscribers:
                self._subscribers[project_id].discard(q)
                if not self._subscribers[project_id]:
                    del self._subscribers[project_id]

    def broadcast(self, event: PipelineEvent) -> None:
        """Forward an event to all subscribed queues for this project."""
        with self._lock:
            queues = list(self._subscribers.get(event.project_id, []))
        for q in queues:
            try:
                q.put_nowait(event)
            except Exception:
                pass


EVENT_BROADCASTER = EventBroadcaster()
subscribe_event(EVENT_BROADCASTER.broadcast)


def subscribe_async(project_id: int) -> asyncio.Queue:
    """Subscribe to live pipeline events for project_id using an asyncio Queue."""
    return EVENT_BROADCASTER.subscribe(project_id)


def unsubscribe_async(project_id: int, q: asyncio.Queue) -> None:
    """Unsubscribe an asyncio Queue from project_id pipeline events."""
    EVENT_BROADCASTER.unsubscribe(project_id, q)


