// ── Evaluation (human-validated compliance results) ─────────────────────────
// Mirrors the Evaluation* contracts in app/modules/contracts.py. bim-guard
// only captures BIM-Guard's verdict and a human-confirmed verdict side by
// side; the confusion-matrix/accuracy scoring itself lives in the separate
// bim-guard-evaluation companion repo.

export type EvaluationBimguardVerdict = "PASS" | "FAIL" | "MISSING" | "WAIVED" | "NOT_APPLICABLE";

export type EvaluationHumanVerdict = "PASS" | "FAIL" | "NOT_APPLICABLE" | "INDETERMINATE";

export interface EvaluationCaptureRequest {
  project_id: number;
  rule_folder?: string;
}

export interface EvaluationCaptureResponse {
  captured_count: number;
}

export interface EvaluationFinding {
  id: number;
  project_id: number;
  ifc_file_id?: number | null;
  rule_id?: number | null;
  rule_snapshot: Record<string, unknown>;
  element_global_id: string;
  element_name?: string | null;
  storey?: string | null;
  space?: string | null;
  bimguard_verdict: EvaluationBimguardVerdict;
  bimguard_reason?: string | null;
  captured_by_email?: string | null;
  captured_at?: string | null;
  human_verdict?: EvaluationHumanVerdict | null;
  reviewer_email?: string | null;
  reviewed_at?: string | null;
  review_notes?: string | null;
  created_at?: string | null;
}

export interface EvaluationFindingListResponse {
  findings: EvaluationFinding[];
}

export interface EvaluationFindingReviewRequest {
  human_verdict: EvaluationHumanVerdict;
  review_notes?: string | null;
}

export interface EvaluationBulkReviewRequest {
  finding_ids: number[];
  human_verdict: EvaluationHumanVerdict;
  review_notes?: string | null;
}

export interface EvaluationConfusionMatrix {
  tp: number;
  fp: number;
  fn: number;
  tn: number;
}

export interface EvaluationMetrics {
  accuracy?: number | null;
  precision?: number | null;
  recall?: number | null;
  specificity?: number | null;
  f1?: number | null;
  cohens_kappa?: number | null;
}

export interface EvaluationMatrixResponse {
  project_id: number;
  total_findings: number;
  reviewed_findings: number;
  unreviewed_findings: number;
  confusion_matrix: EvaluationConfusionMatrix;
  metrics: EvaluationMetrics;
  cross_tabulation: Record<string, Record<string, number>>;
}
