"""Tests for the analysis result cache.

The property that matters most is the one the key encodes: a changed model
cannot hit a stale entry. ``analyze.py``'s module-level result globals had no
such guarantee, which is why this exists rather than a dict keyed on project id.

Run: uv run pytest tests/test_analysis_cache.py -v
"""

from __future__ import annotations

import threading

import pytest

from app.services.analysis_cache import AnalysisCache, CacheKey


def key(project_id: int = 1, slug: str = "corrosion", digest: str = "a" * 64) -> CacheKey:
    return CacheKey(project_id=project_id, slug=slug, source_sha256=digest)


def result(n: int = 1) -> dict:
    return {"audit_issues": [f"issue-{i}" for i in range(n)], "issue_stats": {"total": n}}


@pytest.fixture
def cache() -> AnalysisCache:
    return AnalysisCache(max_entries=3, ttl_seconds=60.0)


class TestStoreAndFetch:
    def test_miss_returns_none(self, cache):
        assert cache.get(key()) is None

    def test_stored_value_comes_back(self, cache):
        cache.put(key(), result(5))
        assert cache.get(key())["issue_stats"]["total"] == 5

    def test_put_overwrites(self, cache):
        cache.put(key(), result(1))
        cache.put(key(), result(9))
        assert cache.get(key())["issue_stats"]["total"] == 9

    def test_clear_empties_the_store(self, cache):
        cache.put(key(), result())
        cache.clear()
        assert cache.get(key()) is None
        assert cache.stats()["entries"] == 0


class TestKeyIdentity:
    """Every component of the key must actually separate entries."""

    def test_different_projects_do_not_share(self, cache):
        cache.put(key(project_id=1), result(1))
        assert cache.get(key(project_id=2)) is None

    def test_different_analyses_do_not_share(self, cache):
        cache.put(key(slug="corrosion"), result(1))
        assert cache.get(key(slug="seismic")) is None

    def test_a_changed_model_cannot_hit_a_stale_entry(self, cache):
        """The reason the digest is in the key at all.

        Keyed on project id alone, a re-upload would serve the previous model's
        findings under the new model's name.
        """
        cache.put(key(digest="a" * 64), result(7))
        assert cache.get(key(digest="b" * 64)) is None

    def test_same_model_hits(self, cache):
        cache.put(key(digest="c" * 64), result(7))
        assert cache.get(key(digest="c" * 64)) is not None


class TestBounding:
    """Unlike the module-level globals this replaces, it cannot grow forever."""

    def test_never_exceeds_max_entries(self, cache):
        for i in range(10):
            cache.put(key(project_id=i), result())
        assert cache.stats()["entries"] == 3

    def test_least_recently_used_is_evicted_first(self, cache):
        for i in (1, 2, 3):
            cache.put(key(project_id=i), result())
        cache.get(key(project_id=1))  # 1 is now most recent; 2 is oldest
        cache.put(key(project_id=4), result())

        assert cache.get(key(project_id=2)) is None, "the oldest should have gone"
        assert cache.get(key(project_id=1)) is not None
        assert cache.get(key(project_id=4)) is not None

    def test_reading_an_entry_keeps_it_alive(self, cache):
        cache.put(key(project_id=1), result())
        for i in (2, 3):
            cache.put(key(project_id=i), result())
        cache.get(key(project_id=1))
        cache.put(key(project_id=4), result())
        assert cache.get(key(project_id=1)) is not None


class TestExpiry:
    def test_expired_entry_reads_as_absent(self):
        cache = AnalysisCache(max_entries=4, ttl_seconds=-1.0)
        cache.put(key(), result())
        assert cache.get(key()) is None

    def test_expired_entry_is_dropped_not_just_hidden(self):
        cache = AnalysisCache(max_entries=4, ttl_seconds=-1.0)
        cache.put(key(), result())
        cache.get(key())
        assert cache.stats()["entries"] == 0

    def test_unexpired_entry_survives(self, cache):
        cache.put(key(), result())
        assert cache.get(key()) is not None


class TestInvalidation:
    def test_invalidate_drops_every_entry_for_the_project(self, cache):
        cache.put(key(project_id=1, slug="corrosion"), result())
        cache.put(key(project_id=1, slug="seismic"), result())
        assert cache.invalidate_project(1) == 2
        assert cache.get(key(project_id=1, slug="corrosion")) is None
        assert cache.get(key(project_id=1, slug="seismic")) is None

    def test_invalidate_leaves_other_projects_alone(self, cache):
        cache.put(key(project_id=1), result())
        cache.put(key(project_id=2), result())
        cache.invalidate_project(1)
        assert cache.get(key(project_id=2)) is not None

    def test_invalidating_an_absent_project_is_a_no_op(self, cache):
        assert cache.invalidate_project(999) == 0


class TestStats:
    def test_hits_and_misses_are_counted(self, cache):
        cache.get(key())  # miss
        cache.put(key(), result())
        cache.get(key())  # hit
        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1

    def test_stats_keys_are_stable(self, cache):
        assert set(cache.stats()) == {
            "entries",
            "max_entries",
            "ttl_seconds",
            "hits",
            "misses",
        }


class TestThreadSafety:
    def test_concurrent_writes_do_not_corrupt_the_store(self):
        """uvicorn serves from a thread pool, so this is a real access pattern."""
        cache = AnalysisCache(max_entries=50, ttl_seconds=60.0)

        def worker(offset: int):
            for i in range(50):
                cache.put(key(project_id=offset * 50 + i), result())
                cache.get(key(project_id=offset * 50 + i))

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert cache.stats()["entries"] <= 50
