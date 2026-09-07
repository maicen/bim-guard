"""FastAPI router for high-level compliance dashboard statistics and connectivity."""

from __future__ import annotations

import time
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, Query, Response

from app.api.dependencies import (
    get_membership_service,
    get_profile_service,
    get_projects_service,
)
from app.api.projects import visible_project_rows
from app.auth import CurrentUser, get_current_user
from app.logging_config import get_logger
from app.modules.contracts import DashboardStatsResponse
from app.services.membership_service import MembershipService
from app.services.persistence import PersistenceService
from app.services.pipeline_services import PipelineOrchestratorService
from app.services.profile_service import ProfileService
from app.services.projects_service import ProjectsService
from app.services.report_artifacts import ReportArtifactService

logger = get_logger(__name__)

router = APIRouter()


_DB_HEALTH_CACHE = {
    "checked_at": 0.0,
    "ok": False,
}
_DB_HEALTH_TTL = 15.0


def _probe_db_health() -> bool:
    now = time.monotonic()
    if (now - _DB_HEALTH_CACHE["checked_at"]) <= _DB_HEALTH_TTL:
        return bool(_DB_HEALTH_CACHE["ok"])

    ok = False
    try:
        db = PersistenceService.get_db()
        db.table("projects").select("id").limit(1).execute()
        ok = True
    except Exception:
        ok = False

    _DB_HEALTH_CACHE["checked_at"] = now
    _DB_HEALTH_CACHE["ok"] = ok
    return ok


@router.get("/stats", response_model=DashboardStatsResponse, summary="Get dashboard summary stats")
def get_dashboard_stats(
    response: Response,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ProjectsService, Depends(get_projects_service)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    organization_id: Optional[int] = Query(None, description="Filter by organization ID"),
    x_org_id: Optional[str] = Header(None, alias="X-Organization-Id"),
) -> DashboardStatsResponse:
    """Return high-level counts for projects, documents, rules, and connectivity.

    total_documents and total_rules are platform-wide: the `documents` and
    `rules` tables carry no organization_id or project_id, so there is no
    real per-org relationship to scope them by (adding one would need a
    schema migration, not just a query change).

    total_projects and issues_found ARE scoped to the caller's visible
    projects -- and, when an organization_id is given (via query or
    X-Organization-Id header), further narrowed to that org -- using the
    same visibility rules as GET /api/projects, so none of these ever
    disagree about which projects are in view.
    """
    response.headers["Cache-Control"] = "private, max-age=5, stale-while-revalidate=15"
    db_ok = _probe_db_health()
    backend = PersistenceService.DB_BACKEND.upper()

    stats = {
        "total_projects": 0,
        "total_documents": 0,
        "total_rules": 0,
    }
    try:
        stats = PipelineOrchestratorService.get_dashboard_stats()
    except Exception as exc:
        logger.warning("Could not fetch dashboard stats from orchestrator: %s", exc)

    effective_org_id: Optional[int] = organization_id
    if effective_org_id is None and x_org_id and x_org_id.strip().isdigit():
        effective_org_id = int(x_org_id.strip())

    visible_rows = visible_project_rows(
        service.list_projects(),
        user_id=current_user.id,
        organization_id=effective_org_id,
        memberships=memberships,
        profiles=profiles,
    )
    total_projects = len(visible_rows)

    # "Issues Identified" is the sum of each visible project's most recent
    # architectural-analysis run (BCF export persists one report_artifacts
    # row with a real issue_count every time run_analysis() executes -- see
    # ArchAnalysisService.run_analysis). Projects never analyzed, or issues
    # from corrosion engines (which don't persist a report artifact),
    # aren't reflected -- this is real analysis history, not a live
    # recount of every engine, but it replaces what used to be a constant
    # that never changed regardless of org, project, or analysis results.
    issues_found = 0
    try:
        visible_project_ids = {row.get("id") for row in visible_rows}
        latest_issue_count_by_project: dict[int, int] = {}
        for artifact in ReportArtifactService().list_bcf():  # newest first
            pid = artifact.get("project_id")
            if pid not in latest_issue_count_by_project:
                latest_issue_count_by_project[pid] = int(artifact.get("issue_count") or 0)
        issues_found = sum(
            count
            for pid, count in latest_issue_count_by_project.items()
            if pid in visible_project_ids
        )
    except Exception as exc:
        logger.warning("Could not compute issues_found from report artifacts: %s", exc)

    return DashboardStatsResponse(
        total_projects=total_projects,
        total_documents=stats.get("total_documents", 0),
        total_rules=stats.get("total_rules", 0),
        issues_found=issues_found,
        db_ok=db_ok,
        db_backend=backend,
    )

