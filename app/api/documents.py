"""FastAPI router for document management and text extraction."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool

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

import hashlib

router = APIRouter()


@router.get("", response_model=list[DocumentResponse], summary="List all uploaded specification documents")
def list_documents(
    service: Annotated[DocumentService, Depends(get_documents_service)],
    response: Response,
    if_none_match: str | None = Header(default=None, alias="If-None-Match"),
) -> list[DocumentResponse]:
    """Retrieve all specification documents ordered newest first."""
    response.headers["Cache-Control"] = "private, max-age=5, stale-while-revalidate=30"
    rows = service.list_documents()
    etag = f'"{hashlib.sha256(str(len(rows)).encode() + (rows[0]["created_at"].encode() if rows and "created_at" in rows[0] else b"")).hexdigest()[:16]}"'
    response.headers["ETag"] = etag
    if if_none_match and if_none_match.strip() == etag:
        response.status_code = status.HTTP_304_NOT_MODIFIED
        return []
    res = []
    for r in rows:
        text = r.get("extracted_text") or ""
        preview = text[:200] + "..." if len(text) > 200 else text
        res.append(
            DocumentResponse(
                id=r["id"],
                filename=r.get("filename", "document"),
                doc_type=r.get("doc_type") or "Specification",
                file_path=r.get("file_path"),
                upload_date=r.get("upload_date"),
                extracted_text_preview=preview,
                char_count=len(text),
                project_code=r.get("project_code", ""),
                originator=r.get("originator", ""),
                volume_system=r.get("volume_system", ""),
                level=r.get("level", ""),
                type=r.get("type", ""),
                role=r.get("role", ""),
                number=r.get("number", ""),
                suitability_code=r.get("suitability_code", "S0"),
                revision_code=r.get("revision_code", "P01.01"),
                cde_state=r.get("cde_state") or "WIP",
            )
        )
    return res


@router.get("/{document_id}", response_model=DocumentDetailResponse, summary="Get document details & extracted text")
def get_document(
    document_id: int,
    service: Annotated[DocumentService, Depends(get_documents_service)],
    response: Response,
) -> DocumentDetailResponse:
    """Retrieve a document by ID including its full extracted text."""
    response.headers["Cache-Control"] = "private, max-age=10, stale-while-revalidate=60"
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
        doc_type=doc.get("doc_type") or "Specification",
        file_path=doc.get("file_path"),
        upload_date=doc.get("upload_date"),
        extracted_text=text,
        char_count=len(text),
        project_code=doc.get("project_code", ""),
        originator=doc.get("originator", ""),
        volume_system=doc.get("volume_system", ""),
        level=doc.get("level", ""),
        type=doc.get("type", ""),
        role=doc.get("role", ""),
        number=doc.get("number", ""),
        suitability_code=doc.get("suitability_code", "S0"),
        revision_code=doc.get("revision_code", "P01.01"),
        cde_state=doc.get("cde_state") or "WIP",
    )


@router.post("", response_model=DocumentDetailResponse, status_code=status.HTTP_201_CREATED, summary="Upload document")
async def upload_document(
    file: UploadFile = File(...),
    doc_type: Annotated[str, Form()] = "Specification",
    project_code: Annotated[str, Form()] = "",
    originator: Annotated[str, Form()] = "",
    suitability_code: Annotated[str, Form()] = "S0",
    revision_code: Annotated[str, Form()] = "P01.01",
    parser: Annotated[str, Form()] = "auto",
    service: Annotated[DocumentService, Depends(get_documents_service)] = None,
) -> DocumentDetailResponse:
    """Upload a specification document (PDF, DOCX, XLSX, CSV, TXT, MD) and extract text.

    `parser` selects the extraction engine: "auto" (Unstructured's Workflow/
    Jobs API, falling back to a light local extractor), "unstructured"
    (force the hosted API — an async job, several to tens of seconds per
    document), or "light" (force the local extractor — pypdf/python-docx/
    openpyxl/csv, no upload, no API key, effectively instant).
    """
    if service is None:
        service = DocumentService()

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    clean_filename = safe_upload_name(file.filename)

    error_msg = validate_document_upload(clean_filename, file.content_type, content)
    if error_msg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    clean_doc_type = (doc_type or "").strip() or "Specification"
    file_md5 = md5_hex(content)

    # Auto-extract ISO 19650 container metadata from filename if valid
    from app.modules.module1_doc_parser.iso_validator import ISO19650Validator
    val = ISO19650Validator.validate_filename(clean_filename)
    if val.is_valid:
        project_code = project_code or val.fields.get("project_code", "")
        originator = originator or val.fields.get("originator", "")
        suitability_code = suitability_code if suitability_code != "S0" else val.fields.get("suitability_code", "S0")
        revision_code = revision_code if revision_code != "P01.01" else val.fields.get("revision_code", "P01.01")

    existing = service.find_by_md5(file_md5)
    if existing:
        text = existing.get("extracted_text") or ""
        return DocumentDetailResponse(
            id=existing["id"],
            filename=existing.get("filename", clean_filename),
            doc_type=existing.get("doc_type") or clean_doc_type,
            file_path=existing.get("file_path"),
            upload_date=existing.get("upload_date"),
            extracted_text=text,
            char_count=len(text),
            project_code=existing.get("project_code", project_code),
            originator=existing.get("originator", originator),
            volume_system=existing.get("volume_system", ""),
            level=existing.get("level", ""),
            type=existing.get("type", ""),
            role=existing.get("role", ""),
            number=existing.get("number", ""),
            suitability_code=existing.get("suitability_code", suitability_code),
            revision_code=existing.get("revision_code", revision_code),
            cde_state=existing.get("cde_state") or "WIP",
        )

    clean_parser = (parser or "auto").strip().lower()
    try:
        # The Unstructured path runs an async job under the hood (several to
        # tens of seconds) — offload to a worker thread so it doesn't block
        # the event loop for every other in-flight request.
        extracted_text = await run_in_threadpool(
            service.extract_document_text, clean_filename, content, parser=clean_parser
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("Document extraction failed filename=%s parser=%s error=%s", clean_filename, clean_parser, exc)
        extracted_text = f"[Text extraction error: {exc}]"

    file_path = service.store_document_file(clean_filename, content)
    created = service.create_document(
        md5_hash=file_md5,
        filename=clean_filename,
        file_path=file_path,
        extracted_text=extracted_text,
        doc_type=clean_doc_type,
        project_code=project_code,
        originator=originator,
        suitability_code=suitability_code,
        revision_code=revision_code,
        cde_state="WIP",
    )

    return DocumentDetailResponse(
        id=created["id"],
        filename=clean_filename,
        doc_type=created.get("doc_type") or clean_doc_type,
        file_path=file_path,
        upload_date=created.get("upload_date"),
        extracted_text=extracted_text,
        char_count=len(extracted_text),
        project_code=project_code,
        originator=originator,
        suitability_code=suitability_code,
        revision_code=revision_code,
        cde_state="WIP",
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
    doc_type = payload.doc_type if payload.doc_type is not None else existing.get("doc_type", "Specification")

    service.update_document(
        document_id,
        filename=filename.strip(),
        extracted_text=extracted_text,
        doc_type=doc_type,
        project_code=payload.project_code,
        originator=payload.originator,
        suitability_code=payload.suitability_code,
        revision_code=payload.revision_code,
        cde_state=payload.cde_state.value if hasattr(payload.cde_state, "value") else payload.cde_state,
    )
    updated = service.get_document(document_id) or existing
    text = updated.get("extracted_text") or ""

    return DocumentDetailResponse(
        id=updated["id"],
        filename=updated.get("filename", filename),
        doc_type=updated.get("doc_type") or doc_type or "Specification",
        file_path=updated.get("file_path"),
        upload_date=updated.get("upload_date"),
        extracted_text=text,
        char_count=len(text),
        project_code=updated.get("project_code", ""),
        originator=updated.get("originator", ""),
        volume_system=updated.get("volume_system", ""),
        level=updated.get("level", ""),
        type=updated.get("type", ""),
        role=updated.get("role", ""),
        number=updated.get("number", ""),
        suitability_code=updated.get("suitability_code", "S0"),
        revision_code=updated.get("revision_code", "P01.01"),
        cde_state=updated.get("cde_state") or "WIP",
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

