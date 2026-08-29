/**
 * Type contracts corresponding directly to backend Pydantic models in app/modules/contracts.py
 */

export interface Project {
  id: number;
  name: string;
  description?: string;
  status: string;
  country: string;
  analysis_type: string;
  ifc_file_path?: string | null;
  ifc_md5_hash?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
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
  analysis_type?: string;
}

export interface Rule {
  id: number;
  rule_id?: string;
  description?: string;
  source_text?: string;
  mechanism?: string;
  ruleset_id?: string;
  rule_category?: string;
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
  rules: Rule[];
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
  band: 'critical' | 'high' | 'medium' | 'low';
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
  kind: 'standard' | 'document';
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
  status: 'pending' | 'running' | 'complete' | 'failed' | 'not_implemented';
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
  event_type: 'stage_transition' | 'metric_increment' | 'engine_complete' | 'engine_failed' | string;
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

export interface DocumentItem {
  id: number;
  filename: string;
  file_path?: string | null;
  upload_date?: string | null;
  extracted_text_preview?: string | null;
  char_count: number;
}

export interface DocumentDetail extends DocumentItem {
  extracted_text: string;
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
  status?: string;  // PASS, FAIL, MISSING
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
  status?: string;  // PASS, FAIL, MISSING_DATA, NO_ELEMENTS
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

