"""Server-side pagination of ``GET /api/analyze/results/{project_id}/{slug}``.

``run_analysis`` is replaced with a synthetic run, so these assert on the route
layer's own arithmetic — filtering, ordering, slicing and what it reports about
the window — without a model, a database or an engine in the way. The
substitute returns the same shape the real runner does: ``Issue`` objects under
``audit_issues`` and a whole-run ``issue_stats``.

Run: uv run pytest tests/test_api_analyze_pagination.py -v
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

import app.api.analyze as analyze_module
from app.main import app
from app.modules.comparator.issue_schema import Issue, RiskBand

PROJECT_ID = 4242
RESULTS_URL = f"/api/analyze/results/{PROJECT_ID}/corrosion"

#: Engine codes the synthetic run spreads its findings across, cycled so that
#: band, engine and score vary independently of each other.
ENGINES = ("GC-001", "CC-001", "MC-001")

BANDS = (RiskBand.CRITICAL, RiskBand.HIGH, RiskBand.MEDIUM, RiskBand.LOW)

#: Verdicts, on top of which the run carries one data-quality note per engine.
VERDICT_COUNT = 60

TOTAL_ISSUES = VERDICT_COUNT + len(ENGINES)


def _synthetic_issues() -> list[Issue]:
    """Build a run whose bands, engines and scores are deliberately unaligned.

    Scores descend as ids ascend while bands and engines cycle, so an ordering
    that ignores band, or that leans on the emitted order, produces a visibly
    different first page from one that does not.
    """
    issues: list[Issue] = []
    for n in range(VERDICT_COUNT):
        engine = ENGINES[n % len(ENGINES)]
        band = BANDS[n % len(BANDS)]
        issues.append(
            Issue(
                id=f"BGR-{n:04d}",
                element_id=f"GUID-{n:04d}",
                rule_id=f"{engine}.{(n % 4) + 1:02d}",
                title=f"Finding {n}",
                description="A synthetic finding.",
                band=band,
                score=round(1.0 - n / 100, 4),
                mechanism=f"{engine} synthetic",
                mitigation="Replace the coupling.",
            )
        )
    for engine in ENGINES:
        issues.append(
            Issue(
                id=f"BGR-DQ-{engine}",
                element_id="GUID-DQ",
                rule_id=f"{engine}.DATA",
                title=f"{engine} could not be assessed",
                band=RiskBand.LOW,
                score=0.0,
                mechanism="data_quality",
            )
        )
    return issues


def _synthetic_result() -> dict:
    issues = _synthetic_issues()
    return {
        "audit_issues": issues,
        "issue_stats": analyze_module._issue_stats(issues),
        "ifc_element_count": 999,
        "compliance_error": None,
        "compliance_is_demo": False,
        "cached": False,
    }


@pytest.fixture(autouse=True)
def _stub_run_analysis(monkeypatch):
    """Serve every request from one fixed run, so paging is the only variable."""
    monkeypatch.setattr(
        analyze_module, "run_analysis", lambda *args, **kwargs: _synthetic_result()
    )


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def whole_run(client) -> dict:
    """Return the unpaginated body, i.e. what this endpoint returned before."""
    response = client.get(RESULTS_URL)
    assert response.status_code == 200
    return response.json()


class TestBackwardCompatibility:
    """A request that asks for no window must be indistinguishable from before."""

    def test_no_parameters_returns_the_whole_run(self, whole_run):
        assert len(whole_run["audit_issues"]) == TOTAL_ISSUES

    def test_no_parameters_carries_no_page_object(self, whole_run):
        # None rather than merely falsy: an existing consumer sees the key
        # empty, not a window it was never written to read.
        assert whole_run["page"] is None

    def test_no_parameters_preserves_the_emitted_order(self, whole_run):
        ids = [i["id"] for i in whole_run["audit_issues"]]
        assert ids == [i.id for i in _synthetic_issues()]

    def test_explicit_defaults_are_the_same_as_sending_nothing(self, client, whole_run):
        """``offset=0`` and ``include_data_quality=true`` ask for no narrowing."""
        response = client.get(f"{RESULTS_URL}?offset=0&include_data_quality=true")
        assert response.json() == whole_run


class TestWindow:
    def test_limit_and_offset_cut_the_requested_slice(self, client):
        body = client.get(f"{RESULTS_URL}?limit=10&offset=10").json()
        assert len(body["audit_issues"]) == 10
        assert body["page"] == {
            "limit": 10,
            "offset": 10,
            "returned": 10,
            "total_matching": TOTAL_ISSUES,
            "has_more": True,
        }

    def test_stats_still_describe_the_whole_run(self, client, whole_run):
        body = client.get(f"{RESULTS_URL}?limit=10&offset=10").json()
        assert body["issue_stats"] == whole_run["issue_stats"]
        assert body["issue_stats"]["total"] == VERDICT_COUNT

    def test_element_count_is_not_the_page_length(self, client, whole_run):
        body = client.get(f"{RESULTS_URL}?limit=10").json()
        assert body["element_count"] == whole_run["element_count"] == 999

    def test_the_last_page_reports_no_more(self, client):
        body = client.get(f"{RESULTS_URL}?limit=10&offset={TOTAL_ISSUES - 5}").json()
        assert body["page"]["returned"] == 5
        assert body["page"]["has_more"] is False

    def test_offset_past_the_end_is_an_empty_page_not_a_404(self, client):
        response = client.get(f"{RESULTS_URL}?limit=10&offset=100000")
        assert response.status_code == 200
        body = response.json()
        assert body["audit_issues"] == []
        assert body["page"]["returned"] == 0
        assert body["page"]["has_more"] is False
        assert body["page"]["total_matching"] == TOTAL_ISSUES

    def test_a_filter_alone_still_reports_the_window(self, client):
        """No ``limit`` means one page holding everything that matched."""
        page = client.get(f"{RESULTS_URL}?band=critical").json()["page"]
        assert page["limit"] is None
        assert page["returned"] == page["total_matching"]
        assert page["has_more"] is False


class TestFilters:
    def test_band_narrows_the_issues_but_not_the_stats(self, client, whole_run):
        body = client.get(f"{RESULTS_URL}?band=critical").json()
        assert {i["band"] for i in body["audit_issues"]} == {"critical"}
        assert body["page"]["total_matching"] < whole_run["issue_stats"]["total"]
        assert body["page"]["total_matching"] == whole_run["issue_stats"]["critical"]
        assert body["issue_stats"] == whole_run["issue_stats"]

    def test_bands_are_additive(self, client, whole_run):
        body = client.get(f"{RESULTS_URL}?band=critical&band=high").json()
        assert {i["band"] for i in body["audit_issues"]} == {"critical", "high"}
        assert (
            body["page"]["total_matching"]
            == whole_run["issue_stats"]["critical"] + whole_run["issue_stats"]["high"]
        )

    def test_a_band_filter_excludes_data_quality_notes(self, client):
        """A note carries a band but is not a verdict, as the page's filter has it."""
        body = client.get(f"{RESULTS_URL}?band=low").json()
        assert body["audit_issues"]
        assert all(i["mechanism"] != "data_quality" for i in body["audit_issues"])

    def test_mechanism_selects_an_engine_and_its_data_quality_notes(self, client):
        body = client.get(f"{RESULTS_URL}?mechanism=GC-001").json()
        rule_ids = [i["rule_id"] for i in body["audit_issues"]]
        assert rule_ids
        assert all(r.startswith("GC-001") for r in rule_ids)
        assert "GC-001.DATA" in rule_ids

    def test_mechanism_accepts_a_bare_prefix(self, client):
        by_prefix = client.get(f"{RESULTS_URL}?mechanism=GC").json()
        by_code = client.get(f"{RESULTS_URL}?mechanism=GC-001").json()
        assert by_prefix["page"]["total_matching"] == by_code["page"]["total_matching"]

    def test_an_unknown_mechanism_selects_nothing_rather_than_everything(self, client):
        body = client.get(f"{RESULTS_URL}?mechanism=ZZ-999").json()
        assert body["audit_issues"] == []
        assert body["page"]["total_matching"] == 0

    def test_data_quality_can_be_left_out(self, client):
        body = client.get(f"{RESULTS_URL}?include_data_quality=false").json()
        assert all(i["mechanism"] != "data_quality" for i in body["audit_issues"])
        assert body["page"]["total_matching"] == VERDICT_COUNT

    def test_filters_combine(self, client):
        body = client.get(f"{RESULTS_URL}?band=critical&mechanism=GC-001").json()
        assert body["audit_issues"]
        for issue in body["audit_issues"]:
            assert issue["band"] == "critical"
            assert issue["rule_id"].startswith("GC-001")


