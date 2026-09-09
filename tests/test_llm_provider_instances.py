"""Test suite for candidate LLM provider connection testing (pre-save)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import httpx
import pytest
from starlette.testclient import TestClient

from app.api.dependencies import get_membership_service, get_profile_service
from app.main import app
from app.services.llm_provider_instances_service import LLMProviderInstancesService


def _install_transport(monkeypatch, handler):
    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)


def test_service_test_connection_success(monkeypatch):
    """Test candidate connection succeeds against a mock driver."""
    def handler(request):
        assert str(request.url) == "http://ollama.test:11434/api/tags"
        return httpx.Response(
            200,
            json={"models": [{"name": "qwen2.5:7b"}, {"name": "llama3.2:latest"}]},
        )

    _install_transport(monkeypatch, handler)

    service = LLMProviderInstancesService(MagicMock())
    result = asyncio.run(
        service.test_connection("ollama", api_base="http://ollama.test:11434")
    )
    assert result.ok is True
    assert "2 model(s) available" in result.detail


def test_service_test_connection_missing_required_key():
    """Testing an instance kind that requires an API key without one raises ValueError."""
    service = LLMProviderInstancesService(MagicMock())
    with pytest.raises(ValueError, match="api_key is required"):
        asyncio.run(service.test_connection("openai", api_key=""))


def test_service_test_connection_invalid_kind():
    """Testing an unknown provider kind raises ValueError."""
    service = LLMProviderInstancesService(MagicMock())
    with pytest.raises(ValueError, match="kind must be one of"):
        asyncio.run(service.test_connection("non_existent_kind"))


def test_api_test_connection_endpoint(monkeypatch):
    """POST /api/organizations/{org_id}/llm-providers/test-connection verifies candidate credentials."""
    def handler(request):
        return httpx.Response(
            200,
            json={"models": [{"name": "llama3.2:latest"}]},
        )

    _install_transport(monkeypatch, handler)

    mock_profile_service = MagicMock()
    mock_profile_service.is_superadmin.return_value = True

    mock_membership_service = MagicMock()
    mock_membership_service.role_for_user.return_value = "admin"
    mock_membership_service.get_organization.return_value = {"id": 1, "name": "Default"}

    app.dependency_overrides[get_profile_service] = lambda: mock_profile_service
    app.dependency_overrides[get_membership_service] = lambda: mock_membership_service

    try:
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/organizations/1/llm-providers/test-connection",
            json={
                "kind": "ollama",
                "api_base": "http://ollama.test:11434",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "1 model(s) available" in data["detail"]

        # Missing required key returns 400 Bad Request
        resp_bad = client.post(
            "/api/organizations/1/llm-providers/test-connection",
            json={
                "kind": "openai",
                "api_key": "",
            },
        )
        assert resp_bad.status_code == 400
        assert "api_key is required" in resp_bad.json()["detail"]

        # Unknown kind returns 400 Bad Request
        resp_invalid_kind = client.post(
            "/api/organizations/1/llm-providers/test-connection",
            json={
                "kind": "invalid_kind_123",
            },
        )
        assert resp_invalid_kind.status_code == 400
    finally:
        app.dependency_overrides.pop(get_profile_service, None)
        app.dependency_overrides.pop(get_membership_service, None)
