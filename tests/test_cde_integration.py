"""Tests for OpenCDE Foundation and Documents REST API."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.report_artifacts import ReportArtifactService

client = TestClient(app)


@pytest.fixture
def cde_test_project():
    """Create a project for the test and delete it afterward.

    These tests exercise the real projects API/DB, so without teardown every
    run left an orphaned "OpenCDE ..." project behind.
    """
    created_ids: list[int] = []

    def _create(name: str, country: str, analysis_type: str) -> int:
        resp = client.post(
            "/api/projects",
            json={
                "name": name,
                "short_name": name[:24],
                "project_code": f"CDE{len(created_ids)}",
                "country": country,
                "analysis_type": analysis_type,
            },
        )
        assert resp.status_code == 201
        project_id = resp.json()["id"]
        created_ids.append(project_id)
        return project_id

    yield _create
    for project_id in created_ids:
        client.delete(f"/api/projects/{project_id}")


def test_opencde_versions_discovery():
    response = client.get("/api/cde/versions")
    assert response.status_code == 200
    data = response.json()
    assert "versions" in data
    types = {v["api_type"] for v in data["versions"]}
    assert "foundation" in types
    assert "documents" in types
    assert "bcf" in types


def test_opencde_user_profile():
    response = client.get("/api/cde/v1/user")
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "name" in data
    assert "role" in data


def test_opencde_auth_config_and_token():
    response = client.get("/api/cde/v1/auth/config")
    assert response.status_code == 200
    data = response.json()
    assert "oauth2_token_url" in data

    token_resp = client.post("/api/cde/v1/auth/token", json={"grant_type": "client_credentials"})
    assert token_resp.status_code == 200
    token_data = token_resp.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "Bearer"


def test_opencde_project_documents_list_and_etags(cde_test_project):
    # First create a test project to query
    proj_id = cde_test_project("OpenCDE Test Hospital", "GB", "Piping")

    # Query OpenCDE documents
    response = client.get(f"/api/cde/v1/projects/{proj_id}/documents")
    assert response.status_code == 200
    etag = response.headers.get("ETag")
    assert etag is not None

    # Test conditional GET with If-None-Match
    cached_response = client.get(
        f"/api/cde/v1/projects/{proj_id}/documents",
        headers={"If-None-Match": etag},
    )
    assert cached_response.status_code == 304


def test_opencde_documents_sync(cde_test_project):
    proj_id = cde_test_project("OpenCDE Sync Project", "US", "Arch")

    payload = {
        "cde_server_url": "https://cde.autodesk.com/acc/v1",
        "project_id": proj_id,
        "external_project_id": "ACC-PRJ-8829",
        "document_ids": ["MODEL-001", "SPEC-002"],
    }
    response = client.post(f"/api/cde/v1/projects/{proj_id}/documents/sync", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["synced_documents_count"] == 2


def test_gate1_promote_succeeds_with_no_outstanding_issues(cde_test_project):
    proj_id = cde_test_project("Gate1 Clean Project", "GB", "Piping")

    response = client.post("/api/cde/gate1/promote", json={"project_id": proj_id})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["cde_state"] == "SHARED"
    assert data["disposition"] == "ACCEPTED"


def test_gate1_promote_blocked_by_persisted_critical_issues(cde_test_project):
    """Gate 1 must reflect real findings, not the previous hardcoded pass.

    Regression test for the bug where `promote_gate1` always passed
    `critical_issues_count=0` regardless of actual compliance results.
    """
    proj_id = cde_test_project("Gate1 Blocked Project", "GB", "Piping")

    report_service = ReportArtifactService()
    artifact = report_service.persist_bcf(
        proj_id,
        [
            {
                "guid": "issue-1",
                "element_guid": "elem-1",
                "rule_id": "GC-001.01",
                "title": "Dissimilar metal coupling",
                "priority": "critical",
            }
        ],
    )
    assert artifact is not None

    try:
        response = client.post("/api/cde/gate1/promote", json={"project_id": proj_id})
        assert response.status_code == 400
        assert "critical compliance issues" in response.json()["detail"]
    finally:
        report_service.delete_bcf(artifact["id"])


def test_opencde_webhook_event():
    payload = {
        "event_type": "document.published",
        "external_project_id": "BIM360-9901",
        "document_id": "DOC-772",
        "document_name": "Hospital_MEP_Coordination.ifc",
        "download_url": "https://cde.example.com/download/DOC-772.ifc",
    }
    response = client.post("/api/cde/v1/webhooks/cde-sync", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"
    assert data["event"] == "document.published"
