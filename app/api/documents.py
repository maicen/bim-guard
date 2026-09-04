"""FastAPI router for document management and text extraction."""

import mimetypes
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from app.api.dependencies import get_documents_service, get_parsing_engine_instances_service
from app.logging_config import get_logger
from app.modules.contracts import (
    DocumentDetailResponse,
    DocumentIngestResponse,
    DocumentResponse,
    DocumentUpdateRequest,
    GoogleDriveImportRequest,
    GoogleDriveImportResponse,
    GoogleDriveImportResult,
    RuleExtractionDraft,
    RuleExtractionDraftListResponse,
)
from app.services.documents_service import DocumentService
from app.services.parsing_engine_instances_service import ParsingEngineInstancesService
from app.services.rule_extraction_service import RuleExtractionService
from app.utils import safe_upload_name, validate_document_upload

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


@router.get("/{document_id}/file", summary="Download/stream the original uploaded document file")
def get_document_file(
    document_id: int,
    service: Annotated[DocumentService, Depends(get_documents_service)],
) -> FileResponse:
    """Stream the original uploaded file bytes for the document viewer.

    Resolves `documents.file_path` via `ObjectStorage.materialize_local_path`
    — the same resolution path already used for re-extraction — so this
    works whether the file lives in Supabase Storage, on disk, or at a
    cached http(s) URL.
    """
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found.",
        )
    file_path = doc.get("file_path")
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} has no stored file.",
        )

    local_path = service.materialize_local_path(file_path)
    if local_path is None or not local_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stored file for document {document_id} could not be resolved.",
        )

    filename = doc.get("filename") or local_path.name
    media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return FileResponse(path=local_path, media_type=media_type, filename=filename)


def _row_to_detail_response(row: dict) -> DocumentDetailResponse:
    """Build a DocumentDetailResponse from a `documents` row dict."""
    text = row.get("extracted_text") or ""
    return DocumentDetailResponse(
        id=row["id"],
        filename=row.get("filename", "document"),
        doc_type=row.get("doc_type") or "Specification",
        file_path=row.get("file_path"),
        upload_date=row.get("upload_date"),
        extracted_text=text,
        char_count=len(text),
        project_code=row.get("project_code", ""),
        originator=row.get("originator", ""),
        volume_system=row.get("volume_system", ""),
        level=row.get("level", ""),
        type=row.get("type", ""),
        role=row.get("role", ""),
        number=row.get("number", ""),
        suitability_code=row.get("suitability_code", "S0"),
        revision_code=row.get("revision_code", "P01.01"),
        cde_state=row.get("cde_state") or "WIP",
    )


def _resolve_parsing_instance(
    engine_instance: str,
    instances_service: ParsingEngineInstancesService,
) -> dict | None:
    clean_instance_name = (engine_instance or "").strip()
    if clean_instance_name:
        resolved = instances_service.get_by_name(clean_instance_name)
        if not resolved:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Parsing engine instance '{clean_instance_name}' is not configured.",
            )
        return resolved
    return instances_service.get_default()


