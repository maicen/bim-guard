"""FastAPI router for organization membership and invite administration."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import (
    get_document_access_service,
    get_membership_service,
    get_profile_service,
    get_projects_service,
    get_ruleset_access_service,
)
from app.auth import CurrentUser, get_current_user
from app.modules.contracts import (
    GroupCreateRequest,
    GroupListResponse,
    GroupProjectGrantsResponse,
    GroupProjectGrantsUpdateRequest,
    GroupResponse,
    MemberGroupUpdateRequest,
    MemberRoleUpdateRequest,
    OrganizationDocumentGrantsResponse,
    OrganizationDocumentGrantsUpdateRequest,
    OrganizationInviteCreateRequest,
    OrganizationInviteListResponse,
    OrganizationInviteResponse,
    OrganizationListResponse,
    OrganizationMemberListResponse,
    OrganizationMemberResponse,
    OrganizationProjectGrantsResponse,
    OrganizationProjectGrantsUpdateRequest,
    OrganizationRulesetGrantsResponse,
    OrganizationRulesetGrantsUpdateRequest,
    OrganizationSummary,
)
from app.services.document_access_service import DocumentAccessService
from app.services.membership_service import MembershipService
from app.services.profile_service import ProfileService
from app.services.projects_service import ProjectsService
from app.services.ruleset_access_service import RulesetAccessService

router = APIRouter()


def _require_superadmin(current_user: CurrentUser, profiles: ProfileService) -> None:
    """Raise 403 unless the caller is the platform superadmin."""
    if not profiles.is_superadmin(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the platform superadmin can do this.",
        )


@router.get(
    "",
    response_model=OrganizationListResponse,
    summary="List every organization on the platform",
)
def list_organizations(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> OrganizationListResponse:
    """Return every organization.

    Superadmin only -- this backs the platform ruleset-grant screen, not
    anything an ordinary member needs.
    """
    _require_superadmin(current_user, profiles)
    return OrganizationListResponse(
        organizations=[OrganizationSummary(**o) for o in memberships.list_all_organizations()]
    )


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
    row: dict, profiles_by_id: dict[str, dict], groups_by_id: dict[int, dict]
) -> OrganizationMemberResponse:
    profile = profiles_by_id.get(row["user_id"], {})
    group_id = row.get("group_id")
    group = groups_by_id.get(group_id) if group_id is not None else None
    return OrganizationMemberResponse(
        user_id=row["user_id"],
        email=profile.get("email") or "",
        full_name=profile.get("full_name") or "",
        avatar_url=profile.get("avatar_url") or "",
        role=row["role"],
        group_id=group_id,
        group_name=group.get("name") if group else None,
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
    """Return every member of the organization, with their profile, role, and group."""
    _require_membership(organization_id, current_user, memberships, profiles)
    rows = memberships.list_members_raw(organization_id)
    profiles_by_id = profiles.get_many([row["user_id"] for row in rows])
    groups_by_id = {g["id"]: g for g in memberships.list_groups(organization_id)}
    return OrganizationMemberListResponse(
        organization_id=organization_id,
        members=[_member_response(row, profiles_by_id, groups_by_id) for row in rows],
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


# ---------------------------------------------------------------------------
# RBAC: Groups
# ---------------------------------------------------------------------------


@router.get(
    "/{organization_id}/groups",
    response_model=GroupListResponse,
    summary="List an organization's groups",
)
def list_groups(
    organization_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> GroupListResponse:
    """Return every group in the organization, with member counts."""
    _require_membership(organization_id, current_user, memberships, profiles)
    return GroupListResponse(
        organization_id=organization_id,
        groups=[GroupResponse(**g) for g in memberships.list_groups(organization_id)],
    )


@router.post(
    "/{organization_id}/groups",
    response_model=GroupListResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a group",
)
def create_group(
    organization_id: int,
    payload: GroupCreateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> GroupListResponse:
    """Create a new group within the organization. Owner/admin only."""
    _require_org_admin(organization_id, current_user, memberships, profiles)
    try:
        memberships.create_group(organization_id, payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return list_groups(organization_id, current_user, memberships, profiles)


@router.delete(
    "/{organization_id}/groups/{group_id}",
    response_model=GroupListResponse,
    summary="Delete a group",
)
def delete_group(
    organization_id: int,
    group_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> GroupListResponse:
    """Delete a group. Its members become ungrouped, not removed from the organization."""
    _require_org_admin(organization_id, current_user, memberships, profiles)
    try:
        memberships.delete_group(organization_id, group_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return list_groups(organization_id, current_user, memberships, profiles)


@router.patch(
    "/{organization_id}/members/{user_id}/group",
    response_model=OrganizationMemberListResponse,
    summary="Move a member into a group (or ungroup them)",
)
def update_member_group(
    organization_id: int,
    user_id: str,
    payload: MemberGroupUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> OrganizationMemberListResponse:
    """Change which group a member belongs to. A member belongs to at most one group."""
    _require_org_admin(organization_id, current_user, memberships, profiles)
    try:
        memberships.set_member_group(organization_id, user_id, payload.group_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return list_members(organization_id, current_user, memberships, profiles)


@router.get(
    "/{organization_id}/groups/{group_id}/projects",
    response_model=GroupProjectGrantsResponse,
    summary="Get the projects a group can access",
)
def get_group_project_grants(
    organization_id: int,
    group_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> GroupProjectGrantsResponse:
    """Return the ids of every project this group is granted access to."""
    _require_membership(organization_id, current_user, memberships, profiles)
    group = memberships.get_group(group_id)
    if group is None or group.get("organization_id") != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Group {group_id} not found in organization {organization_id}.",
        )
    return GroupProjectGrantsResponse(
        group_id=group_id, project_ids=memberships.list_group_project_ids(group_id)
    )


@router.put(
    "/{organization_id}/groups/{group_id}/projects",
    response_model=GroupProjectGrantsResponse,
    summary="Set the projects a group can access",
)
def set_group_project_grants(
    organization_id: int,
    group_id: int,
    payload: GroupProjectGrantsUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    projects_service: Annotated[ProjectsService, Depends(get_projects_service)],
) -> GroupProjectGrantsResponse:
    """Replace the set of projects this group can access. Owner/admin only.

    Every project id must be one this organization can itself reach -- either
    one it owns, or one shared into it via a superadmin's cross-org grant
    (``organization_project_grants``). A group can never be granted a project
    its own organization has no claim to.
    """
    _require_org_admin(organization_id, current_user, memberships, profiles)
    group = memberships.get_group(group_id)
    if group is None or group.get("organization_id") != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Group {group_id} not found in organization {organization_id}.",
        )
    owned_ids = {
        row["id"] for row in projects_service.list_projects() if row.get("organization_id") == organization_id
    }
    granted_ids = set(memberships.list_org_project_grants(organization_id))
    outside = set(payload.project_ids) - owned_ids - granted_ids
    if outside:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Project(s) {sorted(outside)!r} are not reachable by this organization.",
        )
    memberships.set_group_project_grants(group_id, payload.project_ids)
    return get_group_project_grants(organization_id, group_id, current_user, memberships, profiles)


# ---------------------------------------------------------------------------
# RBAC: Organization Ruleset Grants (superadmin only)
# ---------------------------------------------------------------------------


@router.get(
    "/{organization_id}/ruleset-grants",
    response_model=OrganizationRulesetGrantsResponse,
    summary="Get the rulesets an organization may use",
)
def get_organization_ruleset_grants(
    organization_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    ruleset_access: Annotated[RulesetAccessService, Depends(get_ruleset_access_service)],
) -> OrganizationRulesetGrantsResponse:
    """Return the rulesets this organization is allowed to use at all.

    Superadmin only -- this is the platform-wide grant, not something an
    organization's own owner can see or change about themselves.
    """
    _require_superadmin(current_user, profiles)
    return OrganizationRulesetGrantsResponse(
        organization_id=organization_id,
        ruleset_ids=ruleset_access.list_org_grants(organization_id),
    )


@router.put(
    "/{organization_id}/ruleset-grants",
    response_model=OrganizationRulesetGrantsResponse,
    summary="Set the rulesets an organization may use",
)
def set_organization_ruleset_grants(
    organization_id: int,
    payload: OrganizationRulesetGrantsUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    ruleset_access: Annotated[RulesetAccessService, Depends(get_ruleset_access_service)],
) -> OrganizationRulesetGrantsResponse:
    """Replace the set of rulesets this organization may use. Superadmin only."""
    _require_superadmin(current_user, profiles)
    ruleset_access.set_org_grants(organization_id, payload.ruleset_ids)
    return get_organization_ruleset_grants(organization_id, current_user, profiles, ruleset_access)


# ---------------------------------------------------------------------------
# RBAC: Organization Project Grants (cross-org sharing, superadmin only)
# ---------------------------------------------------------------------------


@router.get(
    "/{organization_id}/project-grants",
    response_model=OrganizationProjectGrantsResponse,
    summary="Get the projects shared into an organization from elsewhere",
)
def get_organization_project_grants(
    organization_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
) -> OrganizationProjectGrantsResponse:
    """Return the projects shared into this organization from elsewhere.

    Superadmin only. Projects the organization owns outright don't appear
    here -- this is only the cross-org sharing grant on top of ownership.
    """
    _require_superadmin(current_user, profiles)
    return OrganizationProjectGrantsResponse(
        organization_id=organization_id,
        project_ids=memberships.list_org_project_grants(organization_id),
    )


@router.put(
    "/{organization_id}/project-grants",
    response_model=OrganizationProjectGrantsResponse,
    summary="Set the projects shared into an organization from elsewhere",
)
def set_organization_project_grants(
    organization_id: int,
    payload: OrganizationProjectGrantsUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
) -> OrganizationProjectGrantsResponse:
    """Replace the set of projects shared into this organization. Superadmin only."""
    _require_superadmin(current_user, profiles)
    memberships.set_org_project_grants(organization_id, payload.project_ids)
    return get_organization_project_grants(organization_id, current_user, profiles, memberships)


# ---------------------------------------------------------------------------
# RBAC: Organization Document Grants (superadmin only)
# ---------------------------------------------------------------------------


@router.get(
    "/{organization_id}/document-grants",
    response_model=OrganizationDocumentGrantsResponse,
    summary="Get the documents an organization may use",
)
def get_organization_document_grants(
    organization_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    document_access: Annotated[DocumentAccessService, Depends(get_document_access_service)],
) -> OrganizationDocumentGrantsResponse:
    """Return the documents this organization is allowed to use at all. Superadmin only."""
    _require_superadmin(current_user, profiles)
    return OrganizationDocumentGrantsResponse(
        organization_id=organization_id,
        document_ids=document_access.list_org_grants(organization_id),
    )


@router.put(
    "/{organization_id}/document-grants",
    response_model=OrganizationDocumentGrantsResponse,
    summary="Set the documents an organization may use",
)
def set_organization_document_grants(
    organization_id: int,
    payload: OrganizationDocumentGrantsUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    document_access: Annotated[DocumentAccessService, Depends(get_document_access_service)],
) -> OrganizationDocumentGrantsResponse:
    """Replace the set of documents this organization may use. Superadmin only."""
    _require_superadmin(current_user, profiles)
    document_access.set_org_grants(organization_id, payload.document_ids)
    return get_organization_document_grants(organization_id, current_user, profiles, document_access)
