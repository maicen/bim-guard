"""Tests for /api/events and /api/workflow endpoints."""

from __future__ import annotations

from starlette.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_workflow_snapshot_json():
    """Verify /api/workflow/{project_id} returns workflow engines snapshot."""
    response = client.get("/api/workflow/1")
    assert response.status_code == 200
    data = response.json()
    assert "engines" in data
    assert "GC-001" in data["engines"]


def test_workflow_snapshot_bad_id():
    """Verify /api/workflow/0 returns 400."""
    response = client.get("/api/workflow/0")
    assert response.status_code == 400


def test_sse_endpoint_connects_and_streams():
    """Verify /api/events/{project_id} responds with text/event-stream."""
    with client.stream("GET", "/api/events/1") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        # Read first chunk (initial snapshot)
        lines = []
        for line in response.iter_lines():
            if line:
                lines.append(line)
            if len(lines) >= 2:
                break

        content = "\n".join(lines)
        assert "event: status" in content
        assert "data:" in content


def test_sse_endpoint_bad_id():
    """Verify /api/events/0 returns 400."""
    response = client.get("/api/events/0")
    assert response.status_code == 400


def test_sse_endpoint_with_max_events():
    """Verify /api/events/{project_id}?max_events=1 limits event yield."""
    with client.stream("GET", "/api/events/1?max_events=1") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        lines = [line for line in response.iter_lines() if line]
        assert len(lines) >= 2
        content = "\n".join(lines)
        assert "event: status" in content
        assert "data:" in content

