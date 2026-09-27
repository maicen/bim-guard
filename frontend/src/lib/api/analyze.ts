import type {
  AnalysisResult,
  BcfArtifact,
  WorkflowStatus,
} from "../types";
import { getActiveOrgId, withAuthToken } from "../authToken";
import { API_BASE, apiFetch, handleResponse } from "./client";

function engineQuery(engines?: string[]): string {
  if (!engines) return "";
  if (engines.length === 0) return "&engines=";
  return engines.map((e) => `&engines=${encodeURIComponent(e)}`).join("");
}

/**
 * Severity bands a results page can be limited to.
 *
 * `data_quality` is not a band the engines emit; it selects the notes that
 * report what could not be assessed, which is how the analyse page's severity
 * dropdown already presents them.
 */
export type IssueBand = "critical" | "high" | "medium" | "low" | "data_quality";

/**
 * Order a results page is cut from.
 *
 * `band_then_score` is the default and matches the analyse table's own
 * ordering — criticals first — with score then id as tiebreaks. `score_desc`
 * ignores bands; `natural` keeps the run's own order, which is what an
 * unpaginated response lists. `band_asc` and `score_asc` are the ascending
 * counterparts, and are not reversals: data-quality notes sort last in both,
 * so an ascending page opens on the mildest verdict rather than on the
 * elements no engine could score.
 */
export type IssueSort =
  | "band_then_score"
  | "score_desc"
  | "natural"
  | "band_asc"
  | "score_asc";

/**
 * Optional server-side paging and filtering of `audit_issues`.
 *
 * Every field is optional and an empty object is the same as sending nothing,
 * so a caller that does not paginate keeps the response it has today.
 */
export interface ResultPageQuery {
  limit?: number;
  offset?: number;
  bands?: IssueBand[];
  /** Engine code prefixes, or the token `data_quality` for the notes. */
  mechanisms?: string[];
  includeDataQuality?: boolean;
  sort?: IssueSort;
  /** Free text over title, rule id, element id, mechanism and citations. */
  search?: string;
}

/**
 * `include_low` for a URL, omitted when the caller expressed no preference.
 *
 * Unlike the page filters, this selects what the run computes: it changes the
 * server's cache key, so sending it needlessly would split the cache between
 * two spellings of the same request.
 */
function includeLowQuery(includeLow?: boolean): string {
  return includeLow === undefined ? "" : `&include_low=${includeLow}`;
}

function pageQuery(page?: ResultPageQuery): string {
  if (!page) return "";
  const parts: string[] = [];
  if (page.limit !== undefined) parts.push(`limit=${page.limit}`);
  if (page.offset !== undefined) parts.push(`offset=${page.offset}`);
  for (const band of page.bands ?? []) parts.push(`band=${encodeURIComponent(band)}`);
  for (const code of page.mechanisms ?? []) parts.push(`mechanism=${encodeURIComponent(code)}`);
  if (page.includeDataQuality !== undefined) {
    parts.push(`include_data_quality=${page.includeDataQuality}`);
  }
  if (page.sort !== undefined) parts.push(`sort=${page.sort}`);
  if (page.search) parts.push(`q=${encodeURIComponent(page.search)}`);
  return parts.length ? `&${parts.join("&")}` : "";
}

