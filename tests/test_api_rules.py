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

