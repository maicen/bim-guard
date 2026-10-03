"""Tests for the /mcp Model Context Protocol endpoint."""

from __future__ import annotations

import json

import pytest
from starlette.testclient import TestClient

from app import mcp_server
from app.auth import CurrentUser
from app.main import app

pytestmark = pytest.mark.api

HEADERS = {
    "Authorization": "Bearer test-token",
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


@pytest.fixture
def mcp_client(monkeypatch):
    """Yield a client with the app lifespan running and token verification stubbed."""
    monkeypatch.setattr(
        mcp_server, "_verify", lambda token: CurrentUser(id="u1", email=None, claims={})
    )
    with TestClient(app) as client:
        yield client


def _rpc(client: TestClient, method: str, params: dict | None = None, headers=HEADERS):
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    return client.post("/mcp/", json=body, headers=headers)


def test_mcp_rejects_missing_token(mcp_client):
    response = _rpc(mcp_client, "tools/list", headers={k: v for k, v in HEADERS.items() if k != "Authorization"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Bearer")


def test_mcp_rejects_invalid_token(monkeypatch, mcp_client):
    from fastapi import HTTPException

    def reject(token):
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token")

    monkeypatch.setattr(mcp_server, "_verify", reject)
    assert _rpc(mcp_client, "tools/list").status_code == 401


def test_mcp_lists_tools(mcp_client):
    response = _rpc(mcp_client, "tools/list")
    assert response.status_code == 200
    names = {t["name"] for t in response.json()["result"]["tools"]}
    assert {
        "list_projects",
        "list_rulesets",
        "list_rules",
        "run_architecture_analysis",
        "get_analysis_status",
        "get_analysis_results",
    } <= names


def test_mcp_tool_forwards_to_api(mcp_client):
    response = _rpc(
        mcp_client, "tools/call", {"name": "get_analysis_status", "arguments": {"project_id": 999_999_999}}
    )
    result = response.json()["result"]
    assert not result.get("isError")
    assert json.loads(result["content"][0]["text"])["project_id"] == 999_999_999


def test_mcp_tool_surfaces_api_errors(mcp_client):
    response = _rpc(
        mcp_client,
        "tools/call",
        {"name": "run_architecture_analysis", "arguments": {"project_id": 999_999_999}},
    )
    result = response.json()["result"]
    assert result["isError"] is True
    assert "failed (" in result["content"][0]["text"]


@pytest.fixture
def supabase_env(monkeypatch):
    monkeypatch.setenv("PUBLIC_SUPABASE_URL", "https://supabase.example.test/")
    monkeypatch.setenv("BIM_GUARD_PUBLIC_URL", "https://app.example.test")


@pytest.mark.parametrize(
    "path",
    ["/.well-known/oauth-protected-resource", "/.well-known/oauth-protected-resource/mcp"],
)
def test_protected_resource_metadata(mcp_client, supabase_env, path):
    response = mcp_client.get(path)
    assert response.status_code == 200
    assert response.json() == {
        "resource": "https://app.example.test/mcp",
        "authorization_servers": ["https://supabase.example.test/auth/v1"],
        "bearer_methods_supported": ["header"],
        "resource_name": "BIM-Guard",
    }


def test_unauthenticated_challenge_points_at_metadata(mcp_client, supabase_env):
    response = _rpc(mcp_client, "tools/list", headers={"Accept": HEADERS["Accept"]})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == (
        'Bearer resource_metadata="https://app.example.test/.well-known/oauth-protected-resource"'
    )


def test_mcp_lists_exploration_tools(mcp_client):
    names = {t["name"] for t in _rpc(mcp_client, "tools/list").json()["result"]["tools"]}
    assert {
        "list_models",
        "list_documents",
        "find_elements",
        "ask_project_knowledge",
        "list_cypher_queries",
        "run_cypher_query",
    } <= names
    # Free-form Cypher must never be reachable: only named presets are.
    run = next(
        t for t in _rpc(mcp_client, "tools/list").json()["result"]["tools"] if t["name"] == "run_cypher_query"
    )
    assert "cypher" not in run["inputSchema"]["properties"]


def test_list_cypher_queries_includes_class_search(mcp_client):
    result = _rpc(mcp_client, "tools/call", {"name": "list_cypher_queries", "arguments": {}}).json()["result"]
    presets = json.loads(result["content"][0]["text"])
    by_key = {p["key"]: p for p in presets}
    assert by_key["elements-by-ifc-class"]["params"] == ["ifc_class"]


def test_unknown_cypher_query_is_rejected(mcp_client):
    result = _rpc(
        mcp_client,
        "tools/call",
        {"name": "run_cypher_query", "arguments": {"project_id": 1, "query": "MATCH (n) RETURN n"}},
    ).json()["result"]
    assert result["isError"] is True
