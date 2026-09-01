"""Test CRUD operations for projects and documents and token-free enhancement."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.services.documents_service import DocumentService
from app.services.projects_service import ProjectsService


@pytest.fixture(scope="module")
def client() -> TestClient:
    """One test client for the FastAPI application."""
    return TestClient(app, raise_server_exceptions=False)


def test_project_update_endpoint(client: TestClient) -> None:
    """PUT /api/projects/{id} updates metadata fields including country and analysis_type."""
    service = ProjectsService()
    project = service.create_project(
        name="CRUD Test Project",
        description="Original description",
        status="Draft",
        country="US",
        analysis_type="Arch",
    )
    project_id = project["id"]

    try:
        response = client.put(
            f"/api/projects/{project_id}",
            json={
                "name": "Updated Project Name",
                "description": "Updated description",
                "status": "Active",
                "country": "Canada",
                "analysis_type": "Piping",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Project Name"
        assert data["description"] == "Updated description"
        assert data["status"] == "Active"
        assert data["country"] == "Canada"
        assert data["analysis_type"] == "Piping"
    finally:
        service.delete_project(project_id)


def test_project_enhance_endpoint_requires_no_token(client: TestClient) -> None:
    """POST /api/projects/{id}/enhance allows invocation without an authorization token."""
    service = ProjectsService()
    project = service.create_project(
        name="Enhancement Token Test",
        country="US",
        analysis_type="Arch",
    )
    project_id = project["id"]

    try:
        # Without IFC attached, should fail with 400 Bad Request, NOT 403 Forbidden!
        response = client.post(f"/api/projects/{project_id}/enhance", json={})
        assert response.status_code == 400
        assert "no IFC model attached" in response.json()["detail"]
    finally:
        service.delete_project(project_id)


def test_document_update_endpoint(client: TestClient) -> None:
    """PUT /api/documents/{id} updates document filename, doc_type, and extracted text."""
    doc_service = DocumentService()
    created = doc_service.create_document(
        md5_hash="dummy-md5-for-test",
        filename="original_spec.txt",
        file_path="uploads/test.txt",
        extracted_text="Original extracted text content",
        doc_type="Specification",
    )
    doc_id = created["id"]

    try:
        response = client.put(
            f"/api/documents/{doc_id}",
            json={
                "filename": "updated_spec.txt",
                "doc_type": "Code",
                "extracted_text": "Updated parsed rules text content",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "updated_spec.txt"
        assert data["doc_type"] == "Code"
        assert data["extracted_text"] == "Updated parsed rules text content"
        assert data["char_count"] == len("Updated parsed rules text content")
    finally:
        doc_service.delete_document(doc_id)


def test_document_create_and_link_with_doc_type() -> None:
    """DocumentService preserves doc_type and ProjectsService propagates it to client_documents."""
    doc_service = DocumentService()
    proj_service = ProjectsService()

    doc = doc_service.create_document(
        md5_hash="dummy-md5-manual-test",
        filename="equipment_manual.pdf",
        file_path="uploads/equipment_manual.pdf",
        extracted_text="Operating and maintenance procedures",
        doc_type="Manual",
    )
    doc_id = doc["id"]

    project = proj_service.create_project(
        name="Doc Link Test Project",
        country="Canada",
        analysis_type="Arch",
    )
    project_id = project["id"]

    try:
        linked_count = proj_service.link_library_documents(project_id, [doc_id])
        assert linked_count == 1
        client_docs = proj_service.get_client_documents_by_project(project_id)
        assert len(client_docs) == 1
        assert client_docs[0]["category"] == "Manual"
        assert client_docs[0]["filename"] == "equipment_manual.pdf"
    finally:
        proj_service.delete_project(project_id)
        doc_service.delete_document(doc_id)

