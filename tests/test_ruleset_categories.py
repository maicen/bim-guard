"""Tests verifying ruleset categorization across Arch, Piping, and seismic."""

from __future__ import annotations

from starlette.testclient import TestClient

from app.main import app
from app.services.rules_service import RULESET_CATEGORIES, RuleService

client = TestClient(app)


def test_category_normalization():
    """Verify normalize_category maps various inputs to Arch, Piping, or seismic."""
    assert RuleService.normalize_category("arch") == "Arch"
    assert RuleService.normalize_category("Architecture") == "Arch"
    assert RuleService.normalize_category("CODE") == "Arch"
    assert RuleService.normalize_category("piping") == "Piping"
    assert RuleService.normalize_category("MEP") == "Piping"
    assert RuleService.normalize_category("corrosion") == "Piping"
    assert RuleService.normalize_category("seismic") == "seismic"
    assert RuleService.normalize_category("HALO") == "seismic"
    assert RuleService.normalize_category("SB-001") == "seismic"


def test_category_inference():
    """Verify infer_category correctly classifies rules and folders."""
    assert RuleService.infer_category({"mechanism": "GC-001"}) == "Piping"
    assert RuleService.infer_category({"ruleset_id": "BIMGUARD-CC-001"}) == "Piping"
    assert RuleService.infer_category({"mechanism": "SEISMIC"}) == "seismic"
    assert RuleService.infer_category({"ruleset_id": "BIMGUARD-SB-001"}) == "seismic"
    assert RuleService.infer_category({"mechanism": "CODE"}) == "Arch"
    assert RuleService.infer_category({"ruleset_id": "BUILDING-CODE-PART9"}) == "Arch"
    assert RuleService.infer_category({"target_ifc_class": "IfcPipeSegment"}) == "Piping"
    assert RuleService.infer_category({"target_ifc_class": "IfcWall"}) == "Arch"


def test_api_list_folders_has_categories():
    """Verify /api/rules/folders returns category for all folders and matches allowed set."""
    response = client.get("/api/rules/folders")
    assert response.status_code == 200
    folders = response.json()
    assert len(folders) > 0

    found_categories = set()
    for f in folders:
        assert "category" in f
        assert f["category"] in RULESET_CATEGORIES
        found_categories.add(f["category"])

    # Verify all three categories exist
    assert "Arch" in found_categories
    assert "Piping" in found_categories
    assert "seismic" in found_categories


def test_api_list_folders_filter_by_category():
    """Verify /api/rules/folders?category=... filters properly."""
    for cat in ("Arch", "Piping", "seismic"):
        response = client.get(f"/api/rules/folders?category={cat}")
        assert response.status_code == 200
        folders = response.json()
        assert len(folders) > 0
        for f in folders:
            assert f["category"] == cat


def test_api_list_rules_filter_by_category():
    """Verify /api/rules?category=... filters properly."""
    for cat in ("Arch", "Piping", "seismic"):
        response = client.get(f"/api/rules?category={cat}")
        assert response.status_code == 200
        rules = response.json()
        assert len(rules) > 0
        for r in rules:
            assert r.get("category") == cat
