"""FastAPI router for document management and text extraction."""

import asyncio
import csv
import hashlib
import io
import json
import mimetypes
from typing import Annotated, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, StreamingResponse

from app.api.dependencies import (
    get_audit_log_service,
    get_document_access_service,
    get_documents_service,
    get_graph_service,
    get_membership_service,
    get_parsing_engine_instances_service,
    get_permission_service,
    get_profile_service,
    get_rules_service,
    get_ruleset_access_service,
)
from app.auth import CurrentUser, get_current_user, get_current_user_flexible
from app.document_upload_validation import safe_upload_name, validate_document_upload
from app.logging_config import get_logger
from app.modules.contracts import (
    CDEState,
    DocumentConfirmRequest,
    DocumentDetailResponse,
    DocumentElementBbox,
    DocumentElementBboxesResponse,
    DocumentElementWithDrafts,
    DocumentElementWithRules,
    DocumentIngestResponse,
    DocumentResponse,
    DocumentSection,
    DocumentSectionsResponse,
    DocumentSectionTreeResponse,
    DocumentUpdateRequest,
    DraftSourceMapResponse,
    DraftSourceSummary,
    GenerateDoclangRequest,
    GoogleDriveImportRequest,
    GoogleDriveImportResponse,
    GoogleDriveImportResult,
    RuleCreateRequest,
    RuleDraftExtractionRequest,
    RuleExtractionDraft,
    RuleExtractionDraftListResponse,
    RuleExtractionProgressResponse,
    RuleSourceMapResponse,
    RuleSourceSummary,
    SectionGraphResponse,
    UploadUrlRequest,
    UploadUrlResponse,
)
from app.modules.document_parsing.doclang_chunker import DocLangChunker
from app.modules.document_parsing.document_extractor import NoParsingEngineConfiguredError
from app.modules.document_parsing.smart_toc_generator import build_smart_toc
from app.modules.permissions import Action
from app.services.audit_log_service import AuditLogService
from app.services.cache import cache_service
from app.services.cde_state_machine import CDEStateMachine
from app.services.document_access_service import DocumentAccessService
from app.services.document_graph_service import DocumentGraphService
from app.services.document_orchestrator_service import DocumentOrchestratorService
from app.services.documents_service import DocumentService
from app.services.graph_database import GraphService
from app.services.membership_service import MembershipService
from app.services.parsing_engine_instances_service import ParsingEngineInstancesService
from app.services.permission_service import PermissionService
from app.services.profile_service import ProfileService
from app.services.rule_extraction_service import RuleExtractionService, RuleGenerationFailedError
from app.services.rule_source_mapping import group_rows_by_element
from app.services.rules_service import RuleService
from app.services.ruleset_access_service import RulesetAccessService

logger = get_logger(__name__)

# Documents are a shared global library gated by organization grants (see
# DocumentAccessService), the same shape as the rules catalog -- not a
# per-user or per-project owned resource. So, like app/api/rules.py, this
# requires sign-in at the router level rather than resource-by-resource
# ownership checks that don't fit the data model.
router = APIRouter(dependencies=[Depends(get_current_user)])

# A second router, mounted at the same prefix (see app/main.py), for the
# handful of routes the frontend opens via plain `<a href>`/`window.location`
# browser navigation rather than `fetch` -- those can't carry a custom
# `Authorization` header, so they need `get_current_user_flexible` (bearer
# token via header OR `?token=`) instead of `router`'s blanket
# header-only `get_current_user`.
flexible_router = APIRouter(dependencies=[Depends(get_current_user_flexible)])


def _require_document_grant(
    document_id: Optional[int],
    current_user: CurrentUser,
    memberships: MembershipService,
    document_access: DocumentAccessService,
    profiles: ProfileService,
    *,
    for_mutation: bool = False,
) -> None:
    """Raise 403 unless *current_user* may access or mutate *document_id*.

    Documents are global records whose access is gated by organization grants
    (via ``organization_document_grants``). A superadmin bypasses the check.
    For regular users, at least one of their organizations must hold a grant
    for this document.
    """
    if document_id is None:
        return
    if profiles.is_superadmin(current_user.id):
        return

    org_ids = memberships.org_ids_for_user(current_user.id)
    for org_id in org_ids:
        if document_id in document_access.list_org_grants(org_id):
            if for_mutation:
                role = memberships.role_for_user(org_id, current_user.id)
                if role not in ("owner", "admin", "member"):
                    continue
            return

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Document {document_id} not found.",
    )


class DocumentAccessChecker:
    """Callable wrapper around :func:`_require_document_grant`."""

    def __init__(
        self,
        current_user: CurrentUser,
        memberships: MembershipService,
        document_access: DocumentAccessService,
        profiles: ProfileService,
    ) -> None:
        self._current_user = current_user
        self._memberships = memberships
        self._document_access = document_access
        self._profiles = profiles

    def __call__(self, document_id: Optional[int], *, for_mutation: bool = False) -> None:
        _require_document_grant(
            document_id,
            self._current_user,
            self._memberships,
            self._document_access,
            self._profiles,
            for_mutation=for_mutation,
        )