class TestOrdering:
    def test_the_default_leads_with_the_criticals(self, client):
        bands = [i["band"] for i in client.get(f"{RESULTS_URL}?limit=2000").json()["audit_issues"]]
        weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        ranks = [weights[b] for b in bands]
        assert ranks == sorted(ranks, reverse=True)

    def test_within_a_band_the_order_is_score_then_id(self, client):
        issues = client.get(f"{RESULTS_URL}?band=high&limit=2000").json()["audit_issues"]
        keys = [(-i["score"], i["id"]) for i in issues]
        assert keys == sorted(keys)

    def test_score_desc_ignores_bands(self, client):
        issues = client.get(f"{RESULTS_URL}?sort=score_desc&limit=2000").json()["audit_issues"]
        scores = [i["score"] for i in issues]
        assert scores == sorted(scores, reverse=True)

    def test_natural_keeps_the_run_order(self, client, whole_run):
        issues = client.get(f"{RESULTS_URL}?sort=natural&limit=2000").json()["audit_issues"]
        assert [i["id"] for i in issues] == [i["id"] for i in whole_run["audit_issues"]]

    def test_adjacent_pages_are_disjoint_and_cover_the_whole_set(self, client):
        collected: list[str] = []
        for offset in range(0, TOTAL_ISSUES, 7):
            page = client.get(f"{RESULTS_URL}?limit=7&offset={offset}").json()
            collected.extend(i["id"] for i in page["audit_issues"])
        assert len(collected) == len(set(collected)) == TOTAL_ISSUES

        one_shot = client.get(f"{RESULTS_URL}?limit=2000").json()["audit_issues"]
        assert collected == [i["id"] for i in one_shot]

    def test_paging_a_filtered_set_reproduces_it_exactly(self, client):
        whole = client.get(f"{RESULTS_URL}?band=medium&limit=2000").json()
        expected = [i["id"] for i in whole["audit_issues"]]

        collected: list[str] = []
        for offset in range(0, whole["page"]["total_matching"], 4):
            page = client.get(f"{RESULTS_URL}?band=medium&limit=4&offset={offset}").json()
            collected.extend(i["id"] for i in page["audit_issues"])
        assert collected == expected


class TestValidation:
    @pytest.mark.parametrize("limit", [0, -1, 5000])
    def test_a_limit_outside_the_range_is_rejected(self, client, limit):
        assert client.get(f"{RESULTS_URL}?limit={limit}").status_code == 422

    def test_a_negative_offset_is_rejected(self, client):
        assert client.get(f"{RESULTS_URL}?offset=-1").status_code == 422

    def test_an_unknown_band_is_rejected(self, client):
        assert client.get(f"{RESULTS_URL}?band=catastrophic").status_code == 422

    def test_an_unknown_sort_is_rejected(self, client):
        assert client.get(f"{RESULTS_URL}?sort=alphabetical").status_code == 422
