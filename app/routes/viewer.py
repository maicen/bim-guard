"""IFC model viewer routes and preload wiring for project model files."""

import json

from fasthtml.common import Div, Option, Script, Title
from monsterui.all import Button, ButtonT, Container, Form, FormLabel, H2, Select

from app.components.layout import DashboardLayout
from app.components.ui import BackAction, NotFoundBlock
from app.services.projects_service import ProjectsService

_projects_service = ProjectsService()


def setup_routes(rt):
    """Register 3D viewer page routes."""

    @rt("/viewer")
    def viewer_page(
        project_id: int | None = None,
        target_x: float | None = None,
        target_y: float | None = None,
        target_z: float | None = None,
    ):
        projects = [row for row in _projects_service.list_projects() if row.get("ifc_file_path")]
        project = _projects_service.get_project(project_id) if project_id is not None else None

        if project_id is not None and project is None:
            return Title("Not Found — BIM Guard"), DashboardLayout(
                Container(NotFoundBlock("Project", "/projects", "Back to Projects"))
            )

        ifc_url = ""
        if project and project.get("ifc_file_path"):
            ifc_url = f"/projects/{project_id}/ifc"
        viewer_title = "3D Viewer"
        if project is not None:
            viewer_title = f"3D Viewer - {project.get('name', 'Project')}"
        preload_ifc_url = json.dumps(ifc_url)

        # Optional fly-to target from a compliance failure — e.g. a "View in
        # 3D" link. Coordinates arrive in mm (Module 2's world unit); the
        # viewer's three.js scene works in metres (its default camera/grid
        # constants are metre-scaled), so convert here rather than pushing
        # that unit knowledge into the client script.
        focus_target = None
        if target_x is not None and target_y is not None and target_z is not None:
            focus_target = {"x": target_x / 1000, "y": target_y / 1000, "z": target_z / 1000}
        preload_focus_target = json.dumps(focus_target)
        project_options = [
            Option("Select a project", value="", selected=project_id is None),
            *[
                Option(
                    item.get("name", f"Project {item['id']}"),
                    value=str(item["id"]),
                    selected=item["id"] == project_id,
                )
                for item in projects
            ],
        ]

        return Title("Viewer - BIM Guard"), DashboardLayout(
            Div(
                # Toolbar
                Div(
                    H2(
                        viewer_title,
                        cls="text-primary-foreground bg-primary px-4 py-2 rounded-md font-semibold",
                    ),
                    Div(
                        Form(
                            Div(
                                FormLabel("Project", fr="viewer-project-id", cls="text-sm"),
                                Select(
                                    *project_options,
                                    id="viewer-project-id",
                                    name="project_id",
                                    onchange="this.form.requestSubmit()",
                                    cls="min-w-64",
                                ),
                                cls="space-y-1",
                            ),
                            Button("View Project", type="submit", cls=ButtonT.primary),
                            action="/viewer",
                            method="get",
                            cls="flex flex-col gap-2 sm:flex-row sm:items-end",
                        ),
                        BackAction(href="javascript:history.back()", title="Back"),
                        cls="flex flex-col gap-3 sm:flex-row sm:items-end",
                    ),
                    cls="mb-4 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between",
                ),
                # Viewer Container
                Div(
                    id="viewer-container",
                    cls="w-full h-full min-h-[75vh] rounded-xl shadow-xl overflow-hidden border border-border relative z-10",
                    style="background-color: hsl(var(--foreground) / 0.95);",
                ),
                # Initialization Script
                Script(
                    """
import { initViewer } from '/static/js/ifc-viewer.js';

window.addEventListener('DOMContentLoaded', async () => {
    const viewerAPI = await initViewer('viewer-container');
    if (viewerAPI) {
        const ifcUrl = IFC_URL_PLACEHOLDER;
        if (ifcUrl) {
            await viewerAPI.loadIfc(ifcUrl);
            const focusTarget = FOCUS_TARGET_PLACEHOLDER;
            if (focusTarget) {
                viewerAPI.focusOn(focusTarget.x, focusTarget.y, focusTarget.z);
            }
        }
    }
});
                """.replace("IFC_URL_PLACEHOLDER", preload_ifc_url).replace(
                        "FOCUS_TARGET_PLACEHOLDER", preload_focus_target
                    ),
                    type="module",
                ),
                cls="h-full flex flex-col p-4 bg-muted/30 rounded-xl",
            )
        )
