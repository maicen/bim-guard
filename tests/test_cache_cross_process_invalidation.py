"""Cache invalidation must reach every uvicorn worker, not only the one that wrote.

Regression: each worker had its own 24 h in-memory cache, so a new document stayed
missing from GET /api/documents on the other workers until the TTL expired.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

from app.services.cache import InMemoryTTLCacheBackend, SharedInvalidationLog


def _worker(path):
    # A separate SharedInvalidationLog per backend has its own read offset, exactly
    # like a separate process would.
    return InMemoryTTLCacheBackend(maxsize=100, ttl=3600, shared_log=SharedInvalidationLog(str(path)))


def test_invalidation_in_one_worker_evicts_matching_keys_in_another(tmp_path):
    log = tmp_path / "inv.log"
    a, b = _worker(log), _worker(log)
    for backend in (a, b):
        backend.set("bimguard:documents:list", ["doc-1"])
        backend.set("bimguard:rules:list", ["rule-1"])

    a.invalidate_prefix("bimguard:documents:list")

    assert b.get("bimguard:documents:list") is None
    assert b.get("bimguard:rules:list") == ["rule-1"]  # unrelated keys survive


def test_clear_propagates_and_log_is_only_read_once(tmp_path):
    log = tmp_path / "inv.log"
    a, b = _worker(log), _worker(log)
    b.set("k", 1)
    a.clear()
    assert b.get("k") is None
    b.set("k", 2)
    assert b.get("k") == 2  # the old CLEAR entry is not re-applied


def test_worker_started_later_ignores_earlier_history(tmp_path):
    log = tmp_path / "inv.log"
    a = _worker(log)
    a.invalidate_prefix("bimguard:documents:list")
    late = _worker(log)
    late.set("bimguard:documents:list", ["fresh"])
    assert late.get("bimguard:documents:list") == ["fresh"]


def test_invalidation_crosses_real_process_boundaries(tmp_path):
    log = tmp_path / "inv.log"
    reader = _worker(log)
    reader.set("bimguard:documents:list", ["stale"])
    code = textwrap.dedent(f"""
        from app.services.cache import InMemoryTTLCacheBackend, SharedInvalidationLog
        b = InMemoryTTLCacheBackend(shared_log=SharedInvalidationLog({str(log)!r}))
        b.invalidate_prefix("bimguard:documents:list")
    """)
    subprocess.run([sys.executable, "-c", code], check=True)
    assert reader.get("bimguard:documents:list") is None


def test_backend_without_shared_log_stays_process_local(tmp_path):
    backend = InMemoryTTLCacheBackend(maxsize=10, ttl=60)
    backend.set("k", 1)
    backend.invalidate_prefix("k")
    assert backend.get("k") is None
