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
    CountTableItemSpec,
    ItemsCountDataTable,
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
                                        FormLabel("Count Options"),
                                        Div(
                                            Div(
                                                Checkbox(
                                                    id="include_openings",
                                                    name="include_openings",
                                                    value="1",
                                                    checked=True,
                                                    cls="mr-2",
                                                ),
                                                Label(
                                                    "Include openings (IfcOpeningElement)",
                                                    for_="include_openings",
                                                    cls="text-sm cursor-pointer",
                                                ),
                                                cls="flex items-center gap-1",
                                            ),
                                            Div(
                                                Checkbox(
                                                    id="include_spaces",
                                                    name="include_spaces",
                                                    value="1",
                                                    checked=True,
                                                    cls="mr-2",
                                                ),
                                                Label(
                                                    "Include spaces (IfcSpace)",
                                                    for_="include_spaces",
                                                    cls="text-sm cursor-pointer",
                                                ),
                                                cls="flex items-center gap-1",
                                            ),
                                            Div(
                                                Checkbox(
                                                    id="include_type_definitions",
                                                    name="include_type_definitions",
                                                    value="1",
                                                    cls="mr-2",
                                                ),
                                                Label(
                                                    "Include type definitions (IfcElementType)",
                                                    for_="include_type_definitions",
                                                    cls="text-sm cursor-pointer",
                                                ),
                                                cls="flex items-center gap-1",
                                            ),
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
        include_openings = bool(form.get("include_openings"))
        include_spaces = bool(form.get("include_spaces"))
        include_type_definitions = bool(form.get("include_type_definitions"))
        result = _bim_guard_app.orchestrate_workflow(
            project_id,
            doc_ids,
            include_openings=include_openings,
            include_spaces=include_spaces,
            include_type_definitions=include_type_definitions,
        )

        if "error" in result:
            return Alert(result["error"], cls=AlertT.error)

        project = result["project"]
        ifc_count = result["ifc_element_count"]
        ifc_type_counts = result.get("ifc_type_counts") or {}
        ifc_totals = result.get("ifc_totals") or {}
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
            filters = ifc_totals.get("filters") or {}
            deltas = ifc_totals.get("excluded_or_added") or {}
            counts_table = ItemsCountDataTable(
                [
                    CountTableItemSpec(
                        label="Built Elements",
                        total=int(ifc_totals.get("built_elements", ifc_count)),
                        subtotal=int(ifc_totals.get("built_elements", ifc_count)),
                        note="Schema-aware building entities",
                    ),
                    CountTableItemSpec(
                        label="All Physical Elements",
                        total=int(ifc_totals.get("all_physical_elements", 0)),
                        subtotal=int(
                            ifc_totals.get("adjusted_physical_elements", ifc_count)
                        ),
                        note="Based on IfcElement",
                    ),
                    CountTableItemSpec(
                        label="All Products",
                        total=int(ifc_totals.get("all_products", 0)),
                        subtotal=int(ifc_totals.get("adjusted_products", 0)),
                        note="Based on IfcProduct",
                    ),
                ],
                caption="Built, physical, and product item counts",
                options_summary=(
                    "Options: "
                    f"openings={'on' if filters.get('include_openings', True) else 'off'} "
                    f"(count: {deltas.get('openings', 0)}), "
                    f"spaces={'on' if filters.get('include_spaces', True) else 'off'} "
                    f"(count: {deltas.get('spaces', 0)}), "
                    f"type defs={'on' if filters.get('include_type_definitions', False) else 'off'} "
                    f"(count: {deltas.get('type_definitions', 0)})."
                ),
                built_type_breakdown=ifc_type_counts,
            )

            ifc_detail = Div(
                counts_table,
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
