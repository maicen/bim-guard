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

    def fake_corrosion(content, project_id, engines=None):
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


class TestSeismicIsUnaffected:
    """A single kernel has nothing to select between."""

    def test_engines_do_not_split_the_seismic_entry(self, calls):
        runner.run_analysis("seismic", 1, engines=["GC"])
        runner.run_analysis("seismic", 1)
        assert ANALYSIS_CACHE.stats()["entries"] == 1
