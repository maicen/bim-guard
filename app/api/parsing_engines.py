"""FastAPI router for managing configured document-parsing engine instances."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_parsing_engine_instances_service, get_profile_service
from app.api.organizations import _require_superadmin
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
from app.services.parsing_engine_instances_service import ParsingEngineInstancesService
from app.services.profile_service import ProfileService

logger = get_logger(__name__)

# These instances hold live api_key/api_url credentials server-side and can
# be repointed at an arbitrary URL (test_instance makes an outbound request
# to whatever api_url an instance carries), so registering, editing, deleting
# or connectivity-testing one is superadmin-only, matching how
# app/api/organizations.py gates other platform-wide config. Listing/reading
# stays open to any signed-in user: the document upload flow (any user, any
# org) reads this list to populate its parsing-engine picker, and the
# response never includes the actual api_key (see _to_response's
# has_api_key).
router = APIRouter()


def _to_response(row: dict[str, Any]) -> ParsingEngineInstanceResponse:
    return ParsingEngineInstanceResponse(
        id=row["id"],
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
    "/kinds",
    response_model=list[ParsingEngineKindResponse],
    summary="List registered parsing engine kinds",
)
def list_kinds(current_user: Annotated[CurrentUser, Depends(get_current_user)]) -> list[ParsingEngineKindResponse]:
    """Return metadata for every registered parsing-engine driver.

    The Settings UI renders its "Kind" selector from this list instead of a
    hardcoded set — a new backend driver (see app/modules/document_parsing/
    engines) appears here, and therefore in the UI, without any frontend change.
    """
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


@router.get("", response_model=list[ParsingEngineInstanceResponse], summary="List configured parsing engines")
def list_instances(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ParsingEngineInstancesService, Depends(get_parsing_engine_instances_service)],
) -> list[ParsingEngineInstanceResponse]:
    """Return all configured parsing-engine instances."""
    return [_to_response(row) for row in service.list_instances()]


@router.post(
    "",
    response_model=ParsingEngineInstanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a parsing engine instance",
)
def create_instance(
    payload: ParsingEngineInstanceCreateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[ParsingEngineInstancesService, Depends(get_parsing_engine_instances_service)],
) -> ParsingEngineInstanceResponse:
    """Register a new parsing-engine instance of any registered kind."""
    _require_superadmin(current_user, profiles)
    try:
        created = service.create_instance(
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


@router.get("/{instance_id}", response_model=ParsingEngineInstanceResponse, summary="Get a parsing engine instance")
def get_instance(
    instance_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ParsingEngineInstancesService, Depends(get_parsing_engine_instances_service)],
) -> ParsingEngineInstanceResponse:
    """Retrieve a single configured parsing-engine instance by ID."""
    row = service.get_instance(instance_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parsing engine instance {instance_id} not found.",
        )
    return _to_response(row)


@router.put("/{instance_id}", response_model=ParsingEngineInstanceResponse, summary="Update a parsing engine instance")
def update_instance(
    instance_id: int,
    payload: ParsingEngineInstanceUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[ParsingEngineInstancesService, Depends(get_parsing_engine_instances_service)],
) -> ParsingEngineInstanceResponse:
    """Update metadata for an existing configured parsing-engine instance."""
    _require_superadmin(current_user, profiles)
    try:
        updated = service.update_instance(
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


@router.delete("/{instance_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a parsing engine instance")
def delete_instance(
    instance_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[ParsingEngineInstancesService, Depends(get_parsing_engine_instances_service)],
) -> None:
    """Delete a configured parsing-engine instance by ID."""
    _require_superadmin(current_user, profiles)
    if not service.get_instance(instance_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parsing engine instance {instance_id} not found.",
        )
    service.delete_instance(instance_id)


@router.post(
    "/{instance_id}/test",
    response_model=ParsingEngineInstanceTestResponse,
    summary="Check connectivity to a configured parsing engine",
)
def test_instance(
    instance_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[ParsingEngineInstancesService, Depends(get_parsing_engine_instances_service)],
) -> ParsingEngineInstanceTestResponse:
    """Ping a configured instance to confirm it is reachable and responding.

    Delegates to the instance's driver (ParsingEngineRegistry.get(kind)
    .test_connection(...)) — this endpoint has no per-kind branching itself.
    """
    _require_superadmin(current_user, profiles)
    row = service.get_instance(instance_id)
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
            "Parsing engine instance test failed id=%s kind=%s error=%s", instance_id, kind, exc
        )
        return ParsingEngineInstanceTestResponse(ok=False, detail=str(exc))
