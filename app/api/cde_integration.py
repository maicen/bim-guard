"""openCDE API Implementation (Foundation API & Documents API).

buildingSMART openCDE standards:
- Foundation API: https://github.com/buildingSMART/foundation-api
- Documents API: https://github.com/buildingSMART/documents-API
- OpenCDE Ecosystem: https://github.com/buildingSMART/OpenCDE-API

Features:
- Standard version negotiation (/api/cde/versions)
- User profile (/api/cde/v1/user)
- OAuth 2.0 configuration & token handling
- OData v4 query filtering ($filter, $top, $skip, $select, $orderby)
- HTTP ETag generation and 304 Not Modified caching
- ISO 19650 governed document synchronization & webhook triggers
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from fastapi.concurrency import run_in_threadpool

from app.api.dependencies import (
    get_documents_service,
    get_membership_service,
    get_models_service,
    get_profile_service,
    get_projects_service,
)
from app.api.projects import get_authorized_project, require_project_access
from app.auth import CurrentUser, get_current_user
from app.logging_config import get_logger
from app.modules.contracts import (
    CDEAuthConfigResponse,
    CDEDocumentItem,
    CDEPromoteRequest,
    CDEPromoteResponse,
    CDESyncRequest,
    CDESyncResponse,
    CDETokenResponse,
    CDEUserResponse,
    CDEVersionItem,
    CDEVersionsResponse,
    CDEWebhookPayload,
)
from app.services.cde_state_machine import CDEStateMachine
from app.services.documents_service import DocumentService
from app.services.exchange_disposition import DispositionInput, compute_disposition
from app.services.ids_validation_service import IDSValidationService
from app.services.membership_service import MembershipService
from app.services.models_service import ModelsService
from app.services.opencde_client import OpenCDEClientError, OpenCDEDocumentsClient
from app.services.profile_service import ProfileService
from app.services.projects_service import ProjectsService
from app.services.report_artifacts import ReportArtifactService
from app.utils import safe_upload_name, validate_document_upload

logger = get_logger(__name__)

router = APIRouter()


# ------------------------------------------------------------------------------
# Helpers: ETag and OData v4 Filtering
# ------------------------------------------------------------------------------


def compute_etag(data: Any) -> str:
    """Compute strong ETag digest from serializable data."""
    serialized = json.dumps(data, sort_keys=True, default=str)
    return f'"{hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]}"'


def apply_odata_filter(
    items: list[dict[str, Any]],
    filter_expr: str | None = None,
    top: int | None = None,
    skip: int | None = None,
    orderby: str | None = None,
) -> list[dict[str, Any]]:
    """Apply basic OData v4 filtering, sorting, and pagination."""
    filtered = items

    # Basic substring or equality filter
    if filter_expr:
        expr = filter_expr.strip()
        if " eq " in expr:
            parts = expr.split(" eq ")
            if len(parts) == 2:
                key, val = parts[0].strip(), parts[1].strip().strip("'\"")
                filtered = [i for i in filtered if str(i.get(key, "")) == val]
        elif "contains(" in expr:
            # e.g. contains(name, 'Clinic')
            inner = expr[expr.find("(") + 1 : expr.rfind(")")]
            parts = inner.split(",")
            if len(parts) == 2:
                key, needle = parts[0].strip(), parts[1].strip().strip("'\"")
                filtered = [i for i in filtered if needle.lower() in str(i.get(key, "")).lower()]

    # Ordering
    if orderby:
        order_parts = orderby.strip().split()
        order_field = order_parts[0]
        descending = len(order_parts) > 1 and order_parts[1].lower() == "desc"
        filtered = sorted(
            filtered,
            key=lambda x: str(x.get(order_field, "")),
            reverse=descending,
        )

    # Pagination
    if skip and skip > 0:
        filtered = filtered[skip:]
    if top and top > 0:
        filtered = filtered[:top]

    return filtered


# ------------------------------------------------------------------------------
# 1. OpenCDE Foundation API Endpoints
# ------------------------------------------------------------------------------


@router.get(
    "/versions",
    response_model=CDEVersionsResponse,
    summary="OpenCDE Versions Discovery",
    tags=["OpenCDE Foundation"],
)
def get_cde_versions() -> CDEVersionsResponse:
    """Return list of supported OpenCDE API versions per buildingSMART Foundation API spec."""
    return CDEVersionsResponse(
        versions=[
            CDEVersionItem(version="1.0", api_type="foundation", detailed_version="1.0.0"),
            CDEVersionItem(version="1.0", api_type="documents", detailed_version="1.0.0"),
            CDEVersionItem(version="2.1", api_type="bcf", detailed_version="2.1.0"),
        ]
    )


@router.get(
    "/v1/user",
    response_model=CDEUserResponse,
    summary="OpenCDE User Profile",
    tags=["OpenCDE Foundation"],
)
def get_cde_user() -> CDEUserResponse:
    """Return authenticated user or service agent context in standard OpenCDE format."""
    return CDEUserResponse(
        id="usr_bimguard_admin",
        name="BIMGuard Engineering Agent",
        email="engineering@bimguard.ai",
        role="BIM Coordinator / Compliance Officer",
    )


@router.get(
    "/v1/auth/config",
    response_model=CDEAuthConfigResponse,
    summary="OpenCDE OAuth2 Configuration Discovery",
    tags=["OpenCDE Foundation", "Public"],
)
def get_cde_auth_config() -> CDEAuthConfigResponse:
    """Return OpenCDE OAuth2 discovery configuration metadata."""
    return CDEAuthConfigResponse(
        oauth2_auth_url="/api/cde/v1/auth/authorize",
        oauth2_token_url="/api/cde/v1/auth/token",
        supported_scopes=["foundation.read", "documents.read", "documents.write", "bcf.read", "bcf.write"],
        token_type="Bearer",
    )


@router.post(
    "/v1/auth/token",
    response_model=CDETokenResponse,
    summary="OpenCDE Token Exchange / Refresh",
    tags=["OpenCDE Foundation", "Public"],
)
def exchange_cde_token(payload: dict[str, Any]) -> CDETokenResponse:
    """Simulate standard OpenCDE OAuth 2.0 Bearer token exchange."""
    grant_type = payload.get("grant_type", "client_credentials")
    return CDETokenResponse(
        access_token="bimguard_cde_access_token_demo_2026",
        token_type="Bearer",
        expires_in=86400,
        scope="foundation.read documents.read documents.write bcf.read bcf.write",
        grant_type=grant_type,
    )


# ------------------------------------------------------------------------------
# 2. OpenCDE Documents API Endpoints
# ------------------------------------------------------------------------------


@router.get(
    "/v1/projects/{project_id}/documents",
    response_model=list[CDEDocumentItem],
    summary="OpenCDE Project Documents List",
    tags=["OpenCDE Documents"],
)
def list_cde_documents(
    project_id: int,
    request: Request,
    response: Response,
    _project_auth: Annotated[dict, Depends(get_authorized_project)],
    projects_service: Annotated[ProjectsService, Depends(get_projects_service)],
    models_service: Annotated[ModelsService, Depends(get_models_service)],
    documents_service: Annotated[DocumentService, Depends(get_documents_service)],
    filter: Optional[str] = Query(None, alias="$filter", description="OData filter expression"),
    top: Optional[int] = Query(None, alias="$top", description="OData top page limit"),
    skip: Optional[int] = Query(None, alias="$skip", description="OData skip offset"),
    orderby: Optional[str] = Query(None, alias="$orderby", description="OData sort order"),
    if_none_match: Optional[str] = Header(None, alias="If-None-Match"),
) -> list[CDEDocumentItem]:
    """List documents and models for a project conforming to OpenCDE Documents API and ISO 19650."""
    try:
        project = projects_service.get_project(project_id) or {}
    except Exception:
        project = {}

    items: list[dict[str, Any]] = []

    # 1. IFC Models attached to project
    try:
        files = models_service.list_models(project_id)
    except Exception:
        files = []
    for f in files:
        file_id = str(f.get("id") or f.get("file_name", "model.ifc"))
        etag = f'"{hashlib.sha256(f.get("file_path", "").encode()).hexdigest()[:16]}"'
        items.append(
            {
                "id": f"ifc_{file_id}",
                "name": f.get("file_name", "model.ifc"),
                "document_type": "IFC",
                "size_bytes": 0,
                "etag": etag,
                "url": f.get("file_path"),
                "created_at": f.get("uploaded_at"),
                "project_code": f.get("project_code") or project.get("project_code") or "",
                "originator": f.get("originator") or project.get("originator") or "",
                "volume_system": f.get("volume_system") or project.get("volume_system") or "",
                "level": f.get("level") or project.get("level") or "",
                "type": f.get("type") or "M3",
                "role": f.get("role") or "primary",
                "number": f.get("number") or "0001",
                "suitability_code": f.get("suitability_code") or project.get("suitability_code") or "S0",
                "revision_code": f.get("revision_code") or project.get("revision_code") or "P01.01",
                "cde_state": f.get("cde_state") or project.get("cde_state") or "WIP",
            }
        )

    # 2. Project specification documents (scoped to project bindings, client documents, or matching project_code)
    try:
        from app.bootstrap import get_container

        document_access = get_container().document_access_service
        bound_ids = set(document_access.list_project_bindings(project_id))
    except Exception:
        bound_ids = set()

    try:
        client_docs = projects_service.get_client_documents_by_project(project_id)
        client_doc_ids = {cd.get("document_id") for cd in client_docs if cd.get("document_id")}
    except Exception:
        client_doc_ids = set()

    project_code = project.get("project_code")
    all_docs = documents_service.list_documents()
    docs = [
        d
        for d in all_docs
        if d.get("id") in bound_ids
        or d.get("id") in client_doc_ids
        or (project_code and d.get("project_code") == project_code)
    ]
    for d in docs:
        d_id = str(d.get("id"))
        etag = f'"{hashlib.sha256(str(d_id).encode()).hexdigest()[:16]}"'
        items.append(
            {
                "id": f"doc_{d_id}",
                "name": d.get("filename", "document.pdf"),
                "document_type": d.get("doc_type") or "Specification",
                "size_bytes": d.get("char_count", 0),
                "etag": etag,
                "url": d.get("file_path"),
                "created_at": d.get("upload_date"),
                "project_code": d.get("project_code") or project.get("project_code") or "",
                "originator": d.get("originator") or project.get("originator") or "",
                "volume_system": d.get("volume_system") or project.get("volume_system") or "",
                "level": d.get("level") or project.get("level") or "",
                "type": d.get("type") or "SP",
                "role": d.get("role") or "",
                "number": d.get("number") or "0001",
                "suitability_code": d.get("suitability_code") or "S0",
                "revision_code": d.get("revision_code") or "P01.01",
                "cde_state": d.get("cde_state") or "WIP",
            }
        )

    # Apply OData filter/sort/slice
    filtered = apply_odata_filter(items, filter_expr=filter, top=top, skip=skip, orderby=orderby)

    # ETag computation & validation
    current_etag = compute_etag(filtered)
    response.headers["ETag"] = current_etag

    if if_none_match and if_none_match.strip() == current_etag:
        response.status_code = status.HTTP_304_NOT_MODIFIED
        return []

    return [CDEDocumentItem(**item) for item in filtered]


@router.post(
    "/v1/projects/{project_id}/documents/sync",
    response_model=CDESyncResponse,
    summary="Synchronize external CDE documents & models",
    tags=["OpenCDE Documents"],
)
async def sync_external_cde_documents(
    project_id: int,
    payload: CDESyncRequest,
    request: Request,
    project: Annotated[dict, Depends(get_authorized_project)],
    documents_service: Annotated[DocumentService, Depends(get_documents_service)],
) -> CDESyncResponse:
    """Pull an external openCDE Documents API server's project documents into BIM-Guard.

    Lists the external project's documents via the CDE's admin REST API
    (``GET /api/projects/{id}/documents``), optionally narrowed to
    ``payload.document_ids``, downloads each one's content
    (``GET .../documents/{id}/content``), and ingests it through the same
    extract/store/create path as a regular upload -- one bad document does not
    abort the batch, matching the Google Drive import endpoint's behavior.
    """
    auth_header = request.headers.get("authorization", "")
    caller_token = auth_header.removeprefix("Bearer ").strip() if auth_header else ""
    access_token = payload.access_token or caller_token
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No access token available for the external CDE -- pass one in "
            "the request body, or call this endpoint with your own bearer token.",
        )

    client = OpenCDEDocumentsClient(base_url=payload.cde_server_url, access_token=access_token)

    try:
        documents = await run_in_threadpool(client.list_project_documents, payload.external_project_id)
    except OpenCDEClientError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    if payload.document_ids:
        wanted_ids = set(payload.document_ids)
        documents = [d for d in documents if str(d.get("id")) in wanted_ids]

    synced_files: list[str] = []
    errors: list[str] = []
    for document in documents:
        document_id = str(document.get("id") or "")
        if not document_id or not document.get("contentAvailable", True):
            continue
        try:
            filename, content_type, content = await run_in_threadpool(
                client.download_document, payload.external_project_id, document_id
            )
            clean_filename = safe_upload_name(filename or document.get("fileName") or document_id)
            error_msg = validate_document_upload(clean_filename, content_type, content)
            if error_msg:
                errors.append(f"{clean_filename}: {error_msg}")
                continue

            row, _created = await run_in_threadpool(
                documents_service.ingest_uploaded_bytes,
                clean_filename,
                content,
                doc_type="Specification",
                project_code=project.get("project_code", "") or "",
            )
            synced_files.append(clean_filename)
        except OpenCDEClientError as exc:
            logger.warning(
                "OpenCDE sync download failed project_id=%d document_id=%s error=%s",
                project_id,
                document_id,
                exc,
            )
            errors.append(f"{document_id}: {exc}")
        except Exception as exc:  # noqa: BLE001 - one bad document must not abort the batch
            logger.exception(
                "OpenCDE sync ingestion failed unexpectedly project_id=%d document_id=%s",
                project_id,
                document_id,
            )
            errors.append(f"{document_id}: {exc}")

    if payload.auto_analyze and synced_files:
        logger.info(
            "OpenCDE sync requested auto_analyze project_id=%d, but automatic analysis "
            "triggering is not wired up yet -- run analysis manually for now.",
            project_id,
        )

    logger.info(
        "OpenCDE sync executed project_id=%d cde_url=%s synced=%d errors=%d",
        project_id,
        payload.cde_server_url,
        len(synced_files),
        len(errors),
    )

    return CDESyncResponse(
        success=len(errors) == 0,
        synced_documents_count=len(synced_files),
        synced_files=synced_files,
        errors=errors,
        message=f"Synchronized {len(synced_files)} document(s) from external CDE."
        + (f" {len(errors)} failed." if errors else ""),
    )


@router.post(
    "/v1/webhooks/cde-sync",
    response_model=dict[str, Any],
    summary="OpenCDE Ingestion Webhook Trigger",
    tags=["OpenCDE Documents"],
)
def handle_cde_webhook(
    payload: CDEWebhookPayload,
    projects_service: Annotated[ProjectsService, Depends(get_projects_service)],
) -> dict[str, Any]:
    """Process incoming OpenCDE webhook event to automatically ingest updated IFC models and documents.

    Deliberately left without a ``get_current_user`` dependency: a webhook is
    called by an external CDE system, not a signed-in browser session, so it
    can never carry a Supabase bearer token. It is also inert today -- it
    only logs and echoes the payload back, with no database read or write --
    so there is nothing here for the missing auth to actually protect.
    Wiring it up for real (persisting ingested models/documents) should come
    with its own verification (a shared webhook secret or signature header),
    not a user JWT.
    """
    logger.info(
        "Received OpenCDE webhook event=%s doc=%s ext_project=%s",
        payload.event_type,
        payload.document_name,
        payload.external_project_id,
    )

    # Return success acknowledgement
    return {
        "status": "received",
        "event": payload.event_type,
        "document_name": payload.document_name,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post(
    "/gate1/promote",
    response_model=CDEPromoteResponse,
    summary="Promote CDE state through Gate 1 (WIP -> SHARED)",
    tags=["OpenCDE Documents"],
)
def promote_gate1(
    payload: CDEPromoteRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    projects_service: Annotated[ProjectsService, Depends(get_projects_service)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> CDEPromoteResponse:
    """Promote a project's CDE state from WIP to SHARED if there are no critical errors."""
    state_machine = CDEStateMachine(projects_service=projects_service)
    require_project_access(
        payload.project_id, current_user, projects_service, memberships, profiles
    )

    # Real Tier-1/Tier-4 signal: the project's most recently persisted audit
    # report's issue count. This counts every open finding rather than only
    # critical-severity ones -- report_artifacts does not currently persist a
    # severity breakdown -- but it replaces the previous hardcoded 0, which
    # let every project promote regardless of outstanding findings.
    latest_report = ReportArtifactService().latest_bcf(payload.project_id)
    critical_issues_count = int(latest_report.get("issue_count") or 0) if latest_report else 0

    # Real Tier-2 signal: buildingSMART IDS 1.0 execution against the
    # project's IFC model, when a ruleset was supplied. With no ruleset,
    # Tier 2 is not applicable to this promotion rather than treated as failed.
    ids_check_passed = True
    ids_result: Any = None
    if payload.ruleset_id:
        ids_result = IDSValidationService().validate_project(payload.project_id, payload.ruleset_id)
        ids_check_passed = ids_result.passed
        if not ids_result.passed:
            logger.info(
                "Gate 1 IDS check failed project_id=%d ruleset_id=%s error=%s failed_specs=%s",
                payload.project_id,
                payload.ruleset_id,
                ids_result.error,
                [spec.name for spec in ids_result.failed_specifications],
            )

    disposition = compute_disposition(
        DispositionInput(
            tier2_result=ids_result,
            tier4_critical_count=critical_issues_count,
        )
    )

    # The state machine transition throws a ValueError on failure.
    try:
        updated_project = state_machine.transition_project(
            project_id=payload.project_id,
            target_state="SHARED",
            actor=payload.actor or "Lead Appointed Party",
            critical_issues_count=critical_issues_count,
            ids_check_passed=ids_check_passed,
        )
        return CDEPromoteResponse(
            success=True,
            cde_state=updated_project.get("cde_state", "SHARED"),
            message="Successfully promoted to SHARED state.",
            disposition=disposition,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
