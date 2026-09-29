import type { BoundingBox, Timestamps } from "./common";

export type RulesetCategory = "Arch";

/**
 * How reliably a rule can be checked against a real IFC model, graded from the
 * property it reads (mirrors `RuleReliability` in app/modules/contracts.py).
 */
export type RuleReliabilityLevel = "high" | "medium" | "low";

export interface RuleReliability {
  level: RuleReliabilityLevel;
  /** Machine-readable basis, e.g. "standard_attribute", "custom", "derived". */
  category: string;
  /** Plain-language explanation shown to the user. */
  reason: string;
  /** Whether the buildingSMART Data Dictionary (bSDD) defines the property; null when it can't be checked. */
  bsdd_defined?: boolean | null;
}

/** The rule fields that decide reliability, for grading a rule before it is saved. */
export interface RuleReliabilityRequest {
  property_set?: string | null;
  property_name?: string | null;
  compare_property?: string | null;
  value_min_property?: string | null;
  value_max_property?: string | null;
}

export interface Rule extends Timestamps {
  id: number;
  rule_id?: string;
  description?: string;
  source_text?: string;
  source_document_id?: number | null;
  source_node_id?: string | null;
  /** Matches DocumentElementBbox.element_id -- the exact structural element this rule was extracted from, when known. */
  source_element_id?: string | null;
  source_page_number?: number | null;
  source_bbox?: BoundingBox | null;
  mechanism?: string;
  ruleset_id?: string;
  rule_category?: string;
  category?: RulesetCategory | string;
  /** rule_check_categories id this rule's results are grouped under; null = uncategorized. */
  check_category_id?: number | null;
  /** IFC entity type the rule applies to (e.g. IfcDoor, IfcWindow), often bSDD-sourced. */
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
  value_min_scale?: string | number | null;
  value_max_scale?: string | number | null;
  compare_property?: string | null;
  name_pattern?: string | null;
  uniqueness_scope?: string | null;
  unit?: string | null;
  severity: string;
  confidence?: string | null;
  extraction_method?: string | null;
  needs_review?: number;
  rase_requirement?: string | null;
  rase_applicability?: Record<string, unknown> | null;
  rase_selection?: Record<string, unknown> | null;
  rase_exception?: Record<string, unknown> | null;
  /** Null when the rule names no IFC property to grade. */
  reliability?: RuleReliability | null;
  /** Scope predicate narrowing which elements the rule governs, e.g.
   * {"room_type_any_of": ["bedroom"]}; null when the rule has none. */
  applies_when?: Record<string, unknown> | null;
}

/** One ontology-vocabulary mismatch found on a rule's target class/property. */
export interface RuleAlignmentIssue {
  field: "target_ifc_class" | "property_name" | "property_set";
  severity: "blocking" | "warning";
  message: string;
  suggestion?: string | null;
}

/** A rule or draft whose constraint is jointly unsatisfiable or in discrepancy with candidate's. */
export interface RuleConflictWarning {
  conflicting_rule_id?: number | null;
  conflicting_draft_id?: number | null;
  conflicting_reference: string;
  conflict_type?:
    | "mutually_exclusive_range"
    | "threshold_mismatch"
    | "exact_value_mismatch"
    | "scope_precedence_clash";
  severity?: "critical" | "warning" | "caution";
  message: string;
  resolution_suggestion?: string | null;
  conflicting_details?: Record<string, any> | null;
}

export interface RuleDraftConflictDetectionRequest {
  draft_ids?: number[];
  document_id?: number;
  ruleset_id?: string;
  include_threshold_discrepancies?: boolean;
}

export interface RuleDraftConflictDetectionResponse {
  total_drafts_analyzed: number;
  total_conflicts_found: number;
  drafts_with_conflicts: RuleExtractionDraft[];
}

/** `Rule` plus the semantic-alignment outcome of promoting it -- non-persisted. */
export interface RulePromotionResponse extends Rule {
  alignment_issues: RuleAlignmentIssue[];
  conflicts: RuleConflictWarning[];
}

export interface RuleSourceResponse {
  document_id: number;
  filename: string;
  page_number?: number | null;
  snippet: string;
  bbox?: BoundingBox | null;
  source_element_id?: string | null;
}

/** Mirrors RuleShaclShapeResponse in app/modules/contracts.py. */
export interface RuleShaclShapeResponse {
  rule_id: number;
  eligible: boolean;
  turtle: string;
  reason?: string | null;
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
  /** Check category id to assign; 0 clears it. */
  check_category_id?: number;
}

/** One entry of the ordered check-category list (mirrors RuleCheckCategoryResponse). */
export interface RuleCheckCategory {
  id: number;
  name: string;
  /** What rules in this category test; shown under its heading. */
  description: string;
  /** Element types the category groups (e.g. ["IfcWindow"]); empty = every element type. */
  target_ifc_classes: string[];
  sort_order: number;
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
  value_min_scale?: string | number;
  value_max_scale?: string | number;
  compare_property?: string;
  name_pattern?: string;
  uniqueness_scope?: string;
  unit?: string;
  severity: string;
  confidence?: string;
  selected?: boolean;
  /** Graded by the server from the property above; null when no property is named. */
  reliability?: RuleReliability | null;
}

