/**
 * Type contracts corresponding directly to backend Pydantic models in app/modules/contracts.py
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
 * Canonical analysis domains. Mirrors the keys normalised by
 * `normalize_analysis_type` in app/constants.py; legacy stored values
 * ('Architectural', 'Piping (Corrosive)', 'Halo') collapse onto these via
 * `normalizeAnalysisDomain` in ./analysisDomain.ts.
 */
export type AnalysisDomain = "Arch" | "Piping" | "seismic";

export interface Project {
  id: number;
  name: string;
  description?: string;
  status: string;
  country: string;
  analysis_type: AnalysisDomain | string;
  building_code?: string | null;
  project_type?: string | null;
  project_size_sqm?: number | null;
  buildings_count?: number | null;
  floors_count?: number | null;
  ifc_file_path?: string | null;
  ifc_md5_hash?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
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
  cde_approved_by?: string;
  cde_approved_at?: string | null;
  /** bSDD dictionary code (e.g. uniclass_2015, omniclass_2020) this project is classified against. */
  classification_standard?: string | null;
}

/**
 * Discipline/role an attached IFC model carries.
 * Restriced to primary or context in the project setup wizard.
 */
export const IFC_FILE_ROLES = ["primary", "context"] as const;

export type IfcFileRole = (typeof IFC_FILE_ROLES)[number];

/** One IFC model attached to a project. Mirrors ProjectIfcFileResponse. */
export interface ProjectIfcFile {
  /** project_ifc_files.id; null for a model attached before that table existed. */
  id: number | null;
  project_id: number;
  file_path: string;
  file_name: string;
  is_primary: boolean;
  role: IfcFileRole | string;
  uploaded_at?: string | null;
  project_code?: string;
  originator?: string;
  volume_system?: string;
  level?: string;
  type?: string;
  number?: string;
  suitability_code?: string;
  revision_code?: string;
  cde_state?: CDEState;
  cde_approved_by?: string;
  cde_approved_at?: string | null;
}

/** Outcome of attaching one or more IFC models. Mirrors ProjectIfcUploadResponse. */
export interface ProjectIfcUploadResponse {
  success: boolean;
  files: ProjectIfcFile[];
  primary_id: number | null;
}

export interface ProjectListResponse {
  total: number;
  projects: Project[];
}

