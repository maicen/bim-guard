/** Mirrors ProofNodeType in app/modules/contracts.py. */
export type ProofNodeType = "asserted_fact" | "rule_axiom" | "inference_step" | "verdict";

/** Mirrors ProofEdgeType in app/modules/contracts.py. */
export type ProofEdgeType = "satisfies" | "violates" | "infers" | "applies";

/** Mirrors ProofNodeContract in app/modules/contracts.py. */
export interface ProofNodeContract {
  id: string;
  label: string;
  node_type: ProofNodeType;
  metadata: Record<string, any>;
}

/** Mirrors ProofEdgeContract in app/modules/contracts.py. */
export interface ProofEdgeContract {
  source: string;
  target: string;
  label: ProofEdgeType;
}

/** Mirrors IssueProofGraphContract in app/modules/contracts.py. */
export interface IssueProofGraphContract {
  issue_id: string;
  rule_id: string;
  element_id: string;
  nodes: ProofNodeContract[];
  edges: ProofEdgeContract[];
  explanation: string;
}

/** Causal decision lineage graph response. */
export interface DecisionCausalChainResponse {
  project_id: number;
  issue_id: string;
  verdict: Record<string, any>;
  rule: Record<string, any>;
  element: Record<string, any>;
  lineage_nodes: Array<{
    id: string;
    label: string;
    node_type: string;
    properties?: Record<string, any>;
  }>;
  lineage_edges: Array<{
    source: string;
    target: string;
    label: string;
  }>;
  prov_summary: string;
}

/** Rule compliance impact analysis response. */
export interface RuleImpactResponse {
  project_id: number;
  rule_id: string;
  total_elements_evaluated: number;
  total_findings: number;
  impacted_elements: Array<{
    verdict_id?: string;
    issue_id?: string;
    element_id: string;
    element_name?: string;
    ifc_type?: string;
    outcome: string;
    risk_band: string;
    score: number;
    title?: string;
  }>;
}

/** Mirrors GraphStatusContract in app/modules/contracts.py. */
export interface GraphStatusContract {
  project_id: number;
  node_count: number;
  edge_count: number;
  has_spatial_boundaries: boolean;
  is_geometric_fallback: boolean;
  centrality_summary: Record<string, any>;
}

/** Mirrors GraphHealResponse in app/modules/contracts.py. */
export interface GraphHealResponse {
  project_id: number;
  healed_spaces: number;
  created_boundaries: number;
  total_boundaries: number;
  status: string;
  message: string;
}

/** Mirrors SpatialTreeNodeContract in app/modules/contracts.py. */
export interface SpatialTreeNodeContract {
  guid: string;
  label: string;
  ifc_type: string;
  children: SpatialTreeNodeContract[];
  truncated_count: number;
}

/** Mirrors SpatialTreeResponse in app/modules/contracts.py. */
export interface SpatialTreeResponse {
  project_id: number;
  root: SpatialTreeNodeContract | null;
}

/** Mirrors ElementRelationEdge in app/modules/contracts.py. */
export interface ElementRelationEdge {
  predicate: string;
  guid: string;
  label: string;
}

/** Mirrors ElementRelationshipsResponse in app/modules/contracts.py. */
export interface ElementRelationshipsResponse {
  project_id: number;
  guid: string;
  exists: boolean;
  ifc_type?: string | null;
  label?: string | null;
  bot_classes: string[];
  s4bldg_classes: string[];
  outgoing: ElementRelationEdge[];
  incoming: ElementRelationEdge[];
}

/** Mirrors GraphQueryPresetSummary in app/modules/contracts.py. */
export interface GraphQueryPresetSummary {
  key: string;
  label: string;
  description: string;
  params: string[];
}

/** Mirrors GraphQueryPresetListResponse in app/modules/contracts.py. */
export interface GraphQueryPresetListResponse {
  presets: GraphQueryPresetSummary[];
}

/** Mirrors GraphQueryResultResponse in app/modules/contracts.py. */
export interface GraphQueryResultResponse {
  rows: Record<string, unknown>[];
  row_count: number;
}

/** Mirrors CodeToIfcTraceEntry in app/modules/contracts.py. */
export interface CodeToIfcTraceEntry {
  rule_id: number;
  reference: string;
  description: string;
  target_ifc_class: string;
  element_count: number;
  source_document_id?: number | null;
  source_page_number?: number | null;
}

/** Mirrors CodeToIfcTraceResponse in app/modules/contracts.py. */
export interface CodeToIfcTraceResponse {
  project_id: number;
  entries: CodeToIfcTraceEntry[];
}

