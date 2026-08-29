import type {
  AnalysisResult,
  BcfArtifact,
  DocumentDetail,
  DocumentItem,
  DocumentUpdatePayload,
  Project,
  ProjectCreatePayload,
  ProjectListResponse,
  ProjectUpdatePayload,
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

  async getInputs(id: number): Promise<any[]> {
    const res = await fetch(`${API_BASE}/projects/${id}/inputs`);
    return handleResponse<any[]>(res);
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

  async update(id: number, payload: ProjectUpdatePayload): Promise<Project> {
    const res = await fetch(`${API_BASE}/projects/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
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

  async update(id: number, payload: Partial<Rule>): Promise<Rule> {
    const res = await fetch(`${API_BASE}/rules/${id}`, {
      method: 'PUT',
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
  async uploadIfc(projectId: number, file: File): Promise<{ success: boolean; filename: string; size_bytes?: number; sha256?: string }> {
    const form = new FormData();
    form.append('project_id', projectId.toString());
    form.append('ifc_file', file);

    const res = await fetch(`${API_BASE}/analyze/upload`, {
      method: 'POST',
      body: form,
    });
    return handleResponse<{ success: boolean; filename: string; size_bytes?: number; sha256?: string }>(res);
  },

  async run(projectId: number, slug: 'corrosion' | 'seismic' = 'corrosion', background = false, useCache = true): Promise<AnalysisResult> {
    const res = await fetch(`${API_BASE}/analyze/run?background=${background}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: projectId, slug, use_cache: useCache }),
    });
    return handleResponse<AnalysisResult>(res);
  },

  async getResults(projectId: number, slug: 'corrosion' | 'seismic' = 'corrosion', useCache = true): Promise<AnalysisResult> {
    const res = await fetch(`${API_BASE}/analyze/results/${projectId}/${slug}?use_cache=${useCache}`);
    return handleResponse<AnalysisResult>(res);
  },

  async getStatus(projectId: number): Promise<WorkflowStatus> {
    const res = await fetch(`${API_BASE}/analyze/status/${projectId}`);
    return handleResponse<WorkflowStatus>(res);
  },

  getExportUrl(projectId: number, slug: string, fmt: 'bcf' | 'csv' | 'json'): string {
    return `${API_BASE}/analyze/export?project_id=${projectId}&slug=${slug}&fmt=${fmt}`;
  },

  getBcfArtifactUrl(artifactId: number): string {
    return `${API_BASE}/analyze/bcf/artifacts/${artifactId}`;
  },

  getLatestBcfUrl(projectId: number): string {
    return `${API_BASE}/analyze/bcf/latest/${projectId}`;
  },

  async runArch(projectId: number, ruleFolder = ''): Promise<any> {
    const form = new FormData();
    form.append('project_id', projectId.toString());
    if (ruleFolder) form.append('rule_folder', ruleFolder);

    const res = await fetch(`${API_BASE}/analyze/arch`, {
      method: 'POST',
      body: form,
    });
    return handleResponse<any>(res);
  },

  async listBcfArtifacts(): Promise<BcfArtifact[]> {
    const res = await fetch(`${API_BASE}/analyze/bcf/list`);
    return handleResponse<BcfArtifact[]>(res);
  },
};

export const dashboardApi = {
  async getStats(): Promise<any> {
    const res = await fetch(`${API_BASE}/dashboard/stats`);
    return handleResponse<any>(res);
  },
};

export const documentsApi = {
  async list(): Promise<DocumentItem[]> {
    const res = await fetch(`${API_BASE}/documents`);
    return handleResponse<DocumentItem[]>(res);
  },

  async get(id: number): Promise<DocumentDetail> {
    const res = await fetch(`${API_BASE}/documents/${id}`);
    return handleResponse<DocumentDetail>(res);
  },

  async upload(file: File): Promise<DocumentDetail> {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${API_BASE}/documents`, {
      method: 'POST',
      body: form,
    });
    return handleResponse<DocumentDetail>(res);
  },

  async update(id: number, payload: DocumentUpdatePayload): Promise<DocumentDetail> {
    const res = await fetch(`${API_BASE}/documents/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse<DocumentDetail>(res);
  },

  async delete(id: number): Promise<void> {
    const res = await fetch(`${API_BASE}/documents/${id}`, {
      method: 'DELETE',
    });
    return handleResponse<void>(res);
  },
};

export const settingsApi = {
  async get(): Promise<any> {
    const res = await fetch(`${API_BASE}/settings`);
    return handleResponse<any>(res);
  },

  async update(settings: Record<string, string>): Promise<any> {
    const res = await fetch(`${API_BASE}/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(token ? { token } : {}),
    });
    return handleResponse<any>(res);
  },
};

export const ruleExtractionApi = {
  async extract(file?: File, rawText?: string): Promise<{ rules: any[]; warnings: string[]; count: number }> {
    const form = new FormData();
    if (file) form.append('file', file);
    if (rawText) form.append('raw_text', rawText);

    const res = await fetch(`${API_BASE}/rules/extract`, {
      method: 'POST',
      body: form,
    });
    return handleResponse<any>(res);
  },

  async bulkCreate(rules: any[]): Promise<any> {
    const res = await fetch(`${API_BASE}/rules/bulk`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(rules),
    });
    return handleResponse<any>(res);
  },

  async seed(): Promise<any> {
    const res = await fetch(`${API_BASE}/rules/seed`, {
      method: 'POST',
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
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse<any>(res);
  },
};



