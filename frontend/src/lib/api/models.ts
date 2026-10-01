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

  /** Replace an attached model's stored IFC file with a new direct-to-cloud upload, in place. */
  async replace(projectId: number, modelId: number, file: File, signal?: AbortSignal, onProgress?: (percent: number) => void): Promise<Model> {
    // 1. Get presigned URL
    const urlRes = await apiFetch(`${API_BASE}/projects/${projectId}/models/upload-url`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_name: file.name, size_bytes: file.size, content_type: file.type || "application/octet-stream" }),
      signal,
    });
    const { signed_url, storage_reference, token } = await handleResponse<any>(urlRes);

    // 2. Direct upload to Supabase via TUS for resumable upload
    const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL;
    const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY;
    const tus = await import("tus-js-client");
    
    await new Promise<void>((resolve, reject) => {
      const upload = new tus.Upload(file, {
        endpoint: `${SUPABASE_URL}/storage/v1/upload/resumable/sign`,
        retryDelays: [0, 3000, 5000, 10000, 20000],
        headers: {
          apikey: SUPABASE_ANON_KEY,
          'x-signature': token,
        },
        uploadDataDuringCreation: true,
        removeFingerprintOnSuccess: true,
        metadata: {
          bucketName: "ifc",
          objectName: storage_reference.replace("sb://ifc/", ""),
          contentType: file.type || "application/octet-stream",
        },
        chunkSize: 6 * 1024 * 1024, // 6MB
        onError: (err) => reject(new Error(`Storage upload failed: ${err.message}`)),
        onProgress: (bytesUploaded, bytesTotal) => {
          if (onProgress) {
            onProgress(Math.round((bytesUploaded / bytesTotal) * 100));
          }
        },
        onSuccess: () => resolve(),
      });

      if (signal) {
        signal.addEventListener("abort", () => {
          upload.abort(true);
          reject(new DOMException("Aborted", "AbortError"));
        });
      }
      upload.start();
    });

    // 3. Confirm replace with backend
    const confirmRes = await apiFetch(`${API_BASE}/models/${modelId}/replace-confirm?project_id=${projectId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        storage_reference,
        file_name: file.name,
      }),
      signal,
    });
    return handleResponse<Model>(confirmRes);
  },

  /**
   * Attach IFC models to an existing project using direct-to-cloud presigned URLs.
   */
  async upload(
    projectId: number,
    files: File[],
    primaryIndex: number,
    roles: string[],
    options?: {
      signal?: AbortSignal;
      onUploadProgress?: (percent: number) => void;
    }
  ): Promise<ModelUploadResponse> {
    let lastResponse: ModelUploadResponse | null = null;
    let totalBytes = files.reduce((sum, f) => sum + f.size, 0);
    let uploadedBytes = 0;

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const role = roles[i] || "";
      const isPrimary = i === primaryIndex;

      // 1. Get presigned URL
      const urlRes = await apiFetch(`${API_BASE}/projects/${projectId}/models/upload-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_name: file.name, size_bytes: file.size, content_type: file.type || "application/octet-stream" }),
        signal: options?.signal,
      });
      const { signed_url, storage_reference, token } = await handleResponse<any>(urlRes);

      // 2. Direct upload to Supabase via TUS for resumable upload
      const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL;
      const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY;
      const tus = await import("tus-js-client");
      
      await new Promise<void>((resolve, reject) => {
        const upload = new tus.Upload(file, {
          endpoint: `${SUPABASE_URL}/storage/v1/upload/resumable/sign`,
          retryDelays: [0, 3000, 5000, 10000, 20000],
          headers: {
            apikey: SUPABASE_ANON_KEY,
            'x-signature': token,
          },
          uploadDataDuringCreation: true,
          removeFingerprintOnSuccess: true,
          metadata: {
            bucketName: "ifc",
            objectName: storage_reference.replace("sb://ifc/", ""),
            contentType: file.type || "application/octet-stream",
          },
          chunkSize: 6 * 1024 * 1024, // 6MB
          onError: (err) => reject(new Error(`Storage upload failed: ${err.message}`)),
          onProgress: (bytesUploaded, bytesTotal) => {
            if (options?.onUploadProgress) {
              const overallPercent = Math.round(((uploadedBytes + bytesUploaded) / totalBytes) * 100);
              options.onUploadProgress(overallPercent);
            }
          },
          onSuccess: () => {
            uploadedBytes += file.size;
            resolve();
          },
        });

        if (options?.signal) {
          options.signal.addEventListener("abort", () => {
            upload.abort(true);
            reject(new DOMException("Aborted", "AbortError"));
          });
        }
        upload.start();
      });

      // 3. Confirm upload with backend
      const confirmRes = await apiFetch(`${API_BASE}/projects/${projectId}/models/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          storage_reference,
          file_name: file.name,
          is_primary: isPrimary,
          role: role,
        }),
        signal: options?.signal,
      });
      lastResponse = await handleResponse<ModelUploadResponse>(confirmRes);
    }

    return lastResponse || { success: true, files: [], primary_id: null, processing: false, warnings: [] };
  },

  /** Poll the background attach job started by `upload()`. */
  async attachStatus(projectId: number): Promise<ModelAttachStatusResponse> {
    const res = await apiFetch(`${API_BASE}/projects/${projectId}/models/attach-status`);
    return handleResponse<ModelAttachStatusResponse>(res);
  },

  /**
   * Attach IFC models and wait for the background job to finish.
   */
  async uploadAndWait(
    projectId: number,
    files: File[],
    primaryIndex: number,
    roles: string[],
    options?: {
      onUploadProgress?: (percent: number) => void;
      onProgress?: (attached: number, total: number) => void;
      pollMs?: number;
      signal?: AbortSignal;
    },
  ): Promise<void> {
    const initial = await modelsApi.upload(projectId, files, primaryIndex, roles, {
      signal: options?.signal,
      onUploadProgress: options?.onUploadProgress,
    });
    if (!initial.processing) return;

    const pollMs = options?.pollMs ?? 1500;
    // eslint-disable-next-line no-constant-condition
    while (true) {
      if (options?.signal?.aborted) return;
      await new Promise((resolve) => setTimeout(resolve, pollMs));
      if (options?.signal?.aborted) return;
      const job = await modelsApi.attachStatus(projectId);
      // Wait, we queued multiple attachments but total might be wrong since we loop.
      // But the progress callback still expects (attached, total).
      options?.onProgress?.(job.attached, Math.max(job.total, files.length));
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
