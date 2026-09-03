"""Tests for OpenCDE Foundation and Documents REST API."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture
def cde_test_project():
    """Create a project for the test and delete it afterward.

    These tests exercise the real projects API/DB, so without teardown every
    run left an orphaned "OpenCDE ..." project behind.
    """

    def _create(name: str, country: str, analysis_type: str) -> int:
        resp = client.post(
            "/api/projects",
            json={"name": name, "country": country, "analysis_type": analysis_type},
        )
        assert resp.status_code == 201
        project_id = resp.json()["id"]
        created_ids.append(project_id)
        return project_id

    created_ids: list[int] = []
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
