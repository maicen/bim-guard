"""FastAPI router for high-level compliance dashboard statistics and connectivity."""

from __future__ import annotations

import time
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.auth import CurrentUser, get_current_user
from app.logging_config import get_logger
from app.modules.contracts import DashboardStatsResponse
from app.services.persistence import PersistenceService
from app.services.pipeline_services import PipelineOrchestratorService

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
) -> DashboardStatsResponse:
    """Return high-level counts for projects, documents, rules, and connectivity."""
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

    return DashboardStatsResponse(
        total_projects=stats.get("total_projects", 0),
        total_documents=stats.get("total_documents", 0),
        total_rules=stats.get("total_rules", 0),
        issues_found=34,
        db_ok=db_ok,
        db_backend=backend,
    )