def get_document_access_checker(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    document_access: Annotated[DocumentAccessService, Depends(get_document_access_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> DocumentAccessChecker:
    """Dependency factory for :class:`DocumentAccessChecker`."""
    return DocumentAccessChecker(current_user, memberships, document_access, profiles)


def get_document_access_checker_flexible(
    current_user: Annotated[CurrentUser, Depends(get_current_user_flexible)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    document_access: Annotated[DocumentAccessService, Depends(get_document_access_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> DocumentAccessChecker:
    """Dependency factory for :class:`DocumentAccessChecker` on flexible routes."""
    return DocumentAccessChecker(current_user, memberships, document_access, profiles)


@router.get("", response_model=list[DocumentResponse], summary="List all uploaded specification documents")
def list_documents(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DocumentService, Depends(get_documents_service)],
    response: Response,
    document_access: Annotated[DocumentAccessService, Depends(get_document_access_service)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    organization_id: Optional[int] = Query(None, description="Filter by organization ID"),
    x_org_id: Optional[str] = Header(None, alias="X-Organization-Id"),
    if_none_match: str | None = Header(default=None, alias="If-None-Match"),
) -> list[DocumentResponse]:
    """Retrieve all specification documents, optionally filtered by organization grants."""
    response.headers["Cache-Control"] = "private, max-age=5, stale-while-revalidate=30"
    rows = service.list_documents()

    effective_org_id: Optional[int] = organization_id
    if effective_org_id is None and x_org_id and x_org_id.strip().isdigit():
        effective_org_id = int(x_org_id.strip())

    if effective_org_id is not None:
        allowed_ids = set(document_access.list_org_grants(effective_org_id))
        rows = [r for r in rows if r["id"] in allowed_ids]
    elif not profiles.is_superadmin(current_user.id):
        user_org_ids = memberships.org_ids_for_user(current_user.id)
        allowed_ids: set[int] = set()
        for oid in user_org_ids:
            allowed_ids.update(document_access.list_org_grants(oid))
        rows = [r for r in rows if r["id"] in allowed_ids]
    # `documents` rows carry no `created_at`/`updated_at` column, so the ETag
    # is derived from the rows' own content (not just their count) — otherwise
    # an edit or DocLang generation that doesn't change the row count would
    # produce an identical ETag and get cached clients stuck on a 304 forever.
    etag = f'"{hashlib.sha256(repr(rows).encode()).hexdigest()[:16]}"'
    response.headers["ETag"] = etag
    if if_none_match and if_none_match.strip() == etag:
        response.status_code = status.HTTP_304_NOT_MODIFIED
        return []
    res = []
    for r in rows:
        char_count = r.get("char_count") or 0
        # DOCUMENT_SUMMARY_COLUMNS deliberately omits the (possibly large,
        # possibly offloaded) doclang_xml column from this list scan, so
        # has_doclang/size can't be read off it directly here — char_count
        # is a reliable cheap proxy since it's derived from DocLang XML
        # only when DocLang was actually generated.
        has_doclang = char_count > 0 or bool(r.get("doclang_storage_path"))
        res.append(
            DocumentResponse(
                id=r["id"],
                filename=r.get("filename", "document"),
                doc_type=r.get("doc_type") or "Specification",
                file_path=r.get("file_path"),
                upload_date=r.get("upload_date"),
                text_preview=r.get("text_preview") or "",
                char_count=char_count,
                has_doclang=has_doclang,
                doclang_storage_path=r.get("doclang_storage_path"),
                doclang_archive_path=r.get("doclang_archive_path"),
                doclang_xml="",
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


@router.get("/{document_id}", response_model=DocumentDetailResponse, summary="Get document details & DocLang-derived text")
def get_document(
    document_id: int,
    service: Annotated[DocumentService, Depends(get_documents_service)],
    response: Response,
    access_checker: Annotated[DocumentAccessChecker, Depends(get_document_access_checker)],
) -> DocumentDetailResponse:
    """Retrieve a document by ID including its full plain text, derived from DocLang."""
    access_checker(document_id)
    response.headers["Cache-Control"] = "private, max-age=10, stale-while-revalidate=60"
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found.",
        )
    text = service.get_document_text(doc)
    return DocumentDetailResponse(
        id=doc["id"],
        filename=doc.get("filename", "document"),
        doc_type=doc.get("doc_type") or "Specification",
        file_path=doc.get("file_path"),
        upload_date=doc.get("upload_date"),
        text=text,
        char_count=len(text),
        doclang_storage_path=doc.get("doclang_storage_path"),
        doclang_archive_path=doc.get("doclang_archive_path"),
        doclang_xml=service.get_doclang_content(doc),
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


@flexible_router.get("/{document_id}/file", summary="Download/stream the original uploaded document file")
def get_document_file(
    document_id: int,
    service: Annotated[DocumentService, Depends(get_documents_service)],
    access_checker: Annotated[DocumentAccessChecker, Depends(get_document_access_checker_flexible)],
) -> FileResponse:
    """Stream the original uploaded file bytes for the document viewer.

    Resolves `documents.file_path` via `ObjectStorage.materialize_local_path`
    — the same resolution path already used for re-extraction — so this
    works whether the file lives in Supabase Storage, on disk, or at a
    cached http(s) URL.
    """
    access_checker(document_id)
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


def _row_to_detail_response(row: dict, service: "DocumentService") -> DocumentDetailResponse:
    """Delegate to :meth:`DocumentOrchestratorService.row_to_detail_response`."""
    return DocumentOrchestratorService.row_to_detail_response(row, service)


def _resolve_llm_organization_id(
    document_id: int,
    doc: dict,
    requested_org_id: Optional[int],
    x_org_id: Optional[str],
    current_user: CurrentUser,
    memberships: MembershipService,
    document_access: DocumentAccessService,
    profiles: ProfileService,
) -> Optional[int]:
    """Delegate to :meth:`DocumentOrchestratorService.resolve_llm_organization_id`."""
    return DocumentOrchestratorService.resolve_llm_organization_id(
        document_id=document_id,
        doc=doc,
        requested_org_id=requested_org_id,
        x_org_id=x_org_id,
        user_id=current_user.id,
        user_org_ids=memberships.org_ids_for_user(current_user.id),
        is_superadmin=profiles.is_superadmin(current_user.id),
        org_grants_fn=document_access.list_org_grants,
    )


def _resolve_parsing_instance(
    engine_instance: str,
    organization_id: int | None,
    instances_service: ParsingEngineInstancesService,
) -> dict | None:
    """Resolve which parsing engine instance an upload should use.

    Named instance: org-scoped first, then platform-wide; 400 if named but
    found in neither. Unnamed: the org's own default if it has one, else the
    platform default. May return None when nothing is configured — the
    caller (documents_service.ingest_uploaded_bytes) is where that turns
    into a NoParsingEngineConfiguredError, so the failure is centralized in
    one place.
    """
    clean_instance_name = (engine_instance or "").strip()
    if clean_instance_name:
        resolved = None
        if organization_id is not None:
            resolved = instances_service.get_by_name(organization_id, clean_instance_name)
        if not resolved:
            resolved = instances_service.get_by_name(None, clean_instance_name)
        if not resolved:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Parsing engine instance '{clean_instance_name}' is not configured.",
            )
        return resolved
    if organization_id is not None:
        return instances_service.get_effective_default(organization_id)
    return instances_service.get_default(None)


def _no_parsing_engine_detail(
    organization_id: int | None,
    current_user: CurrentUser,
    permissions: PermissionService,
) -> str:
    """Build a permission-aware error message for a failed upload with no parsing engine.

    A caller who can self-serve (per the permission matrix) gets pointed at
    where to fix it; anyone else is told to ask someone who can.
    """
    can_self_serve = (
        organization_id is not None
        and permissions.can(organization_id, current_user.id, Action.MANAGE_PARSING_ENGINES)
    )
    if can_self_serve:
        return (
            "No document parsing engine is configured. Add a Docling instance under "
            "Admin → External Providers → Document Parsing."
        )
    return (
        "No document parsing engine is configured for this organization. "
        "Ask an organization owner or admin to configure one."
    )


@router.post("/upload-url", response_model=UploadUrlResponse, status_code=status.HTTP_201_CREATED, summary="Get a short-lived presigned URL to upload a document directly to storage")
def get_document_upload_url(
    payload: UploadUrlRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DocumentService, Depends(get_documents_service)],
) -> UploadUrlResponse:
    """Generate a direct-to-cloud upload URL for a document."""
    if payload.md5_hash:
        existing_doc = service.find_by_md5(payload.md5_hash)
        if existing_doc and existing_doc.get("storage_reference"):
            # Deduplication: file already exists in DB
            return UploadUrlResponse(
                signed_url=None,
                storage_reference=existing_doc["storage_reference"],
                token="",
                already_exists=True
            )

    from app.services.object_storage import ObjectStorage
    storage = ObjectStorage()
    
    try:
        res = storage.create_presigned_upload_url(payload.file_name, "docs")
        return UploadUrlResponse(
            signed_url=res["signed_url"],
            storage_reference=res["storage_reference"],
            token=res["token"],
            already_exists=False
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to generate upload URL: {exc}"
        )

@router.post("/confirm", response_model=DocumentDetailResponse, status_code=status.HTTP_201_CREATED, summary="Confirm document upload")
async def confirm_document_upload(
    payload: DocumentConfirmRequest,
    background_tasks: BackgroundTasks,
    service: Annotated[DocumentService, Depends(get_documents_service)],
    instances_service: Annotated[ParsingEngineInstancesService, Depends(get_parsing_engine_instances_service)],
    document_access: Annotated[DocumentAccessService, Depends(get_document_access_service)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    permissions: Annotated[PermissionService, Depends(get_permission_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> DocumentDetailResponse:
    """Confirm a direct-to-cloud document upload."""
    # Validation logic mirroring upload_document
    target_org_id = payload.organization_id
    if current_user is not None and not profiles.is_superadmin(current_user.id):
        user_orgs = memberships.org_ids_for_user(current_user.id) if memberships else []
        if target_org_id is not None:
            if target_org_id not in user_orgs:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"You do not belong to organization {target_org_id}.",
                )
        elif user_orgs:
            target_org_id = next(iter(user_orgs))

    # 1. Register the document as Processing immediately
    try:
        resolved_instance = _resolve_parsing_instance(payload.engine_instance, target_org_id, instances_service) if payload.generate_doclang else None

        row, _created = service.register_pending_document(
            filename=payload.file_name,
            storage_reference=payload.storage_reference,
            md5_hash=payload.md5_hash,
            doc_type=payload.doc_type,
            project_code=payload.project_code,
            originator=payload.originator or "",
            suitability_code=payload.suitability_code,
            revision_code=payload.revision_code,
        )
        
        # 2. Enqueue the extraction if doclang generation is requested or it's a new file
        if _created or (payload.generate_doclang and not row.get("doclang_xml")):
            background_tasks.add_task(
                service.process_pending_document_background,
                document_id=row["id"],
                filename=payload.file_name,
                storage_reference=payload.storage_reference,
                parser=payload.parser,
                instance=resolved_instance if payload.generate_doclang else None,
            )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        )
    except NoParsingEngineConfiguredError as exc:
        if exc.had_instance:
            # An engine *was* resolved but it failed (e.g. the self-hosted
            # docling-serve container is down) -- telling the caller to
            # "configure a parsing engine" would send them the wrong way.
            logger.warning("Parsing engine failed during upload: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"{exc} Check that the parsing service is running, or choose a different instance.",
            ) from exc
        detail = _no_parsing_engine_detail(payload.organization_id, current_user, permissions)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        )
        
    # Grant access
    if payload.organization_id is not None:
        document_access.grant_org_access(payload.organization_id, row["id"])
    elif current_user is not None and not profiles.is_superadmin(current_user.id):
        user_org_ids = memberships.org_ids_for_user(current_user.id)
        if user_org_ids:
            document_access.grant_org_access(user_org_ids[0], row["id"])

    return _row_to_detail_response(row, service)



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

    resolved_instance = _resolve_parsing_instance(payload.engine_instance or "", None, instances_service)
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
            results.append(GoogleDriveImportResult(url=url, ok=True, document=_row_to_detail_response(row, service)))
        except (GoogleDriveError, ValueError, RuntimeError) as exc:
            logger.warning("Google Drive import failed url=%s error=%s", url, exc)
            results.append(GoogleDriveImportResult(url=url, ok=False, error=str(exc)))
        except Exception as exc:  # noqa: BLE001 - one bad link must not abort the batch
            logger.exception("Google Drive import failed unexpectedly url=%s", url)
            results.append(GoogleDriveImportResult(url=url, ok=False, error=str(exc)))

    return GoogleDriveImportResponse(results=results)


@router.post(
    "/{document_id}/generate-doclang",
    response_model=DocumentDetailResponse,
    summary="Generate and persist DocLang XML for a document whose generation was deferred",
)
async def generate_document_doclang(
    document_id: int,
    payload: GenerateDoclangRequest,
    service: Annotated[DocumentService, Depends(get_documents_service)],
    instances_service: Annotated[
        ParsingEngineInstancesService, Depends(get_parsing_engine_instances_service)
    ],
    access_checker: Annotated[DocumentAccessChecker, Depends(get_document_access_checker)],
) -> DocumentDetailResponse:
    """Run extraction against an already-stored file and persist its DocLang XML.

    Backs the documents datatable's "Generate DocLang" action, enabled for
    documents uploaded with generation deferred (or where an earlier attempt
    failed) — see `DocumentService.generate_doclang_for_existing`.
    """
    access_checker(document_id, for_mutation=True)
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found.",
        )

    if payload.start_page is not None or payload.end_page is not None:
        if payload.start_page is None or payload.end_page is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Both start_page and end_page are required to limit extraction to a page range.",
            )
        filename = doc.get("filename", "")
        if not filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A page range can only be applied to PDF documents.",
            )
        if payload.start_page < 1 or payload.end_page < payload.start_page:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_page must be 1 or greater and end_page must be >= start_page.",
            )

    resolved_instance = _resolve_parsing_instance(payload.engine_instance or "", None, instances_service)
    clean_parser = (payload.parser or "auto").strip().lower()
    try:
        updated = await asyncio.wait_for(
            run_in_threadpool(
                service.generate_doclang_for_existing,
                document_id,
                clean_parser,
                resolved_instance,
                start_page=payload.start_page,
                end_page=payload.end_page,
            ),
            timeout=75.0,
        )
    except asyncio.TimeoutError as exc:
        logger.warning("DocLang generation for document %d timed out after 75s", document_id)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=(
                "DocLang conversion for this document timed out (exceeded 75s). "
                "Large documents like complete building codes or specifications can take "
                "several minutes on CPU; consider extracting smaller sections or uploading with a page range."
            ),
        ) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return _row_to_detail_response(updated, service)


@router.put("/{document_id}", response_model=DocumentDetailResponse, summary="Update document")
def update_document(
    document_id: int,
    payload: DocumentUpdateRequest,
    service: Annotated[DocumentService, Depends(get_documents_service)],
    access_checker: Annotated[DocumentAccessChecker, Depends(get_document_access_checker)],
) -> DocumentDetailResponse:
    """Update specification document metadata."""
    access_checker(document_id, for_mutation=True)
    existing = service.get_document(document_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found.",
        )

    filename = payload.filename if payload.filename is not None else existing.get("filename", "")
    doc_type = payload.doc_type if payload.doc_type is not None else existing.get("doc_type", "Specification")

    target_cde_state = payload.cde_state.value if hasattr(payload.cde_state, "value") else payload.cde_state
    current_cde_state = existing.get("cde_state") or CDEState.WIP.value
    if target_cde_state is not None and target_cde_state != current_cde_state:
        # Route every document CDE state change through the same gate logic
        # projects use, instead of writing cde_state directly -- otherwise a
        # document could jump straight to PUBLISHED with no gate check.
        result = CDEStateMachine.evaluate_transition(
            current_cde_state,
            target_cde_state,
            filename=filename.strip(),
            approved_by=payload.approved_by or "",
            is_approved=bool(payload.approved_by),
        )
        if not result.allowed:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.reason)

    service.update_document(
        document_id,
        filename=filename.strip(),
        doc_type=doc_type,
        project_code=payload.project_code,
        originator=payload.originator,
        suitability_code=payload.suitability_code,
        revision_code=payload.revision_code,
        cde_state=target_cde_state,
    )
    updated = service.get_document(document_id) or existing
    text = service.get_document_text(updated)

    return DocumentDetailResponse(
        id=updated["id"],
        filename=updated.get("filename", filename),
        doc_type=updated.get("doc_type") or doc_type or "Specification",
        file_path=updated.get("file_path"),
        upload_date=updated.get("upload_date"),
        text=text,
        char_count=len(text),
        doclang_storage_path=updated.get("doclang_storage_path"),
        doclang_archive_path=updated.get("doclang_archive_path"),
        doclang_xml=service.get_doclang_content(updated),
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


@router.get("/{document_id}/doclang", summary="Retrieve raw DocLang XML content")
def get_document_doclang(
    document_id: int,
    service: Annotated[DocumentService, Depends(get_documents_service)],
    access_checker: Annotated[DocumentAccessChecker, Depends(get_document_access_checker)],
) -> Response:
    """Retrieve canonical DocLang XML export (including OTSL tables) for a document."""
    access_checker(document_id)
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found.",
        )
    xml_content = service.get_doclang_content(doc)
    if not xml_content.strip():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} has no DocLang XML available.",
        )
    return Response(
        content=xml_content,
        media_type="application/xml",
        headers={"Cache-Control": "private, max-age=3600, stale-while-revalidate=86400"},
    )