export const analyzeApi = {
  async uploadIfc(
    projectId: number,
    file: File,
  ): Promise<{ success: boolean; filename: string; size_bytes?: number; sha256?: string }> {
    const form = new FormData();
    form.append("project_id", projectId.toString());
    form.append("ifc_file", file);

    const res = await apiFetch(`${API_BASE}/analyze/upload`, {
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
    slug: "architecture" = "architecture",
    background = false,
    useCache = true,
    signal?: AbortSignal,
    enableShacl?: boolean,
  ): Promise<AnalysisResult> {
    const res = await apiFetch(`${API_BASE}/analyze/run?background=${background}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_id: projectId,
        slug,
        use_cache: useCache,
        ...(enableShacl === undefined ? {} : { enable_shacl: enableShacl }),
      }),
      signal,
    });
    return handleResponse<AnalysisResult>(res);
  },

  /**
   * Fetch a stored or freshly computed run.
   *
   * `page` is optional and omitting it is the pre-pagination call: the whole
   * run comes back and the response carries no `page` object. Passing any
   * field narrows `audit_issues` only — `issue_stats` still describes the
   * whole run, so a page of criticals reports the run's real totals rather
   * than the window's.
   */
  async getResults(
    projectId: number,
    slug: "architecture" = "architecture",
    useCache = true,
    engines?: string[],
    signal?: AbortSignal,
    page?: ResultPageQuery,
    includeLow?: boolean,
    enableShacl?: boolean,
  ): Promise<AnalysisResult> {
    const res = await apiFetch(
      `${API_BASE}/analyze/results/${projectId}/${slug}?use_cache=${useCache}${engineQuery(engines)}${pageQuery(page)}${includeLowQuery(includeLow)}${enableShacl ? "&enable_shacl=true" : ""}`,
      { signal },
    );
    return handleResponse<AnalysisResult>(res);
  },

  async getStatus(projectId: number): Promise<WorkflowStatus> {
    const res = await apiFetch(`${API_BASE}/analyze/status/${projectId}`);
    return handleResponse<WorkflowStatus>(res);
  },

  /**
   * URL for the whole-run export.
   *
   * `includeLow` must match what the page ran, or the download reports a
   * different set of findings from the results it was taken from.
   */
  getExportUrl(
    projectId: number,
    slug: string,
    fmt: "bcf" | "csv" | "json" | "ifc",
    engines?: string[],
    includeLow?: boolean,
    bands?: string[],
    includeDataQuality?: boolean,
  ): string {
    let url = `${API_BASE}/analyze/export?project_id=${projectId}&slug=${slug}&fmt=${fmt}${engineQuery(engines)}${includeLowQuery(includeLow)}`;
    if (bands && bands.length > 0) {
      url += bands.map((b) => `&band=${encodeURIComponent(b)}`).join("");
    }
    if (includeDataQuality !== undefined) {
      url += `&include_data_quality=${includeDataQuality}`;
    }
    // The page navigates to this URL rather than fetching it, so the token has
    // to travel in the URL -- see withAuthToken.
    return withAuthToken(url);
  },

  /**
   * URL for the deterministic PDF/HTML compliance report (cover, executive
   * summary, findings register, rule register, methodology) built from the
   * project's latest analysis run.
   */
  getReportUrl(projectId: number, slug: string, format: "pdf" | "html" = "pdf"): string {
    return withAuthToken(`${API_BASE}/analyze/report/${projectId}?slug=${slug}&format=${format}`);
  },

  getBcfArtifactUrl(artifactId: number): string {
    return withAuthToken(`${API_BASE}/analyze/bcf/artifacts/${artifactId}`);
  },

  getLatestBcfUrl(projectId: number): string {
    return withAuthToken(`${API_BASE}/analyze/bcf/latest/${projectId}`);
  },

  async runArch(projectId: number, ruleFolder = ""): Promise<any> {
    const form = new FormData();
    form.append("project_id", projectId.toString());
    if (ruleFolder) form.append("rule_folder", ruleFolder);

    const res = await apiFetch(`${API_BASE}/analyze/arch`, {
      method: "POST",
      body: form,
    });
    return handleResponse<any>(res);
  },

  async listBcfArtifacts(organizationId?: number | null): Promise<BcfArtifact[]> {
    const effectiveOrg = organizationId !== undefined ? organizationId : getActiveOrgId();
    const query = effectiveOrg ? `?organization_id=${effectiveOrg}` : "";
    const res = await apiFetch(`${API_BASE}/analyze/bcf/list${query}`);
    return handleResponse<BcfArtifact[]>(res);
  },

  async deleteBcfArtifact(artifactId: number): Promise<void> {
    const res = await apiFetch(`${API_BASE}/analyze/bcf/artifacts/${artifactId}`, {
      method: "DELETE",
    });
    return handleResponse<void>(res);
  },

  /**
   * Save a ruleset-scoped PDF, CSV or Excel report from the caller's most
   * recent run of `ruleFolder` (blank means "All Rules"), returning its
   * persisted artifact metadata. BCF isn't offered here -- it's already
   * saved automatically by `runArch`.
   */
  async persistReportArtifact(
    projectId: number,
    ruleFolder: string,
    artifactType: "pdf" | "csv" | "xlsx",
  ): Promise<BcfArtifact> {
    const form = new FormData();
    form.append("project_id", projectId.toString());
    if (ruleFolder) form.append("rule_folder", ruleFolder);

    const res = await apiFetch(`${API_BASE}/analyze/report-artifacts/${artifactType}`, {
      method: "POST",
      body: form,
    });
    return handleResponse<BcfArtifact>(res);
  },

  getReportArtifactUrl(artifactType: "bcf" | "pdf" | "csv" | "xlsx", artifactId: number): string {
    return withAuthToken(`${API_BASE}/analyze/report-artifacts/${artifactType}/${artifactId}`);
  },

  async listReportArtifacts(
    artifactType: "bcf" | "pdf" | "csv" | "xlsx",
    organizationId?: number | null,
  ): Promise<BcfArtifact[]> {
    const effectiveOrg = organizationId !== undefined ? organizationId : getActiveOrgId();
    const query = effectiveOrg ? `?organization_id=${effectiveOrg}` : "";
    const res = await apiFetch(`${API_BASE}/analyze/report-artifacts/${artifactType}${query}`);
    return handleResponse<BcfArtifact[]>(res);
  },

  async deleteReportArtifact(artifactType: "bcf" | "pdf" | "csv", artifactId: number): Promise<void> {
    const res = await apiFetch(`${API_BASE}/analyze/report-artifacts/${artifactType}/${artifactId}`, {
      method: "DELETE",
    });
    return handleResponse<void>(res);
  },
};

export const revitSyncApi = {
  async sync(payload: any): Promise<any> {
    const res = await apiFetch(`${API_BASE}/analyze/revit-sync`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<any>(res);
  },
};
