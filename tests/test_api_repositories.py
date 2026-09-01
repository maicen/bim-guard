"""Test suite for GitHub repository project storage sources, CRUD, structure reading, and model import endpoints."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.services.github_repo_service import parse_github_url


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Provide a TestClient for FastAPI application endpoints."""
    return TestClient(app, raise_server_exceptions=False)


def test_parse_github_url() -> None:
    """Test URL parsing for various GitHub repository URL formats."""
    owner, repo = parse_github_url("https://github.com/maicen/bimguard-test-models")
    assert owner == "maicen"
    assert repo == "bimguard-test-models"

    owner2, repo2 = parse_github_url("https://github.com/owner/sample-repo.git/")
    assert owner2 == "owner"
    assert repo2 == "sample-repo"

    owner3, repo3 = parse_github_url("owner/repo-name")
    assert owner3 == "owner"
    assert repo3 == "repo-name"

    with pytest.raises(ValueError):
        parse_github_url("invalid-url-format")


def test_list_repositories(client: TestClient) -> None:
    """GET /api/repositories returns registered repositories including seeded default."""
    response = client.get("/api/repositories")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    # Check default pre-seeded repo is present
    seeded = next((r for r in data if "bimguard-test-models" in r["name"]), None)
    assert seeded is not None
    assert seeded["owner"] == "maicen"
    assert seeded["url"] == "https://github.com/maicen/bimguard-test-models"


def test_repository_crud_flow(client: TestClient) -> None:
    """POST, GET, PUT, and DELETE /api/repositories endpoints execute full CRUD cycle."""
    # 1. Create Repository
    create_resp = client.post(
        "/api/repositories",
        json={
            "url": "https://github.com/test-owner/test-model-repo",
            "name": "Custom Test Repo",
            "branch": "main",
            "description": "Integration test repository",
        },
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    repo_id = created["id"]
    assert created["name"] == "Custom Test Repo font" or created["name"] == "Custom Test Repo"
    assert created["owner"] == "test-owner"
    assert created["url"] == "https://github.com/test-owner/test-model-repo"

    try:
        # 2. Get Repository by ID
        get_resp = client.get(f"/api/repositories/{repo_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == repo_id

        # 3. Update Repository
        update_resp = client.put(
            f"/api/repositories/{repo_id}",
            json={
                "name": "Updated Test Repo Name",
                "branch": "develop",
                "description": "Updated description",
            },
        )
        assert update_resp.status_code == 200
        updated = update_resp.json()
        assert updated["name"] == "Updated Test Repo Name"
        assert updated["branch"] == "develop"

    finally:
        # 4. Delete Repository
        delete_resp = client.delete(f"/api/repositories/{repo_id}")
        assert delete_resp.status_code == 204

        # Verify deletion
        get_deleted = client.get(f"/api/repositories/{repo_id}")
        assert get_deleted.status_code == 404


def test_repository_structure_endpoint(client: TestClient) -> None:
    """GET /api/repositories/{id}/structure returns repository items and categories."""
    repos_resp = client.get("/api/repositories")
    assert repos_resp.status_code == 200
    repos = repos_resp.json()
    seeded = next((r for r in repos if "bimguard-test-models" in r["name"]), repos[0])
    repo_id = seeded["id"]

    struct_resp = client.get(f"/api/repositories/{repo_id}/structure")
    assert struct_resp.status_code == 200
    data = struct_resp.json()
    assert data["repo_id"] == repo_id
    assert data["owner"] == "maicen"
    assert data["name"] == "bimguard-test-models"
    assert data["models_count"] > 0
    assert isinstance(data["items"], list)

    # Verify items contain IFC models
    ifc_item = next((item for item in data["items"] if item["extension"] == ".ifc"), None)
    assert ifc_item is not None
    assert "https://raw.githubusercontent.com/maicen/bimguard-test-models" in ifc_item["download_url"]


def test_repository_import_model_endpoint(client: TestClient) -> None:
    """POST /api/repositories/{id}/import imports an IFC model from repo as a new project."""
    repos_resp = client.get("/api/repositories")
    repos = repos_resp.json()
    seeded = next((r for r in repos if "bimguard-test-models" in r["name"]), repos[0])
    repo_id = seeded["id"]

    import_resp = client.post(
        f"/api/repositories/{repo_id}/import",
        json={
            "file_path": "models/hospital/Clinic_Architectural.ifc",
            "name": "Clinic Architectural Imported Project",
            "country": "US",
            "analysis_type": "Arch",
        },
    )
    assert import_resp.status_code == 201
    imported = import_resp.json()
    project_id = imported["id"]
    assert imported["name"] == "Clinic Architectural Imported Project"
    assert imported["analysis_type"] == "Arch"
    assert "raw.githubusercontent.com" in imported["ifc_file_path"]

    # Cleanup imported project
    client.delete(f"/api/projects/{project_id}")
