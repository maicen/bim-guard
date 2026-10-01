import type {
  DocumentDetail,
  DocumentItem,
  DocumentElementBboxesResponse,
  DraftSourceMapResponse,
  DocumentSectionsResponse,
  DocumentSectionTreeResponse,
  SectionGraphResponse,
  DocumentUpdatePayload,
  RuleSourceMapResponse,
  GoogleDriveImportPayload,
  GoogleDriveImportResponse,
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

const _documentsStore = new EntityCacheStore<DocumentItem, number>((d) => d.id, 60_000, 60_000);
const _documentDetailStore = new SWRStore<number, DocumentDetail>(new InMemoryCache(), 60_000);

export const documentsApi = {
  getCachedList(orgId?: number | null): DocumentItem[] | null {
    const effectiveOrg = orgId !== undefined ? orgId : getActiveOrgId();
    const key = `org:${effectiveOrg ?? "all"}`;
    return _documentsStore.getCachedList(key) || _documentsStore.getCachedList("__default__") || null;
  },

  subscribe(listener: (docs: DocumentItem[]) => void): Unsubscribe {
    return _documentsStore.subscribe(listener);
  },

  clearCache(): void {
    _documentsStore.clear();
    _documentDetailStore.clear();
  },

  async list(options: SWROptions & { organization_id?: number | null } = {}): Promise<DocumentItem[]> {
    const effectiveOrg = options.organization_id !== undefined ? options.organization_id : getActiveOrgId();
    const key = `org:${effectiveOrg ?? "all"}`;
    return _documentsStore.fetchList(
      key,
      async () => {
        const query = effectiveOrg ? `?organization_id=${effectiveOrg}` : "";
        const res = await apiFetch(`${API_BASE}/documents${query}`);
        return handleResponse<DocumentItem[]>(res);
      },
      options,
    );
  },

  async get(id: number, options: SWROptions = {}): Promise<DocumentDetail> {
    return _documentDetailStore.execute(
      id,
      async () => {
        const res = await apiFetch(`${API_BASE}/documents/${id}`);
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
      parser?: "auto";
      engine_instance?: string;
      generate_doclang?: boolean;
      organization_id?: number | null;
      start_page?: number | null;
      end_page?: number | null;
      onUploadProgress?: (percent: number) => void;
    },
    signal?: AbortSignal,
  ): Promise<DocumentDetail> {
    const effectiveOrg = isoOptions?.organization_id !== undefined ? isoOptions.organization_id : getActiveOrgId();

    // 1. Get presigned URL
    const urlRes = await apiFetch(`${API_BASE}/documents/upload-url`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_name: file.name, size_bytes: file.size, content_type: file.type || "application/octet-stream" }),
      signal,
    });
    const { signed_url, storage_reference, token } = await handleResponse<any>(urlRes);

    // 2. Direct upload to Supabase via XHR for progress
    await new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("PUT", signed_url);
      if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
      
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && isoOptions?.onUploadProgress) {
          const percent = Math.round((e.loaded / e.total) * 100);
          isoOptions.onUploadProgress(percent);
        }
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve();
        } else {
          reject(new Error(`Storage upload failed: ${xhr.statusText}`));
        }
      };
      xhr.onerror = () => reject(new Error("Storage network error"));
      
      if (signal) {
        signal.addEventListener("abort", () => {
          xhr.abort();
          reject(new DOMException("Aborted", "AbortError"));
        });
      }
      xhr.send(file);
    });

    // 3. Confirm upload
    const payload: Record<string, any> = {
      storage_reference,
      file_name: file.name,
      doc_type: docType,
    };
    if (effectiveOrg) payload.organization_id = effectiveOrg;
    if (isoOptions?.project_code) payload.project_code = isoOptions.project_code;
    if (isoOptions?.originator) payload.originator = isoOptions.originator;
    if (isoOptions?.suitability_code) payload.suitability_code = isoOptions.suitability_code;
    if (isoOptions?.revision_code) payload.revision_code = isoOptions.revision_code;
    if (isoOptions?.parser) payload.parser = isoOptions.parser;
    if (isoOptions?.engine_instance) payload.engine_instance = isoOptions.engine_instance;
    if (isoOptions?.generate_doclang !== undefined) payload.generate_doclang = isoOptions.generate_doclang;
    if (isoOptions?.start_page != null) payload.start_page = isoOptions.start_page;
    if (isoOptions?.end_page != null) payload.end_page = isoOptions.end_page;

    const res = await apiFetch(`${API_BASE}/documents/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal,
    });
    const created = await handleResponse<DocumentDetail>(res);
    _documentsStore.addOrUpdate({
      id: created.id,
      filename: created.filename,
      doc_type: created.doc_type || docType,
      file_path: created.file_path,
      upload_date: created.upload_date,
      text_preview: created.text?.slice(0, 200) || "",
      char_count: created.char_count ?? created.text?.length ?? 0,
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
    const res = await apiFetch(`${API_BASE}/documents/${id}`, {
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
      text_preview: updated.text?.slice(0, 200) || "",
      char_count: updated.char_count ?? updated.text?.length ?? 0,
    });
    _documentDetailStore.set(updated.id, updated);
    return updated;
  },

  async generateDoclang(
    id: number,
    options?: {
      parser?: "auto";
      engine_instance?: string;
      start_page?: number;
      end_page?: number;
      signal?: AbortSignal;
    },
  ): Promise<DocumentDetail> {
    const res = await apiFetch(`${API_BASE}/documents/${id}/generate-doclang`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        parser: options?.parser || "auto",
        engine_instance: options?.engine_instance || "",
        start_page: options?.start_page,
        end_page: options?.end_page,
      }),
      signal: options?.signal,
    });
    const updated = await handleResponse<DocumentDetail>(res);
    _documentsStore.addOrUpdate({
      id: updated.id,
      filename: updated.filename,
      doc_type: updated.doc_type,
      file_path: updated.file_path,
      upload_date: updated.upload_date,
      text_preview: updated.text?.slice(0, 200) || "",
      char_count: updated.char_count ?? updated.text?.length ?? 0,
      has_doclang: Boolean(updated.doclang_xml?.trim()),
    });
    _documentDetailStore.set(updated.id, updated);
    return updated;
  },

  async delete(id: number): Promise<void> {
    const res = await apiFetch(`${API_BASE}/documents/${id}`, {
      method: "DELETE",
    });
    await handleResponse<void>(res);
    _documentsStore.remove(id);
    _documentDetailStore.delete(id);
  },

  getFileUrl(id: number): string {
    return withAuthToken(`${API_BASE}/documents/${id}/file`);
  },

  getDoclangUrl(id: number): string {
    return withAuthToken(`${API_BASE}/documents/${id}/doclang`);
  },

  async getDoclang(id: number): Promise<string> {
    const res = await apiFetch(`${API_BASE}/documents/${id}/doclang`);
    if (!res.ok) {
      throw new Error(`Failed to load DocLang XML (HTTP ${res.status})`);
    }
    return res.text();
  },

  getExportDoclangUrl(id: number): string {
    return withAuthToken(`${API_BASE}/documents/${id}/export-doclang`);
  },

  async getSections(id: number): Promise<DocumentSectionsResponse> {
    const res = await apiFetch(`${API_BASE}/documents/${id}/sections`);
    return handleResponse<DocumentSectionsResponse>(res);
  },

  async getSectionsTree(id: number, regenerate: boolean = false): Promise<DocumentSectionTreeResponse> {
    const url = regenerate
      ? `${API_BASE}/documents/${id}/sections-tree?regenerate=true`
      : `${API_BASE}/documents/${id}/sections-tree`;
    const res = await apiFetch(url);
    return handleResponse<DocumentSectionTreeResponse>(res);
  },

  async regenerateSectionsTree(id: number): Promise<DocumentSectionTreeResponse> {
    const res = await apiFetch(`${API_BASE}/documents/${id}/sections-tree/regenerate`, {
      method: "POST",
    });
    return handleResponse<DocumentSectionTreeResponse>(res);
  },

  getExportSectionsTreeUrl(id: number, format: "json" | "csv" = "json"): string {
    return withAuthToken(`${API_BASE}/documents/${id}/sections-tree/export?format=${format}`);
  },

  async exportSectionsTree(id: number, format: "json" | "csv" = "json"): Promise<Blob> {
    const res = await apiFetch(`${API_BASE}/documents/${id}/sections-tree/export?format=${format}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Export failed" }));
      throw new Error(err.detail || "Failed to export TOC");
    }
    return res.blob();
  },

  async importSectionsTree(id: number, file: File): Promise<DocumentSectionTreeResponse> {
    const formData = new FormData();
    formData.append("file", file);
    const res = await apiFetch(`${API_BASE}/documents/${id}/sections-tree/import`, {
      method: "POST",
      body: formData,
    });
    return handleResponse<DocumentSectionTreeResponse>(res);
  },

  async getSectionsGraph(id: number, sectionId?: string): Promise<SectionGraphResponse> {
    const url = sectionId
      ? `${API_BASE}/documents/${id}/sections-graph?section_id=${encodeURIComponent(sectionId)}`
      : `${API_BASE}/documents/${id}/sections-graph`;
    const res = await apiFetch(url);
    return handleResponse<SectionGraphResponse>(res);
  },

  async getElementBboxes(id: number): Promise<DocumentElementBboxesResponse> {
    const res = await apiFetch(`${API_BASE}/documents/${id}/element-bboxes`);
    return handleResponse<DocumentElementBboxesResponse>(res);
  },

  async getRuleSourceMap(id: number): Promise<RuleSourceMapResponse> {
    const res = await apiFetch(`${API_BASE}/documents/${id}/rule-source-map`);
    return handleResponse<RuleSourceMapResponse>(res);
  },

  async getDraftSourceMap(id: number): Promise<DraftSourceMapResponse> {
    const res = await apiFetch(`${API_BASE}/documents/${id}/draft-source-map`);
    return handleResponse<DraftSourceMapResponse>(res);
  },

  getAssetUrl(id: number, filename: string): string {
    return withAuthToken(`${API_BASE}/documents/${id}/assets/${encodeURIComponent(filename)}`);
  },

  async importFromGoogleDrive(payload: GoogleDriveImportPayload): Promise<GoogleDriveImportResponse> {
    const res = await apiFetch(`${API_BASE}/documents/import/google-drive`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await handleResponse<GoogleDriveImportResponse>(res);
    for (const item of result.results) {
      if (item.ok && item.document) {
        _documentsStore.addOrUpdate({
          id: item.document.id,
          filename: item.document.filename,
          doc_type: item.document.doc_type,
          file_path: item.document.file_path,
          upload_date: item.document.upload_date,
          text_preview: item.document.text?.slice(0, 200) || "",
          char_count: item.document.char_count ?? item.document.text?.length ?? 0,
          project_code: item.document.project_code,
          originator: item.document.originator,
          suitability_code: item.document.suitability_code,
          revision_code: item.document.revision_code,
          cde_state: item.document.cde_state,
        });
        _documentDetailStore.set(item.document.id, item.document);
      }
    }
    return result;
  },

  invalidateCache() {
    _documentsStore.clear();
    _documentDetailStore.clear();
  },
};
