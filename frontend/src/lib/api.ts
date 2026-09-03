import type {
  AnalysisResult,
  BcfArtifact,
  BCFCommentCreatePayload,
  BCFCommentResponse,
  BCFProjectResponse,
  BCFTopicCreatePayload,
  BCFTopicResponse,
  BCFTopicUpdatePayload,
  BCFViewpointCreatePayload,
  BCFViewpointResponse,
  BSDDClassItem,
  BSDDClassSearchResponse,
  BSDDDictionaryItem,
  BSDDPropertySearchResponse,
  CDEDocumentItem,
  CDESyncRequest,
  CDESyncResponse,
  CDEUserResponse,
  CDEVersionsResponse,
  DocumentDetail,
  DocumentItem,
  DocumentUpdatePayload,
  GitHubRepo,
  GitHubRepoCreatePayload,
  GitHubRepoStructure,
  GitHubRepoUpdatePayload,
  IdsImportResult,
  NamingCatalog,
  NamingConfig,
  NamingConfigPayload,
  NamingPreview,
  Project,
  ProjectBulkActionResponse,
  ProjectBulkUpdatePayload,
  ProjectCreatePayload,
  ProjectIfcFile,
  ProjectIfcUploadResponse,
  ProjectImportPayload,
  ProjectOptions,
  ProjectListResponse,
  ProjectUpdatePayload,
  Rule,
  RuleBulkActionResponse,
  RuleBulkUpdatePayload,
  RuleFolder,
  RuleFolderBulkActionResponse,
  RuleFolderBulkUpdatePayload,
  RuleFolderCreatePayload,
  RuleFolderUpdatePayload,
  RulesetCategory,
  RuleSnapshot,
  RuleSnapshotCreatePayload,
  WorkflowStatus,
} from "./types";
import {
  EntityCacheStore,
  InMemoryCache,
  SWRStore,
  type SWROptions,
  type Unsubscribe,
} from "./cache";

const API_BASE = import.meta.env.VITE_API_URL || "/api";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorDetail = res.statusText;
    try {
      const errJson = await res.json();
      const detail = errJson.detail ?? errJson.error;
      if (Array.isArray(detail)) {
        // FastAPI's default 422 validation shape: a list of {loc, msg, ...}.
        errorDetail =
          detail
            .map((d: any) => {
              const field = Array.isArray(d?.loc) ? d.loc.slice(1).join(".") : "";
              return field ? `${field}: ${d.msg}` : d?.msg || JSON.stringify(d);
            })
            .join("; ") || errorDetail;
      } else if (detail) {
        errorDetail = typeof detail === "string" ? detail : JSON.stringify(detail);
      }
    } catch {
      // not json
    }
    throw new Error(errorDetail);
  }
  if (res.status === 204) {
    return {} as T;
  }
  return res.json();
}

// ── Standardized Entity Cache Stores (SOLID Architecture) ─────────────────────
const _projectsStore = new EntityCacheStore<Project, number>((p) => p.id, 60_000, 60_000);
const _projectOptionsStore = new SWRStore<string, ProjectOptions>(new InMemoryCache(), 300_000);

const _rulesStore = new EntityCacheStore<Rule, number>((r) => r.id, 60_000, 60_000);
const _ruleFoldersStore = new SWRStore<string, RuleFolder[]>(new InMemoryCache(), 60_000);

const _documentsStore = new EntityCacheStore<DocumentItem, number>((d) => d.id, 60_000, 60_000);
const _documentDetailStore = new SWRStore<number, DocumentDetail>(new InMemoryCache(), 60_000);

const _dashboardStatsStore = new SWRStore<string, any>(new InMemoryCache(), 15_000);

// Helper for building rule filter cache key
function buildRulesFilterKey(filters?: {
  mechanism?: string;
  ruleset_id?: string;
  category?: RulesetCategory | string;
  keyword?: string;
}): string {
  if (!filters) return "__default__";
  return `${filters.mechanism || ""}_${filters.ruleset_id || ""}_${filters.category || ""}_${filters.keyword || ""}`;
}

