"""Dashboard page routes and high-level compliance stats view."""

# app/routes/dashboard.py

from fasthtml.common import Div, P, Title
from monsterui.all import (
    Alert,
    AlertT,
    H1,
    DivLAligned,
    DivFullySpaced,
    Grid,
)

from app.components.layout import DashboardLayout
from app.components.themed_ui import SiteStyles
from app.components.ui import BentoBox, LinkButton
from app.modules.orchestrator import BIMGuard_App
from app.services.persistence import PersistenceService

# Initialize orchestrator (provides run_dashboard stats)
_bim_guard_app = BIMGuard_App()


def _db_status_badge(is_connected: bool) -> Div:
    """Render a compact database status badge for the dashboard header."""
    tone_cls = (
        "bg-emerald-500/15 text-emerald-800 border-emerald-300"
        if is_connected
        else "bg-rose-500/15 text-rose-800 border-rose-300"
    )
    dot_cls = "bg-emerald-500" if is_connected else "bg-rose-500"
    status_text = "Connected" if is_connected else "Degraded"
    backend = PersistenceService.DB_BACKEND.upper()

    return DivLAligned(
        Div(cls=f"h-2.5 w-2.5 rounded-full {dot_cls}"),
        P(f"DB {backend}: {status_text}", cls="text-xs font-semibold"),
        cls=f"gap-2 rounded-full border px-3 py-1.5 {tone_cls}",
    )


def setup_routes(rt):
    """Register dashboard page routes."""

    @rt("/dashboard")
    def dashboard_page():
        stats = {
            "total_projects": 0,
            "total_documents": 0,
            "total_rules": 0,
        }
        db_ok = False

        try:
            stats = _bim_guard_app.run_dashboard()
            db_ok = True
        except Exception:
            # Keep dashboard available even if the configured DB backend is down.
            db_ok = False

        db_alert = (
            ()
            if db_ok
            else (
                Alert(
                    "Database connection is degraded. Showing fallback counters until connectivity is restored.",
                    cls=AlertT.warning,
                ),
            )
        )

        return Title("Dashboard - BIM Guard"), DashboardLayout(
            # Page Header
            DivFullySpaced(cls="items-end mb-8")(
                Div(cls="space-y-1")(
                    P("Overview", cls=SiteStyles.caption),
                    H1("Compliance Dashboard", cls=SiteStyles.h1),
                    _db_status_badge(db_ok),
                ),
                LinkButton(
                    "New Check",
                    href="/projects/new",
                    variant="primary",
                    cls="rounded-full px-6 py-2",
                ),
            ),
            *db_alert,
            # Bento Stats Grid
            Grid(cols=2, cols_md=2, cols_lg=4, cls="gap-6")(
                BentoBox(
                    "Total Projects",
                    str(stats["total_projects"]),
                    "Active in project registry",
                ),
                BentoBox(
                    "Documents",
                    str(stats["total_documents"]),
                    "Uploaded specification documents",
                ),
                BentoBox("Rules", str(stats["total_rules"]), "Compliance rules defined"),
                BentoBox("Issues Found (TODO)", "34", "-12 from last week"),
            ),
        )
