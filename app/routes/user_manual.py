"""User Manual page for the end-to-end BIM Guard workflow."""

from fasthtml.common import P, Span, Title
from monsterui.all import H1, Container, DivLAligned, DivVStacked, Grid, UkIcon

from app.components.layout import DashboardLayout
from app.components.themed_ui import SiteStyles
from app.components.ui import Card, CardContent, CardHeader, CardTitle, LinkButton

_WORKFLOW_STEPS = (
    {
        "title": "Create a project and upload the IFC model",
        "icon": "folder-plus",
        "description": (
            "Create a project record, add a clear name and description, and upload the IFC "
            "model that BIM Guard will inspect. The project becomes the shared source for the "
            "viewer, analysis tools, and reports."
        ),
        "result": "Result: the project appears in the project registry with its IFC file attached.",
        "links": (
            ("Create Project", "/projects/new", "primary"),
            ("View Projects", "/projects", "secondary"),
        ),
    },
    {
        "title": "Inspect the model in the 3D Viewer",
        "icon": "scan-eye",
        "description": (
            "Open the viewer and select the uploaded project. Orbit through the model and verify "
            "that the expected building elements are present before running compliance checks."
        ),
        "result": "Result: you confirm that the IFC can be loaded and visually inspected.",
        "links": (("Open Viewer", "/viewer", "primary"),),
    },
    {
        "title": "Add the compliance reference documents",
        "icon": "book-open",
        "description": (
            "Upload the PDF, Markdown, or text documents that define the requirements for the "
            "project. BIM Guard stores each source and extracts its text for rule creation."
        ),
        "result": "Result: the source documents and their extracted text are available in the library.",
        "links": (("Open Documents", "/library/documents", "primary"),),
    },
    {
        "title": "Extract and review compliance rules",
        "icon": "list-checks",
        "description": (
            "Use Rule Extraction Studio to turn a reference document into structured checks. "
            "Review the extracted rules in the Rules library, correct their parameters, and "
            "organize them into the folder you plan to use for analysis."
        ),
        "result": "Result: a reviewed rule set is ready to run against the IFC model.",
        "links": (
            ("Extract Rules", "/library/rules/extract", "primary"),
            ("Review Rules", "/library/rules", "secondary"),
        ),
    },
    {
        "title": "Run the appropriate analysis",
        "icon": "play-circle",
        "description": (
            "Choose ARCH for architectural and building-code checks, or MEP for mechanical, "
            "electrical, piping, corrosion, and clearance checks. Select the project and relevant "
            "rule folder, then start the analysis and review each result."
        ),
        "result": "Result: BIM Guard produces pass, warning, and failure findings for the project.",
        "links": (
            ("Run ARCH Analysis", "/analysis/ARCH", "primary"),
            ("Run MEP Analysis", "/analysis/MEP", "secondary"),
        ),
    },
    {
        "title": "Review and share the results",
        "icon": "file-check-2",
        "description": (
            "Open Reports to review generated BCF artifacts. Download a report for coordination, "
            "or open a BCF result in the 3D Viewer to inspect reported issues in model context."
        ),
        "result": "Result: findings are ready for coordination, correction, and another analysis cycle.",
        "links": (
            ("Open Reports", "/reports", "primary"),
            ("Return to Viewer", "/viewer", "secondary"),
        ),
    },
)


def _workflow_step(number: int, step: dict):
    """Render one numbered workflow step with its relevant page links."""
    return Card(
        CardHeader(
            DivLAligned(
                Span(
                    str(number),
                    cls=(
                        "inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full "
                        "bg-primary text-sm font-bold text-primary-foreground"
                    ),
                ),
                UkIcon(step["icon"], height=20, width=20, cls="text-muted-foreground shrink-0"),
                CardTitle(step["title"], cls="text-lg leading-snug"),
                cls="gap-3",
            )
        ),
        CardContent(
            P(step["description"], cls="text-sm leading-6 text-muted-foreground"),
            P(step["result"], cls="text-sm font-medium"),
            DivLAligned(
                *[
                    LinkButton(label, href=href, variant=variant)
                    for label, href, variant in step["links"]
                ],
                cls="flex-wrap gap-2 pt-2",
            ),
            cls="space-y-3",
        ),
        cls="h-full",
    )


def setup_routes(rt):
    """Register the User Manual route."""

    @rt("/user-manual")
    def user_manual_page():
        return Title("User Manual - BIM Guard"), DashboardLayout(
            Container(
                DivVStacked(
                    P("Guided workflow", cls=SiteStyles.caption),
                    H1("User Manual", cls="text-4xl font-bold tracking-tight"),
                    P(
                        "Follow these steps from IFC upload to a shareable compliance report. "
                        "Each step links directly to the BIM Guard page where the work happens.",
                        cls="max-w-3xl text-lg text-muted-foreground",
                    ),
                    cls="space-y-2",
                ),
                Card(
                    CardHeader(CardTitle("Before you start")),
                    CardContent(
                        P(
                            "Prepare an IFC model and the compliance references that apply to it. "
                            "For the most reliable results, model required element properties before "
                            "uploading; consult the Modeling Manual for IFC-specific guidance.",
                            cls="text-sm leading-6 text-muted-foreground",
                        ),
                        LinkButton(
                            "Open Modeling Manual",
                            href="/modeling-manual",
                            variant="secondary",
                        ),
                        cls="space-y-3",
                    ),
                ),
                Grid(
                    *[
                        _workflow_step(number, step)
                        for number, step in enumerate(_WORKFLOW_STEPS, start=1)
                    ],
                    cols=1,
                    cols_lg=2,
                    cls="gap-4",
                ),
                cls="space-y-6",
            ),
            content_cls="p-6 md:p-10 max-w-6xl mx-auto",
        )