export const projectsApi = {
  getCachedList(): ProjectListResponse | null {
    const list = _projectsStore.getCachedList("__default__");
    if (!list) return null;
    return {
      projects: list,
      total: list.length,
    };
  },

  subscribe(listener: (projects: Project[]) => void): Unsubscribe {
    return _projectsStore.subscribe(listener);
  },

  async list(options: SWROptions = {}): Promise<ProjectListResponse> {
    const list = await _projectsStore.fetchList(
      "__default__",
      async () => {
        const res = await fetch(`${API_BASE}/projects`);
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
        const res = await fetch(`${API_BASE}/projects/${id}`);
        return handleResponse<Project>(res);
      },
      options,
    );
  },

  async getInputs(id: number): Promise<any[]> {
    const res = await fetch(`${API_BASE}/projects/${id}/inputs`);
    return handleResponse<any[]>(res);
  },

  async options(options: SWROptions = {}): Promise<ProjectOptions> {
    return _projectOptionsStore.execute(
      "__options__",
      async () => {
        const res = await fetch(`${API_BASE}/projects/options`);
        return handleResponse<ProjectOptions>(res);
      },
      options,
    );
  },

  async create(payload: ProjectCreatePayload): Promise<Project> {
    const res = await fetch(`${API_BASE}/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const created = await handleResponse<Project>(res);
    _projectsStore.addOrUpdate(created);
    return created;
  },

  async uploadWithIfc(formData: FormData): Promise<Project> {
    const res = await fetch(`${API_BASE}/projects/upload`, {
      method: "POST",
      body: formData,
    });
    const created = await handleResponse<Project>(res);
    _projectsStore.addOrUpdate(created);
    return created;
  },

  async update(id: number, payload: ProjectUpdatePayload): Promise<Project> {
    const res = await fetch(`${API_BASE}/projects/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const updated = await handleResponse<Project>(res);
    _projectsStore.addOrUpdate(updated);
    return updated;
  },

  async delete(id: number): Promise<void> {
    const res = await fetch(`${API_BASE}/projects/${id}`, {
      method: "DELETE",
    });
    await handleResponse<void>(res);
    _projectsStore.remove(id);
  },

  async bulkDelete(ids: number[]): Promise<ProjectBulkActionResponse> {
    const res = await fetch(`${API_BASE}/projects/bulk-delete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_ids: ids }),
    });
    const result = await handleResponse<ProjectBulkActionResponse>(res);
    ids.forEach((id) => _projectsStore.remove(id));
    return result;
  },

  async bulkUpdate(payload: ProjectBulkUpdatePayload): Promise<ProjectBulkActionResponse> {
    const res = await fetch(`${API_BASE}/projects/bulk-update`, {
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
    return `${API_BASE}/projects/${id}/ifc`;
  },

  /** URL for one specific attached model, rather than the project's primary. */
  getIfcFileUrl(projectId: number, fileId: number): string {
    return `${API_BASE}/projects/${projectId}/files/${fileId}/ifc`;
  },

  async listIfcFiles(projectId: number): Promise<ProjectIfcFile[]> {
    const res = await fetch(`${API_BASE}/projects/${projectId}/files`);
    return handleResponse<ProjectIfcFile[]>(res);
  },

  /**
   * Attach IFC models to an existing project.
   *
   * `roles` goes over the wire as one repeated form entry per file, not as a
   * JSON blob: the endpoint declares `roles: list[str] = Form()`, which FastAPI
   * fills from repeated entries. A single JSON string would arrive as a
   * one-element list and be rejected for not matching the file count.
   */
  async uploadIfcFiles(
    projectId: number,
    files: File[],
    primaryIndex: number,
    roles: string[],
  ): Promise<ProjectIfcUploadResponse> {
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    form.append("primary_index", String(primaryIndex));
    roles.forEach((role) => form.append("roles", role));

    const res = await fetch(`${API_BASE}/projects/${projectId}/upload`, {
      method: "POST",
      body: form,
    });
    // The primary is mirrored onto projects.ifc_file_path server-side, so a
    // caller holding a project row fetched before this call should re-read it
    // with { forceRefresh: true } -- the cache cannot know the column moved.
    return handleResponse<ProjectIfcUploadResponse>(res);
  },
};

export const rulesApi = {
  getCachedList(filters?: {
    mechanism?: string;
    ruleset_id?: string;
    category?: RulesetCategory | string;
    keyword?: string;
  }): Rule[] | null {
    const key = buildRulesFilterKey(filters);
    const cached = _rulesStore.getCachedList(key);
    return cached || null;
  },

  getCachedFolders(category?: RulesetCategory | string): RuleFolder[] | null {
    const key = category || "__default__";
    const cached = _ruleFoldersStore.getCached(key);
    return cached || null;
  },

  subscribe(listener: (rules: Rule[]) => void): Unsubscribe {
    return _rulesStore.subscribe(listener);
  },

  async list(
    filters?: {
      mechanism?: string;
      ruleset_id?: string;
      category?: RulesetCategory | string;
      keyword?: string;
    },
    options: SWROptions = {},
  ): Promise<Rule[]> {
    const key = buildRulesFilterKey(filters);
    return _rulesStore.fetchList(
      key,
      async () => {
        const params = new URLSearchParams();
        if (filters?.mechanism) params.set("mechanism", filters.mechanism);
        if (filters?.ruleset_id) params.set("ruleset_id", filters.ruleset_id);
        if (filters?.category) params.set("category", filters.category);
        if (filters?.keyword) params.set("keyword", filters.keyword);
        const query = params.toString() ? `?${params.toString()}` : "";
        const res = await fetch(`${API_BASE}/rules${query}`);
        return handleResponse<Rule[]>(res);
      },
      options,
    );
  },

  async folders(
    category?: RulesetCategory | string,
    options: SWROptions = {},
  ): Promise<RuleFolder[]> {
    const key = category || "__default__";
    const query = category ? `?category=${encodeURIComponent(category)}` : "";
    return _ruleFoldersStore.execute(
      key,
      async () => {
        const res = await fetch(`${API_BASE}/rules/folders${query}`);
        return handleResponse<RuleFolder[]>(res);
      },
      options,
    );
  },

  async createFolder(payload: RuleFolderCreatePayload): Promise<RuleFolder> {
    const res = await fetch(`${API_BASE}/rules/folders`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const created = await handleResponse<RuleFolder>(res);
    _ruleFoldersStore.clear();
    return created;
  },

  async updateFolder(rulesetId: string, payload: RuleFolderUpdatePayload): Promise<RuleFolder> {
    const res = await fetch(`${API_BASE}/rules/folders/${encodeURIComponent(rulesetId)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const updated = await handleResponse<RuleFolder>(res);
    _ruleFoldersStore.clear();
    return updated;
  },

  async deleteFolder(
    rulesetId: string,
  ): Promise<{ success: boolean; ruleset_id: string; deleted_rules: number }> {
    const res = await fetch(`${API_BASE}/rules/folders/${encodeURIComponent(rulesetId)}`, {
      method: "DELETE",
    });
    const result = await handleResponse<{
      success: boolean;
      ruleset_id: string;
      deleted_rules: number;
    }>(res);
    _ruleFoldersStore.clear();
    _rulesStore.clear();
    return result;
  },

  async bulkUpdateFolders(
    payload: RuleFolderBulkUpdatePayload,
  ): Promise<RuleFolderBulkActionResponse> {
    const res = await fetch(`${API_BASE}/rules/folders/bulk-update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await handleResponse<RuleFolderBulkActionResponse>(res);
    _ruleFoldersStore.clear();
    _rulesStore.clear();
    return result;
  },

  async bulkDeleteFolders(rulesetIds: string[]): Promise<RuleFolderBulkActionResponse> {
    const res = await fetch(`${API_BASE}/rules/folders/bulk-delete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ruleset_ids: rulesetIds }),
    });
    const result = await handleResponse<RuleFolderBulkActionResponse>(res);
    _ruleFoldersStore.clear();
    _rulesStore.clear();
    return result;
  },

  async getFolder(rulesetId: string): Promise<RuleFolder> {
    const res = await fetch(`${API_BASE}/rules/folders/${encodeURIComponent(rulesetId)}`);
    return handleResponse<RuleFolder>(res);
  },

  async get(id: number, options: SWROptions = {}): Promise<Rule> {
    return _rulesStore.fetchItem(
      id,
      async () => {
        const res = await fetch(`${API_BASE}/rules/${id}`);
        return handleResponse<Rule>(res);
      },
      options,
    );
  },

  async create(payload: Partial<Rule>): Promise<Rule> {
    const res = await fetch(`${API_BASE}/rules`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const created = await handleResponse<Rule>(res);
    _rulesStore.addOrUpdate(created);
    _ruleFoldersStore.clear();
    return created;
  },

  async update(id: number, payload: Partial<Rule>): Promise<Rule> {
    const res = await fetch(`${API_BASE}/rules/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const updated = await handleResponse<Rule>(res);
    _rulesStore.addOrUpdate(updated);
    _ruleFoldersStore.clear();
    return updated;
  },

  async delete(id: number): Promise<void> {
    const res = await fetch(`${API_BASE}/rules/${id}`, {
      method: "DELETE",
    });
    await handleResponse<void>(res);
    _rulesStore.remove(id);
    _ruleFoldersStore.clear();
  },

  async bulkUpdate(payload: RuleBulkUpdatePayload): Promise<RuleBulkActionResponse> {
    const res = await fetch(`${API_BASE}/rules/bulk-update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await handleResponse<RuleBulkActionResponse>(res);
    _rulesStore.clear();
    _ruleFoldersStore.clear();
    return result;
  },

  async bulkDelete(ruleIds: number[]): Promise<RuleBulkActionResponse> {
    const res = await fetch(`${API_BASE}/rules/bulk-delete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rule_ids: ruleIds }),
    });
    const result = await handleResponse<RuleBulkActionResponse>(res);
    _rulesStore.clear();
    _ruleFoldersStore.clear();
    return result;
  },

  invalidateCache() {
    _rulesStore.clear();
    _ruleFoldersStore.clear();
  },

  getIdsExportUrl(rulesetId?: string): string {
    if (rulesetId) {
      return `${API_BASE}/rules/export-ids/${encodeURIComponent(rulesetId)}`;
    }
    return `${API_BASE}/rules/export-ids`;
  },

  async importIds(file: File, rulesetId: string): Promise<IdsImportResult> {
    const form = new FormData();
    form.append("file", file);
    form.append("ruleset_id", rulesetId);
    const res = await fetch(`${API_BASE}/rules/import-ids`, {
      method: "POST",
      body: form,
    });
    const result = await handleResponse<IdsImportResult>(res);
    _rulesStore.clear();
    _ruleFoldersStore.clear();
    return result;
  },

  async createSnapshot(payload: RuleSnapshotCreatePayload): Promise<RuleSnapshot> {
    const res = await fetch(`${API_BASE}/rules/snapshots`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<RuleSnapshot>(res);
  },

  async listSnapshots(): Promise<RuleSnapshot[]> {
    const res = await fetch(`${API_BASE}/rules/snapshots`);
    return handleResponse<RuleSnapshot[]>(res);
  },

  async deleteSnapshot(snapshotId: number): Promise<void> {
    const res = await fetch(`${API_BASE}/rules/snapshots/${snapshotId}`, {
      method: "DELETE",
    });
    if (!res.ok) {
      throw new Error(`Failed to delete snapshot ${snapshotId}`);
    }
  },

  getSnapshotPdfUrl(snapshotId: number): string {
    return `${API_BASE}/rules/snapshots/${snapshotId}/pdf`;
  },
};

function engineQuery(engines?: string[]): string {
  if (!engines) return "";
  if (engines.length === 0) return "&engines=";
  return engines.map((e) => `&engines=${encodeURIComponent(e)}`).join("");
}

/** True when a rejection is an aborted fetch rather than a real failure. */
export function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

export const analyzeApi = {
  async uploadIfc(
    projectId: number,
    file: File,
  ): Promise<{ success: boolean; filename: string; size_bytes?: number; sha256?: string }> {
    const form = new FormData();
    form.append("project_id", projectId.toString());
    form.append("ifc_file", file);

    const res = await fetch(`${API_BASE}/analyze/upload`, {
      method: "POST",
      body: form,
    });
    return handleResponse<{
      success: boolean;
      filename: string;
      size_bytes?: number;
      sha256?: string;
    }>(res);
  },

  /**
   * Trigger a compliance run.
   *
   * `signal` lets the caller abandon a run in flight — both for an explicit
   * Cancel and to discard a stale response when the user switches project
   * mid-request, which would otherwise land on top of the newer selection.
   */
  async run(
    projectId: number,
    slug: "corrosion" | "seismic" = "corrosion",
    background = false,
    useCache = true,
    engines?: string[],
    signal?: AbortSignal,
  ): Promise<AnalysisResult> {
    const res = await fetch(`${API_BASE}/analyze/run?background=${background}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_id: projectId,
        slug,
        use_cache: useCache,
        engines: engines ?? null,
      }),
      signal,
    });
    return handleResponse<AnalysisResult>(res);
  },

  async getResults(
    projectId: number,
    slug: "corrosion" | "seismic" = "corrosion",
    useCache = true,
    engines?: string[],
    signal?: AbortSignal,
  ): Promise<AnalysisResult> {
    const res = await fetch(
      `${API_BASE}/analyze/results/${projectId}/${slug}?use_cache=${useCache}${engineQuery(engines)}`,
      { signal },
    );
    return handleResponse<AnalysisResult>(res);
  },

  async getStatus(projectId: number): Promise<WorkflowStatus> {
    const res = await fetch(`${API_BASE}/analyze/status/${projectId}`);
    return handleResponse<WorkflowStatus>(res);
  },

  getExportUrl(
    projectId: number,
    slug: string,
    fmt: "bcf" | "csv" | "json",
    engines?: string[],
  ): string {
    return `${API_BASE}/analyze/export?project_id=${projectId}&slug=${slug}&fmt=${fmt}${engineQuery(engines)}`;
  },

  getBcfArtifactUrl(artifactId: number): string {
    return `${API_BASE}/analyze/bcf/artifacts/${artifactId}`;
  },

  getLatestBcfUrl(projectId: number): string {
    return `${API_BASE}/analyze/bcf/latest/${projectId}`;
  },

  async runArch(projectId: number, ruleFolder = ""): Promise<any> {
    const form = new FormData();
    form.append("project_id", projectId.toString());
    if (ruleFolder) form.append("rule_folder", ruleFolder);

    const res = await fetch(`${API_BASE}/analyze/arch`, {
      method: "POST",
      body: form,
    });
    return handleResponse<any>(res);
  },

  async listBcfArtifacts(): Promise<BcfArtifact[]> {
    const res = await fetch(`${API_BASE}/analyze/bcf/list`);
    return handleResponse<BcfArtifact[]>(res);
  },

  async deleteBcfArtifact(artifactId: number): Promise<void> {
    const res = await fetch(`${API_BASE}/analyze/bcf/artifacts/${artifactId}`, {
      method: "DELETE",
    });
    return handleResponse<void>(res);
  },
};

