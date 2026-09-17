"""Managed ProcessPoolExecutor for CPU-parallel compliance and analysis workflows.

Provides a shared, process-lifecycle-aware ProcessPoolExecutor to bypass the
Python GIL for compute-heavy IFC parsing, corrosion evaluations, and 3D clash
detections without spawning ad-hoc processes per request.

SELF-HEALING

    A ``ProcessPoolExecutor`` whose worker dies abruptly (a native crash, an
    out-of-memory kill, ``os._exit``) is permanently broken: every later
    ``submit`` raises ``BrokenProcessPool``. Holding that executor in a
    module-level global for the life of the backend turned one bad run into
    every later run falling back to sequential until restart. The pool is
    checked before it is handed out, and a broken one is shut down and replaced.

    Rebuilding is not free -- it spawns ``get_worker_count()`` interpreters --
    and a data-dependent crash breaks the fresh pool too. After
    :data:`MAX_CONSECUTIVE_BREAKS` breaks with no successful batch between them,
    parallel execution is suspended for :data:`BREAK_COOLDOWN_SECONDS`, so a
    repeatedly-crashing workload runs sequentially instead of respawning a full
    pool on every request.

    A pool that broke must never be shut down with ``wait=True``. On Windows,
    CPython 3.12 terminates the workers and then joins the call queue's feeder
    thread, which can stay blocked forever writing a large pickled chunk into
    the dead pipe; ``wait=True`` joins that same thread and hangs the caller.

WORKER MEMORY

    Each worker imports numpy and scipy, and OpenBLAS commits a buffer per
    thread it expects to use -- one per logical CPU. On a 32-thread machine
    that was ~1.7 GB of committed memory per worker (~154 MB with one BLAS
    thread), so a 31-worker pool asked Windows for ~53 GB of commit charge and
    workers died with ``WinError 1455`` (paging file too small) once a few
    backends were running. The chunks are pure-Python loops that gain nothing
    from BLAS threads, so worker processes are started with one.
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
from concurrent.futures import Future, ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from typing import Any, Callable, Iterable, TypeVar

from app.logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

MAX_CONSECUTIVE_BREAKS = 3
"""Pool breaks, with no successful batch between them, before parallel mode is suspended."""

BREAK_COOLDOWN_SECONDS = 600.0
"""How long parallel mode stays suspended once the break limit is reached."""

_POOL: ProcessPoolExecutor | None = None
_LOCK = threading.Lock()
_consecutive_breaks = 0
_suspended_until = 0.0

# Marker set on an executor once its break has been counted, so two callers
# that both hit the same dead pool count it once.
_BREAK_COUNTED = "_bimguard_break_counted"

WORKER_THREAD_ENV_VARS = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")
"""Native thread-pool sizes pinned to 1 for workers; see WORKER MEMORY above."""


def is_multiprocessing_enabled() -> bool:
    """Check if multiprocessing pool execution is enabled and supported.

    Returns False while parallel mode is suspended after repeated pool breaks.
    """
    flag = os.environ.get("BIMGUARD_DISABLE_MULTIPROCESSING", "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return False
    if time.monotonic() < _suspended_until:
        return False
    # If system reports only 1 CPU core, multi-process overhead exceeds benefit
    cpus = os.cpu_count() or 1
    return cpus > 1


def get_worker_count() -> int:
    """Return the configured or default number of worker processes."""
    env_workers = os.environ.get("BIMGUARD_MAX_COMPUTE_WORKERS")
    if env_workers:
        try:
            count = int(env_workers)
            if count > 0:
                return count
        except ValueError:
            logger.warning(
                "Invalid BIMGUARD_MAX_COMPUTE_WORKERS=%r; falling back to CPU count heuristic",
                env_workers,
            )

    cpus = os.cpu_count() or 4
    # Leave 1 core for FastAPI gateway and OS operations
    return max(1, cpus - 1)


def _is_broken(pool: ProcessPoolExecutor) -> bool:
    """Return True if ``pool`` has been marked broken by a dead worker.

    ``_broken`` is a CPython internal; ``getattr`` keeps this a best-effort
    check, backed by the ``BrokenProcessPool`` handling in :func:`run_in_pool`.
    """
    return bool(getattr(pool, "_broken", False))


def _discard(pool: ProcessPoolExecutor) -> None:
    """Shut down ``pool`` without blocking, cancelling anything still queued."""
    try:
        pool.shutdown(wait=False, cancel_futures=True)
    except Exception as exc:
        logger.warning("Error while discarding compute pool: %s", exc)


def _count_break_locked(pool: ProcessPoolExecutor) -> None:
    """Count one break of ``pool`` and suspend parallel mode at the limit. Hold ``_LOCK``."""
    global _consecutive_breaks, _suspended_until
    if getattr(pool, _BREAK_COUNTED, False):
        return
    setattr(pool, _BREAK_COUNTED, True)
    _consecutive_breaks += 1
    if _consecutive_breaks >= MAX_CONSECUTIVE_BREAKS:
        _suspended_until = time.monotonic() + BREAK_COOLDOWN_SECONDS
        logger.error(
            "Compute pool broke %d times in a row; running sequentially for %.0fs",
            _consecutive_breaks,
            BREAK_COOLDOWN_SECONDS,
        )
        _consecutive_breaks = 0


def get_compute_pool() -> ProcessPoolExecutor:
    """Return the shared ProcessPoolExecutor, creating or rebuilding it as needed.

    A pool left broken by a crashed worker is shut down and replaced here, so
    callers never receive an executor that will reject their work.
    """
    global _POOL
    pool = _POOL
    if pool is not None and not _is_broken(pool):
        return pool

    with _LOCK:
        if _POOL is not None and _is_broken(_POOL):
            logger.warning("Compute pool is broken; shutting it down and rebuilding")
            _count_break_locked(_POOL)
            _discard(_POOL)
            _POOL = None
        if _POOL is None:
            workers = get_worker_count()
            logger.info("Initializing shared compute ProcessPoolExecutor workers=%d", workers)
            _limit_worker_native_threads()
            _POOL = ProcessPoolExecutor(max_workers=workers)
        return _POOL


def _limit_worker_native_threads() -> None:
    """Start worker processes with single-threaded BLAS/OpenMP.

    Spawned workers inherit this process's environment when they start, and
    OpenBLAS reads its thread count only when it loads, so the variables are
    set here rather than in a pool initializer (a worker may import numpy
    before an initializer runs). ``setdefault`` leaves any value an operator
    configured untouched. By the time a pool is built the backend has already
    loaded numpy, so its own BLAS thread count is unaffected.
    """
    for name in WORKER_THREAD_ENV_VARS:
        os.environ.setdefault(name, "1")


def report_pool_broken(pool: ProcessPoolExecutor) -> None:
    """Record that ``pool`` broke and discard it so the next caller gets a fresh one.

    Only the current shared pool is detached: if another thread has already
    replaced it, the replacement is left alone.
    """
    global _POOL
    with _LOCK:
        if _POOL is pool:
            _POOL = None
        _count_break_locked(pool)
    _discard(pool)


def report_pool_success() -> None:
    """Record a batch that completed on the pool, resetting the break counter."""
    global _consecutive_breaks
    with _LOCK:
        _consecutive_breaks = 0


def run_in_pool(func: Callable[..., T], arg_sets: Iterable[tuple[Any, ...]]) -> list[T]:
    """Run ``func(*args)`` for each argument tuple on the shared pool, in order.

    Every result is gathered before returning, so a caller that falls back to
    sequential work on failure never holds partial output. If a worker dies,
    the broken pool is discarded before ``BrokenProcessPool`` propagates, so
    the next call runs on a fresh pool rather than failing against the dead one.

    Raises:
        BrokenProcessPool: A worker terminated abruptly during this batch.
        Exception: Whatever ``func`` raised in a worker.
    """
    pool = get_compute_pool()
    futures: list[Future[T]] = []
    try:
        futures = [pool.submit(func, *args) for args in arg_sets]
        results = [future.result() for future in futures]
    except BrokenProcessPool:
        report_pool_broken(pool)
        raise
    except BaseException:
        for future in futures:
            future.cancel()
        raise
    report_pool_success()
    return results


def shutdown_compute_pool(wait: bool = True) -> None:
    """Shut down the compute process pool and release worker resources."""
    global _POOL
    with _LOCK:
        if _POOL is not None:
            if wait and _is_broken(_POOL):
                # Joining a broken pool's feeder thread can hang forever.
                wait = False
            logger.info("Shutting down shared compute ProcessPoolExecutor wait=%s", wait)
            try:
                _POOL.shutdown(wait=wait, cancel_futures=True)
            except Exception as exc:
                logger.warning("Error while shutting down compute pool: %s", exc)
            finally:
                _POOL = None


async def run_cpu_bound(func: Callable[..., T], *args: Any) -> T:
    """Execute a CPU-bound function in the compute pool without blocking the async event loop."""
    if not is_multiprocessing_enabled():
        return func(*args)

    loop = asyncio.get_running_loop()
    pool = get_compute_pool()
    try:
        result = await loop.run_in_executor(pool, func, *args)
    except BrokenProcessPool:
        report_pool_broken(pool)
        raise
    report_pool_success()
    return result
