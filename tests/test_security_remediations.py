"""Security remediation regression tests covering BG-SEC-01 through BG-SEC-08.

Validates fixes for:
- BG-SEC-01: SPA Path Traversal & .env Leakage
- BG-SEC-02: Rules & Rule Snapshot Multi-Tenant Authorization
- BG-SEC-03: Document Authorization & IDOR Protection
- BG-SEC-04: OpenCDE & BCF Project Scoping
- BG-SEC-06: Server-Side Request Forgery (SSRF) Protection
- BG-SEC-07: Missing Security Headers & Insecure CORS
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.testclient import TestClient

from app.auth import CurrentUser
from app.main import app
from app.services.object_storage import ObjectStorage
from app.services.ssrf_protection import is_safe_url

client = TestClient(app)


# ---------------------------------------------------------------------------
# BG-SEC-01: SPA Path Traversal & Information Disclosure
# ---------------------------------------------------------------------------


def test_spa_path_traversal_blocked_env_leak():
    """Verify encoded directory traversal attempts cannot escape frontend/dist to access .env."""
    response = client.get("/..%2f..%2f.env")
    assert response.status_code == 404
    assert "SUPABASE_SERVICE_ROLE_KEY" not in response.text
    assert "SECRET" not in response.text


def test_spa_path_traversal_blocked_pyproject():
    """Verify traversal attempts to reach pyproject.toml in repo root fail with 404."""
    response = client.get("/..%2f..%2fpyproject.toml")
    assert response.status_code == 404
    assert "[project]" not in response.text


def test_spa_path_traversal_blocked_readme():
    """Verify traversal attempts to reach README.md fail with 404."""
    response = client.get("/..%2f..%2fREADME.md")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# BG-SEC-07: Security Headers & CORS Policy
# ---------------------------------------------------------------------------


def test_security_headers_present_on_api_responses():
    """Verify security headers are injected on responses."""
    response = client.get("/api/health")
    assert response.status_code == 200
    headers = response.headers

    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "geolocation=()" in headers.get("Permissions-Policy", "")
    assert "default-src 'self'" in headers.get("Content-Security-Policy", "")
    assert "worker-src 'self' blob:" in headers.get("Content-Security-Policy", "")
    assert "child-src 'self' blob:" in headers.get("Content-Security-Policy", "")
    assert "https://static.cloudflareinsights.com" in headers.get("Content-Security-Policy", "")


def test_security_headers_present_on_spa_routes():
    """Verify security headers are injected on root/SPA responses."""
    response = client.get("/")
    assert response.status_code == 200
    headers = response.headers

    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"


# ---------------------------------------------------------------------------
# BG-SEC-06: SSRF Protection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "unsafe_url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://169.254.169.254/latest/api/token",
        "http://127.0.0.1:8000/internal",
        "http://127.0.0.1:22",
        "http://localhost:8080/admin",
        "http://10.0.0.1/secret",
        "http://192.168.1.1/router",
        "http://172.16.0.1/api",
        "file:///etc/passwd",
        "gopher://127.0.0.1:25/",
        "ftp://10.0.0.1/resource",
        "javascript:alert(1)",
        "",
        "not-a-url",
    ],
)
def test_ssrf_protection_blocks_dangerous_urls(unsafe_url: str):
    """Verify SSRF protection utility blocks loopback, private IPs, cloud metadata, and bad schemes."""
    assert is_safe_url(unsafe_url, allow_localhost=False) is False


def test_ssrf_protection_allows_valid_public_urls():
    """Verify SSRF protection allows external public HTTPS/HTTP endpoints."""
    assert is_safe_url("https://api.openai.com/v1/models") is True
    assert is_safe_url("https://raw.githubusercontent.com/org/repo/main/model.ifc") is True
    assert is_safe_url("https://api.anthropic.com/v1/messages") is True


def test_ssrf_protection_localhost_override_for_ollama():
    """Verify localhost is strictly blocked by default but allowed only when explicitly permitted."""
    assert is_safe_url("http://localhost:11434/api/generate", allow_localhost=False) is False
    assert is_safe_url("http://127.0.0.1:11434/api/generate", allow_localhost=False) is False

    assert is_safe_url("http://localhost:11434/api/generate", allow_localhost=True) is True
    assert is_safe_url("http://127.0.0.1:11434/api/generate", allow_localhost=True) is True

    # Cloud metadata is never allowed even when allow_localhost is True
    assert is_safe_url("http://169.254.169.254/latest/meta-data", allow_localhost=True) is False


def test_object_storage_blocks_ssrf_url():
    """Verify ObjectStorage rejects download of cloud metadata and internal IPs."""
    storage = ObjectStorage()
    result = storage.materialize_local_path("http://169.254.169.254/latest/meta-data/iam/credentials")
    assert result is None

    result_local = storage.materialize_local_path("http://127.0.0.1:8000/internal_model.ifc")
    assert result_local is None


# ---------------------------------------------------------------------------
# BG-SEC-02: Rules & Snapshot Multi-Tenant Authorization
# ---------------------------------------------------------------------------


def test_ruleset_access_checker_enforces_organization_grants():
    """Verify _require_ruleset_grant rejects mutation by non-superadmins without grant."""
    from unittest.mock import MagicMock

    from app.api.rules import _require_ruleset_grant

    user = CurrentUser(id="user-123", email="u@example.com", claims={})
    memberships = MagicMock()
    ruleset_access = MagicMock()
    profiles = MagicMock()

    # Case 1: Superadmin bypass
    profiles.is_superadmin.return_value = True
    # Should not raise
    _require_ruleset_grant("PRIVATE-RULESET", user, memberships, ruleset_access, profiles)

    # Case 2: Regular user with grant
    profiles.is_superadmin.return_value = False
    memberships.org_ids_for_user.return_value = [10]
    ruleset_access.list_org_grants.return_value = ["PRIVATE-RULESET"]
    # Should not raise
    _require_ruleset_grant("PRIVATE-RULESET", user, memberships, ruleset_access, profiles)

    # Case 3: Regular user without grant -> 403 Forbidden
    ruleset_access.list_org_grants.return_value = ["OTHER-RULESET"]
    with pytest.raises(HTTPException) as exc_info:
        _require_ruleset_grant("PRIVATE-RULESET", user, memberships, ruleset_access, profiles)
    assert exc_info.value.status_code == 403
    assert "has not been granted access" in exc_info.value.detail


# ---------------------------------------------------------------------------
# BG-SEC-03: Document Authorization & IDOR Protection
# ---------------------------------------------------------------------------


def test_document_access_checker_enforces_organization_grants():
    """Verify _require_document_grant rejects document access by non-superadmins without grant."""
    from unittest.mock import MagicMock

    from app.api.documents import _require_document_grant

    user = CurrentUser(id="user-123", email="u@example.com", claims={})
    memberships = MagicMock()
    document_access = MagicMock()
    profiles = MagicMock()

    # Case 1: Superadmin bypass
    profiles.is_superadmin.return_value = True
    _require_document_grant(999, user, memberships, document_access, profiles)

    # Case 2: Regular user with grant
    profiles.is_superadmin.return_value = False
    memberships.org_ids_for_user.return_value = [5]
    document_access.list_org_grants.return_value = [999]
    _require_document_grant(999, user, memberships, document_access, profiles)

    # Case 3: Regular user without grant -> 404 Not Found (not 403, to avoid
    # confirming the document's existence to an unauthorized caller).
    document_access.list_org_grants.return_value = [100, 101]
    with pytest.raises(HTTPException) as exc_info:
        _require_document_grant(999, user, memberships, document_access, profiles)
    assert exc_info.value.status_code == 404
    assert "Document 999 not found" in exc_info.value.detail


def test_document_route_returns_404_for_ungranted_document():
    """Integration-level check that GET /api/documents/{id} is wired to the real DocumentAccessChecker.

    Not just that the checker function itself works. tests/conftest.py overrides get_document_access_checker to a permissive
    no-op for every other test file's convenience; this test removes that
    override for the duration of the call so the real dependency chain
    (memberships/document_access/profiles, all hitting the actual services)
    runs end to end, the same way a real unauthorized request would.
    """
    from app.api.documents import get_document_access_checker

    original_override = app.dependency_overrides.pop(get_document_access_checker, None)
    try:
        response = client.get("/api/documents/999999999")
        assert response.status_code == 404
    finally:
        if original_override is not None:
            app.dependency_overrides[get_document_access_checker] = original_override


# ---------------------------------------------------------------------------
# BG-SEC-04: OpenCDE & BCF Project Access Scoping
# ---------------------------------------------------------------------------


def test_bcf_project_access_scoping():
    """Verify _require_bcf_project_access rejects access to projects outside caller's tenant."""
    from unittest.mock import MagicMock

    from app.api.bcf_routes import _require_bcf_project_access

    user = CurrentUser(id="user-123", email="u@example.com", claims={})
    projects_service = MagicMock()
    memberships = MagicMock()
    profiles = MagicMock()

    profiles.is_superadmin.return_value = False
    # Project 42 exists in DB
    projects_service.get_project.return_value = {"id": 42, "name": "Confidential Project", "organization_id": 99}
    # User belongs to org 5, not org 99
    memberships.organizations_with_project_access.return_value = {99}
    memberships.org_ids_for_user.return_value = {5}

    with pytest.raises(HTTPException) as exc_info:
        _require_bcf_project_access("42", user, projects_service, memberships, profiles)
    assert exc_info.value.status_code == 404


