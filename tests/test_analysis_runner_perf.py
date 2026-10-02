"""Digest memoisation and single-flight in the analysis runner."""

from __future__ import annotations

import hashlib
import threading
import time

from app.services import analysis_runner as runner
from app.services.analysis_cache import ANALYSIS_CACHE


def test_file_digest_is_memoised_until_the_file_changes(tmp_path, monkeypatch):
    path = tmp_path / "model.ifc"
    path.write_bytes(b"first")
    monkeypatch.setattr(runner, "_DIGESTS", {})

    assert runner._file_digest(path) == hashlib.sha256(b"first").hexdigest()

    reads = []
    real_open = type(path).open
    monkeypatch.setattr(type(path), "open", lambda self, *a, **k: reads.append(1) or real_open(self, *a, **k))
    runner._file_digest(path)
    assert reads == []  # unchanged file: served from the memo

    path.write_bytes(b"second, longer")
    assert runner._file_digest(path) == hashlib.sha256(b"second, longer").hexdigest()


def test_concurrent_cold_requests_run_the_pipeline_once(monkeypatch):
    calls = []

    def slow_architecture(project_id, enable_shacl=False):
        calls.append(project_id)
        time.sleep(0.2)
        return {"audit_issues": [], "issue_stats": {}, "compliance_error": None}

    monkeypatch.setattr(runner, "model_digest", lambda project_id: ("single-flight-digest", None))
    monkeypatch.setattr(runner, "_run_architecture", slow_architecture)
    ANALYSIS_CACHE.clear()

    results: list[dict] = []
    threads = [
        threading.Thread(target=lambda: results.append(runner.run_analysis("architecture", 99)))
        for _ in range(4)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert calls == [99]
    assert len(results) == 4
    assert sum(not r["cached"] for r in results) == 1
    ANALYSIS_CACHE.clear()
