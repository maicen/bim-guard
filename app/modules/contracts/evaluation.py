"""Evaluation and human-in-the-loop ground truth compliance review contracts."""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

__all__ = ['EvaluationHumanVerdict', 'EvaluationCaptureRequest', 'EvaluationCaptureResponse', 'EvaluationFindingContract', 'EvaluationFindingListResponse', 'EvaluationFindingReviewRequest', 'EvaluationBulkReviewRequest', 'EvaluationBulkDeleteRequest']

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