def test_bcf_topic_and_viewpoint_routes_enforce_project_access():
    """Integration check that every BCF v2.1 sub-resource route calls _require_bcf_project_access.

    Not just list_topics/create_topic. Unlike test_bcf_project_access_scoping above (which calls the checker
    function directly), this hits the real HTTP routes through TestClient so a
    route that forgets to wire the dependency/call in would fail here even
    though the checker itself works fine in isolation.
    """
    from app.api.dependencies import get_projects_service

    class _OtherOrgProjectsService:
        def get_project(self, project_id: int) -> dict:
            return {"id": project_id, "name": "Other Org Project", "organization_id": 999999}

        def list_projects(self) -> list[dict]:
            return [self.get_project(1)]

    app.dependency_overrides[get_projects_service] = lambda: _OtherOrgProjectsService()
    try:
        routes = [
            ("GET", "/api/bcf/v2.1/projects/1/topics/TOPIC-1", None),
            ("PUT", "/api/bcf/v2.1/projects/1/topics/TOPIC-1", {}),
            ("DELETE", "/api/bcf/v2.1/projects/1/topics/TOPIC-1", None),
            ("GET", "/api/bcf/v2.1/projects/1/topics/TOPIC-1/comments", None),
            ("POST", "/api/bcf/v2.1/projects/1/topics/TOPIC-1/comments", {"comment": "test"}),
            ("GET", "/api/bcf/v2.1/projects/1/topics/TOPIC-1/viewpoints", None),
            ("POST", "/api/bcf/v2.1/projects/1/topics/TOPIC-1/viewpoints", {}),
            ("GET", "/api/bcf/v2.1/projects/1/topics/TOPIC-1/viewpoints/VP-1", None),
            ("GET", "/api/bcf/v2.1/projects/1/topics/TOPIC-1/viewpoints/VP-1/snapshot", None),
        ]
        for method, path, body in routes:
            response = client.request(method, path, json=body)
            assert response.status_code == 404, (
                f"{method} {path} returned {response.status_code}, expected 404 "
                "(project belongs to another organization) -- route may be missing "
                "_require_bcf_project_access."
            )
    finally:
        del app.dependency_overrides[get_projects_service]
