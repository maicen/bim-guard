"""Tests for BCF REST API v2.1/v3.0 endpoints and bidirectional sync."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_bcf_list_and_get_projects():
    # List projects
    resp = client.get("/api/bcf/v2.1/projects")
    assert resp.status_code == 200
    projects = resp.json()
    assert isinstance(projects, list)

    # Get single project
    resp_single = client.get("/api/bcf/v2.1/projects/0")
    assert resp_single.status_code == 200
    data = resp_single.json()
    assert "project_id" in data
    assert "name" in data


def test_bcf_topics_crud_and_iso19650_metadata():
    proj_id = "0"
    create_payload = {
        "title": "Severe Galvanic Risk between Cu and Zn",
        "topic_type": "Issue",
        "topic_status": "Open",
        "priority": "Critical",
        "description": "Galvanic corrosion detected between copper riser and zinc fitting.",
        "assigned_to": "Lead MEP Engineer",
        "due_date": "2026-10-01",
        "labels": ["Corrosion", "Galvanic", "HighRisk"],
        "component_guids": ["2O2Fr$t4X7Zf8NOew3FL01", "2O2Fr$t4X7Zf8NOew3FL02"],
        "suitability_code": "S2",
        "revision_code": "P01.02",
        "cde_state": "SHARED",
    }

    # 1. Create Topic
    create_resp = client.post(f"/api/bcf/v2.1/projects/{proj_id}/topics", json=create_payload)
    assert create_resp.status_code == 201
    topic = create_resp.json()
    topic_guid = topic["guid"]
    assert topic["title"] == create_payload["title"]
    assert topic["priority"] == "Critical"
    assert topic["suitability_code"] == "S2"
    assert topic["cde_state"] == "SHARED"
    assert len(topic["component_guids"]) == 2

    # 2. Get Topic
    get_resp = client.get(f"/api/bcf/v2.1/projects/{proj_id}/topics/{topic_guid}")
    assert get_resp.status_code == 200
    assert get_resp.json()["guid"] == topic_guid

    # 3. Update Topic
    update_payload = {
        "topic_status": "InProgress",
        "priority": "Major",
        "cde_state": "PUBLISHED",
    }
    update_resp = client.put(f"/api/bcf/v2.1/projects/{proj_id}/topics/{topic_guid}", json=update_payload)
    assert update_resp.status_code == 200
    updated_topic = update_resp.json()
    assert updated_topic["topic_status"] == "InProgress"
    assert updated_topic["priority"] == "Major"
    assert updated_topic["cde_state"] == "PUBLISHED"

    # 4. List Topics with filter
    list_resp = client.get(f"/api/bcf/v2.1/projects/{proj_id}/topics?topic_status=InProgress")
    assert list_resp.status_code == 200
    matched_guids = [t["guid"] for t in list_resp.json()]
    assert topic_guid in matched_guids


def test_bcf_comments_and_viewpoints():
    proj_id = "0"
    topic_resp = client.post(
        f"/api/bcf/v2.1/projects/{proj_id}/topics",
        json={"title": "Test Viewpoint Topic", "priority": "Normal"},
    )
    topic_guid = topic_resp.json()["guid"]

    # 1. Add Comment
    comment_resp = client.post(
        f"/api/bcf/v2.1/projects/{proj_id}/topics/{topic_guid}/comments",
        json={"comment": "Investigating isolation gasket installation."},
    )
    assert comment_resp.status_code == 201
    assert comment_resp.json()["comment"] == "Investigating isolation gasket installation."

    # 2. List Comments
    comments_list = client.get(f"/api/bcf/v2.1/projects/{proj_id}/topics/{topic_guid}/comments")
    assert comments_list.status_code == 200
    assert len(comments_list.json()) >= 1

    # 3. Create Viewpoint
    vp_payload = {
        "perspective_camera": {
            "camera_view_point": {"x": 10.0, "y": 10.0, "z": 2.5},
            "camera_direction": {"x": -1.0, "y": -1.0, "z": 0.0},
            "camera_up_vector": {"x": 0.0, "y": 0.0, "z": 1.0},
            "field_of_view": 60.0,
        },
        "components": {
            "selection": [{"ifc_guid": "2O2Fr$t4X7Zf8NOew3FL01"}],
            "coloring": [{"color": "FF0000", "components": [{"ifc_guid": "2O2Fr$t4X7Zf8NOew3FL01"}]}],
        },
    }
    vp_resp = client.post(f"/api/bcf/v2.1/projects/{proj_id}/topics/{topic_guid}/viewpoints", json=vp_payload)
    assert vp_resp.status_code == 201
    vp_data = vp_resp.json()
    vp_guid = vp_data["guid"]
    assert "perspective_camera" in vp_data

    # 4. Get Viewpoint
    get_vp_resp = client.get(f"/api/bcf/v2.1/projects/{proj_id}/topics/{topic_guid}/viewpoints/{vp_guid}")
    assert get_vp_resp.status_code == 200
    assert get_vp_resp.json()["guid"] == vp_guid

    # 5. Snapshot binary endpoint
    snapshot_resp = client.get(f"/api/bcf/v2.1/projects/{proj_id}/topics/{topic_guid}/viewpoints/{vp_guid}/snapshot")
    assert snapshot_resp.status_code == 200
    assert snapshot_resp.headers["content-type"] == "image/png"
