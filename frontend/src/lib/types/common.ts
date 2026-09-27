/**
 * Core shared types and ISO 19650 metadata contracts.
 * Corresponding directly to backend Pydantic models in app/modules/contracts.py
 */

export const CDE_STATE_CHOICES = ["WIP", "SHARED", "PUBLISHED", "ARCHIVED"] as const;
export type CDEState = (typeof CDE_STATE_CHOICES)[number];

export const SUITABILITY_CODES = [
  "S0",
  "S1",
  "S2",
  "S3",
  "S4",
  "S5",
  "S6",
  "S7",
  "D1",
  "D2",
  "D3",
  "D4",
  "A1",
  "A2",
  "B1",
  "CR",
] as const;
export type SuitabilityCode = (typeof SUITABILITY_CODES)[number];

export interface BoundingBox {
  l: number;
  t: number;
  r: number;
  b: number;
  coord_origin?: string;
}

export interface ISO19650Metadata {
  project_code: string;
  originator: string;
  volume_system: string;
  level: string;
  type: string;
  role: string;
  number: string;
  suitability_code: string;
  revision_code: string;
  cde_state: CDEState;
  cde_approved_by?: string;
  cde_approved_at?: string | null;
}

/**
 * ISO 19650/CDE metadata block shared by response-style interfaces.
 * Mirrors IsoGovernanceFieldsRequired in app/modules/contracts.py
 * (`project_code` excluded -- its required-ness varies by call site).
 */
export interface IsoGovernanceFieldsRequired {
  originator?: string;
  volume_system?: string;
  level?: string;
  type?: string;
  role?: string;
  number?: string;
  suitability_code?: string;
  revision_code?: string;
  cde_state?: CDEState;
}

/**
 * Same ISO 19650/CDE fields, for partial-update payloads.
 * Mirrors IsoGovernanceFieldsOptional in app/modules/contracts.py.
 */
export interface IsoGovernanceFieldsOptional {
  project_code?: string;
  originator?: string;
  volume_system?: string;
  level?: string;
  type?: string;
  role?: string;
  number?: string;
  suitability_code?: string;
  revision_code?: string;
  cde_state?: CDEState;
}

/** Mirrors TimestampFields in app/modules/contracts.py. */
export interface Timestamps {
  created_at?: string | null;
  updated_at?: string | null;
}

/** Mirrors OrgRole in app/modules/contracts.py. */
export type OrgRole = "owner" | "admin" | "member";

/** Mirrors app.modules.permissions.Action — a superadmin-configurable, role-gated action. */
export type PermissionAction =
  | "manage_org_members"
  | "manage_llm_providers"
  | "manage_project_bindings"
  | "manage_parsing_engines"
  | "manage_scim";

/** Mirrors PermissionActionResponse in app/modules/contracts.py. */
export interface PermissionActionInfo {
  action: PermissionAction;
  description: string;
}

/** Mirrors RolePermissionResponse in app/modules/contracts.py. */
export interface RolePermission {
  action: PermissionAction;
  min_role: OrgRole;
  is_override: boolean;
}

/** Mirrors ScimTokenStatusResponse in app/modules/contracts.py -- never the raw token. */
export interface ScimTokenStatus {
  configured: boolean;
  base_url: string;
  created_at: string | null;
  last_used_at: string | null;
  revoked: boolean;
}

/** Mirrors ScimTokenMintResponse in app/modules/contracts.py -- the raw token, shown exactly once. */
export interface ScimTokenMintResult {
  token: string;
  base_url: string;
}

/**
 * Canonical analysis domains. Mirrors the keys normalised by
 * `normalize_analysis_type` in app/constants.py; legacy stored values
 * ('Architectural', 'Architecture') collapse onto this via
 * `normalizeAnalysisDomain` in ./analysisDomain.ts.
 */
export type AnalysisDomain = "Arch";