@flexible_router.get("/{document_id}/assets/{filename}", summary="Stream an embedded DocLang picture/asset")
def get_document_asset(
    document_id: int,
    filename: str,
    service: Annotated[DocumentService, Depends(get_documents_service)],
    access_checker: Annotated[DocumentAccessChecker, Depends(get_document_access_checker_flexible)],
) -> Response:
    """Resolve a `assets/{filename}` reference from a document's DocLang XML to bytes.

    DocLang XML embeds pictures as `src="assets/asset_N.png"` relative
    references (see `DocLangAssetManager`) rather than inline data URIs once
    offloaded; this endpoint is what the rendered-view `<img src>` points at.
    On `flexible_router` (not `router`) so it works as a bare browser-loaded
    `<img src>` via `?token=`, the same pattern as `/file` and `/export-doclang`.
    """
    access_checker(document_id)
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found.",
        )
    asset_bytes = service.get_asset_bytes(doc, filename)
    if asset_bytes is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset '{filename}' not found for document {document_id}.",
        )
    media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return Response(
        content=asset_bytes,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=3600, stale-while-revalidate=86400"},
    )


@flexible_router.get("/{document_id}/export-doclang", summary="Export document as DocLang archive (.dclx)")
def export_document_doclang_archive(
    document_id: int,
    service: Annotated[DocumentService, Depends(get_documents_service)],
    access_checker: Annotated[DocumentAccessChecker, Depends(get_document_access_checker_flexible)],
    redirect: bool = Query(
        default=False,
        description="Redirect to direct signed storage URL if archive is pre-persisted in Supabase Storage",
    ),
) -> Response:
    """Package document into a standardized DocLang archive (.dclx) zip bundle.

    Contains document.xml and manifest.json, directly loadable in the official
    DocLang Viewer (doclang-project/viewer). If redirect=true and the archive
    is pre-persisted in Supabase Storage, returns a 307 temporary redirect to the signed URL.
    """
    from fastapi.responses import RedirectResponse

    access_checker(document_id)

    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found.",
        )

    if redirect and hasattr(service, "get_doclang_archive_signed_url"):
        signed_url = service.get_doclang_archive_signed_url(doc)
        if signed_url:
            return RedirectResponse(url=signed_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    archive_bytes = None
    if hasattr(service, "get_doclang_archive_bytes"):
        archive_bytes = service.get_doclang_archive_bytes(doc)

    if archive_bytes is None:
        xml_content = service.get_doclang_content(doc)
        if not xml_content.strip():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} has no DocLang XML to export.",
            )
        if hasattr(service, "build_doclang_archive"):
            archive_bytes = service.build_doclang_archive(doc, xml_content)
        else:
            import io
            import json
            import zipfile

            filename = doc.get("filename") or f"document_{document_id}"
            manifest = {
                "format": "doclang-archive",
                "version": "1.0",
                "document_name": filename,
                "entrypoint": "document.xml",
                "created_by": "BIM-Guard DocLang Engine",
                "metadata": {
                    "project_code": doc.get("project_code", ""),
                    "originator": doc.get("originator", ""),
                    "cde_state": doc.get("cde_state", ""),
                    "suitability_code": doc.get("suitability_code", ""),
                    "revision_code": doc.get("revision_code", ""),
                },
            }
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("document.xml", xml_content.encode("utf-8"))
                zf.writestr("manifest.json", json.dumps(manifest, indent=2).encode("utf-8"))
            archive_bytes = buf.getvalue()

    filename = doc.get("filename") or f"document_{document_id}"
    base_name = filename.rsplit(".", 1)[0]
    archive_name = f"{base_name}.dclx"

    headers = {
        "Content-Disposition": f'attachment; filename="{archive_name}"',
        "Cache-Control": "private, max-age=3600, stale-while-revalidate=86400",
    }
    return Response(
        content=archive_bytes,
        media_type="application/zip",
        headers=headers,
    )


