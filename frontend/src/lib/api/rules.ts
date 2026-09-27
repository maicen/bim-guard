import type {
  IdsImportResult,
  Rule,
  RuleBulkActionResponse,
  RuleBulkUpdatePayload,
  RuleFolder,
  RuleFolderBulkActionResponse,
  RuleFolderBulkUpdatePayload,
  RuleFolderCreatePayload,
  RuleFolderUpdatePayload,
  RuleDraftConflictDetectionRequest,
  RuleDraftConflictDetectionResponse,
  RuleDraftReviewRequest,
  RuleExtractionDraft,
  RuleExtractionDraftListResponse,
  RulePromotionResponse,
  RuleReliability,
  RuleReliabilityRequest,
  RuleExtractionProgressResponse,
  RulesetCategory,
  RuleSnapshot,
  RuleSnapshotCreatePayload,
  RuleShaclShapeResponse,
  RulesetSourceMapResponse,
  RuleSourceResponse,
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

const _rulesStore = new EntityCacheStore<Rule, number>((r) => r.id, 60_000, 60_000);
const _ruleFoldersStore = new SWRStore<string, RuleFolder[]>(new InMemoryCache(), 60_000);

// Helper for building rule filter cache key
export function buildRulesFilterKey(filters?: {
  mechanism?: string;
  ruleset_id?: string;
  category?: RulesetCategory | string;
  keyword?: string;
}): string {
  if (!filters) return "__default__";
  return `${filters.mechanism || ""}_${filters.ruleset_id || ""}_${filters.category || ""}_${filters.keyword || ""}`;
}

export const rulesApi = {
  /** Grade how reliably a rule can be checked against an IFC model, before it is saved. */
  async assessReliability(payload: RuleReliabilityRequest): Promise<RuleReliability | null> {
    const res = await apiFetch(`${API_BASE}/rules/assess-reliability`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await handleResponse<{ reliability: RuleReliability | null }>(res);
    return body.reliability ?? null;
  },

  getCachedList(filters?: {
    mechanism?: string;
    ruleset_id?: string;
    category?: RulesetCategory | string;
    keyword?: string;
    organization_id?: number | null;
  }): Rule[] | null {
    const effectiveOrg = filters?.organization_id !== undefined ? filters.organization_id : getActiveOrgId();
    const key = `${buildRulesFilterKey(filters)}_org:${effectiveOrg ?? "all"}`;
    const cached = _rulesStore.getCachedList(key) || _rulesStore.getCachedList(buildRulesFilterKey(filters));
    return cached || null;
  },

  getCachedFolders(category?: RulesetCategory | string, orgId?: number | null): RuleFolder[] | null {
    const effectiveOrg = orgId !== undefined ? orgId : getActiveOrgId();
    const key = `org:${effectiveOrg ?? "all"}:${category || "__default__"}`;
    const cached = _ruleFoldersStore.getCached(key) || _ruleFoldersStore.getCached(category || "__default__");
    return cached || null;
  },

  subscribe(listener: (rules: Rule[]) => void): Unsubscribe {
    return _rulesStore.subscribe(listener);
  },

  clearCache(): void {
    _rulesStore.clear();
    _ruleFoldersStore.clear();
  },

  async list(
    filters?: {
      mechanism?: string;
      ruleset_id?: string;
      category?: RulesetCategory | string;
      keyword?: string;
      organization_id?: number | null;
    },
    options: SWROptions = {},
  ): Promise<Rule[]> {
    const effectiveOrg = filters?.organization_id !== undefined ? filters.organization_id : getActiveOrgId();
    const key = `${buildRulesFilterKey(filters)}_org:${effectiveOrg ?? "all"}`;
    return _rulesStore.fetchList(
      key,
      async () => {
        const params = new URLSearchParams();
        if (filters?.mechanism) params.set("mechanism", filters.mechanism);
        if (filters?.ruleset_id) params.set("ruleset_id", filters.ruleset_id);
        if (filters?.category) params.set("category", filters.category);
        if (filters?.keyword) params.set("keyword", filters.keyword);
        if (effectiveOrg) params.set("organization_id", String(effectiveOrg));
        const query = params.toString() ? `?${params.toString()}` : "";
        const res = await apiFetch(`${API_BASE}/rules${query}`);
        return handleResponse<Rule[]>(res);
      },
      options,
    );
  },

  async folders(
    category?: RulesetCategory | string,
    options: SWROptions & { organization_id?: number | null } = {},
  ): Promise<RuleFolder[]> {
    const effectiveOrg = options.organization_id !== undefined ? options.organization_id : getActiveOrgId();
    const key = `org:${effectiveOrg ?? "all"}:${category || "__default__"}`;
    return _ruleFoldersStore.execute(
      key,
      async () => {
        const params = new URLSearchParams();
        if (category) params.set("category", category);
        if (effectiveOrg) params.set("organization_id", String(effectiveOrg));
        const query = params.toString() ? `?${params.toString()}` : "";
        const res = await apiFetch(`${API_BASE}/rules/folders${query}`);
        return handleResponse<RuleFolder[]>(res);
      },
      options,
    );
  },

  async createFolder(payload: RuleFolderCreatePayload): Promise<RuleFolder> {
    const res = await apiFetch(`${API_BASE}/rules/folders`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const created = await handleResponse<RuleFolder>(res);
    _ruleFoldersStore.clear();
    return created;
  },

  async updateFolder(rulesetId: string, payload: RuleFolderUpdatePayload): Promise<RuleFolder> {
    const res = await apiFetch(`${API_BASE}/rules/folders/${encodeURIComponent(rulesetId)}`, {
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
    const res = await apiFetch(`${API_BASE}/rules/folders/${encodeURIComponent(rulesetId)}`, {
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
    const res = await apiFetch(`${API_BASE}/rules/folders/bulk-update`, {
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
    const res = await apiFetch(`${API_BASE}/rules/folders/bulk-delete`, {
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
    const res = await apiFetch(`${API_BASE}/rules/folders/${encodeURIComponent(rulesetId)}`);
    return handleResponse<RuleFolder>(res);
  },

  async get(id: number, options: SWROptions = {}): Promise<Rule> {
    return _rulesStore.fetchItem(
      id,
      async () => {
        const res = await apiFetch(`${API_BASE}/rules/${id}`);
        return handleResponse<Rule>(res);
      },
      options,
    );
  },

  async getSource(id: number): Promise<RuleSourceResponse> {
    const res = await apiFetch(`${API_BASE}/rules/${id}/source`);
    return handleResponse<RuleSourceResponse>(res);
  },

  async getShaclShape(id: number): Promise<RuleShaclShapeResponse> {
    const res = await apiFetch(`${API_BASE}/rules/${id}/shacl-shape`);
    return handleResponse<RuleShaclShapeResponse>(res);
  },

  async create(payload: Partial<Rule>): Promise<Rule> {
    const res = await apiFetch(`${API_BASE}/rules`, {
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
    const res = await apiFetch(`${API_BASE}/rules/${id}`, {
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
    const res = await apiFetch(`${API_BASE}/rules/${id}`, {
      method: "DELETE",
    });
    await handleResponse<void>(res);
    _rulesStore.remove(id);
    _ruleFoldersStore.clear();
  },

  async bulkUpdate(payload: RuleBulkUpdatePayload): Promise<RuleBulkActionResponse> {
    const res = await apiFetch(`${API_BASE}/rules/bulk-update`, {
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
    const res = await apiFetch(`${API_BASE}/rules/bulk-delete`, {
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
    const url = rulesetId
      ? `${API_BASE}/rules/export-ids/${encodeURIComponent(rulesetId)}`
      : `${API_BASE}/rules/export-ids`;
    return withAuthToken(url);
  },

  getJsonExportUrl(rulesetId?: string): string {
    const url = rulesetId
      ? `${API_BASE}/rules/export-json/${encodeURIComponent(rulesetId)}`
      : `${API_BASE}/rules/export-json`;
    return withAuthToken(url);
  },

  async getRulesetSourceMap(rulesetId: string): Promise<RulesetSourceMapResponse> {
    const res = await apiFetch(`${API_BASE}/rules/rulesets/${encodeURIComponent(rulesetId)}/source-map`);
    return handleResponse<RulesetSourceMapResponse>(res);
  },

  async importIds(file: File, rulesetId: string): Promise<IdsImportResult> {
    const form = new FormData();
    form.append("file", file);
    form.append("ruleset_id", rulesetId);
    const res = await apiFetch(`${API_BASE}/rules/import-ids`, {
      method: "POST",
      body: form,
    });
    const result = await handleResponse<IdsImportResult>(res);
    _rulesStore.clear();
    _ruleFoldersStore.clear();
    return result;
  },

  async importJson(file: File, rulesetId: string): Promise<IdsImportResult> {
    const form = new FormData();
    form.append("file", file);
    form.append("ruleset_id", rulesetId);
    const res = await apiFetch(`${API_BASE}/rules/import-json`, {
      method: "POST",
      body: form,
    });
    const result = await handleResponse<IdsImportResult>(res);
    _rulesStore.clear();
    _ruleFoldersStore.clear();
    return result;
  },

  async createSnapshot(payload: RuleSnapshotCreatePayload): Promise<RuleSnapshot> {
    const res = await apiFetch(`${API_BASE}/rules/snapshots`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<RuleSnapshot>(res);
  },

  async listSnapshots(): Promise<RuleSnapshot[]> {
    const res = await apiFetch(`${API_BASE}/rules/snapshots`);
    return handleResponse<RuleSnapshot[]>(res);
  },

  async deleteSnapshot(snapshotId: number): Promise<void> {
    const res = await apiFetch(`${API_BASE}/rules/snapshots/${snapshotId}`, {
      method: "DELETE",
    });
    if (!res.ok) {
      throw new Error(`Failed to delete snapshot ${snapshotId}`);
    }
  },

  getSnapshotPdfUrl(snapshotId: number): string {
    return withAuthToken(`${API_BASE}/rules/snapshots/${snapshotId}/pdf`);
  },
};

export const lineageApi = {
  async getHistory(projectId: number): Promise<any[]> {
    const res = await apiFetch(`${API_BASE}/projects/${projectId}/enhancements`);
    return handleResponse<any[]>(res);
  },

  async enhance(projectId: number, token?: string): Promise<any> {
    const res = await apiFetch(`${API_BASE}/projects/${projectId}/enhance`, {
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
    model?: string,
  ): Promise<{ rules: any[]; warnings: string[]; count: number }> {
    const form = new FormData();
    if (file) form.append("file", file);
    if (rawText) form.append("raw_text", rawText);
    if (model) form.append("model", model);
    // Without the active organization the server can't find its saved LLM provider key.
    const orgId = getActiveOrgId();
    if (orgId) form.append("organization_id", String(orgId));

    const res = await apiFetch(`${API_BASE}/rules/extract`, {
      method: "POST",
      body: form,
    });
    return handleResponse<any>(res);
  },

  /**
   * Ingest a document and generate persisted, reviewable rule drafts
   * (rule_extraction_drafts). `text`, when given, scopes extraction to a
   * caller-chosen subset of the document (e.g. picked sections) instead of
   * its full extracted text.
   */
  async extractDrafts(
    documentId: number,
    model?: string,
    text?: string,
    organizationId?: number | null,
  ): Promise<RuleExtractionDraftListResponse> {
    // Documents carry no organization, so the server can't tell whose LLM
    // provider key to use unless we say which organization is active.
    const effectiveOrg = organizationId !== undefined ? organizationId : getActiveOrgId();
    const params = new URLSearchParams();
    if (model) params.set("model", model);
    if (effectiveOrg) params.set("organization_id", String(effectiveOrg));
    const query = params.toString() ? `?${params.toString()}` : "";
    const res = await apiFetch(`${API_BASE}/documents/${documentId}/rules/extract-drafts${query}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(text ? { text } : {}),
    });
    return handleResponse<RuleExtractionDraftListResponse>(res);
  },

  async listDrafts(documentId: number): Promise<RuleExtractionDraftListResponse> {
    const res = await apiFetch(`${API_BASE}/documents/${documentId}/rules/drafts`);
    return handleResponse<RuleExtractionDraftListResponse>(res);
  },

  async detectConflicts(
    payload: RuleDraftConflictDetectionRequest = {},
  ): Promise<RuleDraftConflictDetectionResponse> {
    const res = await apiFetch(`${API_BASE}/rules/drafts/detect-conflicts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<RuleDraftConflictDetectionResponse>(res);
  },

  async reviewDraft(draftId: number, payload: RuleDraftReviewRequest): Promise<RuleExtractionDraft> {
    const res = await apiFetch(`${API_BASE}/rules/drafts/${draftId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<RuleExtractionDraft>(res);
  },

  async promoteDraft(draftId: number): Promise<RulePromotionResponse> {
    const res = await apiFetch(`${API_BASE}/rules/drafts/${draftId}/promote`, {
      method: "POST",
    });
    const result = await handleResponse<RulePromotionResponse>(res);
    _ruleFoldersStore.clear();
    return result;
  },

  getIdsPreviewUrl(documentId: number): string {
    return withAuthToken(`${API_BASE}/documents/${documentId}/rules/drafts/ids-preview`);
  },

  /**
   * Fetch the IDS XML a document's current extraction drafts would produce.
   *
   * A plain `<a href={getIdsPreviewUrl(...)}>` link can't carry the bearer
   * token this API requires, so this goes through apiFetch (which does) and
   * returns the XML text for the caller to Blob-download instead.
   */
  async previewDraftsAsIds(documentId: number): Promise<string> {
    const res = await apiFetch(`${API_BASE}/documents/${documentId}/rules/drafts/ids-preview`);
    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      throw new Error(detail || `Failed to generate IDS preview (${res.status}).`);
    }
    return res.text();
  },

  /** Resolve a draft's source document/page for the document-viewer modal. */
  async getDraftSource(draftId: number): Promise<RuleSourceResponse> {
    const res = await apiFetch(`${API_BASE}/rules/drafts/${draftId}/source`);
    return handleResponse<RuleSourceResponse>(res);
  },

  /** Correct which document element a draft is linked to (e.g. the LLM mis-localized it). */
  async relinkDraftSource(draftId: number, elementId: string): Promise<RuleExtractionDraft> {
    const res = await apiFetch(`${API_BASE}/rules/drafts/${draftId}/source-element`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ element_id: elementId }),
    });
    return handleResponse<RuleExtractionDraft>(res);
  },

  /** Poll progress of an in-flight or recent document rule-draft extraction. */
  async getExtractionProgress(documentId: number): Promise<RuleExtractionProgressResponse> {
    const res = await apiFetch(`${API_BASE}/documents/${documentId}/rules/extract-progress`);
    return handleResponse<RuleExtractionProgressResponse>(res);
  },

  async bulkCreate(rules: any[]): Promise<any> {
    const res = await apiFetch(`${API_BASE}/rules/bulk`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(rules),
    });
    const result = await handleResponse<any>(res);
    // A bulk save can implicitly create a new rule folder (RuleService._ensure_folder
    // server-side) for a ruleset_id that didn't exist yet -- clear the cached folder
    // list so it shows up on the next `rulesApi.folders()` call instead of waiting
    // out the SWR TTL.
    _ruleFoldersStore.clear();
    return result;
  },

  async seed(): Promise<any> {
    const res = await apiFetch(`${API_BASE}/rules/seed`, {
      method: "POST",
    });
    return handleResponse<any>(res);
  },

  getIdsExportUrl(rulesetId: string): string {
    return withAuthToken(`${API_BASE}/rules/export-ids/${encodeURIComponent(rulesetId)}`);
  },
};
