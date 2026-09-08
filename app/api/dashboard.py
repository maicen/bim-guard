"""FastAPI router for dashboard connectivity status."""

from __future__ import annotations

import time
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.auth import CurrentUser, get_current_user
from app.modules.contracts import DashboardStatsResponse
from app.services.persistence import PersistenceService

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


@router.get("/stats", response_model=DashboardStatsResponse, summary="Get dashboard connectivity status")
def get_dashboard_stats(
    response: Response,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> DashboardStatsResponse:
    """Return database connectivity status for the dashboard's header chips.

    This used to also compute org-scoped project/document/rule counts and an
    "issues found" total (summing report_artifacts across every visible
    project) -- the single most expensive call on the dashboard, and the
    dashboard no longer renders any of those numbers (see the removal of the
    stat tiles from DashboardView.svelte). All that's left reading this
    response is App.svelte's checkHealth(), which only looks at db_ok and
    db_backend for the header's gateway/database status chips.
    """
    del current_user  # dependency enforces auth; the route itself is org-agnostic
    response.headers["Cache-Control"] = "private, max-age=5, stale-while-revalidate=15"
    return DashboardStatsResponse(
        db_ok=_probe_db_health(),
        db_backend=PersistenceService.DB_BACKEND.upper(),
    )
