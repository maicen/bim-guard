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
    assert data["graph_backend"] in ("neo4j", "kuzu", "none")


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


def test_cors_origin_resolution():
    """Verify CORS origin resolver merges default localhost with custom domains."""
    from app.main import _resolve_allowed_origins

    # Empty env uses defaults
    origins_default = _resolve_allowed_origins("")
    assert "http://localhost:5173" in origins_default
    assert "http://localhost:8000" in origins_default

    # Custom domain merges without losing localhost
    origins_custom = _resolve_allowed_origins("https://bim.example.com, https://app.example.com")
    assert "https://bim.example.com" in origins_custom
    assert "https://app.example.com" in origins_custom
    assert "http://localhost:5173" in origins_custom
    assert "http://localhost:8000" in origins_custom

    # Wildcard origin produces wildcard
    origins_wildcard = _resolve_allowed_origins("*")
    assert origins_wildcard == ["*"]


def test_api_cors_headers():
    """Verify API Gateway returns proper CORS headers for allowed origins."""
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert response.headers.get("access-control-allow-credentials") == "true"


