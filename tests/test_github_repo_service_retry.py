"""Tests for GitHubRepoService._fetch_git_tree's retry-on-transient-failure behavior.

A single connection blip or 503 used to fall straight through to the
per-repo fallback tree (or an empty tree for any other repo) with no
retry -- see the retry loop added to _fetch_git_tree, mirroring the
bsdd_client/opencde_client retry-with-backoff shape for another external
REST API.
"""

from __future__ import annotations

import httpx

from app.services.github_repo_service import GitHubRepoService

#: app.services.github_repo_service does `import httpx` (not `from httpx
#: import Client`), so monkeypatching `app.services.github_repo_service.httpx.Client`
#: patches the *shared* httpx module's Client attribute -- including this
#: test file's own `httpx.Client` reference. Capturing the real class first
#: avoids the mock handler recursively calling itself as "the patched Client".
_RealClient = httpx.Client


def _service() -> GitHubRepoService:
    # _fetch_git_tree never touches self._repos/self._models_service, so a
    # bare, dependency-free instance is enough to exercise it in isolation.
    svc = object.__new__(GitHubRepoService)
    svc._tree_cache = {}
    return svc


def test_retries_transient_5xx_then_succeeds(monkeypatch):
    monkeypatch.setattr("app.services.github_repo_service.time.sleep", lambda _s: None)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503, json={})
        return httpx.Response(200, json={"tree": [{"path": "a.ifc", "type": "blob", "size": 1}]})

    monkeypatch.setattr(
        "app.services.github_repo_service.httpx.Client",
        lambda *a, **kw: _RealClient(transport=httpx.MockTransport(handler), timeout=5.0),
    )

    tree = _service()._fetch_git_tree("owner", "repo", "main")

    assert calls["n"] == 3
    assert tree == [{"path": "a.ifc", "type": "blob", "size": 1}]


def test_no_retry_on_404_falls_back_immediately(monkeypatch):
    monkeypatch.setattr("app.services.github_repo_service.time.sleep", lambda _s: None)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(404, json={})

    monkeypatch.setattr(
        "app.services.github_repo_service.httpx.Client",
        lambda *a, **kw: _RealClient(transport=httpx.MockTransport(handler), timeout=5.0),
    )

    tree = _service()._fetch_git_tree("someowner", "somerepo", "main")

    assert calls["n"] == 1
    assert tree == []


def test_exhausts_retries_on_connection_error_then_falls_back(monkeypatch):
    monkeypatch.setattr("app.services.github_repo_service.time.sleep", lambda _s: None)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectError("refused", request=request)

    monkeypatch.setattr(
        "app.services.github_repo_service.httpx.Client",
        lambda *a, **kw: _RealClient(transport=httpx.MockTransport(handler), timeout=5.0),
    )

    tree = _service()._fetch_git_tree("someowner", "somerepo", "main")

    assert calls["n"] == 3
    assert tree == []


def test_transient_failure_uses_the_static_fallback_tree(monkeypatch):
    """The one repo with a hardcoded fallback still gets it once retries exhaust."""
    monkeypatch.setattr("app.services.github_repo_service.time.sleep", lambda _s: None)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    monkeypatch.setattr(
        "app.services.github_repo_service.httpx.Client",
        lambda *a, **kw: _RealClient(transport=httpx.MockTransport(handler), timeout=5.0),
    )

    tree = _service()._fetch_git_tree("maicen", "bimguard-test-models", "main")

    assert len(tree) > 0
