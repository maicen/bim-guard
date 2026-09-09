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
    get_llm_task_assignment_service,
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
    LLMProviderTestConnectionRequest,
    LLMTaskAssignmentSetRequest,
    LLMTaskModelAssignmentResponse,
    LLMTaskResponse,
)
from app.modules.llm_providers import LLMProviderRegistry
from app.services.llm_provider_instances_service import LLMProviderInstancesService
from app.services.llm_task_assignment_service import LLMTaskAssignmentService
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


@router.post(
    "/{organization_id}/llm-providers/test-connection",
    response_model=LLMProviderInstanceTestResponse,
    summary="Check connectivity for candidate LLM provider credentials",
)
async def test_candidate_connection(
    organization_id: int,
    payload: LLMProviderTestConnectionRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[LLMProviderInstancesService, Depends(get_llm_provider_instances_service)],
) -> LLMProviderInstanceTestResponse:
    """Check connectivity and credentials before registering an LLM provider instance."""
    _require_org_admin(organization_id, current_user, memberships, profiles)
    try:
        result = await service.test_connection(
            kind=payload.kind,
            api_key=payload.api_key,
            api_base=payload.api_base,
        )
        return LLMProviderInstanceTestResponse(ok=result.ok, detail=result.detail)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning(
            "LLM provider candidate test failed org=%s kind=%s error=%s",
            organization_id,
            payload.kind,
            exc,
        )
        return LLMProviderInstanceTestResponse(ok=False, detail=str(exc))


def _to_task_assignment_response(
    row: dict[str, Any], instance_names: dict[int, str]
) -> LLMTaskModelAssignmentResponse:
    instance_id = row["provider_instance_id"]
    return LLMTaskModelAssignmentResponse(
        task_key=row["task_key"],
        provider_instance_id=instance_id,
        provider_instance_name=instance_names.get(instance_id, ""),
        model_id=row["model_id"],
        model_name=row.get("model_name", row["model_id"]),
        context_length=row.get("context_length"),
        input_price_per_million=row.get("input_price_per_million"),
        output_price_per_million=row.get("output_price_per_million"),
        is_default=bool(row.get("is_default", False)),
    )


@router.get(
    "/{organization_id}/llm-providers/tasks",
    response_model=list[LLMTaskResponse],
    summary="List tasks that can have a curated LLM model shortlist",
)
def list_tasks(
    organization_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> list[LLMTaskResponse]:
    """Return every registered task (see app/modules/llm_providers/tasks.py).

    Static, build-time metadata — the External Providers UI's "Task
    Shortlists" section renders from this list instead of a hardcoded set.
    """
    _require_membership(organization_id, current_user, memberships, profiles)
    return [
        LLMTaskResponse(key=task.key, label=task.label, description=task.description)
        for task in LLMTaskAssignmentService.list_tasks()
    ]


@router.get(
    "/{organization_id}/llm-providers/task-assignments",
    response_model=list[LLMTaskModelAssignmentResponse],
    summary="List an organization's shortlisted models, optionally for one task",
)
def list_task_assignments(
    organization_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    instances_service: Annotated[LLMProviderInstancesService, Depends(get_llm_provider_instances_service)],
    assignments_service: Annotated[LLMTaskAssignmentService, Depends(get_llm_task_assignment_service)],
    task_key: str | None = None,
) -> list[LLMTaskModelAssignmentResponse]:
    """Return this organization's shortlisted models.

    Any org member needs this to populate a task's model picker (e.g. Rule
    Extraction Studio).
    """
    _require_membership(organization_id, current_user, memberships, profiles)
    rows = assignments_service.list_assignments(organization_id, task_key)
    instance_names = {i["id"]: i.get("name", "") for i in instances_service.list_instances(organization_id)}
    return [_to_task_assignment_response(row, instance_names) for row in rows]


@router.put(
    "/{organization_id}/llm-providers/task-assignments/{task_key}",
    response_model=list[LLMTaskModelAssignmentResponse],
    summary="Replace an organization's model shortlist for one task",
)
def set_task_assignments(
    organization_id: int,
    task_key: str,
    payload: LLMTaskAssignmentSetRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    instances_service: Annotated[LLMProviderInstancesService, Depends(get_llm_provider_instances_service)],
    assignments_service: Annotated[LLMTaskAssignmentService, Depends(get_llm_task_assignment_service)],
) -> list[LLMTaskModelAssignmentResponse]:
    """Replace the whole shortlist for (organization_id, task_key) in one call."""
    _require_org_admin(organization_id, current_user, memberships, profiles)
    try:
        created = assignments_service.set_assignments(
            organization_id,
            task_key,
            models=[model.model_dump() for model in payload.models],
            default_provider_instance_id=payload.default_provider_instance_id,
            default_model_id=payload.default_model_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    instance_names = {i["id"]: i.get("name", "") for i in instances_service.list_instances(organization_id)}
    return [_to_task_assignment_response(row, instance_names) for row in created]

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
    return [
        LLMProviderModelResponse(
            id=model.id,
            name=model.name,
            context_length=model.context_length,
            input_price_per_million=model.input_price_per_million,
            output_price_per_million=model.output_price_per_million,
            capabilities=list(model.capabilities),
        )
        for model in models
    ]


