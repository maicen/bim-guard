import type {
  AttachRepoModelsPayload,
  GitHubRepo,
  GitHubRepoCreatePayload,
  GitHubRepoStructure,
  GitHubRepoUpdatePayload,
  Model,
  ModelAttachStatusResponse,
  ModelListResponse,
  ModelUploadResponse,
} from "../types";
import { withAuthToken } from "../authToken";
import { API_BASE, apiFetch, handleResponse } from "./client";

export const modelsApi = {
  async list(projectId: number): Promise<Model[]> {
    const res = await apiFetch(`${API_BASE}/models?project_id=${projectId}`);
    const body = await handleResponse<ModelListResponse>(res);
    return body.models;
  },

  /** URL for one specific attached model, rather than the project's primary. */
  downloadUrl(projectId: number, modelId: number): string {
    return withAuthToken(`${API_BASE}/models/${modelId}/download?project_id=${projectId}`);
  },

  /** Promote one attached model to primary. Any previous primary is demoted. */
  async setPrimary(projectId: number, modelId: number): Promise<Model> {
    const res = await apiFetch(`${API_BASE}/models/${modelId}/primary?project_id=${projectId}`, {
      method: "POST",
    });
    return handleResponse<Model>(res);
  },

  /**
   * Detach and delete one attached model. Deleting the primary promotes the
   * next remaining model; deleting a project's last model leaves it with none.
   */
  async delete(projectId: number, modelId: number): Promise<void> {
    const res = await apiFetch(`${API_BASE}/models/${modelId}?project_id=${projectId}`, {
      method: "DELETE",
    });
    await handleResponse<void>(res);
  },

  /** Re-read schema/authoring-app/storey/element/discipline metadata for an attached model. */
  async refreshMetadata(projectId: number, modelId: number): Promise<Model> {
    const res = await apiFetch(
      `${API_BASE}/models/${modelId}/refresh-metadata?project_id=${projectId}`,
      { method: "POST" },
    );
    return handleResponse<Model>(res);
  },

  /** Edit an attached model's display name, role, or ISO 19650 fields. */
  async update(
    projectId: number,
    modelId: number,
    updates: Partial<
      Pick<
        Model,
        | "file_name"
        | "role"
        | "project_code"
        | "originator"
        | "volume_system"
        | "level"
        | "type"
        | "number"
        | "suitability_code"
        | "revision_code"
      >
    >,
  ): Promise<Model> {
    const res = await apiFetch(`${API_BASE}/models/${modelId}?project_id=${projectId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    });
    return handleResponse<Model>(res);
  },

  /** Replace an attached model's stored IFC file with a new upload, in place. */
  async replace(projectId: number, modelId: number, file: File): Promise<Model> {
    const form = new FormData();
    form.append("file", file);
    const res = await apiFetch(`${API_BASE}/models/${modelId}/replace?project_id=${projectId}`, {
      method: "POST",
      body: form,
    });
    return handleResponse<Model>(res);
  },

  /**
   * Attach IFC models to an existing project.
   *
   * `roles` goes over the wire as one repeated form entry per file, not as a
   * JSON blob: the endpoint declares `roles: list[str] = Form()`, which FastAPI
   * fills from repeated entries. A single JSON string would arrive as a
   * one-element list and be rejected for not matching the file count.
   */
  async upload(
    projectId: number,
    files: File[],
    primaryIndex: number,
    roles: string[],
    signal?: AbortSignal,
  ): Promise<ModelUploadResponse> {
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    form.append("primary_index", String(primaryIndex));
    roles.forEach((role) => form.append("roles", role));

    const res = await apiFetch(`${API_BASE}/projects/${projectId}/models`, {
      method: "POST",
      body: form,
      signal,
    });
    // The primary is mirrored onto projects.ifc_file_path server-side, so a
    // caller holding a project row fetched before this call should re-read it
    // with { forceRefresh: true } -- the cache cannot know the column moved.
    return handleResponse<ModelUploadResponse>(res);
  },

  /** Poll the background attach job started by `upload()`. */
  async attachStatus(projectId: number): Promise<ModelAttachStatusResponse> {
    const res = await apiFetch(`${API_BASE}/projects/${projectId}/models/attach-status`);
    return handleResponse<ModelAttachStatusResponse>(res);
  },

  /**
   * Attach IFC models and wait for the background job to finish.
   *
   * `upload()` returns as soon as the request is validated -- storing and
   * attaching the files runs after the response, because doing it inline
   * routinely outran the Cloudflare Tunnel's ~100s idle timeout for large or
   * multi-file attaches (HTTP 524). This polls attach-status until the job is
   * done, surfacing progress through `onProgress`, and throws if the job
   * reports an error.
   */
  async uploadAndWait(
    projectId: number,
    files: File[],
    primaryIndex: number,
    roles: string[],
    options?: {
      onProgress?: (attached: number, total: number) => void;
      pollMs?: number;
      /**
       * Stops the attach-status poll loop below when the caller unmounts
       * (a modal closed, the user navigated away) -- without this, the
       * `while (true)` loop below keeps polling forever with nothing left
       * to report progress to, an orphaned network loop that outlives the
       * component that started it.
       */
      signal?: AbortSignal;
    },
  ): Promise<void> {
    const initial = await modelsApi.upload(projectId, files, primaryIndex, roles, options?.signal);
    if (!initial.processing) return;

    const pollMs = options?.pollMs ?? 1500;
    // eslint-disable-next-line no-constant-condition
    while (true) {
      if (options?.signal?.aborted) return;
      await new Promise((resolve) => setTimeout(resolve, pollMs));
      if (options?.signal?.aborted) return;
      const job = await modelsApi.attachStatus(projectId);
      options?.onProgress?.(job.attached, job.total);
      if (job.error) {
        throw new Error(job.error);
      }
      if (!job.processing) return;
    }
  },
};

let _cachedReposList: GitHubRepo[] | null = null;
const _cachedStructureMap: Record<number, GitHubRepoStructure> = {};

export const githubReposApi = {
  async list(forceRefresh = false): Promise<GitHubRepo[]> {
    if (_cachedReposList && !forceRefresh) {
      apiFetch(`${API_BASE}/repositories`)
        .then((res) => handleResponse<GitHubRepo[]>(res))
        .then((data) => {
          _cachedReposList = data;
        })
        .catch(() => {});
      return _cachedReposList;
    }
    const res = await apiFetch(`${API_BASE}/repositories`);
    const data = await handleResponse<GitHubRepo[]>(res);
    _cachedReposList = data;
    return data;
  },

  async get(id: number): Promise<GitHubRepo> {
    const res = await apiFetch(`${API_BASE}/repositories/${id}`);
    return handleResponse<GitHubRepo>(res);
  },

  async create(payload: GitHubRepoCreatePayload): Promise<GitHubRepo> {
    const res = await apiFetch(`${API_BASE}/repositories`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const created = await handleResponse<GitHubRepo>(res);
    _cachedReposList = null;
    return created;
  },

  async update(id: number, payload: GitHubRepoUpdatePayload): Promise<GitHubRepo> {
    const res = await apiFetch(`${API_BASE}/repositories/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const updated = await handleResponse<GitHubRepo>(res);
    _cachedReposList = null;
    return updated;
  },

  async delete(id: number): Promise<void> {
    const res = await apiFetch(`${API_BASE}/repositories/${id}`, {
      method: "DELETE",
    });
    await handleResponse<void>(res);
    _cachedReposList = null;
    delete _cachedStructureMap[id];
  },

  async getStructure(id: number, forceRefresh = false): Promise<GitHubRepoStructure> {
    if (_cachedStructureMap[id] && !forceRefresh) {
      apiFetch(`${API_BASE}/repositories/${id}/structure`)
        .then((res) => handleResponse<GitHubRepoStructure>(res))
        .then((data) => {
          _cachedStructureMap[id] = data;
        })
        .catch(() => {});
      return _cachedStructureMap[id];
    }
    const res = await apiFetch(`${API_BASE}/repositories/${id}/structure`);
    const data = await handleResponse<GitHubRepoStructure>(res);
    _cachedStructureMap[id] = data;
    return data;
  },

  /**
   * Attach one or more IFC models from this repository to an existing
   * project. No bytes pass through this request -- each model is recorded
   * pointing at the repository's raw-content URL, fetched on demand.
   */
  async attachModelsToProject(
    projectId: number,
    payload: AttachRepoModelsPayload,
  ): Promise<ModelUploadResponse> {
    const res = await apiFetch(`${API_BASE}/projects/${projectId}/models/from-repo`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<ModelUploadResponse>(res);
  },
};
