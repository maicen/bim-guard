"""Test CRUD operations for projects and documents and token-free enhancement."""

from __future__ import annotations

import io

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.services.document_pages_service import DocumentPagesService
from app.services.documents_service import DocumentService
from app.services.projects_service import ProjectsService
from app.services.rule_draft_service import RuleDraftService
from app.services.rules_service import RuleService


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


def _one_page_pdf_bytes(text: str) -> bytes:
    """Build a minimal single-page PDF with reportlab, for page-tagged extraction tests."""
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 720, text)
    pdf.save()
    return buffer.getvalue()


def test_upload_stores_pages_and_serves_original_file(client: TestClient) -> None:
    """Uploading a PDF persists page-tagged text and GET /api/documents/{id}/file streams the original bytes."""
    doc_service = DocumentService()
    pages_service = DocumentPagesService()
    snippet = "Rule test snippet for page lookup"
    pdf_bytes = _one_page_pdf_bytes(snippet)

    row, created = doc_service.ingest_uploaded_bytes(
        "test_pages.pdf", pdf_bytes, parser="light"
    )
    assert created is True
    doc_id = row["id"]

    try:
        pages = pages_service.get_pages(doc_id)
        assert len(pages) == 1
        assert pages[0]["page_number"] == 1
        assert snippet in pages[0]["text"]

        response = client.get(f"/api/documents/{doc_id}/file")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.content == pdf_bytes
    finally:
        doc_service.delete_document_with_file(doc_id)


def test_promote_draft_carries_source_document_and_snippet() -> None:
    """promote_draft() writes source_document_id/source_text onto the canonical rule."""
    from app.modules.contracts import RuleCreateRequest, RuleDraftStatus, RuleExtractionDraft

    doc_service = DocumentService()
    doc = doc_service.create_document(
        md5_hash="dummy-md5-for-promote-test",
        filename="promote_source.txt",
        file_path="uploads/promote_source.txt",
        extracted_text="Doors shall have a clear width of at least 860 mm.",
        doc_type="Code",
    )
    doc_id = doc["id"]

    draft_service = RuleDraftService()
    snippet = "Doors shall have a clear width of at least 860 mm."
    draft = RuleExtractionDraft(
        source_document_id=doc_id,
        source_node_id="node-1",
        source_snippet=snippet,
        proposed_rule=RuleCreateRequest(
            rule_id="REQ-TEST-PROMOTE-001",
            description="Door clear width",
            target_ifc_class="IfcDoor",
            property_name="ClearWidth",
            operator=">=",
            check_value="860",
        ),
        status=RuleDraftStatus.accepted,
    )
    saved = draft_service.save_drafts([draft])[0]
    draft_id = saved.id

    rule_id = None
    try:
        created_rule = draft_service.promote_draft(draft_id)
        rule_id = created_rule["id"]
        assert created_rule["source_document_id"] == doc_id
        assert created_rule["source_text"] == snippet
    finally:
        draft_service._drafts.delete(draft_id)
        if rule_id is not None:
            RuleService().delete_rule(rule_id)
        doc_service.delete_document(doc_id)

