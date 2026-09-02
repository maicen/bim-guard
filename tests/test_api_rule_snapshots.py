"""Tests for /api/rules/import-ids and /api/rules/snapshots endpoints.

These hit the real configured RuleService (Supabase in the deployed
environment, per get_rules_service()/RuleSnapshotService()'s defaults) —
same as test_api_rules.py::test_rule_folder_crud — so they're marked slow
and clean up their fixture data before and after. This suite runs under
pytest-xdist in parallel by default, so each test uses its own uniquely
named ruleset_id — two tests sharing one ruleset_id here previously raced
against the same real production folder and corrupted each other's rule
counts.
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.services.rules_service import RuleService

client = TestClient(app)
NONEXISTENT_ID = 999_999_999

IMPORT_IDS_RULESET_ID = "TEST-SNAPSHOT-API-IMPORT-IDS"
SNAPSHOT_LIFECYCLE_RULESET_ID = "TEST-SNAPSHOT-API-LIFECYCLE"

SAMPLE_IDS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<ids:ids xmlns:ids="http://standards.buildingsmart.org/IDS" version="1.0" identifier="MY-IDS-SET">
  <ids:specifications>
    <ids:specification name="R-101">
      <ids:applicability>
        <ids:entity>
          <ids:name>IfcDoor</ids:name>
        </ids:entity>
      </ids:applicability>
      <ids:requirements>
        <ids:property>
          <ids:propertySet>Pset_DoorCommon</ids:propertySet>
          <ids:name>Width</ids:name>
          <ids:value>
            <ids:simpleValue>900</ids:simpleValue>
          </ids:value>
        </ids:property>
      </ids:requirements>
    </ids:specification>
  </ids:specifications>
</ids:ids>
"""


def _cleanup(ruleset_id: str):
    RuleService().delete_folder(ruleset_id)


@pytest.mark.slow
def test_import_ids_creates_rules_under_ruleset():
    _cleanup(IMPORT_IDS_RULESET_ID)
    try:
        response = client.post(
            "/api/rules/import-ids",
            files={"file": ("test.ids", SAMPLE_IDS_XML, "application/xml")},
            data={"ruleset_id": IMPORT_IDS_RULESET_ID},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["success"] is True
        assert data["created_count"] == 1
        assert data["ruleset_id"] == IMPORT_IDS_RULESET_ID

        rules = RuleService().list_by_ruleset(IMPORT_IDS_RULESET_ID)
        assert len(rules) == 1
        assert rules[0]["target_ifc_class"] == "IfcDoor"
        assert rules[0]["property_name"] == "Width"
    finally:
        _cleanup(IMPORT_IDS_RULESET_ID)


@pytest.mark.slow
def test_import_ids_with_empty_file_returns_400():
    response = client.post(
        "/api/rules/import-ids",
        files={"file": ("empty.ids", "", "application/xml")},
        data={"ruleset_id": IMPORT_IDS_RULESET_ID},
    )
    assert response.status_code == 400


@pytest.mark.slow
def test_snapshot_crud_and_pdf_download_lifecycle():
    _cleanup(SNAPSHOT_LIFECYCLE_RULESET_ID)
    rule_service = RuleService()
    rule_service.create_rule(
        reference="SNAP-TEST-1",
        rule_type="numeric_comparison",
        description="Test rule for snapshot API",
        target_ifc_class="IfcWindow",
        property_set="Pset_WindowCommon",
        property_name="FireRating",
        operator=">=",
        check_value=30.0,
        unit="min",
        mechanism="CODE",
        ruleset_id=SNAPSHOT_LIFECYCLE_RULESET_ID,
        rule_category="property_check",
        category="Arch",
        severity="mandatory",
    )

    try:
        # Create
        create_res = client.post(
            "/api/rules/snapshots",
            json={"ruleset_id": SNAPSHOT_LIFECYCLE_RULESET_ID, "name": "API Test Snapshot", "source_mode": "manual"},
        )
        assert create_res.status_code == 201, create_res.text
        snapshot = create_res.json()
        assert snapshot["rule_count"] == 1
        assert snapshot["source_ruleset_id"] == SNAPSHOT_LIFECYCLE_RULESET_ID
        assert "rules_json" not in snapshot  # internal-only, never shipped in the response
        snapshot_id = snapshot["id"]

        # List
        list_res = client.get("/api/rules/snapshots")
        assert list_res.status_code == 200
        assert any(s["id"] == snapshot_id for s in list_res.json())

        # Get
        get_res = client.get(f"/api/rules/snapshots/{snapshot_id}")
        assert get_res.status_code == 200
        assert get_res.json()["name"] == "API Test Snapshot"

        # Get non-existent -> 404
        assert client.get(f"/api/rules/snapshots/{NONEXISTENT_ID}").status_code == 404

        # PDF download
        pdf_res = client.get(f"/api/rules/snapshots/{snapshot_id}/pdf")
        assert pdf_res.status_code == 200
        assert pdf_res.headers["content-type"] == "application/pdf"
        assert pdf_res.content[:5] == b"%PDF-"

        # Delete
        delete_res = client.delete(f"/api/rules/snapshots/{snapshot_id}")
        assert delete_res.status_code == 204
        assert client.get(f"/api/rules/snapshots/{snapshot_id}").status_code == 404
        assert client.delete(f"/api/rules/snapshots/{snapshot_id}").status_code == 404
    finally:
        _cleanup(SNAPSHOT_LIFECYCLE_RULESET_ID)


@pytest.mark.slow
def test_create_snapshot_from_empty_ruleset_returns_400():
    response = client.post(
        "/api/rules/snapshots",
        json={"ruleset_id": "TEST-EMPTY-RULESET-DOES-NOT-EXIST"},
    )
    assert response.status_code == 400
