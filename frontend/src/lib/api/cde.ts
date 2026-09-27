import type {
  CDEDocumentItem,
  CDESyncRequest,
  CDESyncResponse,
  CDEUserResponse,
  CDEVersionsResponse,
} from "../types";
import { API_BASE, apiFetch, handleResponse } from "./client";

// =============================================================================
// buildingSMART OpenCDE API Client
// =============================================================================

export const cdeApi = {
  async getVersions(): Promise<CDEVersionsResponse> {
    const res = await apiFetch(`${API_BASE}/cde/versions`);
    return handleResponse<CDEVersionsResponse>(res);
  },

  async getUser(): Promise<CDEUserResponse> {
    const res = await apiFetch(`${API_BASE}/cde/v1/user`);
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
    const res = await apiFetch(`${API_BASE}/cde/v1/projects/${projectId}/documents${qs}`);
    return handleResponse<CDEDocumentItem[]>(res);
  },

  async syncDocuments(payload: CDESyncRequest): Promise<CDESyncResponse> {
    const res = await apiFetch(`${API_BASE}/cde/v1/projects/${payload.project_id}/documents/sync`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<CDESyncResponse>(res);
  },
};