export const dashboardApi = {
  getCachedStats(): any | null {
    return _dashboardStatsStore.getCached("__stats__") || null;
  },

  async getStats(options: SWROptions = {}): Promise<any> {
    return _dashboardStatsStore.execute(
      "__stats__",
      async () => {
        const res = await fetch(`${API_BASE}/dashboard/stats`);
        return handleResponse<any>(res);
      },
      options,
    );
  },

  prefetchAll(): void {
    Promise.allSettled([
      projectsApi.list(),
      rulesApi.list(),
      rulesApi.folders(),
      documentsApi.list(),
      dashboardApi.getStats(),
    ]).catch(() => {});
  },

  invalidateCache() {
    _dashboardStatsStore.clear();
  },
};

export const documentsApi = {
  getCachedList(): DocumentItem[] | null {
    return _documentsStore.getCachedList("__default__") || null;
  },

  subscribe(listener: (docs: DocumentItem[]) => void): Unsubscribe {
    return _documentsStore.subscribe(listener);
  },

  async list(options: SWROptions = {}): Promise<DocumentItem[]> {
    return _documentsStore.fetchList(
      "__default__",
      async () => {
        const res = await fetch(`${API_BASE}/documents`);
        return handleResponse<DocumentItem[]>(res);
      },
      options,
    );
  },

  async get(id: number, options: SWROptions = {}): Promise<DocumentDetail> {
    return _documentDetailStore.execute(
      id,
      async () => {
        const res = await fetch(`${API_BASE}/documents/${id}`);
        return handleResponse<DocumentDetail>(res);
      },
      options,
    );
  },

  async upload(
    file: File,
    docType: string = "Specification",
    isoOptions?: {
      project_code?: string;
      originator?: string;
      suitability_code?: string;
      revision_code?: string;
      parser?: "auto" | "unstructured" | "light";
    },
  ): Promise<DocumentDetail> {
    const form = new FormData();
    form.append("file", file);
    form.append("doc_type", docType);
    if (isoOptions?.project_code) form.append("project_code", isoOptions.project_code);
    if (isoOptions?.originator) form.append("originator", isoOptions.originator);
    if (isoOptions?.suitability_code) form.append("suitability_code", isoOptions.suitability_code);
    if (isoOptions?.revision_code) form.append("revision_code", isoOptions.revision_code);
    if (isoOptions?.parser) form.append("parser", isoOptions.parser);
    const res = await fetch(`${API_BASE}/documents`, {
      method: "POST",
      body: form,
    });
    const created = await handleResponse<DocumentDetail>(res);
    _documentsStore.addOrUpdate({
      id: created.id,
      filename: created.filename,
      doc_type: created.doc_type || docType,
      file_path: created.file_path,
      upload_date: created.upload_date,
      extracted_text_preview: created.extracted_text?.slice(0, 200) || "",
      char_count: created.char_count ?? created.extracted_text?.length ?? 0,
      project_code: created.project_code,
      originator: created.originator,
      suitability_code: created.suitability_code,
      revision_code: created.revision_code,
      cde_state: created.cde_state,
    });
    _documentDetailStore.set(created.id, created);
    return created;
  },

  async update(id: number, payload: DocumentUpdatePayload): Promise<DocumentDetail> {
    const res = await fetch(`${API_BASE}/documents/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const updated = await handleResponse<DocumentDetail>(res);
    _documentsStore.addOrUpdate({
      id: updated.id,
      filename: updated.filename,
      doc_type: updated.doc_type || payload.doc_type,
      file_path: updated.file_path,
      upload_date: updated.upload_date,
      extracted_text_preview: updated.extracted_text?.slice(0, 200) || "",
      char_count: updated.char_count ?? updated.extracted_text?.length ?? 0,
    });
    _documentDetailStore.set(updated.id, updated);
    return updated;
  },

  async delete(id: number): Promise<void> {
    const res = await fetch(`${API_BASE}/documents/${id}`, {
      method: "DELETE",
    });
    await handleResponse<void>(res);
    _documentsStore.remove(id);
    _documentDetailStore.delete(id);
  },

  invalidateCache() {
    _documentsStore.clear();
    _documentDetailStore.clear();
  },
};

export const settingsApi = {
  async get(): Promise<any> {
    const res = await fetch(`${API_BASE}/settings`);
    return handleResponse<any>(res);
  },

  async update(settings: Record<string, string>): Promise<any> {
    const res = await fetch(`${API_BASE}/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ settings }),
    });
    return handleResponse<any>(res);
  },
};

