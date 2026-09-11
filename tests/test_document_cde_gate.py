"""PUT /api/documents/{id} must route cde_state changes through CDEStateMachine.

Instead of writing the field directly, so a document can't jump straight to
SHARED/PUBLISHED with no gate check.
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.services.documents_service import DocumentService


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def wip_document():
    service = DocumentService()
    created = service.create_document(
        md5_hash="dummy-md5-cde-gate-test",
        filename="PRJ1-BIMG-01-00-M3-A-0001.pdf",
        file_path="uploads/cde_gate_test.pdf",
        doc_type="Specification",
    )
    doc_id = created["id"]
    yield doc_id
    service.delete_document(doc_id)


def test_wip_to_shared_blocked_on_bad_filename(client: TestClient) -> None:
    service = DocumentService()
    created = service.create_document(
        md5_hash="dummy-md5-bad-filename",
        filename="not-an-iso-name.pdf",
        file_path="uploads/not_iso.pdf",
        doc_type="Specification",
    )
    doc_id = created["id"]
    try:
        response = client.put(f"/api/documents/{doc_id}", json={"cde_state": "SHARED"})
        assert response.status_code == 400
        # The document's cde_state must be unchanged after a rejected transition.
        assert service.get_document(doc_id)["cde_state"] == "WIP"
    finally:
        service.delete_document(doc_id)


def test_wip_to_shared_allowed_with_valid_filename(client: TestClient, wip_document: int) -> None:
    response = client.put(f"/api/documents/{wip_document}", json={"cde_state": "SHARED"})
    assert response.status_code == 200
    assert response.json()["cde_state"] == "SHARED"


def test_shared_to_published_requires_approval(client: TestClient, wip_document: int) -> None:
    promote = client.put(f"/api/documents/{wip_document}", json={"cde_state": "SHARED"})
    assert promote.status_code == 200

    blocked = client.put(f"/api/documents/{wip_document}", json={"cde_state": "PUBLISHED"})
    assert blocked.status_code == 400

    approved = client.put(
        f"/api/documents/{wip_document}",
        json={"cde_state": "PUBLISHED", "approved_by": "Jane Doe"},
    )
    assert approved.status_code == 200
    assert approved.json()["cde_state"] == "PUBLISHED"
