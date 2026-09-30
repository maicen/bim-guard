"""Evaluation and human-in-the-loop ground truth compliance review contracts."""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

__all__ = [
    'EvaluationHumanVerdict',
    'EvaluationCaptureRequest',
    'EvaluationCaptureResponse',
    'EvaluationFindingContract',
    'EvaluationFindingListResponse',
    'EvaluationFindingReviewRequest',
    'EvaluationBulkReviewRequest',
    'EvaluationBulkDeleteRequest',
    'EvaluationConfusionMatrix',
    'EvaluationMetrics',
    'EvaluationMatrixResponse',
]

class EvaluationHumanVerdict(str, Enum):
    """Reviewer-confirmed correct verdict for one captured evaluation finding."""

    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    INDETERMINATE = "INDETERMINATE"


class EvaluationCaptureRequest(BaseModel):
    """Payload to snapshot a ruleset run's current PASS/FAIL results into the evaluation set."""

    project_id: int
    rule_folder: str = Field(default="", description="Ruleset slug to capture; empty runs built-in code rules")
    rule_folders: list[str] = Field(
        default_factory=list, description="Several ruleset slugs to capture together, in addition to rule_folder"
    )

class EvaluationCaptureResponse(BaseModel):
    """Result of a capture request."""

    captured_count: int = Field(..., description="Number of findings inserted into evaluation_findings")

class EvaluationFindingContract(BaseModel):
    """One human-reviewable BIM-Guard verdict, captured for evaluation."""

    id: int
    project_id: int
    ifc_file_id: Optional[int] = None
    rule_id: Optional[int] = None
    rule_snapshot: dict[str, Any] = Field(default_factory=dict)
    element_global_id: str
    element_name: Optional[str] = None
    storey: Optional[str] = None
    space: Optional[str] = None
    bimguard_verdict: str
    bimguard_reason: Optional[str] = None
    captured_by_email: Optional[str] = None
    captured_at: Optional[str] = None
    human_verdict: Optional[EvaluationHumanVerdict] = None
    reviewer_email: Optional[str] = None
    reviewed_at: Optional[str] = None
    review_notes: Optional[str] = None
    created_at: Optional[str] = None

    @field_validator("rule_snapshot", mode="before")
    @classmethod
    def _parse_rule_snapshot(cls, value: Any) -> Any:
        """Accept a JSON string for `rule_snapshot`.

        Supabase's real jsonb column deserializes to a dict via postgrest,
        but the isolated SQLite tables PersistenceService hands tests (see
        get_isolated_sqlite_db) store dict columns as JSON text, so the same
        row shape comes back as a str in that path.
        """
        if isinstance(value, str):
            return json.loads(value) if value else {}
        return value

class EvaluationFindingListResponse(BaseModel):
    """List of captured evaluation findings, most recent first."""

    findings: list[EvaluationFindingContract]

class EvaluationFindingReviewRequest(BaseModel):
    """Payload to record a human verdict on one captured finding."""

    human_verdict: EvaluationHumanVerdict
    review_notes: Optional[str] = None

class EvaluationBulkReviewRequest(BaseModel):
    """Payload to record the same human verdict on several findings at once."""

    finding_ids: list[int] = Field(..., min_length=1)
    human_verdict: EvaluationHumanVerdict
    review_notes: Optional[str] = None

class EvaluationBulkDeleteRequest(BaseModel):
    """Payload to remove several captured findings from the evaluation set."""

    finding_ids: list[int] = Field(..., min_length=1)


class EvaluationConfusionMatrix(BaseModel):
    """Binary 2x2 confusion matrix (positive = violation / FAIL, negative = compliance / PASS)."""

    tp: int = Field(default=0, description="True Positives: BIM-Guard FAIL confirmed by human FAIL")
    fp: int = Field(default=0, description="False Positives: BIM-Guard FAIL refuted by human PASS")
    fn: int = Field(default=0, description="False Negatives: BIM-Guard PASS refuted by human FAIL")
    tn: int = Field(default=0, description="True Negatives: BIM-Guard PASS confirmed by human PASS")


class EvaluationMetrics(BaseModel):
    """Standard statistical validation metrics."""

    accuracy: Optional[float] = Field(default=None, description="(TP + TN) / Total")
    precision: Optional[float] = Field(default=None, description="TP / (TP + FP)")
    recall: Optional[float] = Field(default=None, description="Sensitivity: TP / (TP + FN)")
    specificity: Optional[float] = Field(default=None, description="TN / (TN + FP)")
    f1: Optional[float] = Field(default=None, description="Harmonic mean of precision and recall")
    cohens_kappa: Optional[float] = Field(default=None, description="Inter-rater agreement metric above chance")


class EvaluationMatrixResponse(BaseModel):
    """Response containing the confusion matrix, metrics, and cross-tabulation for a project."""

    project_id: int
    total_findings: int
    reviewed_findings: int
    unreviewed_findings: int
    confusion_matrix: EvaluationConfusionMatrix
    metrics: EvaluationMetrics
    cross_tabulation: dict[str, dict[str, int]] = Field(
        default_factory=dict,
        description="Full cross-tabulation: row=bimguard_verdict, col=human_verdict",
    )
