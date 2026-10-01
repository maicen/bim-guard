import type {
  Project,
  ProjectBulkActionResponse,
  ProjectBulkUpdatePayload,
  ProjectCreatePayload,
  ProjectDocumentBindingsResponse,
  ProjectOptions,
  ProjectClientNamesResponse,
  ProjectListResponse,
  ProjectRulesetBindingsResponse,
  ProjectUpdatePayload,
} from "../types";
import {
  EntityCacheStore,
  InMemoryCache,
  SWRStore,
  type SWROptions,
  type Unsubscribe,
} from "../cache";
import { getActiveOrgId, withAuthToken } from "../authToken";
import { API_BASE, apiFetch, handleResponse } from "./client";

// ── Standardized Entity Cache Stores (SOLID Architecture) ─────────────────────
const _projectsStore = new EntityCacheStore<Project, number>((p) => p.id, 60_000, 60_000);
const _projectOptionsStore = new SWRStore<string, ProjectOptions>(new InMemoryCache(), 300_000);

export const projectsApi = {
  getCachedList(orgId?: number | null): ProjectListResponse | null {
    const effectiveOrg = orgId !== undefined ? orgId : getActiveOrgId();
    const key = `org:${effectiveOrg ?? "all"}`;
    const list = _projectsStore.getCachedList(key) || _projectsStore.getCachedList("__default__");
    if (!list) return null;
    const filtered = effectiveOrg ? list.filter((p) => p.organization_id === effectiveOrg) : list;
    return {
      projects: filtered,
      total: filtered.length,
    };
  },

  subscribe(listener: (projects: Project[]) => void, orgId?: number | null): Unsubscribe {
    const effectiveOrg = orgId !== undefined ? orgId : getActiveOrgId();
    const key = `org:${effectiveOrg ?? "all"}`;
    return _projectsStore.subscribe(listener, key);
  },

  clearCache(): void {
    _projectsStore.clear();
  },

  async list(options: SWROptions & { organization_id?: number | null } = {}): Promise<ProjectListResponse> {
    const effectiveOrg = options.organization_id !== undefined ? options.organization_id : getActiveOrgId();
    const key = `org:${effectiveOrg ?? "all"}`;
    const list = await _projectsStore.fetchList(
      key,
      async () => {
        const query = effectiveOrg ? `?organization_id=${effectiveOrg}` : "";
        const res = await apiFetch(`${API_BASE}/projects${query}`);
        const data = await handleResponse<ProjectListResponse | Project[]>(res);
        return Array.isArray(data) ? data : data.projects;
      },
      options,
    );

    return {
      projects: list,
      total: list.length,
    };
  },

  async get(id: number, options: SWROptions = {}): Promise<Project> {
    return _projectsStore.fetchItem(
      id,
      async () => {
        const res = await apiFetch(`${API_BASE}/projects/${id}`);
        return handleResponse<Project>(res);
      },
      options,
    );
  },

  async getInputs(id: number): Promise<any[]> {
    const res = await apiFetch(`${API_BASE}/projects/${id}/inputs`);
    return handleResponse<any[]>(res);
  },

  async options(options: SWROptions = {}): Promise<ProjectOptions> {
    return _projectOptionsStore.execute(
      "__options__",
      async () => {
        const res = await apiFetch(`${API_BASE}/projects/options`);
        return handleResponse<ProjectOptions>(res);
      },
      options,
    );
  },

  /**
   * Distinct client names already used on projects the caller can see, scoped
   * to the active organization the same way list() is. Not cached: it is read
   * once per wizard opening and must include a client added a moment ago.
   */
  async clientNames(organizationId?: number | null): Promise<ProjectClientNamesResponse> {
    const effectiveOrg = organizationId !== undefined ? organizationId : getActiveOrgId();
    const query = effectiveOrg ? `?organization_id=${effectiveOrg}` : "";
    const res = await apiFetch(`${API_BASE}/projects/client-names${query}`);
    return handleResponse<ProjectClientNamesResponse>(res);
  },

  async create(payload: ProjectCreatePayload): Promise<Project> {
    const res = await apiFetch(`${API_BASE}/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const created = await handleResponse<Project>(res);
    _projectsStore.addOrUpdate(created);
    return created;
  },


  async update(id: number, payload: ProjectUpdatePayload): Promise<Project> {
    const res = await apiFetch(`${API_BASE}/projects/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const updated = await handleResponse<Project>(res);
    _projectsStore.addOrUpdate(updated);
    return updated;
  },

  async delete(id: number): Promise<void> {
    const res = await apiFetch(`${API_BASE}/projects/${id}`, {
      method: "DELETE",
    });
    await handleResponse<void>(res);
    _projectsStore.remove(id);
  },

  async bulkDelete(ids: number[]): Promise<ProjectBulkActionResponse> {
    const res = await apiFetch(`${API_BASE}/projects/bulk-delete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_ids: ids }),
    });
    const result = await handleResponse<ProjectBulkActionResponse>(res);
    ids.forEach((id) => _projectsStore.remove(id));
    return result;
  },

  async bulkUpdate(payload: ProjectBulkUpdatePayload): Promise<ProjectBulkActionResponse> {
    const res = await apiFetch(`${API_BASE}/projects/bulk-update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await handleResponse<ProjectBulkActionResponse>(res);
    _projectsStore.clear();
    return result;
  },

  invalidateCache() {
    _projectsStore.clear();
    _projectOptionsStore.clear();
  },

  getIfcUrl(id: number): string {
    return withAuthToken(`${API_BASE}/projects/${id}/ifc`);
  },

  /** Rulesets bound to this project, and which of its org's grants remain
   * available to bind. A brand-new project has none bound. */
  async getRulesetBindings(projectId: number): Promise<ProjectRulesetBindingsResponse> {
    const res = await apiFetch(`${API_BASE}/projects/${projectId}/ruleset-bindings`);
    return handleResponse<ProjectRulesetBindingsResponse>(res);
  },

  async setRulesetBindings(
    projectId: number,
    rulesetIds: string[],
  ): Promise<ProjectRulesetBindingsResponse> {
    const res = await apiFetch(`${API_BASE}/projects/${projectId}/ruleset-bindings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ruleset_ids: rulesetIds }),
    });
    return handleResponse<ProjectRulesetBindingsResponse>(res);
  },

  async getDocumentBindings(projectId: number): Promise<ProjectDocumentBindingsResponse> {
    const res = await apiFetch(`${API_BASE}/projects/${projectId}/document-bindings`);
    return handleResponse<ProjectDocumentBindingsResponse>(res);
  },

  async setDocumentBindings(
    projectId: number,
    documentIds: number[],
  ): Promise<ProjectDocumentBindingsResponse> {
    const res = await apiFetch(`${API_BASE}/projects/${projectId}/document-bindings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document_ids: documentIds }),
    });
    return handleResponse<ProjectDocumentBindingsResponse>(res);
  },
};
