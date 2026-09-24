"""Tests for OpenCDEDocumentsClient's retry-on-transient-failure behavior.

Exercises the timeout+backoff shape added to mirror
app.services.bsdd_client.BSDDClient._http_get for another external REST API
-- see OpenCDEDocumentsClient._get_with_retry.
"""

from __future__ import annotations

import httpx
import pytest

from app.services.opencde_client import OpenCDEClientError, OpenCDEDocumentsClient


def _client_with(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)


def test_retries_transient_5xx_then_succeeds(monkeypatch):
    monkeypatch.setattr("app.services.opencde_client.time.sleep", lambda _s: None)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503, json={"error": "unavailable"})
        return httpx.Response(200, json=[{"id": "doc1"}])

    doc_client = OpenCDEDocumentsClient(
        base_url="https://fake-cde.example", access_token="tok", client=_client_with(handler)
    )

    docs = doc_client.list_project_documents("proj-1")

    assert calls["n"] == 3
    assert docs == [{"id": "doc1"}]


def test_does_not_retry_real_client_errors(monkeypatch):
    monkeypatch.setattr("app.services.opencde_client.time.sleep", lambda _s: None)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(404, text="not found")

    doc_client = OpenCDEDocumentsClient(
        base_url="https://fake-cde.example", access_token="tok", client=_client_with(handler)
    )

    with pytest.raises(OpenCDEClientError, match="404"):
        doc_client.list_project_documents("proj-1")

    assert calls["n"] == 1


def test_retries_connection_error_then_raises_clean_error(monkeypatch):
    monkeypatch.setattr("app.services.opencde_client.time.sleep", lambda _s: None)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectError("connection refused", request=request)

    doc_client = OpenCDEDocumentsClient(
        base_url="https://fake-cde.example", access_token="tok", client=_client_with(handler)
    )

    with pytest.raises(OpenCDEClientError, match="connection refused"):
        doc_client.list_project_documents("proj-1")

    assert calls["n"] == 3


def test_honors_retry_after_header(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr("app.services.opencde_client.time.sleep", slept.append)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(429, headers={"Retry-After": "7"}, json={})
        return httpx.Response(200, json=[])

    doc_client = OpenCDEDocumentsClient(
        base_url="https://fake-cde.example", access_token="tok", client=_client_with(handler)
    )

    doc_client.list_project_documents("proj-1")

    assert slept == [7.0]