export const lineageApi = {
  async getHistory(projectId: number): Promise<any[]> {
    const res = await fetch(`${API_BASE}/projects/${projectId}/enhancements`);
    return handleResponse<any[]>(res);
  },

  async enhance(projectId: number, token?: string): Promise<any> {
    const res = await fetch(`${API_BASE}/projects/${projectId}/enhance`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(token ? { token } : {}),
    });
    return handleResponse<any>(res);
  },
};

export const ruleExtractionApi = {
  async extract(
    file?: File,
    rawText?: string,
  ): Promise<{ rules: any[]; warnings: string[]; count: number }> {
    const form = new FormData();
    if (file) form.append("file", file);
    if (rawText) form.append("raw_text", rawText);

    const res = await fetch(`${API_BASE}/rules/extract`, {
      method: "POST",
      body: form,
    });
    return handleResponse<any>(res);
  },

  async bulkCreate(rules: any[]): Promise<any> {
    const res = await fetch(`${API_BASE}/rules/bulk`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(rules),
    });
    return handleResponse<any>(res);
  },

  async seed(): Promise<any> {
    const res = await fetch(`${API_BASE}/rules/seed`, {
      method: "POST",
    });
    return handleResponse<any>(res);
  },

  getIdsExportUrl(rulesetId: string): string {
    return `${API_BASE}/rules/export-ids/${rulesetId}`;
  },
};

