"""Tests for /api/bsdd endpoints."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.dependencies import get_bsdd_client
from app.main import app
from app.services.bsdd_client import BSDDClient

client = TestClient(app)


@pytest.fixture(autouse=True)
def _offline_bsdd_client():
    """Force the offline fallback catalog so these tests are deterministic and fast."""
    app.dependency_overrides[get_bsdd_client] = lambda: BSDDClient(enable_network=False)
    yield
    app.dependency_overrides.pop(get_bsdd_client, None)


def test_list_dictionaries():
    """Verify /api/bsdd/dictionaries serves the classification standard catalog."""
    response = client.get("/api/bsdd/dictionaries")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    codes = {d["code"] for d in data}
    assert "uniclass_2015" in codes
    assert "omniclass_2020" in codes


def test_search_classes():
    """Verify /api/bsdd/classes/search resolves an element-name query."""
    response = client.get("/api/bsdd/classes/search", params={"q": "pipe"})
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "pipe"
    assert data["total"] >= 1


def test_search_classes_requires_query():
    """Verify a missing search term is rejected with 422."""
    response = client.get("/api/bsdd/classes/search")
    assert response.status_code == 422


def test_search_properties():
    """Verify /api/bsdd/properties/search resolves a property-name query."""
    response = client.get("/api/bsdd/properties/search", params={"q": "Material"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    names = {p["name"] for p in data["properties"]}
    assert "Material" in names


def test_get_class_found():
    """Verify a known class code resolves with its properties."""
    response = client.get(
        "/api/bsdd/classes/IfcPipeSegment",
        params={"dictionary_uri": "https://identifier.buildingsmart.org/uri/buildingsmart/ifc-4.3"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "IfcPipeSegment"
    assert len(data["properties"]) >= 1


def test_get_class_not_found():
    """Verify an unknown class code returns 404."""
    response = client.get(
        "/api/bsdd/classes/NotARealClass",
        params={"dictionary_uri": "https://identifier.buildingsmart.org/uri/buildingsmart/ifc-4.3"},
    )
    assert response.status_code == 404
