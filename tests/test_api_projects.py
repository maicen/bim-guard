"""Tests for /api/projects endpoints."""

from __future__ import annotations

from starlette.testclient import TestClient

from app.main import app

client = TestClient(app)
NONEXISTENT_ID = 999_999_999


def test_list_projects():
    """Verify /api/projects lists projects with total count."""
    response = client.get("/api/projects")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert isinstance(data["projects"], list)


def test_get_project_not_found():
    """Verify requesting a non-existent project returns 404."""
    response = client.get(f"/api/projects/{NONEXISTENT_ID}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_create_project_validation_failure():
    """Verify creating a project with empty name fails with 422 Unprocessable Entity."""
    response = client.post("/api/projects", json={"name": "", "description": "test"})
    assert response.status_code == 422


def test_download_ifc_not_found():
    """Verify IFC download for non-existent project returns 404."""
    response = client.get(f"/api/projects/{NONEXISTENT_ID}/ifc")
    assert response.status_code == 404

