"""FastAPI router for the superadmin-configurable role-permission matrix.

Edits here change what PermissionService.require() enforces across every
route that gates a mutation by org role (app/api/organizations.py,
app/api/llm_provider_instances.py, app/api/projects.py, and the org-scoped
parsing-engine router) — superadmin-only, matching how
app/api/parsing_engines.py gates its own platform-wide configuration.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_audit_log_service, get_permission_service, get_profile_service
from app.api.organizations import _require_superadmin
from app.auth import CurrentUser, get_current_user
from app.modules.contracts import (
    PermissionActionResponse,
    RolePermissionResponse,
    RolePermissionSetRequest,
)
from app.modules.permissions import ACTION_DESCRIPTIONS, ROLE_RANK, Action
from app.services.audit_log_service import AuditLogService
from app.services.permission_service import PermissionService
from app.services.profile_service import ProfileService

router = APIRouter()


@router.get("/actions", response_model=list[PermissionActionResponse], summary="List every role-gated action")
def list_actions(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[PermissionActionResponse]:
    """Return the static catalogue of actions the matrix can gate."""
    return [
        PermissionActionResponse(action=action.value, description=ACTION_DESCRIPTIONS.get(action, ""))
        for action in Action
    ]


@router.get("/matrix", response_model=list[RolePermissionResponse], summary="Get the effective permission matrix")
def get_matrix(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    permissions: Annotated[PermissionService, Depends(get_permission_service)],
    organization_id: Annotated[int | None, Query()] = None,
) -> list[RolePermissionResponse]:
    """Return every action's effective minimum role for a scope.

    Omit `organization_id` for the platform default; pass one to see that
    organization's effective matrix (its own overrides merged over the
    platform default).
    """
    _require_superadmin(current_user, profiles)
    platform_matrix = permissions.get_effective_matrix(None)
    effective = permissions.get_effective_matrix(organization_id) if organization_id is not None else platform_matrix
    return [
        RolePermissionResponse(
            action=action.value,
            min_role=effective[action],
            is_override=organization_id is not None and effective[action] != platform_matrix[action],
        )
        for action in Action
    ]


@router.put(
    "/matrix/{action}",
    response_model=RolePermissionResponse,
    summary="Set an action's minimum role for a scope",
)
def set_matrix_entry(
    action: str,
    payload: RolePermissionSetRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    permissions: Annotated[PermissionService, Depends(get_permission_service)],
    audit_log: Annotated[AuditLogService, Depends(get_audit_log_service)],
) -> RolePermissionResponse:
    """Set the minimum role for *action*, in the scope named by the payload."""
    _require_superadmin(current_user, profiles)
    try:
        resolved_action = Action(action)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown action '{action}'."
        )
    if payload.min_role not in ROLE_RANK:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"min_role must be one of {sorted(ROLE_RANK)}.",
        )
    permissions.set_min_role(payload.organization_id, resolved_action, payload.min_role)
    audit_log.record(
        actor_id=current_user.id,
        actor_email=current_user.email,
        organization_id=payload.organization_id,
        action="permissions.matrix.entry_set",
        resource_type="role_permission",
        resource_id=resolved_action.value,
        metadata={"min_role": payload.min_role},
    )
    effective = permissions.get_effective_matrix(payload.organization_id)
    platform_matrix = permissions.get_effective_matrix(None)
    return RolePermissionResponse(
        action=resolved_action.value,
        min_role=effective[resolved_action],
        is_override=payload.organization_id is not None
        and effective[resolved_action] != platform_matrix[resolved_action],
    )


@router.delete(
    "/matrix/{action}",
    response_model=RolePermissionResponse,
    summary="Reset an organization's override back to the platform default",
)
def reset_matrix_entry(
    action: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    permissions: Annotated[PermissionService, Depends(get_permission_service)],
    organization_id: Annotated[int, Query()],
) -> RolePermissionResponse:
    """Delete an org's override row for *action*, so it falls back to the platform default."""
    _require_superadmin(current_user, profiles)
    try:
        resolved_action = Action(action)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown action '{action}'."
        )
    permissions.reset_to_default(organization_id, resolved_action)
    platform_matrix = permissions.get_effective_matrix(None)
    return RolePermissionResponse(
        action=resolved_action.value, min_role=platform_matrix[resolved_action], is_override=False
    )
