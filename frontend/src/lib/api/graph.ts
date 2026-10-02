import type {
  CodeToIfcTraceResponse,
  DecisionCausalChainResponse,
  ElementRelationshipsResponse,
  GoverningRequirementsResponse,
  GraphQueryPresetListResponse,
  GraphQueryResultResponse,
  GraphRagCitation,
  GraphRagContextSummary,
  GraphRagQueryRequest,
  GraphRagQueryResponse,
  GraphRagStep,
  GraphRagToolCall,
  ModelHealthAuditReport,
  RegulatoryGraphContextResponse,
  RuleImpactResponse,
  SparqlQueryResult,
  SpatialTreeResponse,
} from "../types";
import { withAuthToken } from "../authToken";
import { API_BASE, apiFetch, handleResponse } from "./client";

export const graphApi = {
  /** Run automated pre-flight model data health and quality audit checks (inspired by ifc-to-graph-assignment). */
  async getModelHealth(projectId: number): Promise<ModelHealthAuditReport> {
    const res = await apiFetch(`${API_BASE}/graph/${projectId}/model-health`);
    return handleResponse<ModelHealthAuditReport>(res);
  },

  /** Retrieve full contextual knowledge graph neighborhood for a regulatory clause. */
  async getRegulatoryClauseContext(clauseRef: string): Promise<RegulatoryGraphContextResponse> {
    const res = await apiFetch(`${API_BASE}/graph/regulations/clauses/${encodeURIComponent(clauseRef)}`);
    return handleResponse<RegulatoryGraphContextResponse>(res);
  },

  /** Get all regulatory requirements governing an IFC entity class across standards. */
  async getGoverningRequirements(ifcType: string = "IfcDoor"): Promise<GoverningRequirementsResponse> {
    const res = await apiFetch(`${API_BASE}/graph/regulations/requirements?ifc_type=${encodeURIComponent(ifcType)}`);
    return handleResponse<GoverningRequirementsResponse>(res);
  },

  /** Ingest regulatory standards and catalog rules into the graph database. */
  async ingestRegulatoryGraph(): Promise<Record<string, any>> {
    const res = await apiFetch(`${API_BASE}/graph/regulations/ingest`, {
      method: "POST",
    });
    return handleResponse<Record<string, any>>(res);
  },
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

  /** Get available documents, model classes, and stats for Graph-RAG in this project. */
  async getRagContext(projectId: number): Promise<GraphRagContextSummary> {
    const res = await apiFetch(`${API_BASE}/graph/${projectId}/rag/context`);
    return handleResponse<GraphRagContextSummary>(res);
  },

  /** Execute synchronous Graph-RAG question answering. */
  async queryRag(projectId: number, payload: GraphRagQueryRequest): Promise<GraphRagQueryResponse> {
    const res = await apiFetch(`${API_BASE}/graph/${projectId}/rag/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<GraphRagQueryResponse>(res);
  },

  /** Stream real-time tokens, reasoning steps, tool calls, and citations via SSE. */
  streamRag(
    projectId: number,
    payload: GraphRagQueryRequest,
    callbacks: {
      onStep?: (step: GraphRagStep) => void;
      onToolCall?: (toolCall: GraphRagToolCall) => void;
      onCitation?: (citation: GraphRagCitation) => void;
      onToken?: (token: string) => void;
      onDone?: (result: GraphRagQueryResponse) => void;
      onError?: (error: string) => void;
    },
  ): () => void {
    const controller = new AbortController();

    (async () => {
      try {
        const res = await apiFetch(`${API_BASE}/graph/${projectId}/rag/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
          signal: controller.signal,
        });

        if (!res.ok) {
          const errText = await res.text();
          callbacks.onError?.(errText || `Stream error: HTTP ${res.status}`);
          return;
        }

        const reader = res.body?.getReader();
        if (!reader) {
          callbacks.onError?.("Readable stream not supported");
          return;
        }

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const events = buffer.split("\n\n");
          buffer = events.pop() || "";

          for (const rawEvent of events) {
            if (!rawEvent.trim()) continue;
            let eventType = "message";
            let dataStr = "";

            for (const line of rawEvent.split("\n")) {
              if (line.startsWith("event: ")) {
                eventType = line.slice(7).trim();
              } else if (line.startsWith("data: ")) {
                dataStr = line.slice(6);
              }
            }

            if (!dataStr) continue;

            try {
              const parsed = JSON.parse(dataStr);
              if (eventType === "step") {
                callbacks.onStep?.(parsed as GraphRagStep);
              } else if (eventType === "tool_call") {
                callbacks.onToolCall?.(parsed as GraphRagToolCall);
              } else if (eventType === "citation") {
                callbacks.onCitation?.(parsed as GraphRagCitation);
              } else if (eventType === "token") {
                callbacks.onToken?.(parsed.token || "");
              } else if (eventType === "done") {
                callbacks.onDone?.(parsed as GraphRagQueryResponse);
              } else if (eventType === "error") {
                callbacks.onError?.(parsed.detail || "Stream error occurred");
              }
            } catch (err) {
              console.warn("Failed parsing SSE frame:", err, dataStr);
            }
          }
        }
      } catch (err: any) {
        if (err.name !== "AbortError") {
          callbacks.onError?.(err.message || String(err));
        }
      }
    })();

    return () => controller.abort();
  },

  adkStreamRag(
    projectId: number,
    payload: GraphRagQueryRequest,
    callbacks: {
      onStep?: (step: GraphRagStep) => void;
      onToolCall?: (toolCall: GraphRagToolCall) => void;
      onCitation?: (citation: GraphRagCitation) => void;
      onToken?: (token: string) => void;
      onDone?: (result: GraphRagQueryResponse) => void;
      onError?: (error: string) => void;
    },
  ): () => void {
    const controller = new AbortController();

    (async () => {
      try {
        const res = await apiFetch(`${API_BASE}/graph/${projectId}/rag/adk-stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
          signal: controller.signal,
        });

        if (!res.body) throw new Error("No response body");
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const events = buffer.split("\n\n");
          buffer = events.pop() || "";

          for (const rawEvent of events) {
            if (!rawEvent.trim()) continue;
            let eventType = "message";
            let dataStr = "";

            for (const line of rawEvent.split("\n")) {
              if (line.startsWith("event: ")) {
                eventType = line.slice(7).trim();
              } else if (line.startsWith("data: ")) {
                dataStr = line.slice(6);
              }
            }

            if (!dataStr) continue;

            try {
              const parsed = JSON.parse(dataStr);
              if (eventType === "step") {
                callbacks.onStep?.(parsed as GraphRagStep);
              } else if (eventType === "tool_call") {
                callbacks.onToolCall?.(parsed as GraphRagToolCall);
              } else if (eventType === "citation") {
                callbacks.onCitation?.(parsed as GraphRagCitation);
              } else if (eventType === "token") {
                callbacks.onToken?.(parsed.token || "");
              } else if (eventType === "done") {
                callbacks.onDone?.(parsed as GraphRagQueryResponse);
              } else if (eventType === "error") {
                callbacks.onError?.(parsed.detail || "Stream error occurred");
              }
            } catch (err) {
              console.warn("Failed parsing SSE frame:", err, dataStr);
            }
          }
        }
      } catch (err: any) {
        if (err.name !== "AbortError") {
          callbacks.onError?.(err.message || String(err));
        }
      }
    })();

    return () => controller.abort();
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
