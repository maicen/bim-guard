"""Route-level tests for the decoupled FastAPI application and Svelte SPA serving."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    """One test client for the FastAPI application."""
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# API Gateway Core Endpoints
# ---------------------------------------------------------------------------


def test_api_health_check(client: TestClient) -> None:
    """Verify /api/health endpoint is operational."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "bim-guard-api"


def test_api_docs_available(client: TestClient) -> None:
    """Verify Swagger UI docs are served at /api/docs."""
    response = client.get("/api/docs")
    assert response.status_code == 200
    assert "swagger-ui" in response.text.lower()


def test_api_openapi_json(client: TestClient) -> None:
    """Verify OpenAPI schema is accessible."""
    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "paths" in data
    assert "/api/projects" in data["paths"]


# ---------------------------------------------------------------------------
# Static Assets
# ---------------------------------------------------------------------------


def test_known_static_asset_is_served(client: TestClient) -> None:
    """Verify static files are served properly."""
    response = client.get("/static/js/ifc-viewer.js")
    assert response.status_code == 200
    assert len(response.content) > 0


def test_missing_static_asset_is_not_a_server_error(client: TestClient) -> None:
    """A missing static file returns 404, not a 500 error."""
    assert client.get("/static/js/does-not-exist.js").status_code == 404


# ---------------------------------------------------------------------------
# Svelte 5 SPA Client Serving & Route Fallback
# ---------------------------------------------------------------------------

SPA_ROUTES = [
    "/",
    "/dashboard",
    "/projects",
    "/viewer",
    "/documents",
    "/rules",
    "/analyze",
    "/reports",
    "/settings",
]


@pytest.mark.parametrize("path", SPA_ROUTES)
def test_spa_routes_served_without_error(client: TestClient, path: str) -> None:
    """Every SPA client route returns 200 without server exceptions."""
    response = client.get(path)
    assert response.status_code == 200, f"{path} returned {response.status_code}"


def test_head_is_supported_on_root(client: TestClient) -> None:
    """HEAD request is supported on the root route for health probes."""
    assert client.head("/").status_code < 400