/** Mirrors the SPARQL JSON results shape execute_sparql_query returns. */
export interface SparqlQueryResult {
  head?: { vars: string[] };
  results?: { bindings: Record<string, { type: string; value: string }>[] };
  boolean?: boolean;
}

/** One automated IFC data-quality audit check result. */
export interface ModelHealthCheckItem {
  key: string;
  name: string;
  description: string;
  severity: "info" | "warning" | "critical";
  passed: boolean;
  violation_count: number;
  details: Record<string, any>[];
  recommendation: string;
}

/** Comprehensive Model Data Health & Hygiene Audit Report. */
export interface ModelHealthAuditReport {
  project_id: number;
  health_score: number;
  grade: "A" | "B" | "C" | "D" | "F";
  total_elements_audited: number;
  total_violations: number;
  checks: ModelHealthCheckItem[];
  evaluated_at: string;
}

/** A clause node in the regulatory knowledge graph. */
export interface RegulatoryClauseNode {
  clause_id: string;
  standard: string;
  section: string;
  title: string;
  text: string;
  target_ifc_types: string[];
  cross_references: string[];
}

/** An atomic measurable requirement extracted from a regulatory standard. */
export interface RegulatoryRequirementItem {
  rule_id?: number | null;
  standard: string;
  clause: string;
  target_ifc_type: string;
  parameter: string;
  operator: string;
  value: any;
  unit?: string | null;
  severity: string;
  description: string;
}

/** Full regulatory graph context for a specific clause or standard. */
export interface RegulatoryGraphContextResponse {
  clause: RegulatoryClauseNode;
  parent_section?: string | null;
  cross_referenced_clauses: RegulatoryClauseNode[];
  governed_ifc_types: string[];
  extracted_requirements: RegulatoryRequirementItem[];
}

/** All regulatory requirements governing a given IFC class across standards. */
export interface GoverningRequirementsResponse {
  ifc_type: string;
  total_requirements: number;
  standards_covered: string[];
  requirements: RegulatoryRequirementItem[];
}

/** Scope of knowledge for Graph-RAG. */
export type GraphRagScope = "document" | "model" | "hybrid";

/** A grounded reference cited by Graph-RAG. */
export interface GraphRagCitation {
  id: string;
  source_type: "document" | "model" | "rule";
  title: string;
  reference: string;
  snippet: string;
  page_number?: number | null;
  element_guid?: string | null;
  ifc_type?: string | null;
  properties?: Record<string, any>;
  score?: number | null;
  retrieval_method?: "vector" | "bm25" | "graph" | "hybrid_rrf" | null;
  rrf_score?: number | null;
}

/** An analytical tool or graph traversal action recorded during Graph-RAG. */
export interface GraphRagToolCall {
  tool_name: string;
  arguments: Record<string, any>;
  output_summary: string;
  cypher_query?: string | null;
  status: "running" | "success" | "error";
}

/** A milestone in the Graph-RAG chain-of-thought or multi-step execution. */
export interface GraphRagStep {
  step_index: number;
  title: string;
  description: string;
  status: "pending" | "running" | "done" | "failed";
  data?: Record<string, any> | null;
}

/** Natural-language question and execution scope for Graph-RAG. */
export interface GraphRagQueryRequest {
  query: string;
  scope?: GraphRagScope;
  document_id?: number | null;
  element_class?: string | null;
  model_name?: string | null;
  temperature?: number | null;
}

/** Grounded answer, explainability trace, and citations from Graph-RAG. */
export interface GraphRagQueryResponse {
  project_id: number;
  scope: GraphRagScope;
  answer: string;
  citations: GraphRagCitation[];
  tool_calls: GraphRagToolCall[];
  reasoning_steps: GraphRagStep[];
  cypher_queries: string[];
  suggested_followups: string[];
  subgraph_data?: {
    nodes?: Array<{ id: string; label: string; type: string }>;
    edges?: Array<{ source: string; target: string; label?: string }>;
  };
  retrieval_mode?: string | null;
  rrf_metrics?: Record<string, any> | null;
}

/** Available document and IFC model entities available for Graph-RAG in a project. */
export interface GraphRagContextSummary {
  project_id: number;
  project_name?: string;
  client_name?: string;
  project_code?: string;
  status?: string;
  has_ifc_model: boolean;
  total_elements: number;
  total_storeys?: number;
  total_spaces?: number;
  ifc_classes: Array<{ class_name: string; count: number }>;
  storeys?: Array<{ guid: string; name: string; element_count: number }>;
  documents: Array<{ id: number; title: string; section_count: number; document_type?: string; cde_state?: string }>;
  rulesets: string[];
  models?: Array<{ id?: number; file_name: string; role?: string; is_primary?: boolean; cde_state?: string; discipline?: string; uploaded_at?: string; revision_code?: string }>;
}

