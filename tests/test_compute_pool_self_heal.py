"""Self-healing tests for the shared compute ProcessPoolExecutor.

A worker is killed with ``os._exit`` -- the same abrupt termination a native
crash or an out-of-memory kill produces -- so these tests exercise the real
``BrokenProcessPool`` path without needing any project's IFC data.
"""

from __future__ import annotations

import os
from concurrent.futures.process import BrokenProcessPool

import pytest

from app.modules.phase_6.phase_6c_corrosion_ui import run_corrosion_analysis
from app.services import compute_pool
from tests.test_compute_pool import _sample_element


def _crash_worker(_: int) -> int:
    """Terminate the worker process abruptly, as a native crash would."""
    os._exit(3)


def _double(value: int) -> int:
    """Top-level (picklable) work item."""
    return value * 2


@pytest.fixture(autouse=True)
def fresh_pool(monkeypatch: pytest.MonkeyPatch):
    """Give each test a small, fresh pool and clean break-tracking state."""
    monkeypatch.setenv("BIMGUARD_MAX_COMPUTE_WORKERS", "2")
    monkeypatch.delenv("BIMGUARD_DISABLE_MULTIPROCESSING", raising=False)
    compute_pool.shutdown_compute_pool(wait=True)
    monkeypatch.setattr(compute_pool, "_consecutive_breaks", 0)
    monkeypatch.setattr(compute_pool, "_suspended_until", 0.0)
    yield
    compute_pool.shutdown_compute_pool(wait=True)


def _worker_processes(pool) -> list:
    """Snapshot the executor's live worker Process objects."""
    return list((pool._processes or {}).values())


def test_pool_rebuilds_after_worker_crash_and_next_batch_succeeds() -> None:
    """A crashed worker breaks one batch; the next batch runs on a fresh pool."""
    assert compute_pool.run_in_pool(_double, [(1,), (2,)]) == [2, 4]
    broken = compute_pool.get_compute_pool()
    workers = _worker_processes(broken)
    assert workers

    with pytest.raises(BrokenProcessPool):
        compute_pool.run_in_pool(_crash_worker, [(0,)])

    # The broken executor was detached and shut down, not left as the global.
    assert compute_pool._POOL is None
    for process in workers:
        process.join(timeout=10)
        assert not process.is_alive(), "a worker of the broken pool leaked"

    assert compute_pool.run_in_pool(_double, [(3,), (4,)]) == [6, 8]
    assert compute_pool.get_compute_pool() is not broken


def test_get_compute_pool_replaces_pool_broken_outside_run_in_pool() -> None:
    """A pool broken by a raw ``submit`` is replaced before it is handed out again."""
    pool = compute_pool.get_compute_pool()
    with pytest.raises(BrokenProcessPool):
        pool.submit(_crash_worker, 0).result()

    healed = compute_pool.get_compute_pool()
    assert healed is not pool
    assert healed.submit(_double, 5).result() == 10


def test_repeated_breaks_suspend_parallel_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """A crash that keeps recurring stops rebuilding pools and runs sequentially."""
    monkeypatch.setattr(compute_pool, "MAX_CONSECUTIVE_BREAKS", 2)

    with pytest.raises(BrokenProcessPool):
        compute_pool.run_in_pool(_crash_worker, [(0,)])
    assert compute_pool.is_multiprocessing_enabled() is True

    with pytest.raises(BrokenProcessPool):
        compute_pool.run_in_pool(_crash_worker, [(0,)])
    assert compute_pool.is_multiprocessing_enabled() is False


def test_success_resets_break_counter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Breaks separated by a successful batch are not consecutive."""
    monkeypatch.setattr(compute_pool, "MAX_CONSECUTIVE_BREAKS", 2)

    with pytest.raises(BrokenProcessPool):
        compute_pool.run_in_pool(_crash_worker, [(0,)])
    assert compute_pool.run_in_pool(_double, [(1,)]) == [2]
    with pytest.raises(BrokenProcessPool):
        compute_pool.run_in_pool(_crash_worker, [(0,)])

    assert compute_pool.is_multiprocessing_enabled() is True


def test_corrosion_fallback_after_pool_break_matches_sequential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A broken pool mid-analysis yields the sequential result, with no duplicates."""
    elements = [_sample_element(i) for i in range(40)]
    parsed = {"quality": {"valid": True}, "elements": elements}
    engines = ["GC-001", "CC-001", "MC-001"]

    monkeypatch.setenv("BIMGUARD_DISABLE_MULTIPROCESSING", "1")
    sequential = run_corrosion_analysis(parsed, include_low=True, engines=engines)
    monkeypatch.delenv("BIMGUARD_DISABLE_MULTIPROCESSING")

    real_run_in_pool = compute_pool.run_in_pool

    def breaking_run_in_pool(func, arg_sets):
        # A real worker crash, raised from inside the analysis's pool call.
        real_run_in_pool(_crash_worker, [(0,)])

    monkeypatch.setattr(compute_pool, "run_in_pool", breaking_run_in_pool)
    fallback = run_corrosion_analysis(parsed, include_low=True, engines=engines)

    assert [i.id for i in fallback["audit_issues"]] == [i.id for i in sequential["audit_issues"]]
    assert [(i.rule_id, i.element_id, i.band) for i in fallback["audit_issues"]] == [
        (i.rule_id, i.element_id, i.band) for i in sequential["audit_issues"]
    ]
