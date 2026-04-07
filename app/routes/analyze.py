from fasthtml.common import Div, Form, Option, P, Request, Title
from app.components.ui import (
    Alert,
    AlertT,
    Card,
    CardContent,
    CardHeader,
    CardTitle,
    Checkbox,
    FormLabel,
    Label,
    Select,
    SubmitButton,
)
from monsterui.all import Container, H1

from app.components.layout import DashboardLayout
from app.modules.orchestrator import BIMGuard_App
from app.services.documents_service import DocumentService
from app.services.projects_service import ProjectsService

_bim_guard_app = BIMGuard_App()
_projects_service = ProjectsService()
_documents_service = DocumentService()


def setup_routes(rt):
    @rt("/analysis/run")
    def analysis_run():
        projects = _projects_service.list_projects()
        documents = _documents_service.list_documents()

        project_options = [
            Option("— select a project —", value="", disabled=True, selected=True)
        ] + [
            Option(p.get("name", f"Project {p['id']}"), value=str(p["id"]))
            for p in projects
        ]

        doc_checkboxes = []
        for doc in documents:
            doc_checkboxes.append(
                Div(
                    Checkbox(
                        id=f"doc_{doc['id']}",
                        name="document_ids",
                        value=str(doc["id"]),
                        cls="mr-2",
                    ),
                    Label(
                        doc.get("filename", f"Document {doc['id']}"),
                        for_=f"doc_{doc['id']}",
                        cls="text-sm cursor-pointer",
                    ),
                    cls="flex items-center gap-1",
                )
            )

        if not doc_checkboxes:
            doc_checkboxes = [
                P("No documents uploaded yet.", cls="text-sm text-muted-foreground")
            ]

        return Title("Run Analysis - BIM Guard"), DashboardLayout(
            Container(
                Div(
                    Card(
                        CardHeader(CardTitle("Select Inputs")),
                        CardContent(
                            Form(
                                Div(
                                    Div(
                                        FormLabel(
                                            "Project (IFC Model)", fr="project_id"
                                        ),
                                        Select(
                                            *project_options,
                                            id="project_id",
                                            name="project_id",
                                            required=True,
                                        ),
                                    ),
                                    Div(
                                        FormLabel("Documents"),
                                        Div(
                                            *doc_checkboxes,
                                            cls="space-y-2 border rounded-md p-3 bg-muted/30",
                                        ),
                                    ),
                                    Div(
                                        SubmitButton(
                                            "Run Analysis",
                                            variant="primary",
                                        ),
                                        Div(
                                            P(
                                                "Running analysis…",
                                                cls="text-sm text-muted-foreground",
                                            ),
                                            id="run-spinner",
                                            cls="htmx-indicator",
                                            style="display:none",
                                        ),
                                        cls="flex items-center gap-4",
                                    ),
                                ),
                                hx_post="/analysis/results",
                                hx_target="#analysis-results",
                                hx_swap="innerHTML",
                                hx_indicator="#run-spinner",
                            ),
                        ),
                    ),
                    Div(id="analysis-results"),
                )
            )
        )

    @rt("/analysis/results", methods=["POST"])
    async def analysis_run_post(req: Request):
        form = await req.form()
        project_id_raw = form.get("project_id") or ""
        if not project_id_raw:
            return Alert("Please select a project.", cls=AlertT.error)
        try:
            project_id = int(project_id_raw)
        except ValueError:
            return Alert("Invalid project selection.", cls=AlertT.error)

        doc_ids = [int(v) for v in form.getlist("document_ids") if v]
        result = _bim_guard_app.orchestrate_workflow(project_id, doc_ids)

        if "error" in result:
            return Alert(result["error"], cls=AlertT.error)

        project = result["project"]
        ifc_count = result["ifc_element_count"]
        ifc_type_counts = result.get("ifc_type_counts") or {}
        ifc_error = result["ifc_error"]

        # IFC summary card
        if ifc_error:
            ifc_detail = P(
                f"IFC parsing error: {ifc_error}", cls="text-sm text-destructive"
            )
        elif not _projects_service.resolve_ifc_file(project_id):
            ifc_detail = P(
                "No IFC file attached to this project.",
                cls="text-sm text-muted-foreground",
            )
        else:
            type_lines = [
                P(f"{element_type}: {count}", cls="text-sm text-muted-foreground")
                for element_type, count in sorted(ifc_type_counts.items())
            ]
            ifc_detail = Div(
                P(f"Total building elements: {ifc_count}", cls="text-sm font-medium"),
                *(
                    type_lines
                    if type_lines
                    else [
                        P(
                            "No IFC element types found.",
                            cls="text-sm text-muted-foreground",
                        )
                    ]
                ),
                cls="space-y-1",
            )

        doc_cards = []
        for doc in result["documents"]:
            doc_cards.append(
                Card(
                    CardHeader(CardTitle(doc["filename"] or "Untitled document")),
                    CardContent(
                        P(
                            f"{doc['section_count']} text sections extracted.",
                            cls="text-sm text-muted-foreground",
                        )
                    ),
                )
            )

        stub_notice = Alert(
            "Rule validation (Module 3–5) is not yet implemented — results will appear here once integrated.",
            cls=AlertT.info if hasattr(AlertT, "info") else "",
        )

        return Div(
            Card(
                CardHeader(CardTitle(project.get("name", "Project"))),
                CardContent(ifc_detail),
            ),
            *(
                doc_cards
                or [P("No documents selected.", cls="text-sm text-muted-foreground")]
            ),
            stub_notice,
            cls="space-y-4",
        )

    @rt("/reports")
    def reports():
        return Title("Reports - BIM Guard"), DashboardLayout(
            Container(
                Div(
                    H1("Reports", cls="text-3xl font-bold mb-4 tracking-tight"),
                    P(
                        "Reports will be available once the compliance pipeline is implemented.",
                        cls="text-muted-foreground mb-6",
                    ),
                    Card(
                        CardHeader(CardTitle("Coming Soon")),
                        CardContent(
                            P(
                                "Add report filters, history, and export actions here.",
                                cls="text-sm text-muted-foreground",
                            )
                        ),
                    ),
                    cls="container mx-auto py-6",
                )
            )
        )
