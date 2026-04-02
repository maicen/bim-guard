from fasthtml.common import Div, Input, Script, Title
from app.components.layout import DashboardLayout
from monsterui.all import Button, H2


def setup_routes(rt):
    @rt("/viewer")
    def get():
        return Title("Viewer - BIM Guard"), DashboardLayout(
            Div(
                # Toolbar
                Div(
                    H2(
                        "3D Viewer",
                        cls="text-primary-foreground bg-primary px-4 py-2 rounded-md font-semibold",
                    ),
                    Div(
                        Button(
                            "Import IFC",
                            onclick="document.getElementById('ifc-file-input').click()",
                        ),
                        Input(
                            type="file",
                            id="ifc-file-input",
                            accept=".ifc",
                            cls="hidden",
                        ),
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
        viewerAPI.setupFileLoader('ifc-file-input');
    }
});
                """,
                    type="module",
                ),
                cls="h-full flex flex-col p-4 bg-muted/30 rounded-xl",
            )
        )
