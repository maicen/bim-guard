import type { OrgRole } from "./common";

/** One organization the authenticated caller belongs to. Mirrors OrganizationMembership. */
export interface OrganizationMembership {
  organization_id: number;
  name: string;
  slug: string;
  /** ISO 19650 Originator Code for this organization. */
  org_code: string;
  role: OrgRole;
}

/** Editable identity/preferences layered on auth.users. Mirrors UserProfile. */
export interface UserProfile {
  full_name: string;
  avatar_url: string;
  title: string;
  default_organization_id: number | null;
  preferences: Record<string, unknown>;
  is_superadmin: boolean;
}

/** Fields to write to the caller's profile. Mirrors ProfileUpdateRequest. */
export type ProfileUpdatePayload = Partial<
  Pick<UserProfile, "full_name" | "avatar_url" | "title" | "default_organization_id" | "preferences">
>;

/** The signed-in caller's identity. Mirrors CurrentUserResponse. */
export interface CurrentUserResponse {
  id: string;
  email: string | null;
  profile: UserProfile;
  organizations: OrganizationMembership[];
}

/** A member of an organization. Mirrors OrganizationMemberResponse. */
export interface OrganizationMember {
  user_id: string;
  email: string;
  full_name: string;
  avatar_url: string;
  role: OrgRole;
  group_id: number | null;
  group_name: string | null;
}

/** Mirrors OrganizationMemberListResponse. */
export interface OrganizationMemberListResponse {
  organization_id: number;
  members: OrganizationMember[];
}

/** A pending or accepted invite into an organization. Mirrors OrganizationInviteResponse. */
export interface OrganizationInvite {
  id: number;
  organization_id: number;
  email: string;
  role: OrgRole;
  accepted_at: string | null;
}

/** Mirrors OrganizationInviteListResponse. */
export interface OrganizationInviteListResponse {
  organization_id: number;
  invites: OrganizationInvite[];
}

/** Mirrors OrganizationInviteCreateRequest. */
export interface OrganizationInviteCreatePayload {
  email: string;
  role: OrgRole;
}

/** One organization, as listed for the platform superadmin. Mirrors OrganizationSummary. */
export interface OrganizationSummary {
  id: number;
  name: string;
  slug: string;
  /** ISO 19650 Originator Code for this organization. */
  org_code: string;
}

/** Mirrors OrganizationListResponse. */
export interface OrganizationListResponse {
  organizations: OrganizationSummary[];
}

/** Mirrors OrganizationCreateRequest. */
export interface OrganizationCreatePayload {
  name: string;
  /** Required: ISO 19650 Originator Code, 2-6 alphanumeric characters. */
  org_code: string;
}

/** Mirrors AddMemberRequest. */
export interface AddMemberPayload {
  user_id: string;
  role: OrgRole;
}

/** One organization a user belongs to. Mirrors UserOrganizationSummary. */
export interface UserOrganizationSummary {
  organization_id: number;
  name: string;
  role: OrgRole;
}

/** One user on the platform, as listed for the superadmin user directory. Mirrors UserSummary. */
export interface UserSummary {
  id: string;
  email: string;
  full_name: string;
  avatar_url: string;
  is_superadmin: boolean;
  organizations: UserOrganizationSummary[];
}

/** Mirrors UserListResponse. */
export interface UserListResponse {
  users: UserSummary[];
}

/** One user group within an organization. Mirrors GroupResponse. */
export interface Group {
  id: number;
  organization_id: number;
  name: string;
  member_count: number;
}

/** Mirrors GroupListResponse. */
export interface GroupListResponse {
  organization_id: number;
  groups: Group[];
}

/** Mirrors GroupProjectGrantsResponse. */
export interface GroupProjectGrantsResponse {
  group_id: number;
  project_ids: number[];
}

/** Mirrors OrganizationRulesetGrantsResponse. */
export interface OrganizationRulesetGrantsResponse {
  organization_id: number;
  ruleset_ids: string[];
}

/** Mirrors ProjectRulesetBindingsResponse. */
export interface ProjectRulesetBindingsResponse {
  project_id: number;
  ruleset_ids: string[];
  available_ruleset_ids: string[];
}

/** Cross-org project sharing grant. Mirrors OrganizationProjectGrantsResponse. */
export interface OrganizationProjectGrantsResponse {
  organization_id: number;
  project_ids: number[];
}

/** Mirrors OrganizationDocumentGrantsResponse. */
export interface OrganizationDocumentGrantsResponse {
  organization_id: number;
  document_ids: number[];
}

/** Mirrors ProjectDocumentBindingsResponse. */
export interface ProjectDocumentBindingsResponse {
  project_id: number;
  document_ids: number[];
  available_document_ids: number[];
}
