import type {
  EvaluationBulkReviewRequest,
  EvaluationCaptureRequest,
  EvaluationCaptureResponse,
  EvaluationFinding,
  EvaluationFindingListResponse,
  EvaluationFindingReviewRequest,
} from "../types";
import { API_BASE, apiFetch, handleResponse } from "./client";

export const evaluationApi = {
  /** Snapshot a ruleset run's current PASS/FAIL verdicts into the evaluation set. */
  async capture(payload: EvaluationCaptureRequest): Promise<EvaluationCaptureResponse> {
    const res = await apiFetch(`${API_BASE}/evaluation/capture`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<EvaluationCaptureResponse>(res);
  },

  async listFindings(
    projectId: number,
    filters?: { ruleId?: number; humanVerdict?: string },
  ): Promise<EvaluationFindingListResponse> {
    const params = new URLSearchParams({ project_id: String(projectId) });
    if (filters?.ruleId) params.set("rule_id", String(filters.ruleId));
    if (filters?.humanVerdict) params.set("human_verdict", filters.humanVerdict);
    const res = await apiFetch(`${API_BASE}/evaluation/findings?${params.toString()}`);
    return handleResponse<EvaluationFindingListResponse>(res);
  },

  async reviewFinding(findingId: number, payload: EvaluationFindingReviewRequest): Promise<EvaluationFinding> {
    const res = await apiFetch(`${API_BASE}/evaluation/findings/${findingId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<EvaluationFinding>(res);
  },

  async bulkReview(payload: EvaluationBulkReviewRequest): Promise<{ updated_count: number }> {
    const res = await apiFetch(`${API_BASE}/evaluation/findings/bulk-review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<{ updated_count: number }>(res);
  },

  async bulkDelete(findingIds: number[]): Promise<{ deleted_count: number }> {
    const res = await apiFetch(`${API_BASE}/evaluation/findings/bulk-delete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ finding_ids: findingIds }),
    });
    return handleResponse<{ deleted_count: number }>(res);
  },
};