export const revitSyncApi = {
  async sync(payload: any): Promise<any> {
    const res = await fetch(`${API_BASE}/analyze/revit-sync`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<any>(res);
  },
};

let _cachedReposList: GitHubRepo[] | null = null;
const _cachedStructureMap: Record<number, GitHubRepoStructure> = {};

export const githubReposApi = {
  async list(forceRefresh = false): Promise<GitHubRepo[]> {
    if (_cachedReposList && !forceRefresh) {
      fetch(`${API_BASE}/repositories`)
        .then((res) => handleResponse<GitHubRepo[]>(res))
        .then((data) => {
          _cachedReposList = data;
        })
        .catch(() => {});
      return _cachedReposList;
    }
    const res = await fetch(`${API_BASE}/repositories`);
    const data = await handleResponse<GitHubRepo[]>(res);
    _cachedReposList = data;
    return data;
  },

  async get(id: number): Promise<GitHubRepo> {
    const res = await fetch(`${API_BASE}/repositories/${id}`);
    return handleResponse<GitHubRepo>(res);
  },

  async create(payload: GitHubRepoCreatePayload): Promise<GitHubRepo> {
    const res = await fetch(`${API_BASE}/repositories`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const created = await handleResponse<GitHubRepo>(res);
    _cachedReposList = null;
    return created;
  },

  async update(id: number, payload: GitHubRepoUpdatePayload): Promise<GitHubRepo> {
    const res = await fetch(`${API_BASE}/repositories/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const updated = await handleResponse<GitHubRepo>(res);
    _cachedReposList = null;
    return updated;
  },

  async delete(id: number): Promise<void> {
    const res = await fetch(`${API_BASE}/repositories/${id}`, {
      method: "DELETE",
    });
    await handleResponse<void>(res);
    _cachedReposList = null;
    delete _cachedStructureMap[id];
  },

  async getStructure(id: number, forceRefresh = false): Promise<GitHubRepoStructure> {
    if (_cachedStructureMap[id] && !forceRefresh) {
      fetch(`${API_BASE}/repositories/${id}/structure`)
        .then((res) => handleResponse<GitHubRepoStructure>(res))
        .then((data) => {
          _cachedStructureMap[id] = data;
        })
        .catch(() => {});
      return _cachedStructureMap[id];
    }
    const res = await fetch(`${API_BASE}/repositories/${id}/structure`);
    const data = await handleResponse<GitHubRepoStructure>(res);
    _cachedStructureMap[id] = data;
    return data;
  },

  async importProject(repoId: number, payload: ProjectImportPayload): Promise<Project> {
    const res = await fetch(`${API_BASE}/repositories/${repoId}/import`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const created = await handleResponse<Project>(res);
    _projectsStore.addOrUpdate(created);
    return created;
  },
};

// =============================================================================
// buildingSMART OpenCDE API Client
// =============================================================================

export const cdeApi = {
  async getVersions(): Promise<CDEVersionsResponse> {
    const res = await fetch(`${API_BASE}/cde/versions`);
    return handleResponse<CDEVersionsResponse>(res);
  },

  async getUser(): Promise<CDEUserResponse> {
    const res = await fetch(`${API_BASE}/cde/v1/user`);
    return handleResponse<CDEUserResponse>(res);
  },

  async listDocuments(
    projectId: number,
    params?: { filter?: string; top?: number; skip?: number; orderby?: string },
  ): Promise<CDEDocumentItem[]> {
    const query = new URLSearchParams();
    if (params?.filter) query.set("$filter", params.filter);
    if (params?.top) query.set("$top", String(params.top));
    if (params?.skip) query.set("$skip", String(params.skip));
    if (params?.orderby) query.set("$orderby", params.orderby);
    const qs = query.toString() ? `?${query.toString()}` : "";
    const res = await fetch(`${API_BASE}/cde/v1/projects/${projectId}/documents${qs}`);
    return handleResponse<CDEDocumentItem[]>(res);
  },

  async syncDocuments(payload: CDESyncRequest): Promise<CDESyncResponse> {
    const res = await fetch(`${API_BASE}/cde/v1/projects/${payload.project_id}/documents/sync`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<CDESyncResponse>(res);
  },
};

// =============================================================================
// buildingSMART BCF REST API Client (v2.1)
// =============================================================================

export const bcfApi = {
  async listProjects(): Promise<BCFProjectResponse[]> {
    const res = await fetch(`${API_BASE}/bcf/v2.1/projects`);
    return handleResponse<BCFProjectResponse[]>(res);
  },

  async getProject(projectId: string | number): Promise<BCFProjectResponse> {
    const res = await fetch(`${API_BASE}/bcf/v2.1/projects/${projectId}`);
    return handleResponse<BCFProjectResponse>(res);
  },

  async listTopics(
    projectId: string | number,
    filters?: {
      topic_status?: string;
      topic_type?: string;
      priority?: string;
      assigned_to?: string;
      cde_state?: string;
    },
  ): Promise<BCFTopicResponse[]> {
    const query = new URLSearchParams();
    if (filters?.topic_status) query.set("topic_status", filters.topic_status);
    if (filters?.topic_type) query.set("topic_type", filters.topic_type);
    if (filters?.priority) query.set("priority", filters.priority);
    if (filters?.assigned_to) query.set("assigned_to", filters.assigned_to);
    if (filters?.cde_state) query.set("cde_state", filters.cde_state);
    const qs = query.toString() ? `?${query.toString()}` : "";
    const res = await fetch(`${API_BASE}/bcf/v2.1/projects/${projectId}/topics${qs}`);
    return handleResponse<BCFTopicResponse[]>(res);
  },

  async getTopic(projectId: string | number, topicGuid: string): Promise<BCFTopicResponse> {
    const res = await fetch(`${API_BASE}/bcf/v2.1/projects/${projectId}/topics/${topicGuid}`);
    return handleResponse<BCFTopicResponse>(res);
  },

  async createTopic(
    projectId: string | number,
    payload: BCFTopicCreatePayload,
  ): Promise<BCFTopicResponse> {
    const res = await fetch(`${API_BASE}/bcf/v2.1/projects/${projectId}/topics`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<BCFTopicResponse>(res);
  },

  async updateTopic(
    projectId: string | number,
    topicGuid: string,
    payload: BCFTopicUpdatePayload,
  ): Promise<BCFTopicResponse> {
    const res = await fetch(`${API_BASE}/bcf/v2.1/projects/${projectId}/topics/${topicGuid}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<BCFTopicResponse>(res);
  },

  async listComments(projectId: string | number, topicGuid: string): Promise<BCFCommentResponse[]> {
    const res = await fetch(
      `${API_BASE}/bcf/v2.1/projects/${projectId}/topics/${topicGuid}/comments`,
    );
    return handleResponse<BCFCommentResponse[]>(res);
  },

  async createComment(
    projectId: string | number,
    topicGuid: string,
    payload: BCFCommentCreatePayload,
  ): Promise<BCFCommentResponse> {
    const res = await fetch(
      `${API_BASE}/bcf/v2.1/projects/${projectId}/topics/${topicGuid}/comments`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    );
    return handleResponse<BCFCommentResponse>(res);
  },

  async listViewpoints(
    projectId: string | number,
    topicGuid: string,
  ): Promise<BCFViewpointResponse[]> {
    const res = await fetch(
      `${API_BASE}/bcf/v2.1/projects/${projectId}/topics/${topicGuid}/viewpoints`,
    );
    return handleResponse<BCFViewpointResponse[]>(res);
  },

  async createViewpoint(
    projectId: string | number,
    topicGuid: string,
    payload: BCFViewpointCreatePayload,
  ): Promise<BCFViewpointResponse> {
    const res = await fetch(
      `${API_BASE}/bcf/v2.1/projects/${projectId}/topics/${topicGuid}/viewpoints`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    );
    return handleResponse<BCFViewpointResponse>(res);
  },

  async deleteTopic(projectId: string | number, topicGuid: string): Promise<void> {
    const res = await fetch(`${API_BASE}/bcf/v2.1/projects/${projectId}/topics/${topicGuid}`, {
      method: "DELETE",
    });
    return handleResponse<void>(res);
  },

  async bulkDeleteTopics(projectId: string | number, topicGuids: string[]): Promise<void> {
    await Promise.all(topicGuids.map((guid) => this.deleteTopic(projectId, guid)));
  },
};

export const namingConfigApi = {
  /** Fetch the conventions, tokens, code library and CDE statuses. */
  async catalog(): Promise<NamingCatalog> {
    const res = await fetch(`${API_BASE}/naming-config/catalog`);
    return handleResponse<NamingCatalog>(res);
  },

  /** Fetch one project's naming setup; unconfigured projects report defaults. */
  async get(projectId: number): Promise<NamingConfig> {
    const res = await fetch(`${API_BASE}/naming-config/projects/${projectId}`);
    return handleResponse<NamingConfig>(res);
  },

  /** Write one project's naming setup. Absent fields keep their stored value. */
  async save(projectId: number, payload: NamingConfigPayload): Promise<NamingConfig> {
    const res = await fetch(`${API_BASE}/naming-config/projects/${projectId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<NamingConfig>(res);
  },

  /** Drop a project's saved setup, returning the defaults it falls back to. */
  async reset(projectId: number): Promise<NamingConfig> {
    const res = await fetch(`${API_BASE}/naming-config/projects/${projectId}`, {
      method: "DELETE",
    });
    return handleResponse<NamingConfig>(res);
  },

  /**
   * Render a sample name from an unsaved configuration.
   *
   * Rendering is a round trip rather than a local string substitution so the
   * name the wizard previews and the name an export writes come from one place.
   */
  async preview(
    config: NamingConfigPayload,
    overrides: Record<string, string> = {},
  ): Promise<NamingPreview> {
    const res = await fetch(`${API_BASE}/naming-config/preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ config, overrides }),
    });
    return handleResponse<NamingPreview>(res);
  },
};

