import type {
  AnalysisResult,
  Project,
  ProjectCreatePayload,
  ProjectListResponse,
  Rule,
  RuleFolder,
  WorkflowStatus,
} from './types';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorDetail = res.statusText;
    try {
      const errJson = await res.json();
      errorDetail = errJson.detail || errJson.error || errorDetail;
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

export const projectsApi = {
  async list(): Promise<ProjectListResponse> {
    const res = await fetch(`${API_BASE}/projects`);
    return handleResponse<ProjectListResponse>(res);
  },

  async get(id: number): Promise<Project> {
    const res = await fetch(`${API_BASE}/projects/${id}`);
    return handleResponse<Project>(res);
  },

  async create(payload: ProjectCreatePayload): Promise<Project> {
    const res = await fetch(`${API_BASE}/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse<Project>(res);
  },

  async uploadWithIfc(formData: FormData): Promise<Project> {
    const res = await fetch(`${API_BASE}/projects/upload`, {
      method: 'POST',
      body: formData,
    });
    return handleResponse<Project>(res);
  },

  async delete(id: number): Promise<void> {
    const res = await fetch(`${API_BASE}/projects/${id}`, {
      method: 'DELETE',
    });
    return handleResponse<void>(res);
  },

  getIfcUrl(id: number): string {
    return `${API_BASE}/projects/${id}/ifc`;
  },
};

export const rulesApi = {
  async list(filters?: { mechanism?: string; ruleset_id?: string; keyword?: string }): Promise<Rule[]> {
    const params = new URLSearchParams();
    if (filters?.mechanism) params.set('mechanism', filters.mechanism);
    if (filters?.ruleset_id) params.set('ruleset_id', filters.ruleset_id);
    if (filters?.keyword) params.set('keyword', filters.keyword);

    const query = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE}/rules${query}`);
    return handleResponse<Rule[]>(res);
  },

  async folders(): Promise<RuleFolder[]> {
    const res = await fetch(`${API_BASE}/rules/folders`);
    return handleResponse<RuleFolder[]>(res);
  },

  async get(id: number): Promise<Rule> {
    const res = await fetch(`${API_BASE}/rules/${id}`);
    return handleResponse<Rule>(res);
  },

  async create(payload: Partial<Rule>): Promise<Rule> {
    const res = await fetch(`${API_BASE}/rules`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse<Rule>(res);
  },

  async delete(id: number): Promise<void> {
    const res = await fetch(`${API_BASE}/rules/${id}`, {
      method: 'DELETE',
    });
    return handleResponse<void>(res);
  },
};

export const analyzeApi = {
  async uploadIfc(projectId: number, file: File): Promise<{ success: boolean; filename: string }> {
    const form = new FormData();
    form.append('project_id', projectId.toString());
    form.append('ifc_file', file);

    const res = await fetch(`${API_BASE}/analyze/upload`, {
      method: 'POST',
      body: form,
    });
    return handleResponse<{ success: boolean; filename: string }>(res);
  },

  async run(projectId: number, slug: 'corrosion' | 'seismic' = 'corrosion', background = false): Promise<AnalysisResult> {
    const res = await fetch(`${API_BASE}/analyze/run?background=${background}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: projectId, slug }),
    });
    return handleResponse<AnalysisResult>(res);
  },

  async getResults(projectId: number, slug: 'corrosion' | 'seismic' = 'corrosion'): Promise<AnalysisResult> {
    const res = await fetch(`${API_BASE}/analyze/results/${projectId}/${slug}`);
    return handleResponse<AnalysisResult>(res);
  },

  async getStatus(projectId: number): Promise<WorkflowStatus> {
    const res = await fetch(`${API_BASE}/analyze/status/${projectId}`);
    return handleResponse<WorkflowStatus>(res);
  },

  getExportUrl(projectId: number, slug: string, fmt: 'bcf' | 'csv' | 'json'): string {
    return `${API_BASE}/analyze/export?project_id=${projectId}&slug=${slug}&fmt=${fmt}`;
  },
};

