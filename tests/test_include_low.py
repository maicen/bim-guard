"""``include_low`` as a cache-key dimension.

Two answers that differ only in whether Low-band verdicts are kept are still
two different results, so they must not share a cache entry.

Run: uv run pytest tests/test_include_low.py -v
"""

from __future__ import annotations

from app.services.analysis_cache import CacheKey


class TestCacheKey:
    """A run that dropped Lows is a different result, not the same one."""

    def test_the_two_answers_do_not_share_an_entry(self):
        base = {
            "project_id": 1,
            "slug": "architecture",
            "source_sha256": "abc",
        }
        assert CacheKey(**base, include_low=True) != CacheKey(**base, include_low=False)

    def test_the_key_defaults_to_keeping_lows(self):
        key = CacheKey(project_id=1, slug="architecture", source_sha256="abc")
        assert key.include_low is True

    def test_a_cache_serves_each_answer_its_own_result(self):
        from app.services.analysis_cache import AnalysisCache

        cache = AnalysisCache()
        base = {"project_id": 1, "slug": "architecture", "source_sha256": "abc"}
        with_low = CacheKey(**base, include_low=True)
        without_low = CacheKey(**base, include_low=False)

        cache.put(with_low, {"audit_issues": ["low kept"]})
        cache.put(without_low, {"audit_issues": []})

        assert cache.get(with_low) == {"audit_issues": ["low kept"]}
        assert cache.get(without_low) == {"audit_issues": []}
