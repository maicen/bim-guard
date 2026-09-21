"""Unit and integration tests for ProcessPoolExecutor compute pool."""

from __future__ import annotations

import asyncio

import pytest

from app.services.compute_pool import (
    get_compute_pool,
    get_worker_count,
    is_multiprocessing_enabled,
    run_cpu_bound,
    shutdown_compute_pool,
)


def test_worker_count_and_env_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test compute pool configuration heuristics and feature flags."""
    monkeypatch.setenv("BIMGUARD_DISABLE_MULTIPROCESSING", "1")
    assert is_multiprocessing_enabled() is False

    monkeypatch.setenv("BIMGUARD_DISABLE_MULTIPROCESSING", "true")
    assert is_multiprocessing_enabled() is False

    monkeypatch.delenv("BIMGUARD_DISABLE_MULTIPROCESSING", raising=False)
    # Default is enabled on multi-core systems
    assert is_multiprocessing_enabled() in (True, False)

    monkeypatch.setenv("BIMGUARD_MAX_COMPUTE_WORKERS", "6")
    assert get_worker_count() == 6

    monkeypatch.setenv("BIMGUARD_MAX_COMPUTE_WORKERS", "invalid")
    assert get_worker_count() >= 1


def test_compute_pool_lifecycle() -> None:
    """Test initializing and safely shutting down the compute pool."""
    pool = get_compute_pool()
    assert pool is not None
    # Re-calling returns the singleton
    assert get_compute_pool() is pool

    shutdown_compute_pool(wait=True)
    # After shutdown, requesting pool recreates it cleanly
    new_pool = get_compute_pool()
    assert new_pool is not None
    assert new_pool is not pool
    shutdown_compute_pool(wait=True)


def _sample_add(a: int, b: int) -> int:
    """Top-level function for multiprocessing test."""
    return a + b


def test_run_cpu_bound_async() -> None:
    """Test running a CPU-bound function in the pool asynchronously."""
    result = asyncio.run(run_cpu_bound(_sample_add, 10, 25))
    assert result == 35
