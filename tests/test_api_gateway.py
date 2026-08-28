"""Tests for FastAPI API Gateway bootstrap, health check, and OpenAPI docs."""

from __future__ import annotations

from starlette.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_api_health():
    """Verify /api/health returns 200 and operational status."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "bim-guard-api"


def test_api_openapi_json():
    """Verify /api/openapi.json returns valid OpenAPI 3.x schema."""
    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "/api/projects" in data["paths"]
    assert "/api/rules" in data["paths"]
    assert "/api/analyze/run" in data["paths"]
    assert "/api/events/{project_id}" in data["paths"]


def test_api_docs_ui():
    """Verify /api/docs Swagger UI HTML is served."""
    response = client.get("/api/docs")
    assert response.status_code == 200
    assert "swagger-ui" in response.text.lower()

