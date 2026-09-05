"""FastAPI router for organization membership and invite administration."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_membership_service, get_profile_service
from app.auth import CurrentUser, get_current_user
from app.modules.contracts import (
    MemberRoleUpdateRequest,
    OrganizationInviteCreateRequest,
    OrganizationInviteListResponse,
    OrganizationInviteResponse,
    OrganizationMemberListResponse,
    OrganizationMemberResponse,
)
from app.services.membership_service import MembershipService
from app.services.profile_service import ProfileService

router = APIRouter()


def _require_membership(
    organization_id: int,
    current_user: CurrentUser,
    memberships: MembershipService,
    profiles: ProfileService,
) -> None:
    """Raise 404 unless the caller belongs to *organization_id* (or is superadmin).

    404 rather than 403, matching ``get_authorized_project``: an organization
    outside the caller's memberships should look like it doesn't exist.
    """
    if profiles.is_superadmin(current_user.id):
        return
    if organization_id not in memberships.org_ids_for_user(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization {organization_id} not found.",
        )


def _require_org_admin(
    organization_id: int,
    current_user: CurrentUser,
    memberships: MembershipService,
    profiles: ProfileService,
) -> None:
    """Raise unless the caller is an owner/admin of *organization_id* (or superadmin)."""
    _require_membership(organization_id, current_user, memberships, profiles)
    if profiles.is_superadmin(current_user.id):
        return
    role = memberships.role_for_user(organization_id, current_user.id)
    if role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an organization owner or admin can do this.",
        )


def _member_response(
    member_id: str, role: str, profiles_by_id: dict[str, dict]
) -> OrganizationMemberResponse:
    profile = profiles_by_id.get(member_id, {})
    return OrganizationMemberResponse(
        user_id=member_id,
        email=profile.get("email") or "",
        full_name=profile.get("full_name") or "",
        avatar_url=profile.get("avatar_url") or "",
        role=role,
    )


@router.get(
    "/{organization_id}/members",
    response_model=OrganizationMemberListResponse,
    summary="List an organization's members",
)
def list_members(
    organization_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> OrganizationMemberListResponse:
    """Return every member of the organization, with their profile and role."""
    _require_membership(organization_id, current_user, memberships, profiles)
    rows = memberships.list_members_raw(organization_id)
    profiles_by_id = profiles.get_many([row["user_id"] for row in rows])
    return OrganizationMemberListResponse(
        organization_id=organization_id,
        members=[_member_response(row["user_id"], row["role"], profiles_by_id) for row in rows],
    )


def _owner_count_after(
    rows: list[dict], *, excluding_user_id: str | None = None, demoted_user_id: str | None = None
) -> int:
    """Count how many owners *rows* would have after a removal or demotion."""
    count = 0
    for row in rows:
        if row["user_id"] == excluding_user_id:
            continue
        role = "member" if row["user_id"] == demoted_user_id else row["role"]
        if role == "owner":
            count += 1
    return count


@router.patch(
    "/{organization_id}/members/{user_id}",
    response_model=OrganizationMemberListResponse,
    summary="Change a member's role",
)
def update_member_role(
    organization_id: int,
    user_id: str,
    payload: MemberRoleUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> OrganizationMemberListResponse:
    """Update a member's role, refusing to leave the organization without an owner."""
    _require_org_admin(organization_id, current_user, memberships, profiles)
    rows = memberships.list_members_raw(organization_id)
    if payload.role != "owner" and _owner_count_after(rows, demoted_user_id=user_id) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An organization must always have at least one owner.",
        )
    try:
        memberships.update_role(organization_id, user_id, payload.role)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return list_members(organization_id, current_user, memberships, profiles)


@router.delete(
    "/{organization_id}/members/{user_id}",
    response_model=OrganizationMemberListResponse,
    summary="Remove a member from an organization",
)
def remove_member(
    organization_id: int,
    user_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> OrganizationMemberListResponse:
    """Remove a member, refusing to leave the organization without an owner."""
    _require_org_admin(organization_id, current_user, memberships, profiles)
    rows = memberships.list_members_raw(organization_id)
    if _owner_count_after(rows, excluding_user_id=user_id) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An organization must always have at least one owner.",
        )
    memberships.remove_member(organization_id, user_id)
    return list_members(organization_id, current_user, memberships, profiles)


@router.get(
    "/{organization_id}/invites",
    response_model=OrganizationInviteListResponse,
    summary="List an organization's invites",
)
def list_invites(
    organization_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> OrganizationInviteListResponse:
    """Return every invite (pending and accepted) sent for the organization."""
    _require_org_admin(organization_id, current_user, memberships, profiles)
    rows = memberships.list_invites(organization_id)
    return OrganizationInviteListResponse(
        organization_id=organization_id,
        invites=[OrganizationInviteResponse(**row) for row in rows],
    )


@router.post(
    "/{organization_id}/invites",
    response_model=OrganizationInviteListResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite someone to an organization",
)
def create_invite(
    organization_id: int,
    payload: OrganizationInviteCreateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> OrganizationInviteListResponse:
    """Create a pending invite; it becomes a membership the first time that email signs in."""
    _require_org_admin(organization_id, current_user, memberships, profiles)
    try:
        memberships.create_invite(organization_id, payload.email, payload.role)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return list_invites(organization_id, current_user, memberships, profiles)


@router.delete(
    "/{organization_id}/invites/{invite_id}",
    response_model=OrganizationInviteListResponse,
    summary="Revoke a pending invite",
)
def revoke_invite(
    organization_id: int,
    invite_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> OrganizationInviteListResponse:
    """Delete a pending invite so that email can no longer redeem it."""
    _require_org_admin(organization_id, current_user, memberships, profiles)
    try:
        memberships.revoke_invite(organization_id, invite_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return list_invites(organization_id, current_user, memberships, profiles)
