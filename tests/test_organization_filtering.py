"""Tests for organization-level data filtering across projects, documents, and rules."""

from __future__ import annotations

from starlette.testclient import TestClient

from app.bootstrap import get_container
from app.main import app

client = TestClient(app)


def test_projects_organization_filtering_query_param():
    """Verify ?organization_id filters projects to the requested organization."""
    # Org 1 (Default Org) has grandfathered projects
    resp1 = client.get("/api/projects?organization_id=1")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["total"] >= 1
    for proj in data1["projects"]:
        assert proj.get("organization_id") in (1, None)

    # Org 3 has 0 projects
    resp3 = client.get("/api/projects?organization_id=3")
    assert resp3.status_code == 200
    data3 = resp3.json()
    for proj in data3["projects"]:
        assert proj.get("organization_id") == 3


def test_projects_organization_filtering_header():
    """Verify X-Organization-Id header filters projects."""
    resp = client.get("/api/projects", headers={"X-Organization-Id": "1"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    for proj in data["projects"]:
        assert proj.get("organization_id") in (1, None)


def test_documents_organization_filtering():
    """Verify ?organization_id and X-Organization-Id filter documents by org grants."""
    container = get_container()
    expected_org2_ids = set(container.document_access_service.list_org_grants(2))

    resp_org2 = client.get("/api/documents?organization_id=2")
    assert resp_org2.status_code == 200
    docs_org2 = resp_org2.json()
    doc_ids_org2 = {d["id"] for d in docs_org2}
    assert doc_ids_org2 == expected_org2_ids

    # Header-based scoping
    resp_header = client.get("/api/documents", headers={"X-Organization-Id": "2"})
    assert resp_header.status_code == 200
    docs_header = resp_header.json()
    assert {d["id"] for d in docs_header} == expected_org2_ids

    # Org 1 (Default Org) has all documents granted
    resp_org1 = client.get("/api/documents?organization_id=1")
    assert resp_org1.status_code == 200
    docs_org1 = resp_org1.json()
    assert len(docs_org1) >= len(docs_org2)


def test_rules_organization_filtering():
    """Verify ?organization_id filters rules and rule folders based on ruleset grants."""
    # Org 1 (Default Org) has all rulesets granted
    resp_rules1 = client.get("/api/rules?organization_id=1")
    assert resp_rules1.status_code == 200
    rules1 = resp_rules1.json()
    assert len(rules1) > 0

    resp_folders1 = client.get("/api/rules/folders?organization_id=1")
    assert resp_folders1.status_code == 200
    folders1 = resp_folders1.json()
    assert len(folders1) > 0

    # Org 2 (Archinova)
    resp_rules2 = client.get("/api/rules?organization_id=2")
    assert resp_rules2.status_code == 200
    rules2 = resp_rules2.json()

    resp_folders2 = client.get("/api/rules/folders?organization_id=2")
    assert resp_folders2.status_code == 200
    folders2 = resp_folders2.json()

    # Rule count in Org 2 should only reflect granted rulesets
    assert isinstance(rules2, list)
    assert isinstance(folders2, list)


def test_create_project_organization_rbac_and_persistence():
    """Verify creating a project with organization_id enforces membership and scopes properly."""
    # 1. TEST_USER is in Org 1, not Org 2. Trying to create in Org 2 should fail with 403.
    unauth_resp = client.post("/api/projects", json={
        "name": "Unauthorized Org Project",
        "description": "Should be forbidden",
        "country": "Canada",
        "analysis_type": "Arch",
        "organization_id": 2,
    })
    assert unauth_resp.status_code == 403

    # 2. Creating in Org 1 (which TEST_USER owns) succeeds.
    create_resp = client.post("/api/projects", json={
        "name": "Org1 Scoped Test Project",
        "description": "Integration test for org-scoped project creation",
        "country": "Canada",
        "analysis_type": "Arch",
        "organization_id": 1,
    })
    assert create_resp.status_code in (200, 201)
    created = create_resp.json()
    project_id = created["id"]
    assert created["organization_id"] == 1

    try:
        # Should appear in org 1 listing
        list_org1 = client.get("/api/projects?organization_id=1").json()
        assert any(p["id"] == project_id for p in list_org1["projects"])

        # Should NOT appear in org 3 listing
        list_org3 = client.get("/api/projects?organization_id=3").json()
        assert not any(p["id"] == project_id for p in list_org3["projects"])
    finally:
        # Cleanup
        client.delete(f"/api/projects/{project_id}")
