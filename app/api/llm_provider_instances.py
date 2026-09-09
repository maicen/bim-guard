"""FastAPI router for managing an organization's configured LLM provider instances.

Mounted at the same `/api/organizations` prefix as app/api/organizations.py
(see app/main.py) so routes read `/api/organizations/{organization_id}/
llm-providers...`, matching the `.../ruleset-grants`, `.../project-grants`
nested-resource convention — kept in its own file (like
app/api/parsing_engines.py is split from documents.py) rather than growing
organizations.py further.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import (
    get_llm_provider_instances_service,
    get_membership_service,
    get_profile_service,
)
from app.api.organizations import _require_membership, _require_org_admin
from app.auth import CurrentUser, get_current_user
from app.logging_config import get_logger
from app.modules.contracts import (
    LLMProviderInstanceCreateRequest,
    LLMProviderInstanceResponse,
    LLMProviderInstanceTestResponse,
    LLMProviderInstanceUpdateRequest,
    LLMProviderKindResponse,
    LLMProviderModelResponse,
)
from app.modules.llm_providers import LLMProviderRegistry
from app.services.llm_provider_instances_service import LLMProviderInstancesService
from app.services.membership_service import MembershipService
from app.services.profile_service import ProfileService

logger = get_logger(__name__)

# These instances hold live api_key/api_base credentials server-side, scoped
# per organization -- an org's own owner/admin manages them (not just
# platform superadmins, unlike parsing engines), matching how every other
# org-mutation endpoint in app/api/organizations.py is gated. Listing/reading
# and the model catalogue stay open to any member of the organization: the
# rule-extraction model picker (any org member) needs to read both, and the
# response never includes the actual api_key (see _to_response's has_api_key).
router = APIRouter()


def _to_response(row: dict[str, Any]) -> LLMProviderInstanceResponse:
    return LLMProviderInstanceResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        name=row.get("name", ""),
        kind=row.get("kind", ""),
        api_base=row.get("api_base", ""),
        has_api_key=bool((row.get("api_key") or "").strip()),
        is_default=bool(row.get("is_default", False)),
        is_enabled=bool(row.get("is_enabled", True)),
        notes=row.get("notes", ""),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


@router.get(
    "/{organization_id}/llm-providers/kinds",
    response_model=list[LLMProviderKindResponse],
    summary="List registered LLM provider kinds",
)
def list_kinds(
    organization_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> list[LLMProviderKindResponse]:
    """Return metadata for every registered LLM provider driver.

    The External Providers UI renders its "Kind" selector from this list
    instead of a hardcoded set — a new backend driver (see
    app/modules/llm_providers) appears here, and therefore in the UI,
    without any frontend change.
    """
    _require_membership(organization_id, current_user, memberships, profiles)
    return [
        LLMProviderKindResponse(
            kind=driver.kind,
            display_name=driver.display_name,
            description=driver.description,
            requires_api_key=driver.requires_api_key,
            default_api_base=driver.default_api_base,
            url_placeholder=driver.url_placeholder,
        )
        for driver in sorted(LLMProviderRegistry.all(), key=lambda d: d.kind)
    ]


@router.get(
    "/{organization_id}/llm-providers",
    response_model=list[LLMProviderInstanceResponse],
    summary="List an organization's configured LLM providers",
)
def list_instances(
    organization_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[LLMProviderInstancesService, Depends(get_llm_provider_instances_service)],
) -> list[LLMProviderInstanceResponse]:
    """Return every LLM provider instance configured for this organization."""
    _require_membership(organization_id, current_user, memberships, profiles)
    return [_to_response(row) for row in service.list_instances(organization_id)]


@router.post(
    "/{organization_id}/llm-providers",
    response_model=LLMProviderInstanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register an LLM provider instance",
)
def create_instance(
    organization_id: int,
    payload: LLMProviderInstanceCreateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[LLMProviderInstancesService, Depends(get_llm_provider_instances_service)],
) -> LLMProviderInstanceResponse:
    """Register a new LLM provider instance of any registered kind for this organization."""
    _require_org_admin(organization_id, current_user, memberships, profiles)
    try:
        created = service.create_instance(
            organization_id,
            name=payload.name,
            kind=payload.kind,
            api_key=payload.api_key,
            api_base=payload.api_base or "",
            is_default=bool(payload.is_default),
            is_enabled=payload.is_enabled if payload.is_enabled is not None else True,
            notes=payload.notes or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_response(created)


@router.get(
    "/{organization_id}/llm-providers/{instance_id}",
    response_model=LLMProviderInstanceResponse,
    summary="Get an LLM provider instance",
)
def get_instance(
    organization_id: int,
    instance_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[LLMProviderInstancesService, Depends(get_llm_provider_instances_service)],
) -> LLMProviderInstanceResponse:
    """Retrieve a single configured LLM provider instance by ID."""
    _require_membership(organization_id, current_user, memberships, profiles)
    row = service.get_instance(organization_id, instance_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"LLM provider instance {instance_id} not found.",
        )
    return _to_response(row)


@router.put(
    "/{organization_id}/llm-providers/{instance_id}",
    response_model=LLMProviderInstanceResponse,
    summary="Update an LLM provider instance",
)
def update_instance(
    organization_id: int,
    instance_id: int,
    payload: LLMProviderInstanceUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[LLMProviderInstancesService, Depends(get_llm_provider_instances_service)],
) -> LLMProviderInstanceResponse:
    """Update metadata for an existing configured LLM provider instance."""
    _require_org_admin(organization_id, current_user, memberships, profiles)
    try:
        updated = service.update_instance(
            organization_id,
            instance_id,
            name=payload.name,
            api_key=payload.api_key,
            api_base=payload.api_base,
            is_default=payload.is_default,
            is_enabled=payload.is_enabled,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"LLM provider instance {instance_id} not found.",
        )
    return _to_response(updated)


@router.delete(
    "/{organization_id}/llm-providers/{instance_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an LLM provider instance",
)
def delete_instance(
    organization_id: int,
    instance_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[LLMProviderInstancesService, Depends(get_llm_provider_instances_service)],
) -> None:
    """Delete a configured LLM provider instance by ID."""
    _require_org_admin(organization_id, current_user, memberships, profiles)
    if not service.get_instance(organization_id, instance_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"LLM provider instance {instance_id} not found.",
        )
    service.delete_instance(organization_id, instance_id)


@router.post(
    "/{organization_id}/llm-providers/{instance_id}/test",
    response_model=LLMProviderInstanceTestResponse,
    summary="Check connectivity to a configured LLM provider",
)
async def test_instance(
    organization_id: int,
    instance_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[LLMProviderInstancesService, Depends(get_llm_provider_instances_service)],
) -> LLMProviderInstanceTestResponse:
    """Ping a configured instance to confirm it is reachable and authorized.

    Delegates to the instance's driver (LLMProviderRegistry.get(kind)
    .test_connection(...)) — this endpoint has no per-kind branching itself.
    """
    _require_org_admin(organization_id, current_user, memberships, profiles)
    try:
        result = await service.test_instance(organization_id, instance_id)
        return LLMProviderInstanceTestResponse(ok=result.ok, detail=result.detail)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning(
            "LLM provider instance test failed org=%s id=%s error=%s", organization_id, instance_id, exc
        )
        return LLMProviderInstanceTestResponse(ok=False, detail=str(exc))


@router.get(
    "/{organization_id}/llm-providers/{instance_id}/models",
    response_model=list[LLMProviderModelResponse],
    summary="List models available from a configured LLM provider",
)
async def list_models(
    organization_id: int,
    instance_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[LLMProviderInstancesService, Depends(get_llm_provider_instances_service)],
) -> list[LLMProviderModelResponse]:
    """Fetch the live model catalogue for a configured instance.

    Used e.g. to populate the Rule Extraction model picker.
    """
    _require_membership(organization_id, current_user, memberships, profiles)
    try:
        models = await service.list_models(organization_id, instance_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return [LLMProviderModelResponse(id=model_id, name=name) for model_id, name in models]
