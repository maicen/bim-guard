"""Tests for engine selection in the analysis runner.

Two properties, and they are separate:

    **The selection reaches the engines.** A checkbox that only filters the
    findings afterwards costs exactly as much compute as running everything;
    the point of the selection is that an unselected engine is never entered.

    **The selection is part of the cache key.** Without that, the first
    narrowed run of a model is served back to every later request for it, and
    a full audit silently reports the narrowed run's findings.

NO LIVE DATABASE. The model bytes and the tracked run are both stubbed, so a
"compute" here is one call to the stub and the cache behaviour is the subject
rather than the engines.

Run: uv run pytest tests/test_analysis_runner_engines.py -v
"""

from __future__ import annotations

import pytest

import app.services.analysis_runner as runner
from app.services.analysis_cache import ANALYSIS_CACHE


def empty_result() -> dict:
    """Build an AnalysisResult with no error, so the runner caches it."""
    return {
        "audit_issues": [],
        "issue_stats": {},
        "cost_impact": None,
        "compliance_error": None,
        "compliance_is_demo": False,
    }


@pytest.fixture(autouse=True)
def cold_cache():
    """Hit and miss counts only mean something from a known starting point."""
    ANALYSIS_CACHE.clear()
    yield
    ANALYSIS_CACHE.clear()


@pytest.fixture
def calls(monkeypatch) -> list:
    """Record every corrosion computation and the selection it ran under."""
    recorded: list = []

    def fake_corrosion(content, project_id, engines=None, include_low=True):
        recorded.append(engines)
        return empty_result()

    monkeypatch.setattr(runner, "model_bytes", lambda project_id: (b"IFC", None))
    # Seismic federates every model the project holds, so it loads through
    # model_bytes_all rather than model_bytes and hands the rest to the kernel
    # as extra_models. Both loaders are stubbed: this file is about the cache
    # key and the engine selection, not about storage.
    monkeypatch.setattr(
        runner, "model_bytes_all", lambda project_id: ([("primary.ifc", b"IFC")], None)
    )
    monkeypatch.setattr(runner, "_run_corrosion_tracked", fake_corrosion)
    monkeypatch.setattr(
        runner, "run_seismic_analysis", lambda content, **kwargs: empty_result()
    )
    return recorded


@pytest.fixture
def low_calls(monkeypatch) -> list:
    """Record the ``include_low`` each corrosion computation ran under."""
    recorded: list = []

    def fake_corrosion(content, project_id, engines=None, include_low=True):
        recorded.append(include_low)
        return empty_result()

    monkeypatch.setattr(runner, "model_bytes", lambda project_id: (b"IFC", None))
    monkeypatch.setattr(runner, "_run_corrosion_tracked", fake_corrosion)
    return recorded


class TestLowBandSelection:
    """A run that dropped Low verdicts is a different result, not the same one.

    Suppressing Lows unconditionally did not merely hide the mild findings:
    every GC-001 verdict on Clinic Plumbing bands Low, so the endpoint reported
    that engine as having found nothing. The default is now to keep them, and
    the two answers must not share a cache entry.
    """

    def test_the_default_keeps_low_verdicts(self, low_calls):
        runner.run_analysis("corrosion", 1)
        assert low_calls == [True]

    def test_the_choice_reaches_the_engines(self, low_calls):
        runner.run_analysis("corrosion", 1, include_low=False)
        assert low_calls == [False]

    def test_dropping_lows_is_not_served_from_a_full_run(self, low_calls):
        runner.run_analysis("corrosion", 1, include_low=True)
        runner.run_analysis("corrosion", 1, include_low=False)
        assert low_calls == [True, False]

    def test_a_full_run_is_not_served_from_one_that_dropped_lows(self, low_calls):
        runner.run_analysis("corrosion", 1, include_low=False)
        runner.run_analysis("corrosion", 1, include_low=True)
        assert low_calls == [False, True]

    def test_repeating_one_choice_computes_once(self, low_calls):
        runner.run_analysis("corrosion", 1, include_low=False)
        runner.run_analysis("corrosion", 1, include_low=False)
        assert low_calls == [False]

    def test_each_choice_keeps_its_own_entry(self, low_calls):
        runner.run_analysis("corrosion", 1, include_low=True)
        runner.run_analysis("corrosion", 1, include_low=False)
        runner.run_analysis("corrosion", 1, include_low=True)
        # The third call is a hit on the first entry, not a recompute.
        assert low_calls == [True, False]


class TestSelectionReachesTheEngines:
    def test_engines_are_passed_through(self, calls):
        runner.run_analysis("corrosion", 1, engines=["GC"])
        assert calls == [["GC"]]

    def test_no_selection_stays_none(self, calls):
        """``None`` must survive the trip: it is what means "run everything"."""
        runner.run_analysis("corrosion", 1)
        assert calls == [None]

    def test_empty_selection_is_not_turned_into_all(self, calls):
        runner.run_analysis("corrosion", 1, engines=[])
        assert calls == [[]]