@router.get(
    "/{document_id}/sections",
    response_model=DocumentSectionsResponse,
    summary="List heading-delimited sections/paragraphs, for scoping rule extraction",
)
def get_document_sections(
    document_id: int,
    service: Annotated[DocumentService, Depends(get_documents_service)],
    access_checker: Annotated[DocumentAccessChecker, Depends(get_document_access_checker)],
) -> DocumentSectionsResponse:
    """Split a document's DocLang XML into sections for scoped rule extraction.

    Returns no sections when the document has no DocLang XML yet (generation
    deferred or failed) — the caller should fall back to a manual excerpt.
    """
    access_checker(document_id)
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found.",
        )
    doclang_xml = service.get_doclang_content(doc).strip()
    chunks = DocLangChunker().chunk(doclang_xml) if doclang_xml else []
    sections = [
        DocumentSection(
            section_number=chunk.get("section_number"),
            section_name=chunk.get("section_name"),
            text=chunk.get("text", ""),
            char_count=chunk.get("char_count", 0),
        )
        for chunk in chunks
    ]
    return DocumentSectionsResponse(document_id=document_id, sections=sections)


async def _build_and_persist_smart_toc(
    document_id: int,
    doc: dict,
    service: DocumentService,
    graph_service: GraphService,
) -> DocumentSectionTreeResponse:
    """Delegate to :meth:`DocumentOrchestratorService.build_and_persist_smart_toc`."""
    return await DocumentOrchestratorService.build_and_persist_smart_toc(
        document_id, doc, service, graph_service
    )


