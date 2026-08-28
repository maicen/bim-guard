"""Shared rendering for the wizard's analysis landing pages.

The project setup wizard finishes by redirecting to ``/analyze/<slug>``, one
slug per :data:`app.constants.ANALYSIS_TYPES` entry. All three destinations show
the same thing — what the wizard just persisted, whether the project is ready
to be analysed, and the handoff into the engine that runs the check — so the
page is built once here and the route modules supply only the per-slug
specifics.

The engine itself is untouched: these pages hand off to the existing
``/analysis/*`` workflows rather than re-implementing the pipeline.
"""

from dataclasses import dataclass

from fasthtml.common import Div, Form, Input, P, Span, Style, Title
from monsterui.all import (
    H1,
    Alert,
    AlertT,
    DivFullySpaced,
    DivLAligned,
    Grid,
    Subtitle,
)

from app.components.layout import DashboardLayout
from app.components.themed_ui import SiteStyles
from app.components.ui import (
    BackAction,
    Card,
    CardContent,
    CardHeader,
    CardTitle,
    LinkButton,
    NotFoundBlock,
    SubmitButton,
)
from app.constants import ANALYSIS_ROUTES, normalise_analysis_types
from app.logging_config import get_logger
from app.services.projects_service import ProjectsService

logger = get_logger(__name__)

_projects_service = ProjectsService()


@dataclass(frozen=True)
class AnalysisSpec:
    """Everything that differs between the three analysis landing pages.

    Attributes:
        slug: URL segment under ``/analyze/``. Must be a value of
            :data:`app.constants.ANALYSIS_ROUTES`.
        analysis_type: The matching :data:`app.constants.ANALYSIS_TYPES` entry,
            used to label the page and to warn when a project was created for a
            different one.
        title: Page heading.
        summary: One-line description shown under the heading.
        run_href: Where the run button sends the user, or ``""`` when no engine
            exists for this analysis type yet.
        run_label: Caption for that button.
        pending_note: Shown instead of the run button when ``run_href`` is
            empty, explaining what is not built yet.
    """

    slug: str
    analysis_type: str
    title: str
    summary: str
    run_href: str = ""
    run_label: str = "Run analysis"
    pending_note: str = ""
    #: Phase 6 endpoint this page posts to via HTMX. When set it takes
    #: precedence over ``run_href``: the check runs in place and swaps its
    #: results into the page, rather than navigating to the older workflow.
    run_endpoint: str = ""

    def __post_init__(self) -> None:
        """Fail at import if the spec has drifted from ``ANALYSIS_ROUTES``.

        The wizard builds its redirect from ``ANALYSIS_ROUTES``, so a slug that
        no longer matches would send a freshly created project to a 404. Better
        to refuse to boot than to discover that at the end of the wizard.

        Raises:
            ValueError: if ``slug`` is not the registered slug for
                ``analysis_type``.
        """
        expected = ANALYSIS_ROUTES.get(self.analysis_type)
        if expected != self.slug:
            raise ValueError(
                f"AnalysisSpec slug {self.slug!r} does not match ANALYSIS_ROUTES entry "
                f"{expected!r} for analysis type {self.analysis_type!r}"
            )


#: Slug -> analysis type, derived from the single mapping in app.constants so
#: the two cannot drift apart.
SLUG_TO_ANALYSIS_TYPE: dict[str, str] = {slug: kind for kind, slug in ANALYSIS_ROUTES.items()}

_STATUS_CLS = {
    "Draft": "bg-muted text-muted-foreground",
    "Active": "bg-green-100 text-green-800",
    "Archived": "bg-yellow-100 text-yellow-800",
}

_KIND_CLS = {
    "standard": "bg-indigo-100 text-indigo-800",
    "document": "bg-teal-100 text-teal-800",
}


def _badge(text: str, cls: str) -> Span:
    """Render one small pill badge."""
    return Span(text, cls=f"inline-block px-2 py-0.5 rounded text-xs font-semibold {cls}")


def _fact(label: str, value: str) -> Div:
    """Render one label/value pair for the project summary grid."""
    return Div(
        P(label, cls="text-xs uppercase tracking-wide text-muted-foreground"),
        P(value or "-", cls="text-sm font-medium"),
        cls="space-y-0.5",
    )


