import type {
  EnvVarStatusResponse,
  ParsingEngineInstance,
  ParsingEngineInstanceCreatePayload,
  ParsingEngineInstanceTestResult,
  ParsingEngineInstanceUpdatePayload,
  ParsingEngineKind,
  LLMProviderInstance,
  LLMProviderInstanceCreatePayload,
  LLMProviderInstanceTestResult,
  LLMProviderInstanceUpdatePayload,
  LLMProviderKind,
  LLMProviderModel,
  LLMProviderTestPayload,
  LLMTask,
  LLMTaskAssignmentSetPayload,
  LLMTaskModelAssignment,
} from "../types";
import { API_BASE, apiFetch, handleResponse } from "./client";

export const settingsApi = {
  async get(): Promise<any> {
    const res = await apiFetch(`${API_BASE}/settings`);
    return handleResponse<any>(res);
  },

  async update(settings: Record<string, string>): Promise<any> {
    const res = await apiFetch(`${API_BASE}/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ settings }),
    });
    return handleResponse<any>(res);
  },

  async getEnvStatus(): Promise<EnvVarStatusResponse> {
    const res = await apiFetch(`${API_BASE}/settings/env-status`);
    return handleResponse<EnvVarStatusResponse>(res);
  },
};

// =============================================================================
// Parsing Engines API Client
// =============================================================================

export const parsingEnginesApi = {
  /** Registered engine kinds (drivers) — drives the Settings UI's kind
   * selector so a new backend driver appears with no frontend change. */
  async kinds(): Promise<ParsingEngineKind[]> {
    const res = await apiFetch(`${API_BASE}/parsing-engines/kinds`);
    return handleResponse<ParsingEngineKind[]>(res);
  },

  async list(): Promise<ParsingEngineInstance[]> {
    const res = await apiFetch(`${API_BASE}/parsing-engines`);
    return handleResponse<ParsingEngineInstance[]>(res);
  },

  async create(payload: ParsingEngineInstanceCreatePayload): Promise<ParsingEngineInstance> {
    const res = await apiFetch(`${API_BASE}/parsing-engines`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<ParsingEngineInstance>(res);
  },

  async update(id: number, payload: ParsingEngineInstanceUpdatePayload): Promise<ParsingEngineInstance> {
    const res = await apiFetch(`${API_BASE}/parsing-engines/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<ParsingEngineInstance>(res);
  },

  async delete(id: number): Promise<void> {
    const res = await apiFetch(`${API_BASE}/parsing-engines/${id}`, {
      method: "DELETE",
    });
    await handleResponse<void>(res);
  },

  async test(id: number): Promise<ParsingEngineInstanceTestResult> {
    const res = await apiFetch(`${API_BASE}/parsing-engines/${id}/test`, {
      method: "POST",
    });
    return handleResponse<ParsingEngineInstanceTestResult>(res);
  },
};

// =============================================================================
// Org-Scoped Parsing Engines API Client (see app/api/parsing_engine_instances.py)
// =============================================================================
// Mirrors parsingEnginesApi above but scoped to one organization — an org's
// own owner/admin manages these; resolution prefers them over the
// platform-wide instances parsingEnginesApi lists.

export const orgParsingEnginesApi = {
  async kinds(organizationId: number): Promise<ParsingEngineKind[]> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/parsing-engines/kinds`);
    return handleResponse<ParsingEngineKind[]>(res);
  },

  async list(organizationId: number): Promise<ParsingEngineInstance[]> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/parsing-engines`);
    return handleResponse<ParsingEngineInstance[]>(res);
  },

  async create(
    organizationId: number,
    payload: ParsingEngineInstanceCreatePayload,
  ): Promise<ParsingEngineInstance> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/parsing-engines`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<ParsingEngineInstance>(res);
  },

  async update(
    organizationId: number,
    id: number,
    payload: ParsingEngineInstanceUpdatePayload,
  ): Promise<ParsingEngineInstance> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/parsing-engines/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<ParsingEngineInstance>(res);
  },

  async delete(organizationId: number, id: number): Promise<void> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/parsing-engines/${id}`, {
      method: "DELETE",
    });
    await handleResponse<void>(res);
  },

  async test(organizationId: number, id: number): Promise<ParsingEngineInstanceTestResult> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/parsing-engines/${id}/test`, {
      method: "POST",
    });
    return handleResponse<ParsingEngineInstanceTestResult>(res);
  },
};

// =============================================================================
// LLM Providers API Client (org-scoped — see app/api/llm_provider_instances.py)
// =============================================================================

export const llmProvidersApi = {
  /** Registered provider kinds (drivers) — drives the External Providers UI's
   * kind selector so a new backend driver appears with no frontend change. */
  async kinds(organizationId: number): Promise<LLMProviderKind[]> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/llm-providers/kinds`);
    return handleResponse<LLMProviderKind[]>(res);
  },

  async list(organizationId: number): Promise<LLMProviderInstance[]> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/llm-providers`);
    return handleResponse<LLMProviderInstance[]>(res);
  },

  async create(
    organizationId: number,
    payload: LLMProviderInstanceCreatePayload,
  ): Promise<LLMProviderInstance> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/llm-providers`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<LLMProviderInstance>(res);
  },

  async update(
    organizationId: number,
    id: number,
    payload: LLMProviderInstanceUpdatePayload,
  ): Promise<LLMProviderInstance> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/llm-providers/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<LLMProviderInstance>(res);
  },

  async delete(organizationId: number, id: number): Promise<void> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/llm-providers/${id}`, {
      method: "DELETE",
    });
    await handleResponse<void>(res);
  },

  async test(organizationId: number, id: number): Promise<LLMProviderInstanceTestResult> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/llm-providers/${id}/test`, {
      method: "POST",
    });
    return handleResponse<LLMProviderInstanceTestResult>(res);
  },

  async testConnection(
    organizationId: number,
    payload: LLMProviderTestPayload,
  ): Promise<LLMProviderInstanceTestResult> {
    const res = await apiFetch(
      `${API_BASE}/organizations/${organizationId}/llm-providers/test-connection`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    );
    return handleResponse<LLMProviderInstanceTestResult>(res);
  },

  async models(organizationId: number, id: number): Promise<LLMProviderModel[]> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/llm-providers/${id}/models`);
    return handleResponse<LLMProviderModel[]>(res);
  },

  /** Registered tasks (e.g. "rule_extraction") — drives the External
   * Providers UI's Task Shortlists section so a new backend task appears
   * with no frontend change. */
  async tasks(organizationId: number): Promise<LLMTask[]> {
    const res = await apiFetch(`${API_BASE}/organizations/${organizationId}/llm-providers/tasks`);
    return handleResponse<LLMTask[]>(res);
  },

  async taskAssignments(organizationId: number, taskKey?: string): Promise<LLMTaskModelAssignment[]> {
    const query = taskKey ? `?task_key=${encodeURIComponent(taskKey)}` : "";
    const res = await apiFetch(
      `${API_BASE}/organizations/${organizationId}/llm-providers/task-assignments${query}`,
    );
    return handleResponse<LLMTaskModelAssignment[]>(res);
  },

  async setTaskAssignments(
    organizationId: number,
    taskKey: string,
    payload: LLMTaskAssignmentSetPayload,
  ): Promise<LLMTaskModelAssignment[]> {
    const res = await apiFetch(
      `${API_BASE}/organizations/${organizationId}/llm-providers/task-assignments/${encodeURIComponent(taskKey)}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    );
    return handleResponse<LLMTaskModelAssignment[]>(res);
  },
};
