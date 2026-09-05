"""``include_low`` from the request down to the engines.

Low-band verdicts were suppressed unconditionally at
``analysis_runner._run_corrosion_tracked``, which did not merely hide the mild
findings: every GC-001 verdict on Clinic Plumbing bands Low, so the endpoint
reported that engine as having found nothing at all. These fix the default at
"emit them" and pin the two things that make the switch safe -- that it reaches
``run_corrosion_analysis``, and that the two answers cannot share a cache entry.

The exports are the exception, and deliberately so: because the two answers
cannot share an entry, an export that forwarded a request for the
Medium-and-above view re-ran the whole analysis. They therefore always run the
superset and subtract from it. See ``TestPlumbing`` below.

Run: uv run pytest tests/test_include_low.py -v
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

import app.services.analysis_runner as runner_module
from app.main import app
from app.modules.contracts import AnalysisRunRequest
from app.services.analysis_cache import CacheKey

PROJECT_ID = 4321


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


class TestCacheKey:
    """A run that dropped Lows is a different result, not the same one."""

    def test_the_two_answers_do_not_share_an_entry(self):
        base = {
            "project_id": 1,
            "slug": "corrosion",
            "source_sha256": "abc",
            "engines": ("GC-001",),
        }
        assert CacheKey(**base, include_low=True) != CacheKey(**base, include_low=False)

    def test_the_key_defaults_to_keeping_lows(self):
        key = CacheKey(project_id=1, slug="corrosion", source_sha256="abc")
        assert key.include_low is True

    def test_a_cache_serves_each_answer_its_own_result(self):
        from app.services.analysis_cache import AnalysisCache

        cache = AnalysisCache()
        base = {"project_id": 1, "slug": "corrosion", "source_sha256": "abc"}
        with_low = CacheKey(**base, include_low=True)
        without_low = CacheKey(**base, include_low=False)

        cache.put(with_low, {"audit_issues": ["low kept"]})
        cache.put(without_low, {"audit_issues": []})

        assert cache.get(with_low) == {"audit_issues": ["low kept"]}
        assert cache.get(without_low) == {"audit_issues": []}


class TestContract:
    def test_the_run_request_keeps_lows_by_default(self):
        assert AnalysisRunRequest(project_id=1).include_low is True

    def test_the_run_request_can_ask_for_medium_and_above(self):
        assert AnalysisRunRequest(project_id=1, include_low=False).include_low is False


class TestPlumbing:
    """What the routes actually hand to ``run_analysis``."""

    @pytest.fixture()
    def captured(self, monkeypatch) -> list[dict]:
        calls: list[dict] = []

        def fake_run_analysis(slug, project_id, **kwargs):
            calls.append({"slug": slug, "project_id": project_id, **kwargs})
            return {
                "audit_issues": [],
                "issue_stats": {},
                "compliance_error": None,
                "ifc_element_count": 0,
            }

        monkeypatch.setattr(runner_module, "run_analysis", fake_run_analysis)
        # The routers imported the name directly, so both bindings are replaced.
        import app.api.analyze as analyze_module

        monkeypatch.setattr(analyze_module, "run_analysis", fake_run_analysis)
        return calls

    def test_results_defaults_to_keeping_lows(self, client, captured):
        client.get(f"/api/analyze/results/{PROJECT_ID}/corrosion")
        assert captured[-1]["include_low"] is True

    def test_results_forwards_an_explicit_false(self, client, captured):
        client.get(f"/api/analyze/results/{PROJECT_ID}/corrosion?include_low=false")
        assert captured[-1]["include_low"] is False

    def test_export_always_runs_the_superset(self, client, captured):
        """The export asks for every band, then filters what it hands back.

        ``include_low`` is part of the cache key, so forwarding a request for
        the Medium-and-above view into the run forked the entry and recomputed
        an analysis the page had just produced. Suppressing Low is a strict
        subtraction inside the engines, so the export takes the superset and
        subtracts — one run, filtered per download.
        """
        client.get(f"/api/analyze/export?project_id={PROJECT_ID}&slug=corrosion&fmt=csv")
        assert captured[-1]["include_low"] is True

    def test_an_explicit_false_filters_rather_than_re_running(self, client, captured):
        """Asking the export to drop Lows must not change what is computed."""
        client.get(
            f"/api/analyze/export?project_id={PROJECT_ID}"
            "&slug=corrosion&fmt=csv&include_low=false"
        )
        assert captured[-1]["include_low"] is True
        assert captured[-1]["use_cache"] is True

    def test_run_defaults_to_keeping_lows(self, client, captured):
        client.post("/api/analyze/run", json={"project_id": PROJECT_ID, "slug": "corrosion"})
        assert captured[-1]["include_low"] is True

    def test_run_forwards_an_explicit_false(self, client, captured):
        client.post(
            "/api/analyze/run",
            json={"project_id": PROJECT_ID, "slug": "corrosion", "include_low": False},
        )
        assert captured[-1]["include_low"] is False

    def test_it_is_a_run_parameter_not_a_page_filter(self, client, captured):
        """Sending it alone must not conjure a ``page`` object."""
        body = client.get(
            f"/api/analyze/results/{PROJECT_ID}/corrosion?include_low=false"
        ).json()
        assert body["page"] is None


class TestEngineHandoff:
    """``run_analysis`` must pass the flag on rather than swallow it."""

    @pytest.fixture()
    def seen(self, monkeypatch) -> list[dict]:
        calls: list[dict] = []

        def fake_corrosion(parsed, *, include_low=False, run_id="BGR", engines=None):
            calls.append({"include_low": include_low, "engines": engines})
            return {"audit_issues": [], "issue_stats": {}, "compliance_error": None}

        monkeypatch.setattr(runner_module, "run_corrosion_analysis", fake_corrosion)
        monkeypatch.setattr(
            runner_module, "parse_ifc_bytes", lambda *a, **k: {"quality": {"valid": True}}
        )
        return calls

    @pytest.mark.parametrize("include_low", [True, False])
    def test_the_flag_reaches_the_engines(self, seen, include_low):
        runner_module._run_corrosion_tracked(
            b"", PROJECT_ID, None, include_low
        )
        assert seen[-1]["include_low"] is include_low

    def test_the_tracked_path_defaults_to_keeping_lows(self, seen):
        runner_module._run_corrosion_tracked(b"", PROJECT_ID)
        assert seen[-1]["include_low"] is True
