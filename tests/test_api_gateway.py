"""Tests for FastAPI API Gateway bootstrap, health check, and OpenAPI docs."""

from __future__ import annotations

import asyncio
import json

from httpx import ConnectError
from starlette.requests import Request
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


def test_supabase_transport_error_returns_clean_503():
    """A network-level Supabase outage should surface as JSON 503, not a bare 500.

    Without the handler, an unreachable Supabase raises `httpx.TransportError`
    up through the route unhandled, and Starlette's default error response is
    plain text with no JSON body -- exactly what leaves the frontend showing a
    bare "Internal Server Error (500)" instead of a real message.
    """
    from app.main import supabase_transport_error_handler

    scope = {"type": "http", "method": "POST", "path": "/api/projects", "headers": []}
    request = Request(scope)
    exc = ConnectError("Connection refused")

    response = asyncio.run(supabase_transport_error_handler(request, exc))

    assert response.status_code == 503
    assert json.loads(response.body) == {
        "detail": "Database temporarily unavailable. Please try again."
    }


def test_request_validation_error_flattens_to_string_detail():
    """A 422's FastAPI-default array body should flatten to this app's plain-string convention.

    Every other error response in the app is ``{"detail": "<string>"}``
    (``HTTPException(detail=...)``); a Pydantic validation failure defaults
    instead to ``{"detail": [{"loc": [...], "msg": ...}, ...]}``. The frontend's
    ``handleResponse`` (frontend/src/lib/api.ts) already flattens that array
    client-side for display -- this handler makes the wire shape consistent
    for any other consumer by flattening it the same way server-side.
    """
    from fastapi.exceptions import RequestValidationError

    from app.main import request_validation_error_handler

    scope = {"type": "http", "method": "POST", "path": "/api/rules", "headers": []}
    request = Request(scope)
    exc = RequestValidationError(
        [
            {"loc": ("body", "rule_id"), "msg": "field required", "type": "missing"},
            {"loc": ("body",), "msg": "value is not a valid dict", "type": "type_error.dict"},
        ]
    )

    response = asyncio.run(request_validation_error_handler(request, exc))

    assert response.status_code == 422
    assert json.loads(response.body) == {
        "detail": "rule_id: field required; value is not a valid dict"
    }


def test_unhandled_exception_returns_clean_500():
    """An exception with no matching handler should surface as JSON 500 with logging.

    Without this handler, an unhandled exception falls through to Starlette's
    default error response -- plain text, no JSON body -- so the frontend's
    error parsing has nothing to read and the failure is invisible in logs.
    """
    from app.main import unhandled_exception_handler

    scope = {"type": "http", "method": "GET", "path": "/api/projects/1", "headers": []}
    request = Request(scope)
    exc = RuntimeError("something broke")

    response = asyncio.run(unhandled_exception_handler(request, exc))

    assert response.status_code == 500
    assert json.loads(response.body) == {"detail": "Internal server error."}


def test_unhandled_exception_handler_does_not_shadow_http_exception():
    """FastAPI's default HTTPException handling must still win over the catch-all.

    Registering @app.exception_handler(Exception) risks shadowing FastAPI's
    own default HTTPException handler if handler lookup didn't prefer the
    more specific type; Starlette's ExceptionMiddleware resolves by walking
    the exception's MRO and picking the most specific registered handler, so
    a plain HTTPException raised by a route must still produce its own
    status/detail, not the catch-all's generic 500.
    """
    response = client.get("/api/projects/999999999")
    assert response.status_code in (401, 404)
    assert response.json()["detail"] != "Internal server error."