@router.get(
    "/{document_id}/sections-tree",
    response_model=DocumentSectionTreeResponse,
    summary="Hierarchical, AI-arranged view of a document's sections, for scoping rule extraction",
)
async def get_document_sections_tree(
    document_id: int,
    service: Annotated[DocumentService, Depends(get_documents_service)],
    access_checker: Annotated[DocumentAccessChecker, Depends(get_document_access_checker)],
    graph_service: Annotated[GraphService, Depends(get_graph_service)],
    regenerate: bool = Query(
        default=False,
        description="Force rebuild of TOC from DocLang XML, replacing the persisted DB and Graph records",
    ),
) -> DocumentSectionTreeResponse:
    """Nest a document's detected sections into a tree for the scope picker.

    Checks the database for a persisted TOC first. If found and regenerate=False,
    returns the stored TOC immediately. When regenerate=True or no TOC is saved yet,
    re-derives the TOC, ingests it into Graph RAG, and saves the new tree to the DB.
    """
    access_checker(document_id)
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found.",
        )

    cache_key = f"section_tree:{document_id}"
    if not regenerate:
        cached = cache_service.get(cache_key)
        if cached is not None:
            return DocumentSectionTreeResponse.model_validate(cached)

        saved_toc = service.get_toc_tree(doc)
        if saved_toc:
            cache_service.set(cache_key, saved_toc)
            return DocumentSectionTreeResponse.model_validate(saved_toc)

    return await _build_and_persist_smart_toc(document_id, doc, service, graph_service)


@router.post(
    "/{document_id}/sections-tree/regenerate",
    response_model=DocumentSectionTreeResponse,
    summary="Regenerate Smart TOC from DocLang XML and replace the persisted DB and Graph records",
)
async def regenerate_document_sections_tree(
    document_id: int,
    service: Annotated[DocumentService, Depends(get_documents_service)],
    access_checker: Annotated[DocumentAccessChecker, Depends(get_document_access_checker)],
    graph_service: Annotated[GraphService, Depends(get_graph_service)],
) -> DocumentSectionTreeResponse:
    """Force re-extracting and rebuilding the Smart TOC, replacing the DB and Graph records."""
    access_checker(document_id)
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found.",
        )
    return await _build_and_persist_smart_toc(document_id, doc, service, graph_service)


@flexible_router.get(
    "/{document_id}/sections-tree/export",
    summary="Export document TOC as JSON or CSV",
)
async def export_document_sections_tree(
    document_id: int,
    service: Annotated[DocumentService, Depends(get_documents_service)],
    access_checker: Annotated[DocumentAccessChecker, Depends(get_document_access_checker_flexible)],
    graph_service: Annotated[GraphService, Depends(get_graph_service)],
    format: str = Query(
        default="json",
        pattern="^(json|csv)$",
        description="Export format: 'json' or 'csv'",
    ),
) -> Response:
    """Export the document's Table of Contents (TOC) as a downloadable JSON or CSV file."""
    access_checker(document_id)
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found.",
        )

    saved_toc = service.get_toc_tree(doc)
    if saved_toc:
        toc_resp = DocumentSectionTreeResponse.model_validate(saved_toc)
    else:
        toc_resp = await _build_and_persist_smart_toc(document_id, doc, service, graph_service)

    raw_filename = doc.get("filename") or f"document_{document_id}"
    base_name = raw_filename.rsplit(".", 1)[0]

    if format.lower() == "json":
        export_payload = {
            "document_id": document_id,
            "filename": raw_filename,
            "tree": [node.model_dump() for node in toc_resp.tree],
            "sections": [sec.model_dump() for sec in toc_resp.sections],
            "enhanced": toc_resp.enhanced,
        }
        json_content = json.dumps(export_payload, indent=2, ensure_ascii=False)
        return Response(
            content=json_content.encode("utf-8"),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{base_name}_toc.json"',
            },
        )

    # CSV export
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id",
        "section_number",
        "section_name",
        "page_number",
        "end_page_number",
        "target_ifc_classes",
        "citations",
        "key_topics",
        "char_count",
        "summary",
    ])
    for s in toc_resp.sections:
        writer.writerow([
            s.id,
            s.section_number or "",
            s.section_name or "",
            s.page_number or "",
            s.end_page_number or "",
            "; ".join(s.target_ifc_classes or []),
            "; ".join(s.citations or []),
            "; ".join(s.key_topics or []),
            s.char_count,
            s.summary or "",
        ])
    csv_content = output.getvalue()
    return Response(
        content=csv_content.encode("utf-8"),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{base_name}_toc.csv"',
        },
    )


