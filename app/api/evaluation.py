"""FastAPI router for the human-validated compliance-evaluation workflow.

Captures a snapshot of BIM-Guard's own PASS/FAIL verdicts for review, then
lets a reviewer record the correct verdict against each one. Scoring those
two columns into a confusion matrix / accuracy / precision / recall / F1 is
out of scope here -- that's done by the separate bim-guard-evaluation
companion repo, which reads this router's endpoints back (see AGENTS.md).
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_evaluation_service
from app.api.projects import ProjectAccessChecker, get_project_access_checker
from app.auth import CurrentUser, get_current_user
from app.modules.contracts import (
    EvaluationBulkDeleteRequest,
    EvaluationBulkReviewRequest,
    EvaluationCaptureRequest,
    EvaluationCaptureResponse,
    EvaluationFindingContract,
    EvaluationFindingListResponse,
    EvaluationFindingReviewRequest,
    EvaluationMatrixResponse,
)
from app.services.evaluation_service import EvaluationService

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.post("/capture", response_model=EvaluationCaptureResponse, summary="Capture a run's results for evaluation")
def capture_evaluation_results(
    payload: EvaluationCaptureRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker)],
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> EvaluationCaptureResponse:
    """Snapshot the current ruleset run's PASS/FAIL verdicts into the evaluation set."""
    project_access(payload.project_id)
    try:
        count = service.capture_results(
            project_id=payload.project_id,
            rule_folder=payload.rule_folder,
            captured_by_email=current_user.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return EvaluationCaptureResponse(captured_count=count)


@router.get(
    "/matrix",
    response_model=EvaluationMatrixResponse,
    summary="Compute evaluation confusion matrix and agreement metrics for a project",
)
def get_evaluation_matrix(
    project_id: Annotated[int, Query()],
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker)],
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> EvaluationMatrixResponse:
    """Compute 2x2 confusion matrix, Cohen's kappa, precision, recall, and F1 over reviewed findings."""
    project_access(project_id)
    return service.compute_evaluation_matrix(project_id=project_id)


@router.get("/findings", response_model=EvaluationFindingListResponse, summary="List captured evaluation findings")
def list_evaluation_findings(
    project_id: Annotated[int, Query()],
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker)],
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
    rule_id: Annotated[Optional[int], Query()] = None,
    human_verdict: Annotated[Optional[str], Query()] = None,
) -> EvaluationFindingListResponse:
    """Return captured findings for one project, most recently captured first."""
    project_access(project_id)
    rows = service.list_findings(project_id=project_id, rule_id=rule_id, human_verdict=human_verdict)
    return EvaluationFindingListResponse(findings=[EvaluationFindingContract.model_validate(row) for row in rows])


@router.patch(
    "/findings/{finding_id}",
    response_model=EvaluationFindingContract,
    summary="Record a human-confirmed verdict for one captured finding",
)
def review_evaluation_finding(
    finding_id: int,
    payload: EvaluationFindingReviewRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> EvaluationFindingContract:
    """Confirm or override BIM-Guard's verdict for one finding."""
    try:
        row = service.review_finding(finding_id, payload, reviewer_email=current_user.email)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return EvaluationFindingContract.model_validate(row)


@router.post("/findings/bulk-review", summary="Record the same human-confirmed verdict on several findings")
def bulk_review_evaluation_findings(
    payload: EvaluationBulkReviewRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> dict:
    """Bulk-confirm/override several findings at once."""
    updated = service.bulk_review(payload, reviewer_email=current_user.email)
    return {"updated_count": updated}


@router.post("/findings/bulk-delete", summary="Remove captured findings from the evaluation set")
def bulk_delete_evaluation_findings(
    payload: EvaluationBulkDeleteRequest,
    service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> dict:
    """Discard captured findings (e.g. a bad or duplicate capture)."""
    deleted = service.delete_findings(payload.finding_ids)
    return {"deleted_count": deleted}
