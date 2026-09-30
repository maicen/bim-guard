"""Human-in-the-loop validation of BIM-Guard's PASS/FAIL compliance results.

Compliance results are otherwise never persisted (see
app/services/analysis_cache.py's "not a database" design note) --
:meth:`EvaluationService.capture_results` is the only path that writes a
run's verdicts to durable storage, and only when a reviewer explicitly asks
for it via ``POST /api/evaluation/capture``. Everything else here is a plain
CRUD/review workflow over the resulting rows. Scoring those rows into a
confusion matrix / accuracy / precision / recall / F1 is out of scope for
this module -- that lives in the separate bim-guard-evaluation companion
repo, which reads the rows back via the API (see AGENTS.md).
"""

from __future__ import annotations

from typing import Any

from app.logging_config import get_logger
from app.modules.contracts import (
    EvaluationBulkReviewRequest,
    EvaluationConfusionMatrix,
    EvaluationFindingReviewRequest,
    EvaluationMatrixResponse,
    EvaluationMetrics,
)
from app.services.arch_analysis_service import ArchAnalysisService
from app.services.persistence import PersistenceService
from app.utils import now_iso_utc

logger = get_logger(__name__)

# Fields copied straight from a rule_compliance entry (see
# ComplianceComparator._result()) into evaluation_findings.rule_snapshot, so
# a later edit to public.rules can't retroactively change what a past
# finding was graded against -- public.rules has no version history.
_RULE_SNAPSHOT_KEYS = (
    "rule_ref",
    "rule_desc",
    "ruleset_id",
    "target",
    "property_name",
    "property_set",
    "operator",
    "check_value",
    "value_min",
    "value_max",
    "unit",
    "severity",
)


