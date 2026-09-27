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

/**
 * Window over a paginated `audit_issues` list.
 *
 * Only present when the request carried a pagination parameter; a call with
 * none returns the whole run and no `page`. `total_matching` counts the issues
 * left after the band/mechanism filters and before offset/limit, so a pager
 * can size itself from it. It is unrelated to `issue_stats`, which always
 * describes the whole run.
 */
export interface ResultPage {
  limit?: number | null;
  offset: number;
  returned: number;
  total_matching: number;
  has_more: boolean;
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
  page?: ResultPage | null;
  duration_seconds?: number | null;
  elements_evaluated?: number | null;
  unique_elements_evaluated?: number | null;
  rules_with_elements?: number | null;
  pass_rate?: number | null;
  bcf_artifact_id?: number | null;
  summary?: Record<string, any>;
  shacl_issues?: Record<string, any>[];
  shacl_error?: string | null;
}

export interface StageRecord {
  stage: number;
  name: string;
  duration_seconds?: number | null;
}

export interface EngineRun {
  /**
   * `code` and `label` are not in the workflow payload — the code is the key
   * in `WorkflowStatus.engines`, and the human name arrives as `engine_name`.
   * Both stay declared and optional for callers that build an EngineRun by
   * hand, but read `engine_name` when rendering one that came from the API.
   */
  code?: string;
  label?: string;
  engine_name?: string;
  /**
   * Which concurrent run reported this engine — "default" (architecture),
   * "graph" or "inspector" (Digital Inspector). Absent on an engine nothing
   * has tracked yet; those are excluded from the progress average by their
   * `pending` status, not by this field.
   */
  run_key?: string;
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
  /**
   * Overall run state: "idle" (nothing tracked), "running", or — once every
   * engine of the run named by `run_key` has finished — "complete" / "failed".
   * Carried by `/api/analyze/status/{id}` and every SSE `status` frame.
   */
  status: string;
  /**
   * The run that reported most recently. A project can have its default
   * analysis run and a graph run tracked at once (the backend keys trackers
   * by project + run), so a progress average scoped to this reports the run
   * the user is actually waiting on instead of blending the two.
   */
  run_key?: string;
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

export interface BcfArtifact {
  id: number;
  project_id: number;
  /** project_ifc_files.id this export was produced from, when known. */
  ifc_file_id?: number | null;
  artifact_type: string;
  filename: string;
  storage_ref: string;
  content_type: string;
  byte_size: number;
  sha256?: string;
  issue_count: number;
  created_at?: string;
  /** Ruleset id the run was scoped to, or blank for an unscoped ("All Rules") run. */
  rule_folder?: string | null;
  /** Ruleset display-name snapshot taken at save time. */
  ruleset_name?: string | null;
  /** Supabase auth user id of whoever triggered the run, when known. */
  created_by?: string | null;
  /** Email snapshot for created_by, taken at save time. */
  created_by_email?: string | null;
}

/** Mirrors app/modules/property_confidence.py's CONFIDENCE_CATEGORIES —
 * which resolution pass supplied a property's value, ranked 1 (most
 * authoritative) to 7 (unresolved). */
export interface PropertyConfidence {
  id:
    | "authored"
    | "derived"
    | "type_inherited"
    | "alias"
    | "fallback"
    | "geometry_estimate"
    | "unresolved";
  label: string;
  description: string;
  rank: number;
  meter_level: number;
}

export interface RuleElementResult {
  element_name?: string;
  guid?: string;
  storey?: string;
  space?: string;
  /** Rooms the element connects to, present when the rule asked about rooms.
   * `space` above is only direct IfcSpace containment, which most exporters
   * never write for a door or wall. */
  connected_rooms?: string[] | null;
  /** IFC GlobalIds of those rooms, in the same order. Unique per room, unlike the name. */
  connected_room_ids?: string[] | null;
  /** Each room as "name [#id]": the name exactly as the model spells it, then the end of
   * its GlobalId, so two rooms called the same thing can be told apart. */
  connected_room_labels?: string[] | null;
  /** How the rooms were linked: self / boundary / containment / host_wall /
   * geometric_bbox / none. See app/modules/ifc_reader/ifc_rooms.py. */
  room_link_source?: string | null;
  /** Present when the element was checked although the rule's scope could not
   * be decided for it (e.g. it connects to a room whose type is unknown). Each
   * entry says what could not be resolved. */
  scope_undetermined?: string[] | null;
  actual?: any;
  status?: string; // PASS, FAIL, MISSING
  reason?: string;
  position_mm?: number[];
  /** Geometry-analysis caveats (e.g. a winder stair whose tread depth was
   * measured along the wrong axis, or a guard whose baluster spacing isn't
   * computed) — present on ANY status, including PASS, since a caveat
   * matters most when a value looks compliant but wasn't reliably measured. */
  data_quality_warnings?: string[] | null;
  /** Which resolution pass supplied `actual` — authored / derived /
   * type-inherited / alias / fallback / geometry-estimate / unresolved. See
   * lib/propertyConfidence.ts. Present on ANY status, same reasoning as
   * data_quality_warnings. */
  property_confidence?: PropertyConfidence | null;
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
  /** Notes about the rule's own room scope, e.g. a room it names that the model
   * does not have, with suggested fixes for likely misspellings. */
  scope_warnings?: string[];
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
