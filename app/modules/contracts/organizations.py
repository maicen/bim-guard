"""Multi-tenant organization membership, RBAC roles, user profiles, and SCIM directory contracts."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.modules.contracts.base import (
    PROJECT_CODE_MAX_LENGTH,
    PROJECT_CODE_MIN_LENGTH,
    PROJECT_CODE_PATTERN,
)

__all__ = ['OrgRole', 'OrganizationMembership', 'UserProfile', 'ProfileUpdateRequest', 'CurrentUserResponse', 'OrganizationMemberResponse', 'OrganizationMemberListResponse', 'MemberRoleUpdateRequest', 'OrganizationInviteResponse', 'OrganizationInviteListResponse', 'OrganizationInviteCreateRequest', 'OrganizationSummary', 'OrganizationListResponse', 'OrganizationCreateRequest', 'AddMemberRequest', 'UserOrganizationSummary', 'UserSummary', 'UserListResponse', 'GroupResponse', 'GroupListResponse', 'GroupCreateRequest', 'MemberGroupUpdateRequest', 'GroupProjectGrantsResponse', 'GroupProjectGrantsUpdateRequest', 'OrganizationRulesetGrantsResponse', 'OrganizationRulesetGrantsUpdateRequest', 'ProjectRulesetBindingsResponse', 'ProjectRulesetBindingsUpdateRequest', 'OrganizationProjectGrantsResponse', 'OrganizationProjectGrantsUpdateRequest', 'OrganizationDocumentGrantsResponse', 'OrganizationDocumentGrantsUpdateRequest', 'ProjectDocumentBindingsResponse', 'ProjectDocumentBindingsUpdateRequest']

# ---------------------------------------------------------------------------
# Auth / Multi-Tenancy Contracts
# ---------------------------------------------------------------------------

OrgRole = Literal["owner", "admin", "member"]

class OrganizationMembership(BaseModel):
    """One organization the authenticated caller belongs to, and their role in it."""

    organization_id: int
    name: str
    slug: str
    org_code: str = Field(
        default="", description="ISO 19650 Originator Code for this organization"
    )
    role: OrgRole
    group_id: Optional[int] = Field(
        default=None, description="The user's assigned group in this organization, if any"
    )

class UserProfile(BaseModel):
    """Editable identity and preferences layered on top of auth.users."""

    full_name: str = ""
    avatar_url: str = ""
    title: str = Field(default="", description="Job title / discipline, shown alongside the name")
    default_organization_id: Optional[int] = None
    preferences: dict[str, Any] = Field(default_factory=dict)
    is_superadmin: bool = Field(
        default=False,
        description="Platform-wide bypass of organization-membership checks. Not settable via PATCH.",
    )

class ProfileUpdateRequest(BaseModel):
    """Fields to write to the caller's profile. Every field is optional."""

    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    title: Optional[str] = None
    default_organization_id: Optional[int] = None
    preferences: Optional[dict[str, Any]] = None

class CurrentUserResponse(BaseModel):
    """The authenticated caller's identity, profile, and organization memberships."""

    id: str = Field(..., description="Supabase auth.users.id (uuid)")
    email: Optional[str] = None
    profile: UserProfile = Field(default_factory=UserProfile)
    organizations: list[OrganizationMembership] = Field(default_factory=list)

class OrganizationMemberResponse(BaseModel):
    """A member of an organization, as shown on the Org Settings screen."""

    user_id: str
    email: str = ""
    full_name: str = ""
    avatar_url: str = ""
    role: OrgRole
    group_id: Optional[int] = None
    group_name: Optional[str] = None

class OrganizationMemberListResponse(BaseModel):
    """Every member of one organization."""

    organization_id: int
    members: list[OrganizationMemberResponse] = Field(default_factory=list)

class MemberRoleUpdateRequest(BaseModel):
    """New role to assign a member."""

    role: OrgRole

class OrganizationInviteResponse(BaseModel):
    """A pending or accepted invite into an organization."""

    id: int
    organization_id: int
    email: str
    role: OrgRole
    accepted_at: Optional[str] = None

class OrganizationInviteListResponse(BaseModel):
    """Every invite (pending and accepted) for one organization."""

    organization_id: int
    invites: list[OrganizationInviteResponse] = Field(default_factory=list)

class OrganizationInviteCreateRequest(BaseModel):
    """A new invite to send for an organization."""

    email: str = Field(..., min_length=3, description="Address the invite is addressed to")
    role: OrgRole = "member"

class OrganizationSummary(BaseModel):
    """One organization, as listed for the platform superadmin."""

    id: int
    name: str
    slug: str
    org_code: str = Field(
        default="", description="ISO 19650 Originator Code for this organization"
    )

class OrganizationListResponse(BaseModel):
    """Every organization on the platform. Superadmin only."""

    organizations: list[OrganizationSummary] = Field(default_factory=list)

