"""Tests for /api/analyze endpoints."""

from __future__ import annotations

from starlette.testclient import TestClient

from app.api.analyze import _selected_engines
from app.main import app
from app.modules.contracts import AnalysisRunRequest

client = TestClient(app)
NONEXISTENT_ID = 999_999_999


def test_analyze_status():
    """Verify /api/analyze/status/{project_id} returns workflow status."""
    response = client.get(f"/api/analyze/status/{NONEXISTENT_ID}")
    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == NONEXISTENT_ID
    assert "engines" in data


def test_analyze_run_invalid_slug():
    """Verify triggering analysis with unsupported slug fails with 400."""
    response = client.post(
        "/api/analyze/run",
        json={"project_id": 1, "slug": "invalid_slug"},
    )
    assert response.status_code == 400
    assert "unknown analysis slug" in response.json()["detail"].lower()


def test_analyze_export_invalid_slug():
    """Verify exporting with invalid slug returns 400."""
    response = client.get("/api/analyze/export?project_id=1&slug=invalid_slug&fmt=bcf")
    assert response.status_code == 400


def test_run_request_accepts_an_engine_selection():
    """The analyse page sends the checked engines; the contract must carry them."""
    payload = AnalysisRunRequest(project_id=1, slug="corrosion", engines=["GC", "CC"])
    assert _selected_engines(payload) == ["GC", "CC"]


def test_run_request_without_engines_selects_everything():
    """``None`` is "no selection made", which runs every engine."""
    assert _selected_engines(AnalysisRunRequest(project_id=1)) is None


def test_empty_engine_selection_is_preserved():
    """An empty list must not be rounded up to "all" on the way through."""
    payload = AnalysisRunRequest(project_id=1, engines=[])
    assert _selected_engines(payload) == []


def test_rule_ids_still_narrow_a_run():
    """The older field names the same thing, so it is honoured as a fallback."""
    payload = AnalysisRunRequest(project_id=1, rule_ids=["GC-001.01"])
    assert _selected_engines(payload) == ["GC-001.01"]


def test_engines_wins_over_rule_ids():
    """When both are sent, the explicit engine selection is the request."""
    payload = AnalysisRunRequest(project_id=1, engines=["CC"], rule_ids=["GC-001.01"])
    assert _selected_engines(payload) == ["CC"]


# ── Export Band Filtering Tests ──────────────────────────────────────────────────


#: Element ids are real 22-character IFC GlobalIds, not labels like
#: "elem_crit_0". bcf_generator only writes a Component's IfcGuid attribute
#: when is_ifc_guid() accepts the value, so a placeholder id produces markup
#: with no Components at all -- and "every IfcGuid is valid" would then pass
#: by finding nothing to check. test_export_bcf_band_filtered asserts the
#: Components exist for that reason.
def _element_guid(prefix: str, index: int) -> str:
    """Return a distinct, schema-legal 22-character IFC GlobalId."""
    return f"{prefix}{index:02d}".ljust(22, "0")[:22]


