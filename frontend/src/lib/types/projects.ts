import type {
  AnalysisDomain,
  CDEState,
  IsoGovernanceFieldsOptional,
  IsoGovernanceFieldsRequired,
  Timestamps,
} from "./common";

export const PROJECT_TYPES = [
  "RESIDENTIAL",
  "COMMERCIAL",
  "MEDICAL",
  "EDUCATIONAL",
  "INDUSTRIAL",
  "AGRICULTURAL",
  "GOVERNMENTAL",
  "MILITARY",
  "PARKING",
  "RELIGIOUS",
  "TRANSPORT",
  "RECREATIONAL",
  "INFRASTRUCTURE",
] as const;

export type ProjectType = (typeof PROJECT_TYPES)[number];

export interface Project extends IsoGovernanceFieldsRequired, Timestamps {
  id: number;
  name: string;
  /** Short display nickname shown in the header/breadcrumbs instead of the full name. */
  short_name?: string;
  /** The client (appointing party) the project is delivered for; '' on projects that predate it. */
  client_name?: string;
  organization_id?: number | null;
  description?: string;
  status: string;
  country: string;
  analysis_type: AnalysisDomain | string;
  building_code?: string | null;
  project_type?: ProjectType | string | null;
  project_size_sqm?: number | null;
  buildings_count?: number | null;
  floors_count?: number | null;
  ifc_file_path?: string | null;
  ifc_md5_hash?: string | null;
  project_code?: string;
  cde_approved_by?: string;
  cde_approved_at?: string | null;
  /** bSDD dictionary code (e.g. uniclass_2015, omniclass_2020) this project is classified against. */
  classification_standard?: string | null;
}

/**
 * ISO 19650 container naming keeps the project code segment short -- 2-6
 * alphanumeric characters, no separators. Mirrors PROJECT_CODE_MIN_LENGTH /
 * PROJECT_CODE_MAX_LENGTH / PROJECT_CODE_PATTERN in app/modules/contracts.py.
 */
export const PROJECT_CODE_MIN_LENGTH = 2;
export const PROJECT_CODE_MAX_LENGTH = 6;
export const PROJECT_CODE_PATTERN = /^[A-Za-z0-9]+$/;

/**
 * The short name is a human-readable nickname (not an ISO 19650 field), kept
 * short enough for the header and breadcrumbs that display it. Mirrors
 * SHORT_NAME_MIN_LENGTH / SHORT_NAME_MAX_LENGTH in app/modules/contracts.py.
 */
export const SHORT_NAME_MIN_LENGTH = 2;
export const SHORT_NAME_MAX_LENGTH = 24;

/**
 * Discipline/role an attached IFC model carries.
 * Restriced to primary or context in the project setup wizard.
 */
export const IFC_FILE_ROLES = ["primary", "context"] as const;

export type IfcFileRole = (typeof IFC_FILE_ROLES)[number];

/** One IFC model attached to a project. Mirrors ModelResponse. */
export interface Model extends IsoGovernanceFieldsRequired {
  /** project_ifc_files.id; null for a model attached before that table existed. */
  id: number | null;
  project_id: number;
  file_path: string;
  file_name: string;
  is_primary: boolean;
  role: IfcFileRole | string;
  uploaded_at?: string | null;
  /** IFC schema version from the model header, e.g. IFC4, IFC2X3. */
  ifc_schema?: string;
  /** Authoring application + version that produced this model. */
  authoring_application?: string;
  /** Count of IfcBuildingStorey entities; null if extraction failed. */
  storey_count?: number | null;
  /** Count of IfcElement occurrences; null if extraction failed. */
  element_count?: number | null;
  /** Heuristic element-count breakdown by discipline (architectural/structural/mep/other). */
  discipline_summary?: Record<string, number>;
  project_code?: string;
  cde_approved_by?: string;
  cde_approved_at?: string | null;
}

export interface UploadUrlRequest {
  file_name: string;
  content_type?: string | null;
  size_bytes?: number | null;
}

export interface UploadUrlResponse {
  signed_url: string;
  storage_reference: string;
  token?: string;
}

export interface ModelConfirmRequest {
  storage_reference: string;
  file_name: string;
  is_primary?: boolean;
  role?: string;
  allow_project_code_mismatch?: boolean;
}

/** Outcome of attaching one or more IFC models. Mirrors ModelUploadResponse. */
export interface ModelUploadResponse {
  success: boolean;
  files: Model[];
  primary_id: number | null;
  /** True while storing/attaching still runs in the background; poll ModelAttachStatusResponse. */
  processing: boolean;
  /** Non-blocking notes, e.g. a filename outside ISO 19650 container naming. */
  warnings: string[];
}

/** Progress of a background attach job. Mirrors ModelAttachStatusResponse. */
export interface ModelAttachStatusResponse {
  processing: boolean;
  total: number;
  attached: number;
  error: string | null;
}

/** A project's attached IFC models. Mirrors ModelListResponse. */
export interface ModelListResponse {
  project_id: number;
  models: Model[];
}

export interface ProjectListResponse {
  total: number;
  projects: Project[];
}

export interface ProjectCreatePayload {
  name: string;
  /** Required: short display nickname shown in the header/breadcrumbs. 2-24 characters. */
  short_name: string;
  /** Required: the client (appointing party) the project is delivered for. */
  client_name: string;
  organization_id?: number | null;
  description?: string;
  country?: string;
  analysis_type?: AnalysisDomain | string;
  building_code?: string | null;
  project_type?: string | null;
  project_size_sqm?: number | null;
  buildings_count?: number | null;
  floors_count?: number | null;
  document_ids?: number[];
  standards_codes?: string[];
  /** Required: ISO 19650 project code, 2-6 alphanumeric characters. */
  project_code: string;
  originator?: string;
  volume_system?: string;
  level?: string;
  type?: string;
  role?: string;
  number?: string;
  suitability_code?: string;
  revision_code?: string;
  cde_state?: CDEState;
  classification_standard?: string | null;
}

/** One selectable normative reference offered by the project setup wizard. */
export interface StandardOption {
  id: string;
  name: string;
  domain: string;
  description?: string;
  applicable_to?: string[];
}

/** One building code offered by the wizard, scoped to the jurisdictions it governs. */
export interface BuildingCodeOption {
  id: string;
  name: string;
  description?: string;
  /** Countries the code governs; empty means it applies everywhere. */
  jurisdictions?: string[];
  /** Seeded ruleset executed for this code, if one is bundled. */
  ruleset_id?: string;
}

/** Reference data the wizard renders its choices from (GET /projects/options). */
export interface ProjectOptions {
  countries: string[];
  project_types: string[];
  analysis_types: string[];
  standards: StandardOption[];
  building_codes: BuildingCodeOption[];
}

/** Distinct client names on the caller's visible projects, for the wizard's pick-list. */
export interface ProjectClientNamesResponse {
  client_names: string[];
}

export interface ProjectUpdatePayload extends IsoGovernanceFieldsOptional {
  name?: string;
  short_name?: string;
  description?: string;
  status?: string;
  country?: string;
  analysis_type?: AnalysisDomain | string;
  project_type?: ProjectType | string | null;
  classification_standard?: string | null;
}

export interface ProjectBulkDeletePayload {
  project_ids: number[];
}

export interface ProjectBulkUpdatePayload {
  project_ids: number[];
  status?: string;
  country?: string;
  analysis_type?: string;
  project_type?: ProjectType | string | null;
}

export interface ProjectBulkActionResponse {
  success_count: number;
  affected_ids: number[];
}
