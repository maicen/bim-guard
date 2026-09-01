"""Tests for OpenCDE Foundation and Documents REST API."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


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


def test_opencde_project_documents_list_and_etags():
    # First create a test project to query
    proj_resp = client.post("/api/projects", json={"name": "OpenCDE Test Hospital", "country": "GB", "analysis_type": "Piping"})
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["id"]

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


def test_opencde_documents_sync():
    proj_resp = client.post("/api/projects", json={"name": "OpenCDE Sync Project", "country": "US", "analysis_type": "Arch"})
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["id"]

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