def _project_card(project: dict) -> Card:
    """Summarise the project the wizard created.

    Only the project's own values appear here — the page's analysis type is
    already the heading, and showing it as a badge next to a differing stored
    value read as a contradiction.
    """
    status = project.get("status") or "Draft"
    fallback_name = f"Project {project.get('id')}"
    return Card(
        CardHeader(CardTitle(project.get("name") or fallback_name)),
        CardContent(
            DivLAligned(
                _badge(status, _STATUS_CLS.get(status, "bg-muted text-muted-foreground")),
                cls="gap-2 mb-4",
            ),
            P(
                project.get("description") or "No description was entered for this project.",
                cls="text-sm text-muted-foreground mb-4",
            ),
            Grid(
                _fact("Project ID", str(project.get("id", ""))),
                _fact("Country", project.get("country") or ""),
                _fact(
                    "Analysis types",
                    ", ".join(normalise_analysis_types(project.get("analysis_types"))),
                ),
                _fact("Created", str(project.get("created_at") or "")[:10]),
                # Grid ignores every per-breakpoint value when `cols` is set, so
                # the responsive steps have to be spelled out instead.
                cols_min=2,
                cols_sm=2,
                cols_md=4,
                cols_lg=4,
                cols_xl=4,
                cls="gap-4",
            ),
        ),
    )


def _model_card(project: dict) -> Card:
    """Report whether an IFC model is attached, without downloading it.

    Reads the stored reference rather than calling ``resolve_ifc_file``, which
    would materialise the object from Supabase Storage on every page view.
    """
    project_id = project.get("id")
    if project.get("ifc_file_path"):
        body = (
            DivLAligned(_badge("Model attached", "bg-green-100 text-green-800"), cls="gap-2 mb-3"),
            P(
                "The IFC model is ready to be read by the analysis engine.",
                cls="text-sm text-muted-foreground mb-4",
            ),
            DivLAligned(
                LinkButton("Open in viewer", href=f"/viewer?project_id={project_id}"),
                LinkButton(
                    "Download IFC",
                    href=f"/projects/{project_id}/ifc",
                    variant="secondary",
                ),
                cls="gap-2",
            ),
        )
    else:
        body = (
            DivLAligned(_badge("No model", "bg-yellow-100 text-yellow-800"), cls="gap-2 mb-3"),
            P(
                "No IFC model is attached to this project yet. Attach one before "
                "running the check — the engine has nothing to read without it.",
                cls="text-sm text-muted-foreground mb-4",
            ),
            LinkButton("Attach a model", href=f"/projects/{project_id}/edit"),
        )
    return Card(CardHeader(CardTitle("IFC Model")), CardContent(*body))


def _input_row(item: dict) -> Div:
    """Render one standard or client document as a list row."""
    kind = item.get("kind", "")
    return DivFullySpaced(
        Div(
            P(item.get("label") or "", cls="text-sm font-medium"),
            P(item.get("detail") or "", cls="text-xs text-muted-foreground"),
            cls="space-y-0.5",
        ),
        _badge(kind.title(), _KIND_CLS.get(kind, "bg-muted text-muted-foreground")),
        cls="items-center border-b border-border py-2 last:border-b-0",
    )


def _inputs_card(inputs: list[dict]) -> Card:
    """List the standards and client documents selected for the project."""
    if not inputs:
        return Card(
            CardHeader(CardTitle("Analysis Inputs")),
            CardContent(
                P(
                    "No standards or client documents are linked to this project.",
                    cls="text-sm text-muted-foreground",
                )
            ),
        )

    standards = sum(1 for item in inputs if item.get("kind") == "standard")
    documents = len(inputs) - standards
    return Card(
        CardHeader(CardTitle(f"Analysis Inputs ({standards} standards, {documents} documents)")),
        CardContent(Div(*[_input_row(item) for item in inputs], cls="divide-border")),
    )


def _run_form(spec: AnalysisSpec, project_id: int) -> Form:
    """Post to the Phase 6 endpoint and swap the results in below.

    An HTMX fragment swap rather than a navigation: the analysis can take
    seconds, and the page already shows the model and inputs it ran against.
    """
    spinner_id = f"run-spinner-{spec.slug}"
    return Form(
        Input(type="hidden", name="project_id", value=str(project_id)),
        SubmitButton(spec.run_label),
        Div(
            Span("Running the check…", cls="text-sm text-muted-foreground"),
            id=spinner_id,
            cls="htmx-indicator",
            style="display:none",
        ),
        Style(".htmx-indicator.htmx-request { display: flex !important; }"),
        hx_post=spec.run_endpoint,
        hx_target=f"#results-{spec.slug}",
        hx_indicator=f"#{spinner_id}",
        cls="space-y-3",
    )