class TestCacheSeparation:
    def test_repeating_a_selection_computes_once(self, calls):
        runner.run_analysis("corrosion", 1, engines=["GC"])
        runner.run_analysis("corrosion", 1, engines=["GC"])
        assert len(calls) == 1

    def test_a_different_selection_recomputes(self, calls):
        runner.run_analysis("corrosion", 1, engines=["GC"])
        runner.run_analysis("corrosion", 1, engines=["CC"])
        assert len(calls) == 2

    def test_a_full_run_is_not_served_from_a_narrowed_one(self, calls):
        runner.run_analysis("corrosion", 1, engines=["GC"])
        runner.run_analysis("corrosion", 1, engines=["GC", "CC", "MC"])
        assert len(calls) == 2

    def test_the_first_selection_is_still_cached_afterwards(self, calls):
        runner.run_analysis("corrosion", 1, engines=["GC"])
        runner.run_analysis("corrosion", 1, engines=["CC"])
        runner.run_analysis("corrosion", 1, engines=["GC", "CC", "MC"])
        runner.run_analysis("corrosion", 1, engines=["GC"])
        assert len(calls) == 3, "the reused selection should have hit the cache"

    def test_spellings_of_one_selection_share_an_entry(self, calls):
        """The key is what runs, not how the caller wrote it."""
        runner.run_analysis("corrosion", 1, engines=["gc"])
        runner.run_analysis("corrosion", 1, engines=["GC-001"])
        assert len(calls) == 1

    def test_selection_order_does_not_split_the_entry(self, calls):
        runner.run_analysis("corrosion", 1, engines=["GC", "CC"])
        runner.run_analysis("corrosion", 1, engines=["CC", "GC"])
        assert len(calls) == 1

    def test_projects_remain_separate_under_one_selection(self, calls):
        runner.run_analysis("corrosion", 1, engines=["GC"])
        runner.run_analysis("corrosion", 2, engines=["GC"])
        assert len(calls) == 2


class TestCachedFlag:
    """``cached`` describes this delivery, not the entry it was served from.

    The flag is the only thing that distinguishes a four-second answer from a
    seven-minute one on the results page. Reporting False on a hit is not a
    cosmetic slip: it tells a reviewer the engines just ran over the model when
    they did not.
    """

    def test_a_computed_result_is_not_cached(self, calls):
        result = runner.run_analysis("corrosion", 1, engines=["GC"])
        assert result["cached"] is False

    def test_a_hit_is_cached(self, calls):
        runner.run_analysis("corrosion", 1, engines=["GC"])
        result = runner.run_analysis("corrosion", 1, engines=["GC"])
        assert len(calls) == 1, "the second call must not have recomputed"
        assert result["cached"] is True

    def test_a_recompute_after_a_hit_is_not_cached(self, calls):
        """A changed selection misses, so the flag has to go back to False."""
        runner.run_analysis("corrosion", 1, engines=["GC"])
        runner.run_analysis("corrosion", 1, engines=["GC"])
        result = runner.run_analysis("corrosion", 1, engines=["CC"])
        assert result["cached"] is False

    def test_use_cache_false_reports_a_computed_result(self, calls):
        runner.run_analysis("corrosion", 1, engines=["GC"])
        result = runner.run_analysis("corrosion", 1, engines=["GC"], use_cache=False)
        assert len(calls) == 2
        assert result["cached"] is False

    def test_the_stored_entry_is_never_flagged(self, calls):
        """The entry must stay flag-free, or the next hit inherits this one's answer."""
        runner.run_analysis("corrosion", 1, engines=["GC"])
        runner.run_analysis("corrosion", 1, engines=["GC"])
        key = runner.CacheKey(
            project_id=1,
            slug="corrosion",
            source_sha256=runner.sha256_of(b"IFC"),
            engines=runner.resolve_engine_codes(["GC"]),
        )
        stored = ANALYSIS_CACHE.get(key)
        assert stored is not None
        assert "cached" not in stored

    def test_the_returned_result_is_not_the_stored_object(self, calls):
        """Mutating what a caller was handed must not corrupt the entry."""
        runner.run_analysis("corrosion", 1, engines=["GC"])
        first = runner.run_analysis("corrosion", 1, engines=["GC"])
        first["audit_issues"] = ["mutated"]
        second = runner.run_analysis("corrosion", 1, engines=["GC"])
        assert second["audit_issues"] == []

    def test_a_third_read_is_still_a_hit(self, calls):
        """Reading twice must not degrade the entry into looking computed."""
        runner.run_analysis("corrosion", 1, engines=["GC"])
        runner.run_analysis("corrosion", 1, engines=["GC"])
        assert runner.run_analysis("corrosion", 1, engines=["GC"])["cached"] is True

    def test_a_failure_is_not_reported_as_cached(self, monkeypatch):
        """A failure is never stored, so it can never be served from the store."""
        monkeypatch.setattr(runner, "model_bytes", lambda project_id: (b"", "unreadable"))
        result = runner.run_analysis("corrosion", 1)
        assert result.get("cached", False) is False

    def test_an_unknown_slug_is_not_reported_as_cached(self):
        assert runner.run_analysis("nonsense", 1).get("cached", False) is False


class TestSeismicIsUnaffected:
    """A single kernel has nothing to select between."""

    def test_engines_do_not_split_the_seismic_entry(self, calls):
        runner.run_analysis("seismic", 1, engines=["GC"])
        runner.run_analysis("seismic", 1)
        assert ANALYSIS_CACHE.stats()["entries"] == 1
