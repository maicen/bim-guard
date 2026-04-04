import json
from pathlib import Path

from fasthtml.common import Div, Script, Title
from app.components.layout import DashboardLayout
from app.components.ui import BackAction
from fastlite import database
from monsterui.all import H2


DB_PATH = Path("data") / "bimguard.sqlite"
_db = database(str(DB_PATH))
_projects = _db["projects"]


def setup_routes(rt):
    @rt("/viewer")
    def get(project_id: int | None = None):
        project = _projects.get(project_id) if project_id is not None else None
        ifc_url = ""
        if project and project.get("ifc_file_path"):
            ifc_url = f"/projects/{project_id}/ifc"
        viewer_title = "3D Viewer"
        if project is not None:
            viewer_title = f"3D Viewer - {project.get('name', 'Project')}"
        preload_ifc_url = json.dumps(ifc_url)

        return Title("Viewer - BIM Guard"), DashboardLayout(
            Div(
                # Toolbar
                Div(
                    H2(
                        viewer_title,
                        cls="text-primary-foreground bg-primary px-4 py-2 rounded-md font-semibold",
                    ),
                    Div(
                        BackAction(href="javascript:history.back()", title="Back"),
                        cls="flex gap-2",
                    ),
                    cls="flex justify-between items-center mb-4",
                ),
                # Viewer Container
                Div(
                    id="viewer-container",
                    cls="w-full h-full min-h-[75vh] bg-black bg-opacity-95 rounded-xl shadow-xl overflow-hidden border border-gray-800 relative z-10",
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
            const response = await fetch(ifcUrl);
            if (response.ok) {
                const blob = await response.blob();
                const file = new File([blob], ifcUrl.split('/').pop() || 'project.ifc', {
                    type: 'application/octet-stream'
                });
                await viewerAPI.loadIfc(file);
            }
        }
    }
});
                """.replace("IFC_URL_PLACEHOLDER", preload_ifc_url),
                    type="module",
                ),
                cls="h-full flex flex-col p-4 bg-muted/30 rounded-xl",
            )
        )