@router.post(
    "/{document_id}/sections-tree/import",
    response_model=DocumentSectionTreeResponse,
    summary="Import document TOC from an uploaded JSON or CSV file, replacing DB and Graph records",
)
async def import_document_sections_tree(
    document_id: int,
    file: UploadFile,
    service: Annotated[DocumentService, Depends(get_documents_service)],
    access_checker: Annotated[DocumentAccessChecker, Depends(get_document_access_checker)],
    graph_service: Annotated[GraphService, Depends(get_graph_service)],
) -> DocumentSectionTreeResponse:
    """Import a customized or corrected TOC from JSON or CSV, updating DB and Graph records."""
    access_checker(document_id)
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found.",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    fname = (file.filename or "").lower()
    sections_list: list[dict] = []
    provided_tree: list[dict] | None = None

    if fname.endswith(".json"):
        try:
            data = json.loads(file_bytes.decode("utf-8"))
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid JSON file format: {exc}",
            )

        if isinstance(data, dict):
            if "tree" in data and "sections" in data:
                provided_tree = data["tree"]
                sections_list = data["sections"]
            elif "sections" in data and isinstance(data["sections"], list):
                sections_list = data["sections"]
            elif "tree" in data and isinstance(data["tree"], list):
                provided_tree = data["tree"]

                def _collect(nodes: list[dict]):
                    for n in nodes:
                        c_copy = dict(n)
                        c_copy.pop("children", None)
                        sections_list.append(c_copy)
                        if n.get("children"):
                            _collect(n["children"])

                _collect(provided_tree)
        elif isinstance(data, list):
            sections_list = data

    elif fname.endswith(".csv"):
        try:
            text = file_bytes.decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(text))
            for i, row in enumerate(reader):
                sec_id = row.get("id") or f"s{i}"
                sec_num = row.get("section_number") or None
                sec_name = row.get("section_name") or None
                p_start = int(row["page_number"]) if row.get("page_number", "").strip().isdigit() else None
                p_end = int(row["end_page_number"]) if row.get("end_page_number", "").strip().isdigit() else None
                ifc_raw = row.get("target_ifc_classes") or ""
                ifc_classes = [c.strip() for c in ifc_raw.replace(";", ",").split(",") if c.strip()]
                cit_raw = row.get("citations") or ""
                citations = [c.strip() for c in cit_raw.replace(";", ",").split(",") if c.strip()]
                top_raw = row.get("key_topics") or ""
                topics = [t.strip() for t in top_raw.replace(";", ",").split(",") if t.strip()]
                char_c = int(row["char_count"]) if row.get("char_count", "").strip().isdigit() else 0
                summary = row.get("summary") or ""
                sections_list.append({
                    "id": sec_id,
                    "section_number": sec_num,
                    "section_name": sec_name,
                    "page_number": p_start,
                    "end_page_number": p_end,
                    "target_ifc_classes": ifc_classes,
                    "citations": citations,
                    "key_topics": topics,
                    "char_count": char_c,
                    "summary": summary,
                    "text": row.get("text", ""),
                })
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse CSV file: {exc}",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Please upload a .json or .csv file.",
        )

    if not sections_list and not provided_tree:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid sections found in the uploaded file.",
        )

    if provided_tree:
        tree = provided_tree
        flat = sections_list
    else:
        tree, flat = build_smart_toc(sections_list)

    # Ingest into Neo4j/Graph RAG
    if graph_service:
        try:
            doc_title = getattr(doc, "name", None) or getattr(doc, "title", None) or f"Document {document_id}"
            DocumentGraphService(graph_service).ingest_document_tree(
                document_id, tree, flat, document_title=doc_title
            )
        except Exception as exc:
            logger.warning("Graph RAG tree ingestion failed on import for doc %d: %s", document_id, exc)

    response = DocumentSectionTreeResponse(
        document_id=document_id,
        tree=tree,
        sections=[DocumentSection(**chunk) for chunk in flat],
        enhanced=True,
    )
    # Persist the newly imported TOC in the DB (replacing the old one)
    service.save_toc_tree(document_id, response.model_dump())
    cache_key = f"section_tree:{document_id}"
    cache_service.set(cache_key, response.model_dump())
    return response


@router.get(
    "/{document_id}/sections-graph",
    response_model=SectionGraphResponse,
    summary="Graph RAG context (hierarchy, citations, IFC mapping) for a document's sections",
)
def get_document_sections_graph(
    document_id: int,
    access_checker: Annotated[DocumentAccessChecker, Depends(get_document_access_checker)],
    graph_service: Annotated[GraphService, Depends(get_graph_service)],
    section_id: Optional[str] = None,
) -> SectionGraphResponse:
    """Retrieve Graph RAG context for a document's sections."""
    access_checker(document_id)
    doc_graph = DocumentGraphService(graph_service)
    if not doc_graph.is_available():
        return SectionGraphResponse(document_id=document_id, section_id=section_id, available=False)

    if section_id:
        subgraph = doc_graph.get_section_subgraph(document_id, section_id)
        records = subgraph.get("records", [])
    else:
        cypher = """
        MATCH (s:DocumentSection {document_id: $doc_id})
        OPTIONAL MATCH (s)-[:CITES]->(cited:DocumentSection)
        OPTIONAL MATCH (s)-[:APPLIES_TO]->(ifc:IfcClass)
        RETURN s.id as section_id, s.section_number as number, s.section_name as name,
               s.summary as summary, collect(DISTINCT cited.id) as citations,
               collect(DISTINCT ifc.id) as ifc_classes
        LIMIT 200
        """
        try:
            records = graph_service.execute(cypher, {"doc_id": document_id})
        except Exception as exc:
            logger.warning("sections-graph query failed: %s", exc)
            records = []

    return SectionGraphResponse(
        document_id=document_id,
        section_id=section_id,
        records=records,
        available=True,
    )


@router.get(
    "/{document_id}/element-bboxes",
    response_model=DocumentElementBboxesResponse,
    summary="Per-rendered-block bounding boxes, for the PDF page overlay and reading-order arrows",
)
def get_document_element_bboxes(
    document_id: int,
    service: Annotated[DocumentService, Depends(get_documents_service)],
    access_checker: Annotated[DocumentAccessChecker, Depends(get_document_access_checker)],
) -> DocumentElementBboxesResponse:
    """Return one bbox per rendered block (heading/paragraph/table/picture), keyed by element id.

    Each `element_id` matches the id injected into the document's DocLang XML
    at extraction time, so the frontend can hit-test/highlight without any
    positional matching between this list and its own XML parse. Returns an
    empty list for documents predating this feature or imported as raw
    `.dclg`/`.dclx` (no Docling extraction pass, so no ids were injected).
    """
    access_checker(document_id)
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found.",
        )
    elements = [DocumentElementBbox(**record) for record in service.get_element_bboxes(doc)]
    return DocumentElementBboxesResponse(document_id=document_id, elements=elements)