/**
 * buildingSMART Data Dictionary (bSDD) client.
 *
 * Backs project-settings classification-standard selection and the rule
 * builder's element/property autocomplete. Search results are inherently
 * transient (typed by the user, one query at a time), so unlike the other
 * clients in this file this one does no caching -- each call is a plain
 * round trip.
 */
export const bsddApi = {
  /** Classification standards a project can be coded against (Uniclass, OmniClass, IFC, ...). */
  async listDictionaries(): Promise<BSDDDictionaryItem[]> {
    const res = await fetch(`${API_BASE}/bsdd/dictionaries`);
    return handleResponse<BSDDDictionaryItem[]>(res);
  },

  /** Search bSDD classes (element/classification codes) matching free text. */
  async searchClasses(query: string, dictionaryUri?: string): Promise<BSDDClassSearchResponse> {
    const params = new URLSearchParams({ q: query });
    if (dictionaryUri) params.set('dictionary_uri', dictionaryUri);
    const res = await fetch(`${API_BASE}/bsdd/classes/search?${params.toString()}`);
    return handleResponse<BSDDClassSearchResponse>(res);
  },

  /** Search bSDD properties (property set + name pairs) matching free text. */
  async searchProperties(query: string, dictionaryUri?: string): Promise<BSDDPropertySearchResponse> {
    const params = new URLSearchParams({ q: query });
    if (dictionaryUri) params.set('dictionary_uri', dictionaryUri);
    const res = await fetch(`${API_BASE}/bsdd/properties/search?${params.toString()}`);
    return handleResponse<BSDDPropertySearchResponse>(res);
  },

  /** Fetch one bSDD class definition with its standardized properties. */
  async getClass(classCode: string, dictionaryUri?: string): Promise<BSDDClassItem> {
    const params = dictionaryUri ? `?dictionary_uri=${encodeURIComponent(dictionaryUri)}` : '';
    const res = await fetch(`${API_BASE}/bsdd/classes/${encodeURIComponent(classCode)}${params}`);
    return handleResponse<BSDDClassItem>(res);
  },
};
