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
from app.constants import DEFAULT_ANALYSIS_TYPE, route_for_analysis_type
from app.logging_config import get_logger
from app.services.projects_service import ProjectsService

logger = get_logger(__name__)

_projects_service = ProjectsService()


def _slug_for(project: dict) -> str:
    """Return the analysis slug a project's own ``analysis_type`` maps to.

    Falls back to the default analysis type's slug when the column is blank or
    holds a value no longer in ``ANALYSIS_ROUTES`` -- an unrecognised type is
    not worth a 500 on a page that only picks a heading and a link.
    """
    analysis_type = (project.get("analysis_type") or "").strip()
    try:
        return route_for_analysis_type(analysis_type)
    except ValueError:
        logger.warning(
            "Unmapped analysis_type=%r on project_id=%s; falling back",
            analysis_type,
            project.get("id"),
        )
        return route_for_analysis_type(DEFAULT_ANALYSIS_TYPE)


def setup_routes(rt):
    """Register the workflow dashboard page."""

    @rt("/workflow/{project_id}", methods=["GET"])
    def workflow_page(project_id: int, slug: str = ""):
        """Render the dashboard for one project.

        Args:
            project_id: Project whose run to display.
            slug: Analysis to show. Defaults to the one the project's own
                ``analysis_type`` maps to -- a literal default cannot do that,
                and the previous ``"corrosion"`` meant a Halo project was
                titled "Corrosion Workflow" and linked back to the corrosion
                page. An explicit slug still wins, so existing links keep
                working.
        """
        project = _projects_service.get_project(project_id)
        if project is None:
            return Title("Workflow - BIM Guard"), DashboardLayout(
                NotFoundBlock("Project", "/projects", "Back to projects")
            )

        slug = slug.strip() or _slug_for(project)
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