def _next_step_card(spec: AnalysisSpec, project_id: int, has_model: bool) -> Card:
    """Render the handoff into the engine, or explain why there is none."""
    if spec.run_endpoint and has_model:
        body = Div(
            P(
                f"Run the {spec.analysis_type} check against this project's model "
                "and the inputs listed above.",
                cls="text-sm text-muted-foreground",
            ),
            _run_form(spec, project_id),
            cls="space-y-4",
        )
    elif spec.run_endpoint and not has_model:
        body = Alert(
            "Attach an IFC model to this project before running the check.",
            cls=AlertT.warning,
        )
    elif not spec.run_href:
        body = Alert(spec.pending_note, cls=AlertT.warning)
    elif not has_model:
        body = Div(
            Alert(
                "Attach an IFC model to this project before running the check.",
                cls=AlertT.warning,
            ),
            LinkButton(spec.run_label, href=spec.run_href, variant="secondary"),
            cls="space-y-4",
        )
    else:
        body = Div(
            P(
                f"Run the {spec.analysis_type} check against this project's model "
                "and the inputs listed above.",
                cls="text-sm text-muted-foreground",
            ),
            LinkButton(spec.run_label, href=spec.run_href),
            cls="space-y-4",
        )
    return Card(
        CardHeader(CardTitle("Next Step")),
        CardContent(
            body,
            Div(
                BackAction(href=f"/projects/{project_id}/edit", title="Edit project"),
                cls="mt-4",
            ),
        ),
    )


def _missing_project_page(spec: AnalysisSpec):
    """Render the page reached without a ``project_id`` query parameter."""
    return Title(f"{spec.title} - BIM Guard"), DashboardLayout(
        Div(
            H1(spec.title, cls=SiteStyles.h1),
            Alert(
                "No project was supplied. Pick one from the project list, or "
                "create a new one with the setup wizard.",
                cls=AlertT.warning,
            ),
            DivLAligned(
                LinkButton("Go to projects", href="/projects"),
                LinkButton("Start the wizard", href="/wizard", variant="secondary"),
                cls="gap-2",
            ),
            cls="space-y-4",
        )
    )


def _mismatch_alert(project: dict, spec: AnalysisSpec) -> tuple:
    """Warn when this page's analysis is not one the project selected.

    A project may be set up for several analyses, so this is a membership test,
    not an equality one: the page is only wrong if its type is absent from the
    list entirely. Setup lands on the project's primary analysis, so reaching a
    page outside the list means the URL was hand-edited or the project was
    changed afterwards. The page still renders; it just says so.
    """
    stored = normalise_analysis_types(project.get("analysis_types"))
    if not stored or spec.analysis_type in stored:
        return ()
    return (
        Alert(
            f"This project is set up for {', '.join(stored)}, not {spec.analysis_type}. "
            f"Showing the {spec.analysis_type} page anyway.",
            cls=AlertT.warning,
        ),
    )


def analysis_landing_page(spec: AnalysisSpec, project_id: int | None):
    """Render one analysis landing page for ``project_id``.

    Args:
        spec: Per-analysis-type page configuration.
        project_id: Project to show, or ``None`` when the route was reached
            without the query parameter. A blank ``?project_id=`` coerces to 0
            rather than None, and no project has id 0, so both are treated as
            "none supplied" instead of reporting a project that is not found.

    Returns:
        The ``(Title, DashboardLayout)`` tuple every full page route returns.
    """
    logger.info("Analyze page requested slug=%s project_id=%s", spec.slug, project_id)

    if not project_id or project_id < 0:
        return _missing_project_page(spec)

    project = _projects_service.get_project(project_id)
    if project is None:
        logger.warning(
            "Analyze page project not found slug=%s project_id=%d", spec.slug, project_id
        )
        return Title(f"{spec.title} - BIM Guard"), DashboardLayout(
            NotFoundBlock("Project", "/projects", "Back to projects")
        )

    inputs = _projects_service.get_analysis_inputs(project_id)
    has_model = bool(project.get("ifc_file_path"))

    logger.info(
        "Analyze page rendered slug=%s project_id=%d inputs=%d has_model=%s",
        spec.slug,
        project_id,
        len(inputs),
        has_model,
    )

    return Title(f"{spec.title} - BIM Guard"), DashboardLayout(
        Div(
            Div(
                P("Analysis", cls=SiteStyles.caption),
                H1(spec.title, cls=SiteStyles.h1),
                Subtitle(spec.summary),
                cls="space-y-1 mb-6",
            ),
            *_mismatch_alert(project, spec),
            _project_card(project),
            # Grid's own defaults give 1 column up to sm and 2 from md, which is
            # what these two cards want; passing `cols` would pin every
            # breakpoint to the same value.
            Grid(_model_card(project), _inputs_card(inputs), cls="gap-6"),
            _next_step_card(spec, project_id, has_model),
            # HTMX swap target for the Phase 6 run endpoints.
            Div(id=f"results-{spec.slug}"),
            cls="space-y-6",
        )
    )
