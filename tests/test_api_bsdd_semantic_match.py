"""Tests for POST /api/bsdd/semantic-match. Auth is overridden globally in conftest.py."""

from __future__ import annotations

from starlette.testclient import TestClient

import app.api.bsdd as bsdd_module
from app.main import app
from app.services.bsdd_semantic_mapper import SemanticMatch

client = TestClient(app)


class FakeMapper:
    def __init__(self, class_match=None, property_match=None):
        self._class_match = class_match
        self._property_match = property_match
        self.calls: list[tuple] = []

    async def suggest_class(self, query, *, model=None, organization_id=None):
        self.calls.append(("class", query, model, organization_id))
        return self._class_match

    async def suggest_property(self, query, target_ifc_class=None, *, model=None, organization_id=None):
        self.calls.append(("property", query, target_ifc_class, model, organization_id))
        return self._property_match


def _patch_mapper(monkeypatch, mapper: FakeMapper):
    monkeypatch.setattr(bsdd_module, "BsddSemanticMapper", lambda: mapper)


def test_semantic_match_class_found(monkeypatch):
    match = SemanticMatch(matched_uri="https://x/IfcWall", matched_code="IfcWall", confidence=0.9, reasoning="same concept")
    _patch_mapper(monkeypatch, FakeMapper(class_match=match))

    response = client.post("/api/bsdd/semantic-match", json={"query": "Firewall", "kind": "class"})

    assert response.status_code == 200
    data = response.json()
    assert data["matched"] is True
    assert data["matched_code"] == "IfcWall"
    assert data["confidence"] == 0.9


def test_semantic_match_property_found_passes_target_class(monkeypatch):
    match = SemanticMatch(matched_uri="https://x/FireRating", matched_code="FireRating", confidence=0.8, reasoning="synonym")
    mapper = FakeMapper(property_match=match)
    _patch_mapper(monkeypatch, mapper)

    response = client.post(
        "/api/bsdd/semantic-match",
        json={"query": "Fire_Resistance_Rating", "kind": "property", "target_ifc_class": "IfcDoor"},
    )

    assert response.status_code == 200
    assert response.json()["matched_code"] == "FireRating"
    assert mapper.calls[0][2] == "IfcDoor"  # target_ifc_class was forwarded


def test_semantic_match_no_match_returns_matched_false(monkeypatch):
    _patch_mapper(monkeypatch, FakeMapper(class_match=None))

    response = client.post("/api/bsdd/semantic-match", json={"query": "Completely Unknown Thing", "kind": "class"})

    assert response.status_code == 200
    data = response.json()
    assert data["matched"] is False
    assert data["matched_uri"] is None


def test_semantic_match_requires_kind():
    response = client.post("/api/bsdd/semantic-match", json={"query": "Something"})
    assert response.status_code == 422


def test_semantic_match_rejects_empty_query():
    response = client.post("/api/bsdd/semantic-match", json={"query": "", "kind": "class"})
    assert response.status_code == 422
