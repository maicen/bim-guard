import type { CDEState } from "./common";

// =============================================================================
// OpenCDE and Validation Types
// =============================================================================

export interface CDEVersionItem {
  version: string;
  api_type: "foundation" | "documents" | "bcf" | string;
  detailed_version?: string | null;
}

export interface CDEVersionsResponse {
  versions: CDEVersionItem[];
}

export interface CDEUserResponse {
  id: string;
  name: string;
  email?: string | null;
  role?: string | null;
}

export interface CDEDocumentItem {
  id: string;
  name: string;
  document_type: string;
  size_bytes: number;
  etag: string;
  url?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
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
}

export interface CDESyncRequest {
  cde_server_url: string;
  project_id: number;
  external_project_id: string;
  document_ids?: string[];
  auto_analyze?: boolean;
  access_token?: string | null;
}

export interface CDESyncResponse {
  success: boolean;
  synced_documents_count: number;
  synced_files: string[];
  errors: string[];
  message: string;
}

// IFC Pre-Flight Validation Types
export interface IFCValidationIssue {
  rule_code: string;
  stage: "syntax" | "schema" | "gherkin_rules" | string;
  severity: "fatal" | "error" | "warning" | "info" | string;
  message: string;
  line_number?: number | null;
  entity_id?: string | null;
}

export interface IFCValidationStageResult {
  stage_name: string;
  passed: boolean;
  issues_count: number;
  details: IFCValidationIssue[];
}

export interface IFCValidationReport {
  valid: boolean;
  schema_version?: string | null;
  file_size_bytes: number;
  syntax_stage: IFCValidationStageResult;
  schema_stage: IFCValidationStageResult;
  rules_stage: IFCValidationStageResult;
  total_issues: number;
  fatal_errors: number;
  warnings: number;
  summary_message: string;
}

// IDS Types
export interface IDSFacetViolation {
  element_guid: string;
  element_type: string;
  spec_name: string;
  facet_type: string;
  details: string;
  expected: string;
  actual?: string | null;
}

export interface IDSValidationReport {
  passed: boolean;
  specifications_count: number;
  total_checks: number;
  passed_checks: number;
  failed_checks: number;
  compliance_percent: number;
  violations: IDSFacetViolation[];
}
