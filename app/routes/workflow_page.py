"""Page that hosts the live workflow dashboard.

    GET /workflow/{project_id}

A standalone page rather than a panel spliced into the analyse routes: the
dashboard is useful on its own — it can be left open while a large model runs —
and keeping it separate avoids editing ``analysis_ui.py``, which the upload work
is also changing.

The JSON the panel polls is served by :mod:`app.routes.workflow_api`.
"""

from __future__ import annotations

from fasthtml.common import Div, P, Title
from monsterui.all import H1

from app.components.layout import DashboardLayout
from app.components.themed_ui import SiteStyles
from app.components.ui import LinkButton, NotFoundBlock
from app.components.workflow_dashboard import workflow_dashboard, workflow_dashboard_assets
from app.logging_config import get_logger
from app.services.projects_service import ProjectsService

logger = get_logger(__name__)

_projects_service = ProjectsService()


def setup_routes(rt):
    """Register the workflow dashboard page."""

    @rt("/workflow/{project_id}", methods=["GET"])
    def workflow_page(project_id: int, slug: str = "corrosion"):
        """Render the dashboard for one project."""
        project = _projects_service.get_project(project_id)
        if project is None:
            return Title("Workflow - BIM Guard"), DashboardLayout(
                NotFoundBlock("Project", "/projects", "Back to projects")
            )

        logger.info("Workflow page project_id=%d slug=%s", project_id, slug)
        return (
            Title(f"{slug.title()} Workflow - BIM Guard"),
            *workflow_dashboard_assets(),
            DashboardLayout(
                Div(
                    Div(
                        P("Live workflow", cls=SiteStyles.caption),
                        H1(project.get("name") or f"Project {project_id}", cls=SiteStyles.h1),
                        cls="space-y-1 mb-6",
                    ),
                    workflow_dashboard(project_id, slug),
                    Div(
                        LinkButton(
                            "Back to analysis",
                            href=f"/analyze/{slug}?project_id={project_id}",
                            variant="secondary",
                        ),
                        cls="mt-6",
                    ),
                    cls="space-y-4",
                )
            ),
        )
