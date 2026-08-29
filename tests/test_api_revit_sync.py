"""Tests for FastAPI Revit direct synchronization endpoint."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_revit_sync_endpoint():
    payload = {
        "project_name": "Test Hospital Unit",
        "theme": "Architecture",
        "elements": [
            {
                "ifc_class": "IfcStairFlight",
                "name": "Stair 01",
                "guid": "test-stair-01",
                "storey": "Level 1",
                "properties": {
                    "Width": 1200.0,
                    "RiserHeight": 175.0,
                    "TreadLength": 280.0,
                },
            },
            {
                "ifc_class": "IfcStairFlight",
                "name": "Stair 02 Failing",
                "guid": "test-stair-02",
                "storey": "Level 1",
                "properties": {
                    "Width": 800.0,
                    "RiserHeight": 220.0,
                    "TreadLength": 220.0,
                },
            },
        ],
    }

    response = client.post("/api/analyze/revit-sync", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["element_count"] == 2
    assert data["theme"] == "Architecture"
    assert "summary" in data
    assert "results" in data
    assert len(data["results"]) > 0