def _synthetic_analysis_result_for_export_tests():
    """Return dict with 3 Critical, 4 High, 5 Medium, 6 Low, 7 DQ."""
    from app.modules.comparator.issue_schema import Issue, RiskBand

    issues = []

    # 3 Critical
    for i in range(3):
        issues.append(
            Issue(
                id=f"BGR-CRIT-{i}",
                element_id=_element_guid("3Kf7q8XzR1pPcrit", i),
                rule_id="GC-001.01",
                title=f"Critical finding {i+1}",
                band=RiskBand.CRITICAL,
                score=0.95,
                mechanism="GC-001",
                metadata={"ifc_type": "IfcPipingElement", "system": "plumbing"},
            )
        )

    # 4 High
    for i in range(4):
        issues.append(
            Issue(
                id=f"BGR-HIGH-{i}",
                element_id=_element_guid("3Kf7q8XzR1pPhigh", i),
                rule_id="CC-001.02",
                title=f"High finding {i+1}",
                band=RiskBand.HIGH,
                score=0.75,
                mechanism="CC-001",
                metadata={"ifc_type": "IfcPipingElement", "system": "crevice"},
            )
        )

    # 5 Medium
    for i in range(5):
        issues.append(
            Issue(
                id=f"BGR-MED-{i}",
                element_id=_element_guid("3Kf7q8XzR1pPmedm", i),
                rule_id="GC-001.03",
                title=f"Medium finding {i+1}",
                band=RiskBand.MEDIUM,
                score=0.5,
                mechanism="GC-001",
                metadata={"ifc_type": "IfcPipingElement", "system": "galvanic"},
            )
        )

    # 6 Low
    for i in range(6):
        issues.append(
            Issue(
                id=f"BGR-LOW-{i}",
                element_id=_element_guid("3Kf7q8XzR1pPlow_", i),
                rule_id="CC-001.04",
                title=f"Low finding {i+1}",
                band=RiskBand.LOW,
                score=0.2,
                mechanism="CC-001",
                metadata={"ifc_type": "IfcPipingElement", "system": "crevice"},
            )
        )

    # 7 Data Quality notes
    for i in range(7):
        issues.append(
            Issue(
                id=f"BGR-DQ-{i}",
                element_id=_element_guid("3Kf7q8XzR1pPdqal", i),
                rule_id="DATA-001.01",
                title=f"Data quality note {i+1}",
                band=RiskBand.LOW,
                score=0.1,
                mechanism="data_quality",
                metadata={"check": "missing_spec"},
            )
        )

    return {
        "pipeline": "audit",
        "project_id": 119,
        "slug": "corrosion",
        "element_count": 50,
        "audit_issues": issues,
        "issue_stats": {"total": 18, "critical": 3, "high": 4, "medium": 5, "low": 6, "data_quality": 7},
        "compliance_error": None,
        "compliance_is_demo": False,
        "cached": False,
    }


def _csv_rows(response) -> list[dict]:
    """Parse an export CSV body into dict rows, header excluded."""
    import csv
    import io

    return list(csv.DictReader(io.StringIO(response.text)))


def _mock_run_analysis_factory(include_low=True):
    """Factory to create a mock run_analysis that respects include_low."""
    def mock_run_analysis(slug, project_id, *, engines=None, include_low=include_low, **kwargs):
        synthetic = _synthetic_analysis_result_for_export_tests()
        if not include_low:
            synthetic["audit_issues"] = [i for i in synthetic["audit_issues"] if i.band != "low" or i.mechanism == "data_quality"]
            synthetic["issue_stats"]["low"] = 0
        return synthetic
    return mock_run_analysis


def test_export_csv_all_findings_with_low():
    """fmt=csv, include_low=true, no band → 25 data rows (+1 header)."""
    from unittest.mock import patch

    synthetic = _synthetic_analysis_result_for_export_tests()
    with patch("app.api.analyze.run_analysis", return_value=synthetic):
        response = client.get("/api/analyze/export?project_id=119&slug=corrosion&fmt=csv&include_low=true")
        assert response.status_code == 200
        lines = response.text.strip().split("\n")
        assert len(lines) == 26


def test_export_csv_without_low():
    """fmt=csv, include_low=false → 19 data rows and no row whose band is Low."""
    from unittest.mock import patch

    with patch("app.api.analyze.run_analysis", side_effect=_mock_run_analysis_factory()):
        response = client.get("/api/analyze/export?project_id=119&slug=corrosion&fmt=csv&include_low=false")
        assert response.status_code == 200
        lines = response.text.strip().split("\n")
        assert len(lines) == 20
        # The 6 Low *findings* are gone. The 7 data-quality notes also carry
        # band=low and are exempt from include_low by design, so the check is
        # "no Low finding", not "no low band" -- the latter would fail on rows
        # that are supposed to survive.
        rows = _csv_rows(response)
        assert [r for r in rows if r["band"] == "low" and r["is_data_quality"] == "no"] == []


def test_export_csv_band_filtered():
    """fmt=csv, band=medium&band=high&band=critical → 12 data rows; no Low; no data_quality."""
    from unittest.mock import patch

    synthetic = _synthetic_analysis_result_for_export_tests()
    with patch("app.api.analyze.run_analysis", return_value=synthetic):
        response = client.get(
            "/api/analyze/export?project_id=119&slug=corrosion&fmt=csv&band=critical&band=high&band=medium"
        )
        assert response.status_code == 200
        lines = response.text.strip().split("\n")
        assert len(lines) == 13
        rows = _csv_rows(response)
        assert [r for r in rows if r["band"] == "low"] == []
        assert [r for r in rows if r["is_data_quality"] == "yes"] == []