class OrganizationCreateRequest(BaseModel):
    """A new organization to create. Superadmin only."""

    name: str = Field(..., min_length=1, max_length=200)
    # ISO 19650 Originator Code -- shares the project code's length/pattern
    # convention (a short alphanumeric segment in container naming); every
    # project and document this organization owns defaults its own
    # `originator` field from this when none is given explicitly.
    org_code: str = Field(
        ...,
        min_length=PROJECT_CODE_MIN_LENGTH,
        max_length=PROJECT_CODE_MAX_LENGTH,
        pattern=PROJECT_CODE_PATTERN,
        description="ISO 19650 Originator Code (2-6 alphanumeric characters)",
    )

class AddMemberRequest(BaseModel):
    """Directly add an existing user to an organization, bypassing the invite flow."""

    user_id: str
    role: OrgRole = "member"

class UserOrganizationSummary(BaseModel):
    """One organization a user belongs to, for the platform user directory."""

    organization_id: int
    name: str
    role: OrgRole

class UserSummary(BaseModel):
    """One user on the platform, as listed for the superadmin user directory."""

    id: str = Field(..., description="Supabase auth.users.id (uuid)")
    email: str = ""
    full_name: str = ""
    avatar_url: str = ""
    is_superadmin: bool = False
    organizations: list[UserOrganizationSummary] = Field(default_factory=list)

class UserListResponse(BaseModel):
    """Every user who has ever signed in, platform-wide. Superadmin only."""

    users: list[UserSummary] = Field(default_factory=list)

# ---------------------------------------------------------------------------
# RBAC: Groups and Resource Grants
# ---------------------------------------------------------------------------


class GroupResponse(BaseModel):
    """One user group within an organization."""

    id: int
    organization_id: int
    name: str
    member_count: int = 0

class GroupListResponse(BaseModel):
    """Every group in one organization."""

    organization_id: int
    groups: list[GroupResponse] = Field(default_factory=list)

class GroupCreateRequest(BaseModel):
    """A new group to create within an organization."""

    name: str = Field(..., min_length=1, max_length=100)

class MemberGroupUpdateRequest(BaseModel):
    """Which group to place a member in, or null to leave them ungrouped."""

    group_id: Optional[int] = None

class GroupProjectGrantsResponse(BaseModel):
    """The set of projects one group can access."""

    group_id: int
    project_ids: list[int] = Field(default_factory=list)

class GroupProjectGrantsUpdateRequest(BaseModel):
    """Replace a group's entire set of granted projects."""

    project_ids: list[int] = Field(default_factory=list)

class OrganizationRulesetGrantsResponse(BaseModel):
    """The set of rulesets one organization may use at all (superadmin-controlled)."""

    organization_id: int
    ruleset_ids: list[str] = Field(default_factory=list)

class OrganizationRulesetGrantsUpdateRequest(BaseModel):
    """Replace an organization's entire set of granted rulesets."""

    ruleset_ids: list[str] = Field(default_factory=list)

class ProjectRulesetBindingsResponse(BaseModel):
    """The rulesets bound to one project.

    Also carries which of the org's grants remain available to bind
    (owner-controlled, subset of ``OrganizationRulesetGrantsResponse``).
    """

    project_id: int
    ruleset_ids: list[str] = Field(default_factory=list)
    available_ruleset_ids: list[str] = Field(default_factory=list)

class ProjectRulesetBindingsUpdateRequest(BaseModel):
    """Replace a project's entire set of bound rulesets."""

    ruleset_ids: list[str] = Field(default_factory=list)

class OrganizationProjectGrantsResponse(BaseModel):
    """Projects shared into one organization from elsewhere.

    Cross-org sharing, superadmin-controlled. Does not include projects the
    organization owns outright -- those need no grant.
    """

    organization_id: int
    project_ids: list[int] = Field(default_factory=list)

class OrganizationProjectGrantsUpdateRequest(BaseModel):
    """Replace an organization's entire set of shared-in (non-owned) projects."""

    project_ids: list[int] = Field(default_factory=list)

class OrganizationDocumentGrantsResponse(BaseModel):
    """The set of documents one organization may use at all (superadmin-controlled)."""

    organization_id: int
    document_ids: list[int] = Field(default_factory=list)

class OrganizationDocumentGrantsUpdateRequest(BaseModel):
    """Replace an organization's entire set of granted documents."""

    document_ids: list[int] = Field(default_factory=list)

class ProjectDocumentBindingsResponse(BaseModel):
    """The documents bound to one project.

    Also carries which of the org's grants remain available to bind
    (owner-controlled, subset of ``OrganizationDocumentGrantsResponse``).
    """

    project_id: int
    document_ids: list[int] = Field(default_factory=list)
    available_document_ids: list[int] = Field(default_factory=list)

class ProjectDocumentBindingsUpdateRequest(BaseModel):
    """Replace a project's entire set of bound documents."""

    document_ids: list[int] = Field(default_factory=list)
