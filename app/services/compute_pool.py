"""Managed ProcessPoolExecutor for CPU-parallel compliance and analysis workflows.

Provides a shared, process-lifecycle-aware ProcessPoolExecutor to bypass the
Python GIL for compute-heavy IFC parsing, corrosion evaluations, and 3D clash
detections without spawning ad-hoc processes per request.
"""

from __future__ import annotations

import asyncio
import os
import threading
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Callable, TypeVar

from app.logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

_POOL: ProcessPoolExecutor | None = None
_LOCK = threading.Lock()


def is_multiprocessing_enabled() -> bool:
    """Check if multiprocessing pool execution is enabled and supported."""
    flag = os.environ.get("BIMGUARD_DISABLE_MULTIPROCESSING", "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
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


def get_compute_pool() -> ProcessPoolExecutor:
    """Return the shared ProcessPoolExecutor, initializing it on first call."""
    global _POOL
    if _POOL is not None:
        return _POOL

    with _LOCK:
        if _POOL is None:
            workers = get_worker_count()
            logger.info("Initializing shared compute ProcessPoolExecutor workers=%d", workers)
            _POOL = ProcessPoolExecutor(max_workers=workers)
    return _POOL


def shutdown_compute_pool(wait: bool = True) -> None:
    """Shut down the compute process pool and release worker resources."""
    global _POOL
    with _LOCK:
        if _POOL is not None:
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
    return await loop.run_in_executor(pool, func, *args)
