"""Tests for /api/rules endpoints."""

from __future__ import annotations

from starlette.testclient import TestClient

from app.main import app

client = TestClient(app)
NONEXISTENT_ID = 999_999_999


def test_list_rules():
    """Verify /api/rules returns list of rules."""
    response = client.get("/api/rules")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_list_rule_folders():
    """Verify /api/rules/folders returns list of folders with rules."""
    response = client.get("/api/rules/folders")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_rule_not_found():
    """Verify requesting a non-existent rule returns 404."""
    response = client.get(f"/api/rules/{NONEXISTENT_ID}")
    assert response.status_code == 404


def test_rule_folder_crud():
    """Verify complete CRUD lifecycle for ruleset folders via REST API."""
    test_ruleset_id = "TEST-CRUD-FOLDER-01"

    # Clean up before testing
    client.delete(f"/api/rules/folders/{test_ruleset_id}")

    # 1. Create folder
    create_res = client.post(
        "/api/rules/folders",
        json={
            "ruleset_id": test_ruleset_id,
            "display_name": "Test Folder Display Name",
            "description": "Test folder description for CRUD testing",
            "mechanism_scope": "CODE",
            "category": "Arch",
        },
    )
    assert create_res.status_code == 201
    created_data = create_res.json()
    assert created_data["ruleset_id"] == test_ruleset_id
    assert created_data["display_name"] == "Test Folder Display Name"
    assert created_data["category"] == "Arch"

    # 2. Get folder by ruleset_id
    get_res = client.get(f"/api/rules/folders/{test_ruleset_id}")
    assert get_res.status_code == 200
    got_data = get_res.json()
    assert got_data["ruleset_id"] == test_ruleset_id
    assert got_data["display_name"] == "Test Folder Display Name"

    # 3. Update folder
    update_res = client.put(
        f"/api/rules/folders/{test_ruleset_id}",
        json={
            "display_name": "Updated Test Folder Display Name",
            "description": "Updated description",
            "category": "Piping",
            "mechanism_scope": "GC-001",
        },
    )
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["display_name"] == "Updated Test Folder Display Name"
    assert updated_data["category"] == "Piping"

    # 4. Delete folder
    delete_res = client.delete(f"/api/rules/folders/{test_ruleset_id}")
    assert delete_res.status_code == 200
    del_data = delete_res.json()
    assert del_data["success"] is True
    assert del_data["ruleset_id"] == test_ruleset_id

    # 5. Confirm deletion (404 on get)
    get_after_res = client.get(f"/api/rules/folders/{test_ruleset_id}")
    assert get_after_res.status_code == 404


def test_rules_bulk_operations():
    """Verify bulk update and bulk delete for rules."""
    # Create 2 test rules
    r1 = client.post(
        "/api/rules",
        json={
            "rule_id": "BULK-TEST-RULE-01",
            "property_name": "FireRating",
            "mechanism": "CODE",
            "category": "Arch",
            "severity": "Medium",
            "ruleset_id": "BUILDING-CODE-PART9",
        },
    ).json()
    r2 = client.post(
        "/api/rules",
        json={
            "rule_id": "BULK-TEST-RULE-02",
            "property_name": "AcousticRating",
            "mechanism": "CODE",
            "category": "Arch",
            "severity": "Medium",
            "ruleset_id": "BUILDING-CODE-PART9",
        },
    ).json()

    rule_ids = [r1["id"], r2["id"]]

    try:
        # Bulk update
        update_res = client.post(
            "/api/rules/bulk-update",
            json={
                "rule_ids": rule_ids,
                "category": "Piping",
                "mechanism": "GC-001",
                "severity": "Critical",
                "needs_review": 1,
            },
        )
        assert update_res.status_code == 200
        assert update_res.json()["success_count"] == 2

        # Verify updates on rules
        updated_r1 = client.get(f"/api/rules/{r1['id']}").json()
        assert updated_r1["category"] == "Piping"
        assert updated_r1["mechanism"] == "GC-001"
        assert updated_r1["severity"] == "Critical"
        assert updated_r1["needs_review"] == 1
    finally:
        # Bulk delete
        del_res = client.post(
            "/api/rules/bulk-delete",
            json={"rule_ids": rule_ids},
        )
        assert del_res.status_code == 200
        assert del_res.json()["success_count"] == 2

        # Verify deletion
        assert client.get(f"/api/rules/{r1['id']}").status_code == 404
        assert client.get(f"/api/rules/{r2['id']}").status_code == 404


def test_folders_bulk_operations():
    """Verify bulk update and bulk delete for ruleset folders."""
    f1_id = "BULK-FOLDER-01"
    f2_id = "BULK-FOLDER-02"

    # Clean up before testing
    client.delete(f"/api/rules/folders/{f1_id}")
    client.delete(f"/api/rules/folders/{f2_id}")

    # Create 2 folders
    client.post("/api/rules/folders", json={"ruleset_id": f1_id, "display_name": "Folder 1", "category": "Arch"})
    client.post("/api/rules/folders", json={"ruleset_id": f2_id, "display_name": "Folder 2", "category": "Arch"})

    try:
        # Bulk update
        bulk_up_res = client.post(
            "/api/rules/folders/bulk-update",
            json={
                "ruleset_ids": [f1_id, f2_id],
                "category": "seismic",
                "mechanism_scope": "SEISMIC",
            },
        )
        assert bulk_up_res.status_code == 200
        assert bulk_up_res.json()["success_count"] == 2

        f1_data = client.get(f"/api/rules/folders/{f1_id}").json()
        assert f1_data["category"] == "seismic"
        assert f1_data["mechanism_scope"] == "SEISMIC"
    finally:
        # Bulk delete
        bulk_del_res = client.post(
            "/api/rules/folders/bulk-delete",
            json={"ruleset_ids": [f1_id, f2_id]},
        )
        assert bulk_del_res.status_code == 200
        assert bulk_del_res.json()["success_count"] == 2

        # Verify 404
        assert client.get(f"/api/rules/folders/{f1_id}").status_code == 404
        assert client.get(f"/api/rules/folders/{f2_id}").status_code == 404