export interface ProjectCreatePayload {
  name: string;
  description?: string;
  status?: string;
  country?: string;
  analysis_type?: AnalysisDomain | string;
  building_code?: string | null;
  project_type?: string | null;
  project_size_sqm?: number | null;
  buildings_count?: number | null;
  floors_count?: number | null;
  document_ids?: number[];
  standards_codes?: string[];
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

export interface ProjectUpdatePayload {
  name?: string;
  description?: string;
  status?: string;
  country?: string;
  analysis_type?: AnalysisDomain | string;
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
}

export interface ProjectBulkActionResponse {
  success_count: number;
  affected_ids: number[];
}

export const DOCUMENT_TYPES = ["Code", "Specification", "Manual"] as const;

export type DocumentType = (typeof DOCUMENT_TYPES)[number];

export interface DocumentItem {
  id: number;
  filename: string;
  doc_type?: string | null;
  file_path?: string | null;
  upload_date?: string | null;
  extracted_text_preview?: string | null;
  char_count: number;
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

export interface DocumentDetail {
  id: number;
  filename: string;
  doc_type?: string | null;
  file_path?: string | null;
  upload_date?: string | null;
  extracted_text: string;
  char_count: number;
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

export interface DocumentUpdatePayload {
  filename?: string;
  doc_type?: string | null;
  extracted_text?: string;
  project_code?: string;
  originator?: string;
  suitability_code?: string;
  revision_code?: string;
  cde_state?: CDEState;
}

export type RulesetCategory = "Arch" | "Piping" | "seismic";

export interface Rule {
  id: number;
  rule_id?: string;
  description?: string;
  source_text?: string;
  mechanism?: string;
  ruleset_id?: string;
  rule_category?: string;
  category?: RulesetCategory | string;
  /** IFC entity type the rule applies to (e.g. IfcPipeSegment), often bSDD-sourced. */
  target_ifc_class?: string | null;
  property_set?: string;
  property_name?: string;
  operator?: string;
  check_value?: string | null;
  value_min?: string | null;
  value_max?: string | null;
  value_min_property?: string | null;
  value_max_property?: string | null;
  value_min_offset?: string | number | null;
  value_max_offset?: string | number | null;
  compare_property?: string | null;
  name_pattern?: string | null;
  uniqueness_scope?: string | null;
  unit?: string | null;
  severity: string;
  confidence?: string | null;
  extraction_method?: string | null;
  needs_review?: number;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface RuleFolder {
  id?: number | null;
  ruleset_id: string;
  display_name: string;
  description?: string;
  mechanism_scope?: string;
  category?: RulesetCategory | string;
  count?: number;
  rules: Rule[];
}

export interface RuleFolderCreatePayload {
  ruleset_id: string;
  display_name?: string;
  description?: string;
  mechanism_scope?: string;
  category?: RulesetCategory | string;
}

export interface RuleFolderUpdatePayload {
  display_name?: string;
  description?: string;
  mechanism_scope?: string;
  category?: RulesetCategory | string;
}

export interface RuleBulkUpdatePayload {
  rule_ids: number[];
  ruleset_id?: string;
  category?: RulesetCategory | string;
  mechanism?: string;
  severity?: string;
  needs_review?: number;
  property_set?: string;
}

export interface RuleBulkActionResponse {
  success_count: number;
  affected_ids: number[];
}

export interface RuleFolderBulkUpdatePayload {
  ruleset_ids: string[];
  category?: RulesetCategory | string;
  mechanism_scope?: string;
}

export interface RuleFolderBulkActionResponse {
  success_count: number;
  affected_ruleset_ids: string[];
  deleted_rules_count: number;
}

export type RuleSnapshotSourceMode = "pdf" | "ids" | "manual" | "mixed";

export interface RuleSnapshot {
  id: number;
  name: string;
  source_ruleset_id: string;
  source_mode: RuleSnapshotSourceMode | string;
  category: string;
  rule_count: number;
  notes?: string;
  created_at?: string | null;
  created_by?: string;
}

export interface RuleSnapshotCreatePayload {
  ruleset_id: string;
  name?: string;
  source_mode?: RuleSnapshotSourceMode;
  notes?: string;
  created_by?: string;
}

export interface IdsImportResult {
  success: boolean;
  created_count: number;
  total_parsed: number;
  ruleset_id: string;
}

export interface Citation {
  standard: string;
  clause: string;
  reason: string;
}

export interface AuditIssue {
  id: string;
  element_id: string;
  rule_id: string;
  title: string;
  band: "critical" | "high" | "medium" | "low";
  score: number;
  mechanism: string;
  description: string;
  mitigation: string;
  assignee_role?: string;
  citations?: Citation[];
  details: Record<string, any>;
}

export interface IssueStats {
  total: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  data_quality?: number;
}

export interface AnalysisInputItem {
  kind: "standard" | "document";
  id: string;
  label: string;
  detail: string;
  file_path?: string;
}

export interface AnalysisResult {
  pipeline: string;
  project_id: number;
  slug: string;
  element_count: number;
  audit_issues: AuditIssue[];
  issue_stats: IssueStats;
  compliance_error?: string | null;
  compliance_is_demo?: boolean;
  cached: boolean;
  duration_seconds?: number | null;
  elements_evaluated?: number | null;
  unique_elements_evaluated?: number | null;
  rules_with_elements?: number | null;
  pass_rate?: number | null;
  bcf_artifact_id?: number | null;
  summary?: Record<string, any>;
}

export interface StageRecord {
  stage: number;
  name: string;
  duration_seconds?: number | null;
}

export interface EngineRun {
  code: string;
  label: string;
  status: "pending" | "running" | "complete" | "failed" | "not_implemented";
  current_stage?: number | null;
  stage_name?: string | null;
  progress_percent: number;
  total_stages: number;
  metrics: Record<string, any>;
  stages: StageRecord[];
  error?: string | null;
}

export interface WorkflowStatus {
  project_id: number;
  status: string;
  engines: Record<string, EngineRun>;
  timestamp?: string | null;
}

export interface PipelineEvent {
  event_type:
    "stage_transition" | "metric_increment" | "engine_complete" | "engine_failed" | string;
  source_module: string;
  project_id: number;
  payload: Record<string, any>;
  timestamp: string;
}

export interface DashboardStats {
  total_projects: number;
  total_documents: number;
  total_rules: number;
  issues_found: number;
  db_ok: boolean;
  db_backend: string;
}

export interface SettingItem {
  key: string;
  value: string;
  description: string;
}

export interface SettingsResponse {
  settings: SettingItem[];
  active_log_level: string;
  db_backend: string;
}

export interface ModelLineageRecord {
  id: number;
  project_id: number;
  source_version: number;
  version: number;
  status: string;
  source_reference?: string;
  output_reference?: string;
  summary?: Record<string, any>;
  created_at?: string;
}

export interface BcfArtifact {
  id: number;
  project_id: number;
  artifact_type: string;
  filename: string;
  storage_ref: string;
  content_type: string;
  byte_size: number;
  sha256?: string;
  issue_count: number;
  created_at?: string;
}

export interface ExtractedRule {
  rule_id: string;
  description: string;
  property_set?: string;
  property_name?: string;
  operator?: string;
  check_value?: string;
  value_min?: string;
  value_max?: string;
  value_min_property?: string;
  value_max_property?: string;
  value_min_offset?: string | number;
  value_max_offset?: string | number;
  compare_property?: string;
  name_pattern?: string;
  uniqueness_scope?: string;
  unit?: string;
  severity: string;
  confidence?: string;
  selected?: boolean;
}

export interface RuleElementResult {
  element_name?: string;
  guid?: string;
  storey?: string;
  space?: string;
  actual?: any;
  status?: string; // PASS, FAIL, MISSING
  reason?: string;
  position_mm?: number[];
}

export interface RuleComplianceResult {
  rule_ref?: string;
  rule_id?: number;
  rule_desc?: string;
  property_name?: string;
  target?: string;
  operator?: string;
  check_value?: any;
  value_min?: number;
  value_max?: number;
  unit?: string;
  status?: string; // PASS, FAIL, MISSING_DATA, NO_ELEMENTS
  pass_count?: number;
  fail_count?: number;
  missing_count?: number;
  total_count?: number;
  all_elements?: RuleElementResult[];
}

export interface BuildingSummary {
  storey_count?: number;
  room_count?: number;
  total_gfa_m2?: number;
  external_door_count?: number;
  element_counts?: Record<string, number>;
  fixture_counts?: Record<string, number>;
  alarm_counts?: Record<string, number>;
  floor_heights?: { from: string; height_mm: number }[];
  rooms_per_storey?: Record<string, { count: number; total_area_m2: number }>;
  storeys?: { name: string }[];
  unplaced_rooms?: any[];
  unnamed_elements?: { type: string; count: number }[];
}

export interface DaylightResult {
  storey_name?: string;
  space_name: string;
  floor_area_m2: number;
  total_window_area_m2: number;
  daylight_ratio: number;
  passes: boolean;
  code_ref?: string;
}

export interface FireSeparationResult {
  wall_name: string;
  adjacent_spaces: string[];
  fire_rating_raw?: string;
  missing_rating?: boolean;
  passes: boolean;
  code_ref?: string;
}

export interface ExitCountResult {
  storey: string;
  exit_count: number;
  required_min: number;
  passes: boolean;
  code_ref?: string;
}

export interface TravelDistanceResult {
  storey_name?: string;
  space_name: string;
  travel_distance_m?: number;
  nearest_exit?: string;
  passes: boolean;
  no_path?: boolean;
  code_ref?: string;
}

export interface GarageResult {
  element_type: string;
  element_name: string;
  garage_space: string;
  adjacent_space: string;
  fire_rating_raw?: string;
  missing_rating?: boolean;
  required_min?: number;
  passes: boolean;
}

export interface ArchAnalysisResult {
  project_id: number;
  project_name: string;
  categories: Record<string, any>;
  total_issues: number;
  issues: any[];
  summary: Record<string, any>;
  rule_compliance_summary?: Record<string, any>;
  bcf_artifact_id?: number | null;
  building_summary?: BuildingSummary;
  spatial_checks?: Record<string, any>;
  egress_checks?: Record<string, any>;
  rule_compliance?: RuleComplianceResult[];
  rule_folder?: string;
  ifc_element_count?: number;
}

export interface RevitSyncElement {
  ifc_class: string;
  name?: string;
  guid?: string;
  storey?: string;
  properties?: Record<string, any>;
}

export interface RevitSyncRequest {
  project_name?: string;
  theme?: string;
  elements: RevitSyncElement[];
}

export interface RevitRuleResult {
  rule_ref?: string;
  rule_desc?: string;
  target?: string;
  property_name?: string;
  status?: string;
  pass_count?: number;
  fail_count?: number;
  missing_count?: number;
  failures?: any[];
}

export interface RevitSyncResponse {
  element_count: number;
  theme: string;
  summary: Record<string, any>;
  results: RevitRuleResult[];
}

export interface GitHubRepo {
  id: number;
  name: string;
  owner: string;
  url: string;
  branch: string;
  description: string;
  is_active: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface GitHubRepoItem {
  path: string;
  name: string;
  type: string;
  size: number;
  extension: string;
  category: string;
  download_url: string;
}

export interface GitHubRepoStructure {
  repo_id: number;
  owner: string;
  name: string;
  url: string;
  branch: string;
  total_files: number;
  models_count: number;
  categories: string[];
  items: GitHubRepoItem[];
}

export interface GitHubRepoCreatePayload {
  url: string;
  name?: string;
  branch?: string;
  description?: string;
}

export interface GitHubRepoUpdatePayload {
  name?: string;
  branch?: string;
  description?: string;
  is_active?: boolean;
}

export interface ProjectImportPayload {
  file_path: string;
  name?: string;
  country?: string;
  analysis_type?: string;
}

export type UnstructuredInstanceKind = "local" | "hosted" | "docling" | "docling-local";

export interface UnstructuredInstance {
  id: number;
  name: string;
  kind: UnstructuredInstanceKind;
  api_url: string;
  has_api_key: boolean;
  strategy: string;
  is_default: boolean;
  is_enabled: boolean;
  notes: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface UnstructuredInstanceCreatePayload {
  name: string;
  kind: UnstructuredInstanceKind;
  api_url: string;
  api_key?: string;
  strategy?: string;
  is_default?: boolean;
  is_enabled?: boolean;
  notes?: string;
}

export interface UnstructuredInstanceUpdatePayload {
  name?: string;
  api_url?: string;
  api_key?: string;
  strategy?: string;
  is_default?: boolean;
  is_enabled?: boolean;
  notes?: string;
}

export interface UnstructuredInstanceTestResult {
  ok: boolean;
  detail: string;
}

// =============================================================================
// buildingSMART Ecosystem Frontend Types
// =============================================================================

// 1. bSDD Types
export interface BSDDPropertyItem {
  uri: string;
  name: string;
  property_set?: string | null;
  data_type?: string | null;
  units?: string | null;
  allowed_values: string[];
  description?: string | null;
}

export interface BSDDClassItem {
  uri: string;
  code: string;
  name: string;
  dictionary_uri: string;
  parent_class_code?: string | null;
  related_ifc_entities: string[];
  properties: BSDDPropertyItem[];
  description?: string | null;
}

export interface BSDDDictionaryItem {
  uri: string;
  code: string;
  name: string;
  version: string;
  organization_code_owner: string;
  language_iso_code: string;
  classes_count: number;
}

export interface BSDDValidationViolation {
  element_guid: string;
  element_type: string;
  field_checked: string;
  expected_constraint: string;
  actual_value?: any;
  severity: "error" | "warning" | "info" | string;
  message: string;
  dictionary_uri?: string | null;
}

export interface BSDDValidationResult {
  passed: boolean;
  dictionary_uri: string;
  total_elements_checked: number;
  total_properties_checked: number;
  passed_count: number;
  violations_count: number;
  compliance_score_pct: number;
  violations: BSDDValidationViolation[];
}

export interface BSDDClassSearchResponse {
  query: string;
  total: number;
  classes: BSDDClassItem[];
}

export interface BSDDPropertySearchResponse {
  query: string;
  total: number;
  properties: BSDDPropertyItem[];
}

// 2. OpenCDE Types
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
}

export interface CDESyncResponse {
  success: boolean;
  synced_documents_count: number;
  synced_files: string[];
  message: string;
}

// 3. IFC Pre-Flight Validation Types
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

// 4. IDS Types
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

// 5. BCF REST API Types
export interface BCFProjectResponse {
  project_id: string;
  name: string;
  authorization?: {
    project_actions: string[];
    topic_actions: string[];
  };
}

export interface BCFCommentResponse {
  guid: string;
  date: string;
  author: string;
  comment: string;
  topic_guid: string;
  modified_date?: string | null;
  modified_author?: string | null;
  viewpoint_guid?: string | null;
}

export interface BCFCommentCreatePayload {
  comment: string;
  viewpoint_guid?: string | null;
}

export interface BCFViewpointResponse {
  guid: string;
  topic_guid: string;
  index: number;
  perspective_camera?: Record<string, any> | null;
  orthogonal_camera?: Record<string, any> | null;
  lines?: Record<string, any>[];
  clipping_planes?: Record<string, any>[];
  components?: Record<string, any>;
  snapshot_url?: string | null;
}

export interface BCFViewpointCreatePayload {
  perspective_camera?: Record<string, any> | null;
  orthogonal_camera?: Record<string, any> | null;
  components?: Record<string, any> | null;
  snapshot_base64?: string | null;
}

export interface BCFTopicResponse {
  guid: string;
  topic_type: string;
  topic_status: string;
  title: string;
  priority: string;
  index: number;
  creation_date: string;
  creation_author: string;
  modified_date?: string | null;
  modified_author?: string | null;
  assigned_to?: string | null;
  description?: string | null;
  due_date?: string | null;
  labels: string[];
  stage?: string | null;
  component_guids: string[];
  project_code?: string | null;
  originator?: string | null;
  suitability_code?: string | null;
  revision_code?: string | null;
  cde_state?: CDEState | null;
  comments_count: number;
  viewpoints_count: number;
}

export interface BCFTopicCreatePayload {
  title: string;
  topic_type?: string;
  topic_status?: string;
  priority?: string;
  description?: string;
  assigned_to?: string;
  due_date?: string;
  labels?: string[];
  component_guids?: string[];
  suitability_code?: string;
  revision_code?: string;
  cde_state?: CDEState;
}

export interface BCFTopicUpdatePayload {
  title?: string;
  topic_type?: string;
  topic_status?: string;
  priority?: string;
  description?: string;
  assigned_to?: string;
  due_date?: string;
  labels?: string[];
  component_guids?: string[];
  suitability_code?: string;
  revision_code?: string;
  cde_state?: CDEState;
}

// ── ISO 19650 naming configuration ───────────────────────────────────────────

/** One entry of the code library. Mirrors NamingCodeContract. */
export interface NamingCode {
  code: string;
  label: string;
}

/** One naming convention: a format string over the token vocabulary. */
export interface NamingConvention {
  id: string;
  name: string;
  format: string;
  separator: string;
  description: string;
  /** True for the five built-ins, which cannot be edited or deleted. */
  preset: boolean;
  /** False for conventions meant for clash-test names rather than for a CDE. */
  iso_compliant: boolean;
}

/** One token a convention format may contain. */
export interface NamingToken {
  token: string;
  label: string;
  /** Where the value comes from: 'config', 'library' or 'runtime'. */
  source: string;
}

/** One row of the CDE status table (ISO 19650-2 Table 1). */
export interface CdeStatus {
  code: string;
  label: string;
  colour: string;
  /** False for rows shown for reference but not offered as a suitability. */
  selectable: boolean;
}

/** The static half of the naming feature. Mirrors NamingCatalogResponseContract. */
export interface NamingCatalog {
  conventions: NamingConvention[];
  tokens: NamingToken[];
  codes: Record<string, NamingCode[]>;
  cde_statuses: CdeStatus[];
  date_formats: string[];
  separators: string[];
  default_convention: string;
}

/** A project's naming configuration. Mirrors NamingConfigContract. */
export interface NamingConfig {
  project_id: number;
  /** False when nothing has been saved and these are the defaults. */
  is_configured: boolean;
  project_code: string;
  originator_code: string;
  type_code: string;
  suitability: string;
  revision: string;
  separator: string;
  date_format: string;
  class_a: string;
  class_b: string;
  active_convention: string;
  level_codes: NamingCode[];
  type_codes: NamingCode[];
  discipline_codes: NamingCode[];
  volume_codes: NamingCode[];
  custom_conventions: NamingConvention[];
  updated_at?: string | null;
}

/** Fields to write. Mirrors NamingConfigUpdateContract; every field optional. */
export type NamingConfigPayload = Partial<
  Omit<NamingConfig, "project_id" | "is_configured" | "updated_at">
>;

/** A rendered sample name. Mirrors NamingPreviewResponseContract. */
export interface NamingPreview {
  name: string;
  convention_id: string;
  /** The format as rendered, with the project's separator substituted. */
  applied_format: string;
  /** Tokens left literal because nothing supplied a value for them. */
  unresolved_tokens: string[];
}
