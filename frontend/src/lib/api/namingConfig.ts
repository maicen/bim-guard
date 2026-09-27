import type {
  NamingCatalog,
  NamingConfig,
  NamingConfigPayload,
  NamingPreview,
} from "../types";
import { API_BASE, apiFetch, handleResponse } from "./client";

export const namingConfigApi = {
  /** Fetch the conventions, tokens, code library and CDE statuses. */
  async catalog(): Promise<NamingCatalog> {
    const res = await apiFetch(`${API_BASE}/naming-config/catalog`);
    return handleResponse<NamingCatalog>(res);
  },

  /** Fetch one project's naming setup; unconfigured projects report defaults. */
  async get(projectId: number): Promise<NamingConfig> {
    const res = await apiFetch(`${API_BASE}/naming-config/projects/${projectId}`);
    return handleResponse<NamingConfig>(res);
  },

  /** Write one project's naming setup. Absent fields keep their stored value. */
  async save(projectId: number, payload: NamingConfigPayload): Promise<NamingConfig> {
    const res = await apiFetch(`${API_BASE}/naming-config/projects/${projectId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<NamingConfig>(res);
  },

  /** Drop a project's saved setup, returning the defaults it falls back to. */
  async reset(projectId: number): Promise<NamingConfig> {
    const res = await apiFetch(`${API_BASE}/naming-config/projects/${projectId}`, {
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
    const res = await apiFetch(`${API_BASE}/naming-config/preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ config, overrides }),
    });
    return handleResponse<NamingPreview>(res);
  },
};
