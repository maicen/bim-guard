import type {
  CodeToIfcTraceResponse,
  DecisionCausalChainResponse,
  ElementRelationshipsResponse,
  GraphQueryPresetListResponse,
  GraphQueryResultResponse,
  RuleImpactResponse,
  SparqlQueryResult,
  SpatialTreeResponse,
} from "../types";
import { withAuthToken } from "../authToken";
import { API_BASE, apiFetch, handleResponse } from "./client";

export const graphApi = {
  /** The project's IFC spatial containment tree (Project->Site->Building->Storey->Space->Element). */
  async getSpatialTree(projectId: number): Promise<SpatialTreeResponse> {
    const res = await apiFetch(`${API_BASE}/graph/${projectId}/spatial-tree`);
    return handleResponse<SpatialTreeResponse>(res);
  },

  /** One element's BOT/SAREF4BLDG classification and graph relationships. */
  async getElementRelationships(
    projectId: number,
    guid: string,
  ): Promise<ElementRelationshipsResponse> {
    const res = await apiFetch(
      `${API_BASE}/graph/${projectId}/element/${encodeURIComponent(guid)}/relationships`,
    );
    return handleResponse<ElementRelationshipsResponse>(res);
  },

  /** Every Cypher preset the GraphRAG query console can run (not project-scoped). */
  async listQueryPresets(): Promise<GraphQueryPresetListResponse> {
    const res = await apiFetch(`${API_BASE}/graph/query-presets`);
    return handleResponse<GraphQueryPresetListResponse>(res);
  },

  /** Run one named Cypher preset; project_id is always enforced server-side. */
  async runQueryPreset(
    projectId: number,
    presetKey: string,
    params: Record<string, string>,
  ): Promise<GraphQueryResultResponse> {
    const res = await apiFetch(
      `${API_BASE}/graph/${projectId}/query-presets/${encodeURIComponent(presetKey)}/run`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(params),
      },
    );
    return handleResponse<GraphQueryResultResponse>(res);
  },

  /** Rule catalog clauses traced to the IFC classes they govern in this project's model. */
  async getCodeToIfcTrace(projectId: number): Promise<CodeToIfcTraceResponse> {
    const res = await apiFetch(`${API_BASE}/graph/${projectId}/code-to-ifc-trace`);
    return handleResponse<CodeToIfcTraceResponse>(res);
  },

  /** Trace full causal decision lineage from an issue finding across Verdict, Rule, and Element nodes. */
  async traceDecision(projectId: number, issueId: string): Promise<DecisionCausalChainResponse> {
    const res = await apiFetch(
      `${API_BASE}/graph/${projectId}/decisions/trace/${encodeURIComponent(issueId)}`,
    );
    return handleResponse<DecisionCausalChainResponse>(res);
  },

  /** Analyze downstream compliance impact and model elements governed by a rule. */
  async getRuleImpact(projectId: number, ruleId: string): Promise<RuleImpactResponse> {
    const res = await apiFetch(
      `${API_BASE}/graph/${projectId}/rules/${encodeURIComponent(ruleId)}/impact`,
    );
    return handleResponse<RuleImpactResponse>(res);
  },

  /** Ingest all compliance audit verdicts for this project into Neo4j decision graph. */
  async ingestDecisions(
    projectId: number,
  ): Promise<{ project_id: number; total_issues_processed: number; ingest_stats: Record<string, number> }> {
    const res = await apiFetch(`${API_BASE}/graph/${projectId}/decisions/ingest`, {
      method: "POST",
    });
    return handleResponse(res);
  },

  /** Get URL for downloading the W3C PROV-O Turtle RDF compliance decision audit trail. */
  getProvOExportUrl(projectId: number): string {
    return withAuthToken(`${API_BASE}/graph/${projectId}/prov-o`);
  },
};

export const sparqlApi = {
  /**
   * Run a free-form SPARQL SELECT/ASK/CONSTRUCT query against the project's
   * named graph. Unlike the Cypher preset console, this is safe to expose
   * as free text: GraphTriplestoreService.query() only accepts pyoxigraph's
   * read-only query forms (never SPARQL Update) and is tenant-isolated via
   * named_graphs scoping to this project alone.
   */
  async query(projectId: number, query: string): Promise<SparqlQueryResult> {
    const res = await apiFetch(`${API_BASE}/sparql/${projectId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    return handleResponse<SparqlQueryResult>(res);
  },
};
