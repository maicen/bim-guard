"""FastAPI router for managing an organization's configured parsing engine instances.

Mounted at the same `/api/organizations` prefix as app/api/organizations.py
and app/api/llm_provider_instances.py (see app/main.py), so routes read
`/api/organizations/{organization_id}/parsing-engines...`. This is the
org-scoped tier of ParsingEngineInstancesService (organization_id set) --
the existing app/api/parsing_engines.py stays the platform-wide tier
(organization_id None, superadmin-managed), used as a fallback when an org
hasn't configured its own instance (see
ParsingEngineInstancesService.get_effective_default).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import (
    get_membership_service,
    get_parsing_engine_instances_service,
    get_permission_service,
    get_profile_service,
)
from app.api.organizations import _require_membership
from app.auth import CurrentUser, get_current_user
from app.logging_config import get_logger
from app.modules.contracts import (
    ParsingEngineInstanceCreateRequest,
    ParsingEngineInstanceResponse,
    ParsingEngineInstanceTestResponse,
    ParsingEngineInstanceUpdateRequest,
    ParsingEngineKindResponse,
)
from app.modules.document_parsing.engines import ParsingEngineRegistry
from app.modules.permissions import Action
from app.services.membership_service import MembershipService
from app.services.parsing_engine_instances_service import ParsingEngineInstancesService
from app.services.permission_service import PermissionService
from app.services.profile_service import ProfileService

logger = get_logger(__name__)

# These instances hold live api_key/api_url credentials server-side, scoped
# per organization -- an org's own owner/admin manages them (gated via
# PermissionService, Action.MANAGE_PARSING_ENGINES), matching how LLM
# provider instances are gated. Listing/reading stays open to any member of
# the organization: document upload (any org member) needs to know what's
# configured, and the response never includes the actual api_key (see
# _to_response's has_api_key).
router = APIRouter()


def _to_response(row: dict[str, Any]) -> ParsingEngineInstanceResponse:
    return ParsingEngineInstanceResponse(
        id=row["id"],
        organization_id=row.get("organization_id"),
        name=row.get("name", ""),
        kind=row.get("kind", ""),
        api_url=row.get("api_url", ""),
        has_api_key=bool((row.get("api_key") or "").strip()),
        strategy=row.get("strategy") or "auto",
        is_default=bool(row.get("is_default", False)),
        is_enabled=bool(row.get("is_enabled", True)),
        notes=row.get("notes", ""),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


@router.get(
    "/{organization_id}/parsing-engines/kinds",
    response_model=list[ParsingEngineKindResponse],
    summary="List registered parsing engine kinds",
)
def list_kinds(
    organization_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> list[ParsingEngineKindResponse]:
    """Return metadata for every registered parsing-engine driver."""
    _require_membership(organization_id, current_user, memberships, profiles)
    return [
        ParsingEngineKindResponse(
            kind=driver.kind,
            family=driver.family,
            display_name=driver.display_name,
            description=driver.description,
            requires_api_key=driver.requires_api_key,
            supports_strategy=driver.supports_strategy,
            url_placeholder=driver.url_placeholder,
        )
        for driver in sorted(ParsingEngineRegistry.all(), key=lambda d: d.kind)
    ]


@router.get(
    "/{organization_id}/parsing-engines",
    response_model=list[ParsingEngineInstanceResponse],
    summary="List an organization's configured parsing engines",
)
def list_instances(
    organization_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[ParsingEngineInstancesService, Depends(get_parsing_engine_instances_service)],
) -> list[ParsingEngineInstanceResponse]:
    """Return every parsing-engine instance configured for this organization."""
    _require_membership(organization_id, current_user, memberships, profiles)
    return [_to_response(row) for row in service.list_instances(organization_id)]


@router.post(
    "/{organization_id}/parsing-engines",
    response_model=ParsingEngineInstanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a parsing engine instance",
)
def create_instance(
    organization_id: int,
    payload: ParsingEngineInstanceCreateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    permissions: Annotated[PermissionService, Depends(get_permission_service)],
    service: Annotated[ParsingEngineInstancesService, Depends(get_parsing_engine_instances_service)],
) -> ParsingEngineInstanceResponse:
    """Register a new parsing-engine instance of any registered kind for this organization."""
    permissions.require(organization_id, current_user, Action.MANAGE_PARSING_ENGINES)
    try:
        created = service.create_instance(
            organization_id,
            name=payload.name,
            kind=payload.kind,
            api_url=payload.api_url,
            api_key=payload.api_key,
            strategy=payload.strategy or "auto",
            is_default=bool(payload.is_default),
            is_enabled=payload.is_enabled if payload.is_enabled is not None else True,
            notes=payload.notes or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_response(created)


@router.get(
    "/{organization_id}/parsing-engines/{instance_id}",
    response_model=ParsingEngineInstanceResponse,
    summary="Get a parsing engine instance",
)
def get_instance(
    organization_id: int,
    instance_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[ParsingEngineInstancesService, Depends(get_parsing_engine_instances_service)],
) -> ParsingEngineInstanceResponse:
    """Retrieve a single configured parsing-engine instance by ID."""
    _require_membership(organization_id, current_user, memberships, profiles)
    row = service.get_instance(organization_id, instance_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parsing engine instance {instance_id} not found.",
        )
    return _to_response(row)


@router.put(
    "/{organization_id}/parsing-engines/{instance_id}",
    response_model=ParsingEngineInstanceResponse,
    summary="Update a parsing engine instance",
)
def update_instance(
    organization_id: int,
    instance_id: int,
    payload: ParsingEngineInstanceUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    permissions: Annotated[PermissionService, Depends(get_permission_service)],
    service: Annotated[ParsingEngineInstancesService, Depends(get_parsing_engine_instances_service)],
) -> ParsingEngineInstanceResponse:
    """Update metadata for an existing configured parsing-engine instance."""
    permissions.require(organization_id, current_user, Action.MANAGE_PARSING_ENGINES)
    try:
        updated = service.update_instance(
            organization_id,
            instance_id,
            name=payload.name,
            api_url=payload.api_url,
            api_key=payload.api_key,
            strategy=payload.strategy,
            is_default=payload.is_default,
            is_enabled=payload.is_enabled,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parsing engine instance {instance_id} not found.",
        )
    return _to_response(updated)


@router.delete(
    "/{organization_id}/parsing-engines/{instance_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a parsing engine instance",
)
def delete_instance(
    organization_id: int,
    instance_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    permissions: Annotated[PermissionService, Depends(get_permission_service)],
    service: Annotated[ParsingEngineInstancesService, Depends(get_parsing_engine_instances_service)],
) -> None:
    """Delete a configured parsing-engine instance by ID."""
    permissions.require(organization_id, current_user, Action.MANAGE_PARSING_ENGINES)
    if not service.get_instance(organization_id, instance_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parsing engine instance {instance_id} not found.",
        )
    service.delete_instance(organization_id, instance_id)


@router.post(
    "/{organization_id}/parsing-engines/{instance_id}/test",
    response_model=ParsingEngineInstanceTestResponse,
    summary="Check connectivity to a configured parsing engine",
)
def test_instance(
    organization_id: int,
    instance_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    permissions: Annotated[PermissionService, Depends(get_permission_service)],
    service: Annotated[ParsingEngineInstancesService, Depends(get_parsing_engine_instances_service)],
) -> ParsingEngineInstanceTestResponse:
    """Ping a configured instance to confirm it is reachable and responding.

    Delegates to the instance's driver (ParsingEngineRegistry.get(kind)
    .test_connection(...)) — this endpoint has no per-kind branching itself.
    """
    permissions.require(organization_id, current_user, Action.MANAGE_PARSING_ENGINES)
    row = service.get_instance(organization_id, instance_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parsing engine instance {instance_id} not found.",
        )

    kind = row.get("kind", "")
    try:
        driver = ParsingEngineRegistry.get(kind)
        result = driver.test_connection(
            api_key=row.get("api_key") or "",
            api_url=(row.get("api_url") or "").rstrip("/"),
        )
        return ParsingEngineInstanceTestResponse(ok=result.ok, detail=result.detail)
    except Exception as exc:
        logger.warning(
            "Parsing engine instance test failed org=%s id=%s kind=%s error=%s",
            organization_id,
            instance_id,
            kind,
            exc,
        )
        return ParsingEngineInstanceTestResponse(ok=False, detail=str(exc))