@router.get(
    "/{document_id}/rule-source-map",
    response_model=RuleSourceMapResponse,
    summary="Every rule extracted from this document, mapped against its exact source element",
)
def get_document_rule_source_map(
    document_id: int,
    service: Annotated[DocumentService, Depends(get_documents_service)],
    rules_service: Annotated[RuleService, Depends(get_rules_service)],
    access_checker: Annotated[DocumentAccessChecker, Depends(get_document_access_checker)],
) -> RuleSourceMapResponse:
    """Group this document's rules by the exact element (`source_element_id`) each was extracted from.

    Rules with no `source_element_id` (extracted before that linkage existed)
    are returned separately in `unmapped_rules`, with only their approximate
    `source_page_number`/`source_bbox` location.
    """
    access_checker(document_id)
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found.",
        )

    elements = [DocumentElementBbox(**record) for record in service.get_element_bboxes(doc)]
    rows = rules_service.list_by_document(document_id)
    by_element, unmapped, orphaned = group_rows_by_element(elements, rows)

    def _summary(row: dict, match_status: str) -> RuleSourceSummary:
        return RuleSourceSummary(
            id=row["id"],
            rule_id=row.get("reference"),
            description=row.get("description"),
            severity=row.get("severity"),
            category=row.get("category"),
            source_page_number=row.get("source_page_number"),
            source_bbox=row.get("source_bbox"),
            source_element_id=row.get("source_element_id"),
            match_status=match_status,
        )

    elements_with_rules = [
        DocumentElementWithRules(
            **el.model_dump(),
            rules=[_summary(row, "exact") for row in by_element.get(el.element_id, [])],
        )
        for el in elements
    ]
    return RuleSourceMapResponse(
        document_id=document_id,
        elements=elements_with_rules,
        unmapped_rules=[_summary(row, "unmapped") for row in unmapped],
        orphaned_rules=[_summary(row, "orphaned") for row in orphaned],
    )


