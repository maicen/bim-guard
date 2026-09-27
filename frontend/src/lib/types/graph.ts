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