def test_export_csv_exclude_data_quality():
    """fmt=csv, include_data_quality=false → 18 data rows."""
    from unittest.mock import patch

    synthetic = _synthetic_analysis_result_for_export_tests()
    with patch("app.api.analyze.run_analysis", return_value=synthetic):
        response = client.get(
            "/api/analyze/export?project_id=119&slug=corrosion&fmt=csv&include_data_quality=false"
        )
        assert response.status_code == 200
        lines = response.text.strip().split("\n")
        assert len(lines) == 19


def test_export_csv_data_quality_only():
    """fmt=csv, band=data_quality → 7 data rows."""
    from unittest.mock import patch

    synthetic = _synthetic_analysis_result_for_export_tests()
    with patch("app.api.analyze.run_analysis", return_value=synthetic):
        response = client.get("/api/analyze/export?project_id=119&slug=corrosion&fmt=csv&band=data_quality")
        assert response.status_code == 200
        lines = response.text.strip().split("\n")
        assert len(lines) == 8


def test_export_bcf_band_filtered():
    """fmt=bcf, band=critical&band=high&band=medium → Topic elements across all markup.bcf files = 12; every Component IfcGuid is valid."""
    import io
    import zipfile
    from unittest.mock import patch
    from xml.etree import ElementTree as ET

    from app.modules.reporter.bcf_generator import is_ifc_guid

    def mock_run_analysis(slug, project_id, *, engines=None, include_low=True, **kwargs):
        synthetic = _synthetic_analysis_result_for_export_tests()
        return synthetic

    with patch("app.api.analyze.run_analysis", side_effect=mock_run_analysis):
        response = client.get(
            "/api/analyze/export?project_id=119&slug=corrosion&fmt=bcf&band=critical&band=high&band=medium"
        )
        assert response.status_code == 200
        bcf_zip = zipfile.ZipFile(io.BytesIO(response.content))
        topic_count = 0
        ifc_guids = []
        for name in bcf_zip.namelist():
            content = bcf_zip.read(name).decode("utf-8") if name.endswith((".bcf", ".bcfv")) else ""
            if name.endswith(".bcf"):
                topic_count += len(ET.fromstring(content).findall(".//Topic"))
            elif name.endswith(".bcfv"):
                # Components live in the viewpoint, not the markup: one under
                # Selection and one under Coloring per topic.
                for component in ET.fromstring(content).findall(".//Component"):
                    ifc_guids.append(component.get("IfcGuid"))
        assert topic_count == 12
        # Guard against a vacuous pass: bcf_generator omits the attribute
        # entirely for an element id it will not vouch for, so "all valid"
        # over an empty list would prove nothing.
        assert len(ifc_guids) == 24
        assert [g for g in ifc_guids if not is_ifc_guid(g)] == []


def test_export_json_critical_only():
    """fmt=json, band=critical → 3 findings."""
    from unittest.mock import patch

    def mock_run_analysis(slug, project_id, *, engines=None, include_low=True, **kwargs):
        synthetic = _synthetic_analysis_result_for_export_tests()
        return synthetic

    with patch("app.api.analyze.run_analysis", side_effect=mock_run_analysis):
        response = client.get("/api/analyze/export?project_id=119&slug=corrosion&fmt=json&band=critical")
        assert response.status_code == 200
        data = response.json()
        assert len(data.get("findings", [])) == 3


# ── Ascending sort orders ────────────────────────────────────────────────────
#
# ``band_asc`` and ``score_asc`` are the ascending counterparts of the two
# descending orders the page already had. The property worth pinning is not
# "the list is reversed" — it is that data-quality notes stay at the end of
# both. The notes carry the Low band, so an ordering that sorted on band alone
# would open an ascending page with the elements the engines refused to score.