@router.post("", response_model=DocumentDetailResponse, status_code=status.HTTP_201_CREATED, summary="Upload document")
async def upload_document(
    file: UploadFile = File(...),
    doc_type: Annotated[str, Form()] = "Specification",
    project_code: Annotated[str, Form()] = "",
    originator: Annotated[str, Form()] = "",
    suitability_code: Annotated[str, Form()] = "S0",
    revision_code: Annotated[str, Form()] = "P01.01",
    parser: Annotated[str, Form()] = "auto",
    engine_instance: Annotated[str, Form()] = "",
    service: Annotated[DocumentService, Depends(get_documents_service)] = None,
    instances_service: Annotated[
        ParsingEngineInstancesService, Depends(get_parsing_engine_instances_service)
    ] = None,
) -> DocumentDetailResponse:
    """Upload a specification document (PDF, DOCX, XLSX, CSV, TXT, MD) and extract text.

    `parser` selects the extraction engine: "auto" (the configured parsing
    engine, falling back to a light local extractor), "unstructured" (force
    the configured engine — a hosted job takes several to tens of seconds
    per document; a local container or Docling responds in one synchronous
    call), or "light" (force the local extractor — pypdf/python-docx/
    openpyxl/csv, no upload, no API key, effectively instant).

    `engine_instance` optionally names one of the configured parsing engines
    (see GET /api/parsing-engines) — a local container, or a specific
    hosted account. When omitted, the registry's default instance is used.
    """
    if service is None:
        service = DocumentService()
    if instances_service is None:
        from app.bootstrap import get_container

        instances_service = get_container().parsing_engine_instances_service

    resolved_instance = _resolve_parsing_instance(engine_instance, instances_service)

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    clean_filename = safe_upload_name(file.filename)

    error_msg = validate_document_upload(clean_filename, file.content_type, content)
    if error_msg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    clean_parser = (parser or "auto").strip().lower()
    try:
        # The Unstructured path runs an async job under the hood (several to
        # tens of seconds) — offload to a worker thread so it doesn't block
        # the event loop for every other in-flight request.
        row, _created = await run_in_threadpool(
            service.ingest_uploaded_bytes,
            clean_filename,
            content,
            doc_type=doc_type,
            project_code=project_code,
            originator=originator,
            suitability_code=suitability_code,
            revision_code=revision_code,
            parser=clean_parser,
            instance=resolved_instance,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return _row_to_detail_response(row)


@router.post(
    "/import/google-drive",
    response_model=GoogleDriveImportResponse,
    summary="Import one or more documents from Google Drive share links",
)
async def import_from_google_drive(
    payload: GoogleDriveImportRequest,
    service: Annotated[DocumentService, Depends(get_documents_service)],
    instances_service: Annotated[
        ParsingEngineInstancesService, Depends(get_parsing_engine_instances_service)
    ],
) -> GoogleDriveImportResponse:
    """Fetch one or more publicly link-shared Google Drive files and ingest them.

    Uses a Google API key (GOOGLE_DRIVE_API_KEY) against the Drive v3 REST
    API — works only for files shared "Anyone with the link"; a private file
    fails with a clear per-URL error rather than aborting the whole batch.
    Each fetched file runs through the same extract/store/create path as a
    regular upload (`DocumentService.ingest_uploaded_bytes`).
    """
    from app.services.google_drive_service import GoogleDriveError, GoogleDriveService

    resolved_instance = _resolve_parsing_instance(payload.engine_instance or "", instances_service)
    drive = GoogleDriveService()

    results: list[GoogleDriveImportResult] = []
    for url in payload.urls:
        try:
            filename, _mimetype, content = await run_in_threadpool(drive.fetch, url)
            clean_filename = safe_upload_name(filename)
            error_msg = validate_document_upload(clean_filename, _mimetype, content)
            if error_msg:
                results.append(GoogleDriveImportResult(url=url, ok=False, error=error_msg))
                continue

            row, _created = await run_in_threadpool(
                service.ingest_uploaded_bytes,
                clean_filename,
                content,
                doc_type=payload.doc_type or "Specification",
                project_code=payload.project_code or "",
                originator=payload.originator or "",
                suitability_code=payload.suitability_code or "S0",
                revision_code=payload.revision_code or "P01.01",
                parser=(payload.parser or "auto").strip().lower(),
                instance=resolved_instance,
            )
            results.append(GoogleDriveImportResult(url=url, ok=True, document=_row_to_detail_response(row)))
        except (GoogleDriveError, ValueError, RuntimeError) as exc:
            logger.warning("Google Drive import failed url=%s error=%s", url, exc)
            results.append(GoogleDriveImportResult(url=url, ok=False, error=str(exc)))
        except Exception as exc:  # noqa: BLE001 - one bad link must not abort the batch
            logger.exception("Google Drive import failed unexpectedly url=%s", url)
            results.append(GoogleDriveImportResult(url=url, ok=False, error=str(exc)))

    return GoogleDriveImportResponse(results=results)


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


@router.post(
    "/{document_id}/ingest",
    response_model=DocumentIngestResponse,
    summary="Run LlamaIndex ingestion (clause metadata + deontic extraction) over a document",
)
async def ingest_document(
    document_id: int,
    service: Annotated[DocumentService, Depends(get_documents_service)],
) -> DocumentIngestResponse:
    """Ingest an already-uploaded document's extracted text via LlamaIndexIngestor.

    Splits the document into clause-annotated nodes and extracts typed
    deontic ("shall"/"must"/"should"/"may") statements. Progress streams on
    the existing `GET /api/events/{document_id}` SSE channel.
    """
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found.",
        )
    text = doc.get("extracted_text") or ""
    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document has no extracted text to ingest.",
        )

    extraction_service = RuleExtractionService()
    nodes = await extraction_service.ingest_with_llamaindex(document_id, text)
    deontic_count = sum(len(node.deontic_statements) for node in nodes)

    return DocumentIngestResponse(
        document_id=document_id,
        nodes=nodes,
        deontic_statement_count=deontic_count,
    )


@router.post(
    "/{document_id}/rules/extract-drafts",
    response_model=RuleExtractionDraftListResponse,
    summary="Extract reviewable rule drafts from a document via LlamaIndex",
)
async def extract_rule_drafts(
    document_id: int,
    service: Annotated[DocumentService, Depends(get_documents_service)],
) -> RuleExtractionDraftListResponse:
    """Ingest a document and generate LlamaIndex rule drafts awaiting review.

    Unlike `POST /api/rules/extract`, results are persisted as
    `pending_review` drafts (see `rule_extraction_drafts`) rather than
    returned for immediate bulk-insert — review via
    `GET /api/documents/{id}/rules/drafts` and
    `PATCH /api/rules/drafts/{draft_id}`.
    """
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found.",
        )
    text = doc.get("extracted_text") or ""
    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document has no extracted text to extract rules from.",
        )

    extraction_service = RuleExtractionService()
    drafts = await extraction_service.extract_rule_drafts(document_id, text)
    return RuleExtractionDraftListResponse(drafts=drafts)


@router.get(
    "/{document_id}/rules/drafts",
    response_model=RuleExtractionDraftListResponse,
    summary="List rule extraction drafts for a document",
)
def list_rule_drafts(document_id: int) -> RuleExtractionDraftListResponse:
    """Return all extraction drafts for one document, newest first."""
    from app.services.rule_draft_service import RuleDraftService

    rows = RuleDraftService().list_drafts(document_id)
    return RuleExtractionDraftListResponse(
        drafts=[RuleExtractionDraft.model_validate(row) for row in rows]
    )


@router.get(
    "/{document_id}/rules/drafts/ids-preview",
    summary="Preview the IDS XML that would be produced by a document's rule drafts",
)
def preview_rule_drafts_ids(document_id: int) -> Response:
    """Render an IDS preview from a document's extraction drafts, before promotion."""
    from app.modules.contracts import RuleExtractionDraft as _RuleExtractionDraft
    from app.modules.rule_builder.ids_exporter import translate_rule_drafts_to_ids
    from app.services.rule_draft_service import RuleDraftService

    rows = RuleDraftService().list_drafts(document_id)
    drafts = [_RuleExtractionDraft.model_validate(row) for row in rows]
    try:
        xml_content = translate_rule_drafts_to_ids(drafts)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return Response(content=xml_content, media_type="application/xml")


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

