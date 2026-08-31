"""Tests for /api/projects endpoints."""

from __future__ import annotations

from starlette.testclient import TestClient

from app.main import app

client = TestClient(app)
NONEXISTENT_ID = 999_999_999


def test_list_projects():
    """Verify /api/projects lists projects with total count."""
    response = client.get("/api/projects")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert isinstance(data["projects"], list)


def test_get_project_not_found():
    """Verify requesting a non-existent project returns 404."""
    response = client.get(f"/api/projects/{NONEXISTENT_ID}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_create_project_validation_failure():
    """Verify creating a project with empty name fails with 422 Unprocessable Entity."""
    response = client.post("/api/projects", json={"name": "", "description": "test"})
    assert response.status_code == 422


def test_download_ifc_not_found():
    """Verify IFC download for non-existent project returns 404."""
    response = client.get(f"/api/projects/{NONEXISTENT_ID}/ifc")
    assert response.status_code == 404



def test_project_options_offer_building_codes():
    """Verify /api/projects/options serves the building-code catalog the wizard filters."""
    response = client.get("/api/projects/options")
    assert response.status_code == 200
    codes = response.json()["building_codes"]
    assert codes, "the wizard's step-3 selector has nothing to render without codes"

    by_id = {code["id"]: code for code in codes}
    # Ontario Part 9 is bundled as a seeded ruleset, so the catalog must name it
    # and point at the rules the engines actually execute.
    assert by_id["OBC-PART9"]["jurisdictions"] == ["Canada"]
    assert by_id["OBC-PART9"]["ruleset_id"] == "BUILDING-CODE-PART9"
    # The international fallback carries no jurisdictions, which is how it stays
    # on offer for the countries with no bundled national code.
    assert by_id["ISO-IFC-INTL"]["jurisdictions"] == []


def test_building_codes_filter_by_jurisdiction():
    """Verify a jurisdiction is offered its own codes plus the ones applying everywhere."""
    from app.constants import BUILDING_CODES, building_codes_for

    canadian = [code["id"] for code in building_codes_for("Canada")]
    assert "OBC-PART9" in canadian
    assert "IBC" not in canadian
    assert "ISO-IFC-INTL" in canadian

    # A jurisdiction with no bundled national code still gets an offer rather
    # than an empty select.
    assert [code["id"] for code in building_codes_for("France")] == ["ISO-IFC-INTL"]

    # No jurisdiction means the whole catalog: that is what the options endpoint
    # serves so the client can re-filter without a round trip.
    assert building_codes_for("") == BUILDING_CODES


def test_create_project_rejects_unknown_building_code():
    """Verify a building code outside the catalog is refused before the row is written."""
    response = client.post(
        "/api/projects",
        json={
            "name": "Unknown code project",
            "country": "Canada",
            "analysis_type": "Arch",
            "building_code": "NOT-A-CODE",
        },
    )
    assert response.status_code == 400
    assert "building_code" in response.json()["detail"]


def test_create_project_persists_building_code():
    """Verify the wizard's step-3 code choice round-trips onto the created project."""
    from app.services.projects_service import ProjectsService

    response = client.post(
        "/api/projects",
        json={
            "name": "Building code round-trip",
            "country": "Canada",
            "analysis_type": "Arch",
            "building_code": "OBC-PART9",
        },
    )
    assert response.status_code == 201
    created = response.json()
    try:
        assert created["building_code"] == "OBC-PART9"
    finally:
        ProjectsService().delete_project(created["id"])


def test_create_project_without_building_code_is_allowed():
    """Verify a Piping project may be created with no code, as step 3 says it may."""
    from app.services.projects_service import ProjectsService

    response = client.post(
        "/api/projects",
        json={"name": "Corrosion, no code", "country": "Canada", "analysis_type": "Piping"},
    )
    assert response.status_code == 201
    created = response.json()
    try:
        assert created["building_code"] is None
    finally:
        ProjectsService().delete_project(created["id"])


def test_bulk_update_projects():
    """Verify POST /api/projects/bulk-update updates multiple projects in batch."""
    from app.services.projects_service import ProjectsService

    svc = ProjectsService()
    p1 = svc.create_project(name="Bulk Update 1", status="Draft", country="US", analysis_type="Arch")
    p2 = svc.create_project(name="Bulk Update 2", status="Draft", country="US", analysis_type="Arch")
    p1_id, p2_id = p1["id"], p2["id"]

    try:
        res = client.post(
            "/api/projects/bulk-update",
            json={
                "project_ids": [p1_id, p2_id],
                "status": "Active",
                "country": "UK",
                "analysis_type": "seismic",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success_count"] == 2
        assert set(data["affected_ids"]) == {p1_id, p2_id}

        up1 = svc.get_project(p1_id)
        up2 = svc.get_project(p2_id)
        assert up1["status"] == "Active" and up1["country"] == "UK" and up1["analysis_type"] == "seismic"
        assert up2["status"] == "Active" and up2["country"] == "UK" and up2["analysis_type"] == "seismic"
    finally:
        svc.delete_project(p1_id)
        svc.delete_project(p2_id)


def test_bulk_delete_projects():
    """Verify POST /api/projects/bulk-delete deletes multiple projects in batch."""
    from app.services.projects_service import ProjectsService

    svc = ProjectsService()
    p1 = svc.create_project(name="Bulk Delete 1", status="Draft", country="US", analysis_type="Arch")
    p2 = svc.create_project(name="Bulk Delete 2", status="Draft", country="US", analysis_type="Arch")
    p1_id, p2_id = p1["id"], p2["id"]

    res = client.post(
        "/api/projects/bulk-delete",
        json={"project_ids": [p1_id, p2_id]},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success_count"] == 2
    assert set(data["affected_ids"]) == {p1_id, p2_id}

    assert svc.get_project(p1_id) is None
    assert svc.get_project(p2_id) is None

