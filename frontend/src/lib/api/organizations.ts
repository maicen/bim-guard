import type {
  AddMemberPayload,
  GroupListResponse,
  GroupProjectGrantsResponse,
  OrganizationCreatePayload,
  OrganizationDocumentGrantsResponse,
  OrganizationInviteCreatePayload,
  OrganizationInviteListResponse,
  OrganizationListResponse,
  OrganizationMember,
  OrganizationMemberListResponse,
  OrganizationProjectGrantsResponse,
  OrganizationRulesetGrantsResponse,
  OrganizationSummary,
  OrgRole,
  PermissionAction,
  PermissionActionInfo,
  RolePermission,
  ScimTokenMintResult,
  ScimTokenStatus,
  UserListResponse,
} from "../types";
import { API_BASE, apiFetch, handleResponse } from "./client";

export const organizationsApi = {
  async listMembers(organizationId: number): Promise<OrganizationMemberListResponse> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/members`);
    return handleResponse<OrganizationMemberListResponse>(res);
  },

  async updateMemberRole(
    organizationId: number,
    userId: string,
    role: OrganizationMember["role"],
  ): Promise<OrganizationMemberListResponse> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/members/${userId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
    });
    return handleResponse<OrganizationMemberListResponse>(res);
  },

  async removeMember(organizationId: number, userId: string): Promise<OrganizationMemberListResponse> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/members/${userId}`, {
      method: "DELETE",
    });
    return handleResponse<OrganizationMemberListResponse>(res);
  },

  async listInvites(organizationId: number): Promise<OrganizationInviteListResponse> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/invites`);
    return handleResponse<OrganizationInviteListResponse>(res);
  },

  async createInvite(
    organizationId: number,
    payload: OrganizationInviteCreatePayload,
  ): Promise<OrganizationInviteListResponse> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/invites`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<OrganizationInviteListResponse>(res);
  },

  async revokeInvite(organizationId: number, inviteId: number): Promise<OrganizationInviteListResponse> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/invites/${inviteId}`, {
      method: "DELETE",
    });
    return handleResponse<OrganizationInviteListResponse>(res);
  },

  /** Every organization on the platform. Superadmin only. */
  async listAll(): Promise<OrganizationListResponse> {
    const res = await apiFetch(`${API_BASE}/organizations`);
    return handleResponse<OrganizationListResponse>(res);
  },

  /** Create a new organization. Superadmin only. */
  async create(payload: OrganizationCreatePayload): Promise<OrganizationSummary> {
    const res = await apiFetch(`${API_BASE}/organizations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<OrganizationSummary>(res);
  },

  /** Permanently delete an organization. Superadmin only. */
  async deleteOrganization(organizationId: number): Promise<void> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}`, {
      method: "DELETE",
    });
    await handleResponse<void>(res);
  },

  /** Every user who has ever signed in, platform-wide. Superadmin only. */
  async listAllUsers(): Promise<UserListResponse> {
    const res = await apiFetch(`${API_BASE}/organizations/users`);
    return handleResponse<UserListResponse>(res);
  },

  /** Directly add an existing user to an organization, bypassing the invite flow. Superadmin only. */
  async addMember(
    organizationId: number,
    payload: AddMemberPayload,
  ): Promise<OrganizationMemberListResponse> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/members`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<OrganizationMemberListResponse>(res);
  },

  /** Permanently delete a user's account. Superadmin only. */
  async deleteUser(userId: string): Promise<void> {
    const res = await apiFetch(`${API_BASE}/organizations/users/${userId}`, {
      method: "DELETE",
    });
    await handleResponse<void>(res);
  },

  /** SCIM provisioning token status -- never the raw value. Owner/admin only. */
  async getScimTokenStatus(organizationId: number): Promise<ScimTokenStatus> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/scim-token`);
    return handleResponse<ScimTokenStatus>(res);
  },

  /** Mint (or rotate) the organization's SCIM token. The raw token is returned exactly once. */
  async mintScimToken(organizationId: number): Promise<ScimTokenMintResult> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/scim-token`, {
      method: "POST",
    });
    return handleResponse<ScimTokenMintResult>(res);
  },

  /** Revoke the organization's SCIM token. */
  async revokeScimToken(organizationId: number): Promise<ScimTokenStatus> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/scim-token`, {
      method: "DELETE",
    });
    return handleResponse<ScimTokenStatus>(res);
  },

  async listGroups(organizationId: number): Promise<GroupListResponse> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/groups`);
    return handleResponse<GroupListResponse>(res);
  },

  async createGroup(organizationId: number, name: string): Promise<GroupListResponse> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/groups`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    return handleResponse<GroupListResponse>(res);
  },

  async deleteGroup(organizationId: number, groupId: number): Promise<GroupListResponse> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/groups/${groupId}`, {
      method: "DELETE",
    });
    return handleResponse<GroupListResponse>(res);
  },

  /** Move a member into a group, or pass `null` to ungroup them. */
  async setMemberGroup(
    organizationId: number,
    userId: string,
    groupId: number | null,
  ): Promise<OrganizationMemberListResponse> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/members/${userId}/group`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ group_id: groupId }),
    });
    return handleResponse<OrganizationMemberListResponse>(res);
  },

  async getGroupProjectGrants(
    organizationId: number,
    groupId: number,
  ): Promise<GroupProjectGrantsResponse> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/groups/${groupId}/projects`);
    return handleResponse<GroupProjectGrantsResponse>(res);
  },

  async setGroupProjectGrants(
    organizationId: number,
    groupId: number,
    projectIds: number[],
  ): Promise<GroupProjectGrantsResponse> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/groups/${groupId}/projects`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_ids: projectIds }),
    });
    return handleResponse<GroupProjectGrantsResponse>(res);
  },

  /** Rulesets an organization may use at all. Superadmin only. */
  async getRulesetGrants(organizationId: number): Promise<OrganizationRulesetGrantsResponse> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/ruleset-grants`);
    return handleResponse<OrganizationRulesetGrantsResponse>(res);
  },

  async setRulesetGrants(
    organizationId: number,
    rulesetIds: string[],
  ): Promise<OrganizationRulesetGrantsResponse> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/ruleset-grants`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ruleset_ids: rulesetIds }),
    });
    return handleResponse<OrganizationRulesetGrantsResponse>(res);
  },

  /** Projects shared into an organization from elsewhere (cross-org sharing). Superadmin only. */
  async getProjectGrants(organizationId: number): Promise<OrganizationProjectGrantsResponse> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/project-grants`);
    return handleResponse<OrganizationProjectGrantsResponse>(res);
  },

  async setProjectGrants(
    organizationId: number,
    projectIds: number[],
  ): Promise<OrganizationProjectGrantsResponse> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/project-grants`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_ids: projectIds }),
    });
    return handleResponse<OrganizationProjectGrantsResponse>(res);
  },

  /** Documents an organization may use at all. Superadmin only. */
  async getDocumentGrants(organizationId: number): Promise<OrganizationDocumentGrantsResponse> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/document-grants`);
    return handleResponse<OrganizationDocumentGrantsResponse>(res);
  },

  async setDocumentGrants(
    organizationId: number,
    documentIds: number[],
  ): Promise<OrganizationDocumentGrantsResponse> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/document-grants`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document_ids: documentIds }),
    });
    return handleResponse<OrganizationDocumentGrantsResponse>(res);
  },
};

// =============================================================================
// Permissions API Client (see app/api/permissions.py)
// =============================================================================
// Superadmin-only: the role-permission matrix (which org role each gated
// action requires). Platform default when organizationId is omitted, else
// that organization's effective matrix.

export const permissionsApi = {
  async actions(): Promise<PermissionActionInfo[]> {
    const res = await apiFetch(`${API_BASE}/permissions/actions`);
    return handleResponse<PermissionActionInfo[]>(res);
  },

  async matrix(organizationId?: number): Promise<RolePermission[]> {
    const query = organizationId != null ? `?organization_id=${organizationId}` : "";
    const res = await apiFetch(`${API_BASE}/permissions/matrix${query}`);
    return handleResponse<RolePermission[]>(res);
  },

  async setMinRole(
    action: PermissionAction,
    minRole: OrgRole,
    organizationId?: number | null,
  ): Promise<RolePermission> {
    const res = await apiFetch(`${API_BASE}/permissions/matrix/${action}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ organization_id: organizationId ?? null, min_role: minRole }),
    });
    return handleResponse<RolePermission>(res);
  },

  async resetToDefault(action: PermissionAction, organizationId: number): Promise<RolePermission> {
    const res = await apiFetch(
      `${API_BASE}/permissions/matrix/${action}?organization_id=${organizationId}`,
      { method: "DELETE" },
    );
    return handleResponse<RolePermission>(res);
  },
};
