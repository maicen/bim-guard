"""Tests verifying ruleset categorization now that Arch is the only domain."""

from __future__ import annotations

from starlette.testclient import TestClient

from app.main import app
from app.services.rules_service import RULESET_CATEGORIES, RuleService

client = TestClient(app)


def test_category_normalization():
    """Verify normalize_category always resolves to 'Arch'."""
    assert RuleService.normalize_category("arch") == "Arch"
    assert RuleService.normalize_category("Architecture") == "Arch"
    assert RuleService.normalize_category("CODE") == "Arch"
    assert RuleService.normalize_category("piping") == "Arch"
    assert RuleService.normalize_category("seismic") == "Arch"
    assert RuleService.normalize_category(None) == "Arch"


def test_category_inference():
    """Verify infer_category always classifies as 'Arch'."""
    assert RuleService.infer_category({"mechanism": "CODE"}) == "Arch"
    assert RuleService.infer_category({"ruleset_id": "BUILDING-CODE-PART9"}) == "Arch"
    assert RuleService.infer_category({"target_ifc_class": "IfcWall"}) == "Arch"
    assert RuleService.infer_category({}) == "Arch"


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

    assert found_categories == {"Arch"}


def test_api_list_folders_filter_by_category():
    """Verify /api/rules/folders?category=Arch filters properly."""
    response = client.get("/api/rules/folders?category=Arch")
    assert response.status_code == 200
    folders = response.json()
    assert len(folders) > 0
    for f in folders:
        assert f["category"] == "Arch"


def test_api_list_rules_filter_by_category():
    """Verify /api/rules?category=Arch filters properly."""
    response = client.get("/api/rules?category=Arch")
    assert response.status_code == 200
    rules = response.json()
    assert len(rules) > 0
    for r in rules:
        assert r.get("category") == "Arch"
