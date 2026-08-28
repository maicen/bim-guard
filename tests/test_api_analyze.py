"""Tests for /api/analyze endpoints."""

from __future__ import annotations

from starlette.testclient import TestClient

from app.main import app

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

