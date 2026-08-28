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
  details: Record<string, any>;
}

export interface IssueStats {
  total: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
}

export interface AnalysisResult {
  pipeline: string;
  project_id: number;
  slug: string;
  element_count: number;
  audit_issues: AuditIssue[];
  issue_stats: IssueStats;
  compliance_error?: string | null;
  cached: boolean;
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

