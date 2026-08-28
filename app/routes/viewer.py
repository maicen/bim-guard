"""IFC model viewer routes and preload wiring for project model files."""

import json

from fasthtml.common import Div, Option, Script, Style, Title
from monsterui.all import H2, Button, ButtonT, Container, Form, FormLabel, Select

from app.components.layout import DashboardLayout
from app.components.ui import BackAction, NotFoundBlock
from app.services.projects_service import ProjectsService
from app.services.report_artifacts import ReportArtifactService

_projects_service = ProjectsService()
_report_artifact_service = ReportArtifactService()


def setup_routes(rt):
    """Register 3D viewer page routes."""

    @rt("/viewer")
    def viewer_page(
        project_id: int | None = None,
        bcf_artifact_id: int | None = None,
        element_guid: str | None = None,
        embed: bool = False,
    ):
        projects = [row for row in _projects_service.list_projects() if row.get("ifc_file_path")]
        project = _projects_service.get_project(project_id) if project_id is not None else None

        if project_id is not None and project is None:
            if embed:
                return Title("Project Not Found"), Div(
                    "Project not found.",
                    cls="flex items-center justify-center h-screen text-muted-foreground",
                )
            return Title("Not Found — BIM Guard"), DashboardLayout(
                Container(NotFoundBlock("Project", "/projects", "Back to Projects"))
            )

        bcf_artifact = (
            _report_artifact_service.get_bcf(bcf_artifact_id)
            if bcf_artifact_id is not None
            else None
        )
        artifact_project_id = int(bcf_artifact.get("project_id") or 0) if bcf_artifact else None
        if bcf_artifact_id is not None and (
            bcf_artifact is None or artifact_project_id != project_id
        ):
            if embed:
                return Title("BCF Export Not Found"), Div(
                    "BCF export not found.",
                    cls="flex items-center justify-center h-screen text-muted-foreground",
                )
            return Title("Not Found — BIM Guard"), DashboardLayout(
                Container(NotFoundBlock("BCF export", "/reports", "Back to Reports"))
            )

        ifc_url = ""
        if project and project.get("ifc_file_path"):
            ifc_url = f"/projects/{project_id}/ifc"
        bcf_url = (
            f"/reports/bcf/artifacts/{bcf_artifact_id}" if bcf_artifact is not None else ""
        )
        viewer_title = "3D Viewer"
        if project is not None:
            viewer_title = f"3D Viewer - {project.get('name', 'Project')}"
        preload_ifc_url = json.dumps(ifc_url)
        preload_bcf_url = json.dumps(bcf_url)
        preload_element_guid = json.dumps(element_guid)
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

        importmap_script = Script(
            '{"imports":{"web-ifc":"https://unpkg.com/web-ifc@0.0.77/web-ifc-api.js"}}',
            type="importmap",
        )
        viewer_script_template = """
import { initViewer } from '/static/js/viewer/ifc-viewer.js?v=error-highlight-2';

async function startViewer() {
    const viewerAPI = await initViewer('viewer-container');
    if (viewerAPI) {
        const ifcUrl = IFC_URL_PLACEHOLDER;
        if (ifcUrl) {
            await viewerAPI.loadIfc(ifcUrl);
        }
        const bcfUrl = BCF_URL_PLACEHOLDER;
        if (bcfUrl) {
            const elementGuid = ELEMENT_GUID_PLACEHOLDER;
            await viewerAPI.loadBcf(bcfUrl, elementGuid);
        }
    }
}

if (document.readyState === 'loading') {
    window.addEventListener('DOMContentLoaded', startViewer);
} else {
    startViewer();
}
"""
        initialization_script = Script(
            viewer_script_template.replace("IFC_URL_PLACEHOLDER", preload_ifc_url)
            .replace("BCF_URL_PLACEHOLDER", preload_bcf_url)
            .replace("ELEMENT_GUID_PLACEHOLDER", preload_element_guid),
            type="module",
        )

        if embed:
            return Title(viewer_title), Div(
                Div(
                    id="viewer-container",
                    cls="w-full h-full relative overflow-hidden",
                    style="width: 100vw; height: 100vh; margin: 0; padding: 0; background-color: hsl(var(--foreground) / 0.95);",
                ),
                Style(
                    """
html, body {
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    overflow: hidden;
    background-color: #020617;
}
#viewer-container {
    width: 100%;
    height: 100%;
}
#viewer-container .bimguard-topics-grid {
    display: grid;
    width: 100%;
    height: 100%;
    min-width: 0;
    min-height: 0;
}
#viewer-container .bimguard-viewport {
    display: block;
    width: 100%;
    height: 100%;
    min-width: 0;
    min-height: 0;
}
#viewer-container .bimguard-topics-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    padding: 0.5rem;
}
#viewer-container .bimguard-topics-toolbar bim-text-input {
    flex: 1 1 15rem;
}
#viewer-container .bimguard-topics-actions {
    display: flex;
    flex: 0 0 auto;
    gap: 0.5rem;
}
.bimguard-topic-dialog {
    width: min(22rem, calc(100vw - 2rem));
    max-width: calc(100vw - 2rem);
    padding: 0;
    border: 0;
    border-radius: 0.5rem;
    background: transparent;
}
.bimguard-topic-dialog::backdrop {
    background: rgb(0 0 0 / 0.55);
}
                    """
                ),
                importmap_script,
                initialization_script,
                cls="w-screen h-screen overflow-hidden m-0 p-0",
            )

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
                    cls="w-full rounded-xl shadow-xl overflow-hidden border border-border relative z-10",
                    style="background-color: hsl(var(--foreground) / 0.95);",
                ),
                Style(
                    """
#viewer-container {
    height: clamp(46rem, 78vh, 64rem);
}
#viewer-container .bimguard-topics-grid {
    display: grid;
    width: 100%;
    height: 100%;
    min-width: 0;
    min-height: 0;
}
#viewer-container .bimguard-viewport {
    display: block;
    width: 100%;
    height: 100%;
    min-width: 0;
    min-height: 0;
}
#viewer-container .bimguard-topics-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
}
#viewer-container .bimguard-topics-toolbar bim-text-input {
    flex: 1 1 15rem;
}
#viewer-container .bimguard-topics-actions {
    display: flex;
    flex: 0 0 auto;
    gap: 0.5rem;
}
.bimguard-topic-dialog {
    width: min(22rem, calc(100vw - 2rem));
    max-width: calc(100vw - 2rem);
    padding: 0;
    border: 0;
    border-radius: 0.5rem;
    background: transparent;
}
.bimguard-topic-dialog::backdrop {
    background: rgb(0 0 0 / 0.55);
}
@media (max-width: 900px) {
    #viewer-container {
        height: 104rem;
    }
    #viewer-container .bimguard-topics-toolbar {
        align-items: stretch;
        flex-direction: column;
    }
    #viewer-container .bimguard-topics-actions {
        flex-wrap: wrap;
    }
}
                    """
                ),
                importmap_script,
                initialization_script,
                cls="h-full flex flex-col p-4 bg-muted/30 rounded-xl",
            )
        )