class EvaluationService:
    """Capture BIM-Guard verdicts for review, and record human-confirmed verdicts against them."""

    def __init__(
        self,
        *,
        findings_repo=None,
        arch_analysis_service: ArchAnalysisService | None = None,
    ) -> None:
        """Initialize the evaluation_findings table adapter and analysis service with dependency injection."""
        self._findings = (
            findings_repo
            if findings_repo is not None
            else PersistenceService.get_table(
                "evaluation_findings",
                {
                    "id": int,
                    "project_id": int,
                    "ifc_file_id": int,
                    "rule_id": int,
                    "rule_snapshot": dict,
                    "element_global_id": str,
                    "element_name": str,
                    "storey": str,
                    "space": str,
                    "bimguard_verdict": str,
                    "bimguard_reason": str,
                    "captured_by_email": str,
                    "captured_at": str,
                    "human_verdict": str,
                    "reviewer_email": str,
                    "reviewed_at": str,
                    "review_notes": str,
                    "created_at": str,
                },
            )
        )
        self._arch_analysis = (
            arch_analysis_service if arch_analysis_service is not None else ArchAnalysisService()
        )

    def capture_results(
        self, project_id: int, rule_folder: str | list[str], captured_by_email: str | None
    ) -> int:
        """Snapshot the current rule_compliance run's PASS/FAIL verdicts for review.

        Recomputes the run server-side via ArchAnalysisService rather than
        trusting a client-supplied result payload, so a captured verdict
        can't be tampered with client-side before it becomes the "ground
        truth" a human reviews. Inserts one row per (rule, element) --
        capturing the same run twice creates a second, independent set of
        rows rather than overwriting the first, so a past review decision
        stays attached to the run it was made against.
        """
        rule_compliance, _summary = self._arch_analysis.compute_rule_compliance(project_id, rule_folder)
        now = now_iso_utc()
        rows_to_insert: list[dict[str, Any]] = []
        for rule_result in rule_compliance:
            snapshot = {key: rule_result.get(key) for key in _RULE_SNAPSHOT_KEYS}
            for element in rule_result.get("all_elements") or []:
                rows_to_insert.append(
                    {
                        "project_id": project_id,
                        "rule_id": rule_result.get("rule_id"),
                        "rule_snapshot": snapshot,
                        "element_global_id": element.get("guid") or "",
                        "element_name": element.get("element_name") or "",
                        "storey": element.get("storey") or "",
                        "space": element.get("space") or "",
                        "bimguard_verdict": element.get("status") or "NOT_APPLICABLE",
                        "bimguard_reason": element.get("reason") or "",
                        "captured_by_email": captured_by_email or "",
                        "captured_at": now,
                        "created_at": now,
                    }
                )

        if rows_to_insert:
            self._findings.insert_many(rows_to_insert)
        logger.info(
            "Captured %d evaluation findings project_id=%s rule_folder=%r",
            len(rows_to_insert),
            project_id,
            rule_folder,
        )
        return len(rows_to_insert)

    def list_findings(
        self,
        *,
        project_id: int | None = None,
        rule_id: int | None = None,
        human_verdict: str | None = None,
        limit: int = 2000,
    ) -> list[dict[str, Any]]:
        """Return captured findings, most recent first, optionally filtered."""
        rows = list(self._findings.rows)
        if project_id is not None:
            rows = [row for row in rows if int(row.get("project_id") or 0) == project_id]
        if rule_id is not None:
            rows = [row for row in rows if row.get("rule_id") == rule_id]
        if human_verdict is not None:
            rows = [row for row in rows if row.get("human_verdict") == human_verdict]
        rows.sort(key=lambda row: row.get("id") or 0, reverse=True)
        return rows[:limit]

    def get_finding(self, finding_id: int) -> dict[str, Any] | None:
        """Return one captured finding by primary key."""
        return self._findings.get(finding_id)

    def review_finding(
        self,
        finding_id: int,
        payload: EvaluationFindingReviewRequest,
        reviewer_email: str | None,
    ) -> dict[str, Any]:
        """Record a human-confirmed verdict for one captured finding."""
        existing = self.get_finding(finding_id)
        if existing is None:
            raise ValueError(f"Evaluation finding {finding_id} not found")

        updates = {
            "human_verdict": payload.human_verdict.value,
            "reviewer_email": reviewer_email or "",
            "reviewed_at": now_iso_utc(),
            "review_notes": payload.review_notes or "",
        }
        self._findings.update(updates=updates, pk_values=finding_id)
        logger.info(
            "Reviewed evaluation finding finding_id=%d human_verdict=%s",
            finding_id,
            payload.human_verdict.value,
        )
        return self.get_finding(finding_id) or {**existing, **updates}

    def bulk_review(self, payload: EvaluationBulkReviewRequest, reviewer_email: str | None) -> int:
        """Record the same human-confirmed verdict on several findings at once."""
        reviewed_at = now_iso_utc()
        updated = 0
        for finding_id in payload.finding_ids:
            if self.get_finding(finding_id) is None:
                continue
            self._findings.update(
                updates={
                    "human_verdict": payload.human_verdict.value,
                    "reviewer_email": reviewer_email or "",
                    "reviewed_at": reviewed_at,
                    "review_notes": payload.review_notes or "",
                },
                pk_values=finding_id,
            )
            updated += 1
        logger.info("Bulk-reviewed %d evaluation findings", updated)
        return updated

    def delete_findings(self, finding_ids: list[int]) -> int:
        """Remove captured findings from the evaluation set (e.g. to discard a bad capture)."""
        self._findings.delete_many(finding_ids)
        logger.info("Deleted %d evaluation findings", len(finding_ids))
        return len(finding_ids)

    def compute_evaluation_matrix(self, project_id: int) -> EvaluationMatrixResponse:
        """Compute the 2x2 confusion matrix, statistical metrics, and cross-tabulation for a project."""
        rows = list(self._findings.rows)
        project_rows = [row for row in rows if int(row.get("project_id") or 0) == project_id]
        total_findings = len(project_rows)

        reviewed_rows = [r for r in project_rows if r.get("human_verdict")]
        reviewed_count = len(reviewed_rows)
        unreviewed_count = total_findings - reviewed_count

        # Build cross-tabulation: [bg_verdict][human_verdict] = count
        cross_tab: dict[str, dict[str, int]] = {}
        for r in reviewed_rows:
            bg_v = str(r.get("bimguard_verdict") or "NOT_APPLICABLE").upper()
            hv = str(r.get("human_verdict") or "").upper()
            if bg_v not in cross_tab:
                cross_tab[bg_v] = {}
            cross_tab[bg_v][hv] = cross_tab[bg_v].get(hv, 0) + 1

        # Binary confusion matrix at compliance action threshold (violation detection):
        # Positive = FAIL, Negative = PASS
        tp = 0
        fp = 0
        fn = 0
        tn = 0
        for r in reviewed_rows:
            bg_v = str(r.get("bimguard_verdict") or "").upper()
            hv = str(r.get("human_verdict") or "").upper()
            if bg_v == "FAIL" and hv == "FAIL":
                tp += 1
            elif bg_v == "FAIL" and hv == "PASS":
                fp += 1
            elif bg_v == "PASS" and hv == "FAIL":
                fn += 1
            elif bg_v == "PASS" and hv == "PASS":
                tn += 1

        binary_total = tp + fp + fn + tn
        accuracy = (tp + tn) / binary_total if binary_total > 0 else None
        precision = tp / (tp + fp) if (tp + fp) > 0 else None
        recall = tp / (tp + fn) if (tp + fn) > 0 else None
        specificity = tn / (tn + fp) if (tn + fp) > 0 else None
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision is not None and recall is not None and (precision + recall) > 0)
            else None
        )

        # Cohen's Kappa over all reviewed rows mapping bimguard verdict to human vocabulary
        # Vocabulary: PASS, FAIL, NOT_APPLICABLE, INDETERMINATE
        bimguard_to_human = {
            "PASS": "PASS",
            "FAIL": "FAIL",
            "MISSING": "INDETERMINATE",
            "WAIVED": "NOT_APPLICABLE",
            "NOT_APPLICABLE": "NOT_APPLICABLE",
        }
        cohens_kappa = None
        if reviewed_count > 0:
            agreed = 0
            cat_counts_bg: dict[str, int] = {}
            cat_counts_human: dict[str, int] = {}
            for r in reviewed_rows:
                bg_raw = str(r.get("bimguard_verdict") or "").upper()
                bg_mapped = bimguard_to_human.get(bg_raw, bg_raw)
                hv = str(r.get("human_verdict") or "").upper()
                if bg_mapped == hv:
                    agreed += 1
                cat_counts_bg[bg_mapped] = cat_counts_bg.get(bg_mapped, 0) + 1
                cat_counts_human[hv] = cat_counts_human.get(hv, 0) + 1

            p_o = agreed / reviewed_count
            all_cats = set(cat_counts_bg.keys()) | set(cat_counts_human.keys())
            p_e = sum(
                (cat_counts_bg.get(c, 0) / reviewed_count) * (cat_counts_human.get(c, 0) / reviewed_count)
                for c in all_cats
            )
            if abs(1.0 - p_e) < 1e-9:
                cohens_kappa = 1.0 if abs(p_o - 1.0) < 1e-9 else 0.0
            else:
                cohens_kappa = (p_o - p_e) / (1.0 - p_e)

        return EvaluationMatrixResponse(
            project_id=project_id,
            total_findings=total_findings,
            reviewed_findings=reviewed_count,
            unreviewed_findings=unreviewed_count,
            confusion_matrix=EvaluationConfusionMatrix(tp=tp, fp=fp, fn=fn, tn=tn),
            metrics=EvaluationMetrics(
                accuracy=round(accuracy, 4) if accuracy is not None else None,
                precision=round(precision, 4) if precision is not None else None,
                recall=round(recall, 4) if recall is not None else None,
                specificity=round(specificity, 4) if specificity is not None else None,
                f1=round(f1, 4) if f1 is not None else None,
                cohens_kappa=round(cohens_kappa, 4) if cohens_kappa is not None else None,
            ),
            cross_tabulation=cross_tab,
        )
