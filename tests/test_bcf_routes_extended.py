"""Tests for BCF-API additions: current-user, ETag/If-Match, comment/viewpoint
PUT+DELETE, list pagination, and BCF-XML (.bcfzip) import.
"""

from fastapi.testclient import TestClient

from app.main import app
from app.modules.reporter.bcf_generator import BCFIssue, generate_bcf

client = TestClient(app)


def test_bcf_current_user():
    resp = client.get("/api/bcf/v2.1/current-user")
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert "name" in data


def test_bcf_topic_etag_and_if_match_conflict():
    proj_id = "0"
    create_resp = client.post(
        f"/api/bcf/v2.1/projects/{proj_id}/topics",
        json={"title": "ETag test topic", "priority": "Normal"},
    )
    topic_guid = create_resp.json()["guid"]

    get_resp = client.get(f"/api/bcf/v2.1/projects/{proj_id}/topics/{topic_guid}")
    etag = get_resp.headers.get("etag")
    assert etag

    # Correct If-Match succeeds.
    ok_resp = client.put(
        f"/api/bcf/v2.1/projects/{proj_id}/topics/{topic_guid}",
        json={"topic_status": "InProgress"},
        headers={"If-Match": etag},
    )
    assert ok_resp.status_code == 200

    # Stale If-Match (etag from before the update above) is rejected.
    stale_resp = client.put(
        f"/api/bcf/v2.1/projects/{proj_id}/topics/{topic_guid}",
        json={"topic_status": "Closed"},
        headers={"If-Match": etag},
    )
    assert stale_resp.status_code == 412


def test_bcf_comment_update_and_delete():
    proj_id = "0"
    topic_resp = client.post(
        f"/api/bcf/v2.1/projects/{proj_id}/topics",
        json={"title": "Comment CRUD topic", "priority": "Normal"},
    )
    topic_guid = topic_resp.json()["guid"]

    comment_resp = client.post(
        f"/api/bcf/v2.1/projects/{proj_id}/topics/{topic_guid}/comments",
        json={"comment": "Original text"},
    )
    comment_guid = comment_resp.json()["guid"]

    update_resp = client.put(
        f"/api/bcf/v2.1/projects/{proj_id}/topics/{topic_guid}/comments/{comment_guid}",
        json={"comment": "Edited text"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["comment"] == "Edited text"

    delete_resp = client.delete(
        f"/api/bcf/v2.1/projects/{proj_id}/topics/{topic_guid}/comments/{comment_guid}"
    )
    assert delete_resp.status_code == 204

    list_resp = client.get(f"/api/bcf/v2.1/projects/{proj_id}/topics/{topic_guid}/comments")
    assert comment_guid not in [c["guid"] for c in list_resp.json()]


def test_bcf_viewpoint_delete():
    proj_id = "0"
    topic_resp = client.post(
        f"/api/bcf/v2.1/projects/{proj_id}/topics",
        json={"title": "Viewpoint delete topic", "priority": "Normal"},
    )
    topic_guid = topic_resp.json()["guid"]

    vp_resp = client.post(
        f"/api/bcf/v2.1/projects/{proj_id}/topics/{topic_guid}/viewpoints",
        json={},
    )
    vp_guid = vp_resp.json()["guid"]

    delete_resp = client.delete(
        f"/api/bcf/v2.1/projects/{proj_id}/topics/{topic_guid}/viewpoints/{vp_guid}"
    )
    assert delete_resp.status_code == 204

    get_resp = client.get(
        f"/api/bcf/v2.1/projects/{proj_id}/topics/{topic_guid}/viewpoints/{vp_guid}"
    )
    assert get_resp.status_code == 404


def test_bcf_list_topics_pagination_headers():
    proj_id = "0"
    for i in range(3):
        client.post(
            f"/api/bcf/v2.1/projects/{proj_id}/topics",
            json={"title": f"Pagination topic {i}", "priority": "Normal"},
        )

    resp = client.get(f"/api/bcf/v2.1/projects/{proj_id}/topics?page=1&per_page=2")
    assert resp.status_code == 200
    assert len(resp.json()) <= 2
    assert "x-total-count" in resp.headers
    assert int(resp.headers["x-total-count"]) >= 3


def test_bcf_import_round_trips_export():
    proj_id = "999"
    issue = BCFIssue(
        guid="BGR-IMPORT-TEST-0001",
        title="Round-trip import topic",
        description="Imported from a generated .bcfzip archive.",
        priority="Major",
        status="Open",
        assigned_to="Lead Engineer",
        due_date="",
        labels=["ImportTest"],
        component_guid="2O2Fr$t4X7Zf8NOew3FL01",
        component_name="Test Pipe",
        service_type="Domestic Water",
        floor="Level 01",
        risk_band="high",
        mechanism="galvanic",
        risk_score=0.82,
        mitigation="Insert dielectric isolation.",
    )
    archive_bytes = generate_bcf([issue])

    resp = client.post(
        f"/api/bcf/v2.1/projects/{proj_id}/import",
        files={"file": ("test.bcfzip", archive_bytes, "application/octet-stream")},
    )
    assert resp.status_code == 201
    imported = resp.json()
    assert len(imported) == 1
    assert imported[0]["title"] == "Round-trip import topic"
    assert imported[0]["priority"] == "Major"

    list_resp = client.get(f"/api/bcf/v2.1/projects/{proj_id}/topics")
    titles = [t["title"] for t in list_resp.json()]
    assert "Round-trip import topic" in titles


def test_bcf_import_rejects_invalid_archive():
    resp = client.post(
        "/api/bcf/v2.1/projects/0/import",
        files={"file": ("bad.bcfzip", b"not a zip file", "application/octet-stream")},
    )
    assert resp.status_code == 400
