"""FastAPI router for high-level compliance dashboard statistics and connectivity."""

from __future__ import annotations

import time
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, Query, Response

from app.api.dependencies import (
    get_document_access_service,
    get_membership_service,
    get_profile_service,
    get_ruleset_access_service,
)
from app.auth import CurrentUser, get_current_user
from app.logging_config import get_logger
from app.modules.contracts import DashboardStatsResponse
from app.services.document_access_service import DocumentAccessService
from app.services.membership_service import MembershipService
from app.services.persistence import PersistenceService
from app.services.pipeline_services import PipelineOrchestratorService
from app.services.profile_service import ProfileService
from app.services.ruleset_access_service import RulesetAccessService

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
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    document_access: Annotated[DocumentAccessService, Depends(get_document_access_service)],
    ruleset_access: Annotated[RulesetAccessService, Depends(get_ruleset_access_service)],
    organization_id: Optional[int] = Query(None, description="Filter by organization ID"),
    x_org_id: Optional[str] = Header(None, alias="X-Organization-Id"),
) -> DashboardStatsResponse:
    """Return high-level counts for projects, documents, rules, and connectivity.

    The actual counting lives in BIMGuard_App.run_dashboard() (the same
    orchestrator every analysis pipeline goes through) -- this route just
    resolves the effective org and hands the request-scoped services down to
    it, so there's one place that decides what "visible to this org" means
    for projects (ownership + grants), documents (per-org document grants),
    and rules (per-org ruleset grants), instead of that logic living
    separately in each route that happens to need a count.
    """
    response.headers["Cache-Control"] = "private, max-age=5, stale-while-revalidate=15"
    db_ok = _probe_db_health()
    backend = PersistenceService.DB_BACKEND.upper()

    effective_org_id: Optional[int] = organization_id
    if effective_org_id is None and x_org_id and x_org_id.strip().isdigit():
        effective_org_id = int(x_org_id.strip())

    stats = {
        "total_projects": 0,
        "total_documents": 0,
        "total_rules": 0,
        "issues_found": 0,
    }
    try:
        stats = PipelineOrchestratorService.get_dashboard_stats(
            organization_id=effective_org_id,
            user_id=current_user.id,
            memberships=memberships,
            profiles=profiles,
            ruleset_access=ruleset_access,
            document_access=document_access,
        )
    except Exception as exc:
        logger.warning("Could not fetch dashboard stats from orchestrator: %s", exc)

    return DashboardStatsResponse(
        total_projects=stats.get("total_projects", 0),
        total_documents=stats.get("total_documents", 0),
        total_rules=stats.get("total_rules", 0),
        issues_found=stats.get("issues_found", 0),
        db_ok=db_ok,
        db_backend=backend,
    )
