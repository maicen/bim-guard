# app/routes/dashboard.py

from fasthtml.common import A, Div, Li, P, Title, Ul
from monsterui.all import (
    DivFullySpaced,
    Grid,
    H1,
    NavContainer,
)
from app.components.layout import DashboardLayout
from app.components.themed_ui import SiteStyles
from app.components.ui import BentoBox, LinkButton
from app.services.projects_service import ProjectsService

# Initialize service
_projects_service = ProjectsService()


def setup_routes(rt):
    @rt("/dashboard")
    def dashboard_page():
        total_projects = _projects_service.total_projects()

        return Title("Dashboard - BIM Guard"), DashboardLayout(
            # Page Header
            DivFullySpaced(cls="items-end mb-8")(
                Div(cls="space-y-1")(
                    P("Overview", cls=SiteStyles.caption),
                    H1("Compliance Dashboard", cls=SiteStyles.h1),
                ),
                LinkButton(
                    "New Check",
                    href="/projects/new",
                    variant="primary",
                    cls="rounded-full px-6 py-2",
                ),
            ),
            # Bento Stats Grid
            Grid(cols=1, cols_md=2, cols_lg=4, cls="gap-6")(
                BentoBox(
                    "Total Projects", str(total_projects), "Active in project registry"
                ),
                BentoBox(
                    "Active Checks (demo)",
                    "5",
                    "3 require attention",
                ),
                BentoBox(
                    "Compliance Rate (demo)", "94%", "+2.1% improvement this month"
                ),
                BentoBox("Issues Found (demo)", "34", "-12 from last week"),
            ),
        )