@router.post(
    "/{document_id}/ingest",
    response_model=DocumentIngestResponse,
    summary="Run LlamaIndex ingestion (clause metadata + deontic extraction) over a document",
)
async def ingest_document(
    document_id: int,
    service: Annotated[DocumentService, Depends(get_documents_service)],
    access_checker: Annotated[DocumentAccessChecker, Depends(get_document_access_checker)],
) -> DocumentIngestResponse:
    """Ingest an already-uploaded document's DocLang-derived text via LlamaIndexIngestor.

    Splits the document into clause-annotated nodes and extracts typed
    deontic ("shall"/"must"/"should"/"may") statements. Progress streams on
    the existing `GET /api/events/{document_id}` SSE channel.
    """
    access_checker(document_id, for_mutation=True)
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found.",
        )
    text = service.get_document_text(doc)
    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document has no extracted text to ingest.",
        )

    extraction_service = RuleExtractionService()
    nodes = await extraction_service.ingest_with_llamaindex(
        document_id, text, organization_id=doc.get("organization_id")
    )
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
    access_checker: Annotated[DocumentAccessChecker, Depends(get_document_access_checker)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    document_access: Annotated[DocumentAccessService, Depends(get_document_access_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    ruleset_access: Annotated[RulesetAccessService, Depends(get_ruleset_access_service)],
    model: Optional[str] = None,
    organization_id: Optional[int] = Query(
        None, description="Organization whose LLM provider key to use; defaults to the caller's."
    ),
    x_org_id: Optional[str] = Header(None, alias="X-Organization-Id"),
    body: Optional[RuleDraftExtractionRequest] = None,
    accept: Annotated[Optional[str], Header()] = None,
) -> RuleExtractionDraftListResponse:
    """Ingest a document and generate LlamaIndex rule drafts awaiting review.

    Unlike `POST /api/rules/extract`, results are persisted as
    `pending_review` drafts (see `rule_extraction_drafts`) rather than
    returned for immediate bulk-insert — review via
    `GET /api/documents/{id}/rules/drafts` and
    `PATCH /api/rules/drafts/{draft_id}`.

    `body.text`, when given, scopes extraction to a caller-chosen subset of
    the document (e.g. sections picked in the UI) rather than its full
    DocLang-derived text.

    A whole building code can take several minutes, well past the
    Cloudflare Tunnel's ~100s timeout (HTTP 524) for a response that sends
    nothing until it is done. A caller sending ``Accept: text/event-stream``
    gets the run as Server-Sent Events instead: ``progress`` events
    (`RuleExtractionProgressResponse`) every few seconds, then exactly one
    ``result`` (`RuleExtractionDraftListResponse`) or ``error``
    (`RuleExtractionProgressResponse` with ``status="failed"``). The stream
    rides the request's own connection, so unlike polling
    `GET .../extract-progress` it works when the server runs several
    workers. Any other caller gets the plain JSON response as before.
    """
    access_checker(document_id, for_mutation=True)
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found.",
        )
    scoped_text = body.text if body and body.text else None
    text = scoped_text or service.get_document_text(doc)
    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document has no extracted text to extract rules from.",
        )

    llm_org_id = _resolve_llm_organization_id(
        document_id, doc, organization_id, x_org_id, current_user, memberships, document_access, profiles
    )
    extraction_service = RuleExtractionService()

    async def run_extraction() -> RuleExtractionDraftListResponse:
        # A whole-document run splits on the DocLang structure (the clauses the
        # Smart TOC shows); a picked-sections run only has the joined text.
        drafts = await extraction_service.extract_rule_drafts(
            document_id,
            text,
            model=model,
            organization_id=llm_org_id,
            doclang_xml=None if scoped_text else service.get_doclang_content(doc),
            element_bboxes=None if scoped_text else service.get_element_bboxes(doc),
        )
        # Each run mints a fresh EXTRACTED-<timestamp> ruleset, the same way
        # create_rule_folder mints a new folder. Reviewing and promoting its drafts
        # is grant-checked (see RulesetAccessChecker), so without this the org that
        # just ran the extraction gets a 403 on every accept/promote.
        if llm_org_id is not None:
            for batch_ruleset_id in {d.proposed_rule.ruleset_id for d in drafts if d.proposed_rule.ruleset_id}:
                ruleset_access.add_org_grant(llm_org_id, batch_ruleset_id)
        return RuleExtractionDraftListResponse(drafts=drafts)

    if accept and "text/event-stream" in accept:
        return StreamingResponse(
            _stream_rule_extraction(document_id, run_extraction()),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    try:
        return await run_extraction()
    except RuleGenerationFailedError as exc:
        # The model rejected every clause (bad/missing key, no credit, ...): report the
        # provider's own reason, not an empty "success".
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


#: Seconds between ``progress`` events on an extraction stream -- each one is
#: also what keeps the Cloudflare Tunnel from timing the connection out.
_EXTRACTION_STREAM_INTERVAL_SECONDS = 3.0

#: Extraction runs whose stream's client went away. Held so the event loop
#: doesn't garbage-collect them mid-run: the drafts still get saved, the same
#: as when a tab closed on the old blocking request.
_detached_extractions: set[asyncio.Task] = set()


def _sse(event: str, payload: RuleExtractionProgressResponse | RuleExtractionDraftListResponse) -> str:
    return f"event: {event}\ndata: {payload.model_dump_json()}\n\n"


async def _stream_rule_extraction(document_id: int, extraction):
    """Run ``extraction`` as a task, emitting SSE progress until it finishes.

    The task is never cancelled by a disconnecting client: if this generator
    is torn down mid-run, the task is parked in ``_detached_extractions`` and
    finishes (and persists its drafts) on its own.
    """
    from app.services import extraction_progress

    # The service only starts tracking once ingestion has counted the
    # clause-nodes; reset now so ingestion doesn't report the last run's counts.
    extraction_progress.start(document_id, total=0)
    task = asyncio.ensure_future(extraction)
    finished = False
    try:
        while not task.done():
            await asyncio.wait({task}, timeout=_EXTRACTION_STREAM_INTERVAL_SECONDS)
            if task.done():
                break
            progress = extraction_progress.snapshot(document_id)
            yield _sse(
                "progress",
                RuleExtractionProgressResponse(
                    document_id=document_id,
                    total=progress.total if progress else 0,
                    completed=progress.completed if progress else 0,
                    status="running",
                ),
            )
        finished = True
        try:
            result = task.result()
        except Exception as exc:  # noqa: BLE001 - reported to the client as the stream's error event
            if not isinstance(exc, RuleGenerationFailedError):
                logger.exception("Rule-draft extraction failed document_id=%d", document_id)
            extraction_progress.fail(document_id, str(exc))
            yield _sse(
                "error",
                RuleExtractionProgressResponse(document_id=document_id, status="failed", error=str(exc)),
            )
            return
        yield _sse("result", result)
    finally:
        if not finished and not task.done():
            _detached_extractions.add(task)
            task.add_done_callback(_on_detached_extraction_done)


def _on_detached_extraction_done(task: asyncio.Task) -> None:
    _detached_extractions.discard(task)
    if not task.cancelled() and task.exception() is not None:
        logger.warning("Detached rule-draft extraction failed: %s", task.exception())


@router.get(
    "/{document_id}/rules/extract-progress",
    response_model=RuleExtractionProgressResponse,
    summary="Poll progress of an in-flight or recent rule-draft extraction",
)
def get_rule_extraction_progress(
    document_id: int,
    access_checker: Annotated[DocumentAccessChecker, Depends(get_document_access_checker)],
) -> RuleExtractionProgressResponse:
    """Return how many of a document's clause-nodes have finished extraction.

    `status="unknown"` means nothing has run for this document since the
    process started (or the last run's entry expired) -- not an error.
    """
    access_checker(document_id)
    from app.services.extraction_progress import snapshot as progress_snapshot

    progress = progress_snapshot(document_id)
    if progress is None:
        return RuleExtractionProgressResponse(document_id=document_id)
    return RuleExtractionProgressResponse(
        document_id=document_id,
        total=progress.total,
        completed=progress.completed,
        status=progress.status,
        error=progress.error,
    )


@router.get(
    "/{document_id}/rules/drafts",
    response_model=RuleExtractionDraftListResponse,
    summary="List rule extraction drafts for a document",
)
def list_rule_drafts(
    document_id: int,
    access_checker: Annotated[DocumentAccessChecker, Depends(get_document_access_checker)],
) -> RuleExtractionDraftListResponse:
    """Return all extraction drafts for one document, newest first."""
    access_checker(document_id)
    from app.services.rule_draft_service import RuleDraftService

    rows = RuleDraftService().list_drafts(document_id)
    return RuleExtractionDraftListResponse(
        drafts=[RuleExtractionDraft.model_validate(row) for row in rows]
    )


@router.get(
    "/{document_id}/draft-source-map",
    response_model=DraftSourceMapResponse,
    summary="Every pending extraction draft for this document, mapped against its exact source element",
)
def get_document_draft_source_map(
    document_id: int,
    service: Annotated[DocumentService, Depends(get_documents_service)],
    access_checker: Annotated[DocumentAccessChecker, Depends(get_document_access_checker)],
) -> DraftSourceMapResponse:
    """Group this document's pending drafts by the exact element each was extracted from.

    Same shape/semantics as `GET /{document_id}/rule-source-map`, but for
    pre-promotion drafts -- lets a reviewer see the whole document's
    extraction coverage at once instead of one draft at a time.
    """
    access_checker(document_id)
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found.",
        )

    from app.services.rule_draft_service import RuleDraftService

    elements = [DocumentElementBbox(**record) for record in service.get_element_bboxes(doc)]
    rows = RuleDraftService().list_drafts(document_id)
    by_element, unmapped, orphaned = group_rows_by_element(elements, rows)

    def _summary(row: dict, match_status: str) -> DraftSourceSummary:
        proposed = row.get("proposed_rule") or {}
        clause = row.get("clause") or {}
        return DraftSourceSummary(
            id=row["id"],
            status=row.get("status") or "pending_review",
            rule_id=proposed.get("rule_id"),
            description=proposed.get("description"),
            severity=proposed.get("severity"),
            confidence=row.get("confidence") or 0.8,
            extraction_method=row.get("extraction_method") or "litellm_legacy",
            source_page_number=clause.get("page_number"),
            source_bbox=row.get("bbox") or clause.get("bbox"),
            source_element_id=row.get("source_element_id"),
            match_status=match_status,
            proposed_rule=RuleCreateRequest.model_validate(proposed) if proposed else None,
        )

    elements_with_drafts = [
        DocumentElementWithDrafts(
            **el.model_dump(),
            drafts=[_summary(row, "exact") for row in by_element.get(el.element_id, [])],
        )
        for el in elements
    ]
    return DraftSourceMapResponse(
        document_id=document_id,
        elements=elements_with_drafts,
        unmapped_drafts=[_summary(row, "unmapped") for row in unmapped],
        orphaned_drafts=[_summary(row, "orphaned") for row in orphaned],
    )


@flexible_router.get(
    "/{document_id}/rules/drafts/ids-preview",
    summary="Preview the IDS XML that would be produced by a document's rule drafts",
)
def preview_rule_drafts_ids(
    document_id: int,
    access_checker: Annotated[DocumentAccessChecker, Depends(get_document_access_checker_flexible)],
) -> Response:
    """Render an IDS preview from a document's extraction drafts, before promotion."""
    access_checker(document_id)
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
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DocumentService, Depends(get_documents_service)],
    access_checker: Annotated[DocumentAccessChecker, Depends(get_document_access_checker)],
    audit_log: Annotated[AuditLogService, Depends(get_audit_log_service)],
) -> None:
    """Delete a document record and its stored file."""
    access_checker(document_id, for_mutation=True)
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found.",
        )
    service.delete_document_with_file(document_id)
    audit_log.record(
        actor_id=current_user.id,
        actor_email=current_user.email,
        action="document.deleted",
        resource_type="document",
        resource_id=document_id,
        metadata={"filename": doc.get("filename")},
    )