export interface ClauseMetadata {
  clause_id?: string | null;
  page_number?: number | null;
  parent_section?: string | null;
  section_path?: string[];
  node_type?: "paragraph" | "table" | "list" | "heading";
  source_document_id: number;
  bbox?: BoundingBox | null;
  element_id?: string | null;
}

export type RuleDraftStatus = "pending_review" | "accepted" | "rejected" | "edited";

export interface RuleCreateRequest {
  rule_id: string;
  description?: string;
  mechanism?: string;
  ruleset_id?: string | null;
  rule_category?: string;
  category?: string | null;
  /** rule_check_categories id this rule's results are grouped under; null = uncategorized. */
  check_category_id?: number | null;
  target_ifc_class?: string | null;
  property_set?: string | null;
  property_name?: string | null;
  operator?: string;
  check_value?: string | null;
  value_min?: string | null;
  value_max?: string | null;
  value_min_property?: string | null;
  value_max_property?: string | null;
  value_min_offset?: string | null;
  value_max_offset?: string | null;
  value_min_scale?: string | null;
  value_max_scale?: string | null;
  compare_property?: string | null;
  name_pattern?: string | null;
  uniqueness_scope?: string | null;
  unit?: string | null;
  severity: string;
  confidence?: string | null;
  extraction_method?: string;
  needs_review?: number;
  /** Scope predicate narrowing which elements this rule governs, e.g. {"material_any_of": ["gypsum"]}. */
  applies_when?: Record<string, unknown> | null;
  /** Waiver predicates excusing an otherwise-failing element; each references another rule. */
  exceptions?: unknown[] | null;
  rase_requirement?: string | null;
  rase_applicability?: Record<string, unknown> | null;
  rase_selection?: Record<string, unknown> | null;
  rase_exception?: Record<string, unknown> | null;
  /** uri of the clause-grounding KG candidate the extraction LLM was shown and picked, if any. Extraction-time audit signal only. */
  kg_candidate_used?: string | null;
}

export interface RuleExtractionDraft {
  id?: number | null;
  source_document_id: number;
  source_node_id?: string | null;
  /** Matches DocumentElementBbox.element_id -- the exact structural element this draft was extracted from, when known. */
  source_element_id?: string | null;
  source_snippet?: string | null;
  clause?: ClauseMetadata | null;
  bbox?: BoundingBox | null;
  proposed_rule: RuleCreateRequest;
  confidence: number;
  extraction_method: "llamaindex_pydantic" | "litellm_legacy";
  status: RuleDraftStatus;
  reviewer_email?: string | null;
  reviewed_at?: string | null;
  review_notes?: string | null;
  created_at?: string | null;
  /** Reliability of `proposed_rule`; follows a reviewer's edits. Null when it names no property. */
  reliability?: RuleReliability | null;
  /** Cross-rule or cross-draft conflicts detected for this candidate. */
  conflicts?: RuleConflictWarning[];
}

export interface RuleExtractionDraftListResponse {
  drafts: RuleExtractionDraft[];
}

/** Lightweight draft shape for the rule-source map's Drafts tab. */
export interface DraftSourceSummary {
  id: number;
  status: RuleDraftStatus;
  rule_id?: string | null;
  description?: string | null;
  severity?: string | null;
  confidence: number;
  extraction_method: string;
  source_page_number?: number | null;
  source_bbox?: BoundingBox | null;
  source_element_id?: string | null;
  match_status: "exact" | "unmapped" | "orphaned";
  /** Full proposed rule, rendered as a structured panel side by side with the source document. */
  proposed_rule?: RuleCreateRequest | null;
}

/** One document element annotated with the pending draft(s) extracted from it. */
export interface DocumentElementWithDrafts {
  element_id: string;
  kind: "heading" | "paragraph" | "list" | "table" | "picture";
  page_number?: number | null;
  bbox?: BoundingBox | null;
  order: number;
  drafts: DraftSourceSummary[];
}

/** Same three-way split as RuleSourceMapResponse, for pending drafts instead of promoted rules. */
export interface DraftSourceMapResponse {
  document_id: number;
  elements: DocumentElementWithDrafts[];
  unmapped_drafts: DraftSourceSummary[];
  orphaned_drafts: DraftSourceSummary[];
}

export interface RuleExtractionProgressResponse {
  document_id: number;
  total: number;
  completed: number;
  status: "running" | "complete" | "failed" | "unknown";
  error?: string | null;
}

export interface RuleDraftReviewRequest {
  status: RuleDraftStatus;
  review_notes?: string | null;
  reviewer_email?: string | null;
  edited_rule?: RuleCreateRequest | null;
}

export interface ModelLineageRecord {
  id: number;
  project_id: number;
  /** project_ifc_files.id this version was produced from, when known. */
  ifc_file_id?: number | null;
  source_version: number;
  version: number;
  status: string;
  source_reference?: string;
  output_reference?: string;
  summary?: Record<string, any>;
  created_at?: string;
}
