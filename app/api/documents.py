"""FastAPI router for document management and text extraction."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.dependencies import get_documents_service
from app.logging_config import get_logger
from app.modules.contracts import (
    DocumentDetailResponse,
    DocumentResponse,
    DocumentUpdateRequest,
)
from app.services.documents_service import DocumentService
from app.utils import md5_hex, safe_upload_name, validate_document_upload

logger = get_logger(__name__)

router = APIRouter()


@router.get("", response_model=list[DocumentResponse], summary="List all uploaded specification documents")
def list_documents(
    service: Annotated[DocumentService, Depends(get_documents_service)],
) -> list[DocumentResponse]:
    """Retrieve all specification documents ordered newest first."""
    rows = service.list_documents()
    res = []
    for r in rows:
        text = r.get("extracted_text") or ""
        preview = text[:200] + "..." if len(text) > 200 else text
        res.append(
            DocumentResponse(
                id=r["id"],
                filename=r.get("filename", "document"),
                file_path=r.get("file_path"),
                upload_date=r.get("upload_date"),
                extracted_text_preview=preview,
                char_count=len(text),
            )
        )
    return res


@router.get("/{document_id}", response_model=DocumentDetailResponse, summary="Get document details & extracted text")
def get_document(
    document_id: int,
    service: Annotated[DocumentService, Depends(get_documents_service)],
) -> DocumentDetailResponse:
    """Retrieve a document by ID including its full extracted text."""
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found.",
        )
    text = doc.get("extracted_text") or ""
    return DocumentDetailResponse(
        id=doc["id"],
        filename=doc.get("filename", "document"),
        file_path=doc.get("file_path"),
        upload_date=doc.get("upload_date"),
        extracted_text=text,
        char_count=len(text),
    )


@router.post("", response_model=DocumentDetailResponse, status_code=status.HTTP_201_CREATED, summary="Upload document")
async def upload_document(
    file: UploadFile = File(...),
    service: Annotated[DocumentService, Depends(get_documents_service)] = None,
) -> DocumentDetailResponse:
    """Upload a specification document (PDF, TXT, MD) and extract text."""
    if service is None:
        service = DocumentService()

    valid, error_msg = validate_document_upload(file)
    if not valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    clean_filename = safe_upload_name(file.filename)
    file_md5 = md5_hex(content)

    existing = service.find_by_md5(file_md5)
    if existing:
        text = existing.get("extracted_text") or ""
        return DocumentDetailResponse(
            id=existing["id"],
            filename=existing.get("filename", clean_filename),
            file_path=existing.get("file_path"),
            upload_date=existing.get("upload_date"),
            extracted_text=text,
            char_count=len(text),
        )

    # Extract text based on file extension
    extracted_text = ""
    lower_name = clean_filename.lower()
    if lower_name.endswith(".pdf"):
        try:
            extracted_text = service.parse_pdf_content(content)
        except Exception as exc:
            logger.warning("PDF extraction failed: %s", exc)
            extracted_text = f"[Text extraction error: {exc}]"
    else:
        extracted_text = content.decode("utf-8", errors="replace")

    file_path = service.store_document_file(clean_filename, content)
    created = service.create_document(
        md5_hash=file_md5,
        filename=clean_filename,
        file_path=file_path,
        extracted_text=extracted_text,
    )

    return DocumentDetailResponse(
        id=created["id"],
        filename=clean_filename,
        file_path=file_path,
        upload_date=created.get("upload_date"),
        extracted_text=extracted_text,
        char_count=len(extracted_text),
    )


@router.put("/{document_id}", response_model=DocumentDetailResponse, summary="Update document")
def update_document(
    document_id: int,
    payload: DocumentUpdateRequest,
    service: Annotated[DocumentService, Depends(get_documents_service)],
) -> DocumentDetailResponse:
    """Update specification document metadata and/or extracted text."""
    existing = service.get_document(document_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found.",
        )

    filename = payload.filename if payload.filename is not None else existing.get("filename", "")
    extracted_text = (
        payload.extracted_text if payload.extracted_text is not None else existing.get("extracted_text", "")
    )

    service.update_document(document_id, filename=filename.strip(), extracted_text=extracted_text)
    updated = service.get_document(document_id) or existing
    text = updated.get("extracted_text") or ""

    return DocumentDetailResponse(
        id=updated["id"],
        filename=updated.get("filename", filename),
        file_path=updated.get("file_path"),
        upload_date=updated.get("upload_date"),
        extracted_text=text,
        char_count=len(text),
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete document")
def delete_document(
    document_id: int,
    service: Annotated[DocumentService, Depends(get_documents_service)],
) -> None:
    """Delete a document record and its stored file."""
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found.",
        )
    service.delete_document_with_file(document_id)