def _sortable_issues():
    """Three verdicts spanning three bands, plus one data-quality note."""
    from app.modules.comparator.issue_schema import Issue, RiskBand

    return [
        Issue(
            id="BGR-0001",
            element_id="GUID-1",
            rule_id="GC-001.01",
            title="critical finding",
            band=RiskBand.CRITICAL,
            score=0.90,
            mechanism="GC-001 galvanic",
            mitigation="",
        ),
        Issue(
            id="BGR-0002",
            element_id="GUID-2",
            rule_id="CC-001.01",
            title="medium finding",
            band=RiskBand.MEDIUM,
            score=0.40,
            mechanism="CC-001 crevice",
            mitigation="",
        ),
        Issue(
            id="BGR-0003",
            element_id="GUID-3",
            rule_id="MC-001.01",
            title="low finding",
            band=RiskBand.LOW,
            score=0.20,
            mechanism="MC-001 microbiological",
            mitigation="",
        ),
        Issue(
            id="BGR-DQ-1",
            element_id="GUID-4",
            rule_id="MC-001.DATA",
            title="unassessable element",
            band=RiskBand.LOW,
            score=0.10,
            mechanism="data_quality",
            mitigation="",
        ),
    ]


def test_band_asc_orders_mildest_verdict_first():
    from app.api.analyze import _sort_issues

    ordered = _sort_issues(_sortable_issues(), "band_asc")
    assert [i.id for i in ordered] == ["BGR-0003", "BGR-0002", "BGR-0001", "BGR-DQ-1"]


def test_score_asc_orders_lowest_score_first():
    from app.api.analyze import _sort_issues

    ordered = _sort_issues(_sortable_issues(), "score_asc")
    assert [i.id for i in ordered] == ["BGR-0003", "BGR-0002", "BGR-0001", "BGR-DQ-1"]


def test_data_quality_notes_sort_last_in_both_ascending_orders():
    """The note has the lowest score of all four, and must still not lead."""
    from app.api.analyze import _sort_issues

    for sort in ("band_asc", "score_asc"):
        ordered = _sort_issues(_sortable_issues(), sort)
        assert ordered[-1].id == "BGR-DQ-1", sort
        assert ordered[0].id != "BGR-DQ-1", sort


def test_ascending_orders_are_not_merely_the_descending_ones_reversed():
    """Reversing band_then_score would put the note first; band_asc does not."""
    from app.api.analyze import _sort_issues

    issues = _sortable_issues()
    descending = [i.id for i in _sort_issues(issues, "band_then_score")]
    ascending = [i.id for i in _sort_issues(issues, "band_asc")]
    assert descending[-1] == "BGR-DQ-1"
    assert ascending != list(reversed(descending))
    assert ascending[-1] == "BGR-DQ-1"


def test_ascending_sorts_break_ties_on_id():
    """Two issues equal on every other key keep a reproducible order."""
    from app.api.analyze import _sort_issues
    from app.modules.comparator.issue_schema import Issue, RiskBand

    def twin(issue_id: str) -> Issue:
        return Issue(
            id=issue_id,
            element_id="GUID-T",
            rule_id="GC-001.01",
            title="tie",
            band=RiskBand.MEDIUM,
            score=0.5,
            mechanism="GC-001 galvanic",
            mitigation="",
        )

    pair = [twin("BGR-0009"), twin("BGR-0004")]
    for sort in ("band_asc", "score_asc"):
        assert [i.id for i in _sort_issues(pair, sort)] == ["BGR-0004", "BGR-0009"], sort


def test_results_endpoint_accepts_the_ascending_sort_values():
    """The route must not 422 the two new values."""
    from unittest.mock import patch

    from app.api.analyze import _issue_stats

    issues = _sortable_issues()

    def mock_run_analysis(*args, **kwargs):
        return {
            "audit_issues": issues,
            "issue_stats": _issue_stats(issues),
            "ifc_element_count": 4,
            "compliance_error": None,
            "compliance_is_demo": False,
            "cached": False,
        }

    with patch("app.api.analyze.run_analysis", side_effect=mock_run_analysis):
        for sort, first in (("band_asc", "BGR-0003"), ("score_asc", "BGR-0003")):
            response = client.get(
                f"/api/analyze/results/4242/corrosion?limit=10&sort={sort}"
            )
            assert response.status_code == 200, (sort, response.text)
            body = response.json()
            assert body["audit_issues"][0]["id"] == first, sort
            assert body["audit_issues"][-1]["id"] == "BGR-DQ-1", sort


def test_results_endpoint_still_rejects_an_unknown_sort():
    """The Literal must stay closed, or a typo would silently sort by default."""
    response = client.get("/api/analyze/results/4242/corrosion?limit=10&sort=sideways")
    assert response.status_code == 422
