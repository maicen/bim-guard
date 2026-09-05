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


def test_export_csv_with_band_parameter():
    """Verify export endpoint accepts band filtering parameter."""
    response = client.get(
        "/api/analyze/export?project_id=119&slug=corrosion&fmt=csv&band=critical&band=high"
    )
    assert response.status_code in (200, 409)


def test_export_csv_with_include_low_parameter():
    """Verify export endpoint accepts include_low filtering parameter."""
    response = client.get(
        "/api/analyze/export?project_id=119&slug=corrosion&fmt=csv&include_low=false"
    )
    assert response.status_code in (200, 409)


def test_export_csv_with_include_data_quality_parameter():
    """Verify export endpoint accepts include_data_quality filtering parameter."""
    response = client.get(
        "/api/analyze/export?project_id=119&slug=corrosion&fmt=csv&include_data_quality=false"
    )
    assert response.status_code in (200, 409)


def test_export_bcf_with_band_filters():
    """Verify BCF export accepts band filtering parameter."""
    response = client.get(
        "/api/analyze/export?project_id=119&slug=corrosion&fmt=bcf&band=critical&band=high&band=medium"
    )
    # Should accept band parameters (200 success or 409 compliance error, not 400 bad param)
    assert response.status_code in (200, 409)
    if response.status_code == 200:
        assert response.headers.get("content-type") in ["application/zip", "application/octet-stream"]


def test_export_json_with_band_parameter():
    """Verify JSON export accepts band filtering parameter."""
    response = client.get(
        "/api/analyze/export?project_id=119&slug=corrosion&fmt=json&band=critical"
    )
    # Should accept band parameters (200 success or 409 compliance error, not 400 bad param)
    assert response.status_code in (200, 409)


def test_export_csv_with_multiple_band_parameters():
    """Verify CSV export accepts multiple band parameters."""
    response = client.get(
        "/api/analyze/export?project_id=119&slug=corrosion&fmt=csv&band=critical&band=high&band=medium&band=low&band=data_quality"
    )
    assert response.status_code in (200, 409)
