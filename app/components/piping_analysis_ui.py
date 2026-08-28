"""Form and page for the Piping (Corrosion) analysis.

    GET /analysis/piping/{project_id}

Extracted into ``app/components/`` rather than living in the route module for
the same reason :mod:`app.components.analysis_ui` is: the route decides *what*
to render, this decides *how*, and the two change for different reasons.

STYLING

    The markup follows ``docs/experimental/bimguard-frontend-prototype-v1.html``
    rather than the MonsterUI defaults used elsewhere. The prototype's rules are
    reproduced here as a scoped stylesheet -- every selector sits under
    ``.pp-scope`` so nothing here can restyle a page that does not opt in. The
    palette, spacing and control sizing are the prototype's own values, not
    approximations of them.

WHAT THE ENGINE SELECTOR CAN AND CANNOT DO

    MM-001 and XM-001 are the Path B comparators, gated by
    ``FEATURE_PATH_B_MM`` / ``FEATURE_PATH_B_XM`` (see
    :mod:`app.modules.config`). Both default off, which is why they are
    unchecked. With the flag off they are rendered disabled: a control that
    could not affect the run should not look like one that could.

    GC-001, CC-001 and MC-001 are wired into ``phase_6c_corrosion_ui.MECHANISMS``
    and run on every corrosion pass.
    :func:`app.services.analysis_runner.run_analysis` takes no engine subset, so
    clearing one of those boxes narrows what this page asks for and is recorded
    with the run, but does not currently stop that engine computing. The helper
    text under the selector says so rather than implying otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass

from fasthtml.common import Div, Form, Input, Label, Option, P, Select, Span, Style, Title

from app.components.layout import DashboardLayout
from app.components.ui import NotFoundBlock
from app.logging_config import get_logger
from app.modules.config import FEATURE_PATH_B_MM, FEATURE_PATH_B_XM
from app.services.documents_service import DocumentService
from app.services.projects_service import ProjectsService
from app.services.rules_service import RuleService

logger = get_logger(__name__)

_projects_service = ProjectsService()
_documents_service = DocumentService()
_rule_service = RuleService()

#: Where the form posts. Kept here so the route module and the form cannot
#: drift apart.
RUN_ENDPOINT = "/analysis/piping/run"


@dataclass(frozen=True)
class EngineOption:
    """One row of the corrosion engine selector.

    Attributes:
        code: Ruleset code, and the value submitted under ``engines``.
        label: Human name for the mechanism.
        detail: One line on what the engine looks for.
        default_checked: Whether the box starts ticked.
        flag_enabled: ``False`` when a feature flag keeps this engine from
            running at all, which renders the row disabled.
    """

    code: str
    label: str
    detail: str
    default_checked: bool
    flag_enabled: bool = True


def engine_options() -> tuple[EngineOption, ...]:
    """Return the five corrosion engines in queue order.

    Built per call rather than at import so the Path B flags are read from the
    environment the request is served in, not the one the module was first
    imported in.
    """
    return (
        EngineOption(
            "GC-001",
            "Galvanic corrosion",
            "Dissimilar metals in contact across the piping network.",
            default_checked=True,
        ),
        EngineOption(
            "CC-001",
            "Crevice corrosion",
            "Joints, flanges and fittings that trap stagnant fluid.",
            default_checked=True,
        ),
        EngineOption(
            "MC-001",
            "Microbially influenced corrosion",
            "Media and flow conditions that let biofilms establish.",
            default_checked=True,
        ),
        EngineOption(
            "MM-001",
            "Material / media comparator",
            "Pipe material against the media it carries.",
            default_checked=False,
            flag_enabled=FEATURE_PATH_B_MM,
        ),
        EngineOption(
            "XM-001",
            "Cross-material comparator",
            "Material changes along a run, against the galvanic series.",
            default_checked=False,
            flag_enabled=FEATURE_PATH_B_XM,
        ),
    )


#: The IFC count filters, matching the names ``orchestrate_workflow`` reads.
COUNT_OPTIONS: tuple[tuple[str, str, bool], ...] = (
    ("include_openings", "Include openings (IfcOpeningElement)", True),
    ("include_spaces", "Include spaces (IfcSpace)", True),
    ("include_type_definitions", "Include type definitions (IfcElementType)", False),
)


# ---------------------------------------------------------------------------
# Prototype stylesheet
# ---------------------------------------------------------------------------

#: The prototype's component rules, scoped to ``.pp-scope``.
#:
#: Values are lifted from the prototype rather than re-derived: --primary
#: #006BA6, --border #E2E8F0, --text-muted #94A3B8, cards on #fff. Scoping
#: matters because the app loads MonsterUI and Basecoat globally; an unscoped
#: ``.card`` here would collide with both.
_PROTO_CSS = """
/* The app shell runs in dark mode (html.dark, color-scheme:dark) while the
   prototype is a light design. Pinning the scope to light is what stops native
   controls -- checkboxes especially -- rendering dark inside a white card, and
   keeps inherited text from the global sheets off the prototype's palette. */
.pp-scope{font-size:13px;color:#0F172A;color-scheme:light;
  background:#F0F2F7;border-radius:10px;padding:18px 20px 24px}
.pp-scope p,.pp-scope label,.pp-scope span,.pp-scope div{color:inherit}
.pp-scope .card{background:#fff;border:1px solid #E2E8F0;border-radius:8px;
  transition:box-shadow .15s}
.pp-scope .card:hover{box-shadow:0 4px 14px rgba(15,23,42,.07)}
.pp-scope .card-h{padding:12px 15px;border-bottom:1px solid #E2E8F0}
.pp-scope .card-h .ttl{margin:0;font-size:13px;font-weight:600;color:#0F172A}
.pp-scope .card-h .sub{font-size:10.5px;color:#94A3B8;margin:2px 0 0}
.pp-scope .card-b{padding:15px}
.pp-scope .fld{display:block;font-size:11px;font-weight:600;margin-bottom:4px;color:#334155}
.pp-scope .fld .req{color:#BE3A34}
.pp-scope .inp{width:100%;font-size:12.5px;padding:8px 10px;border:1px solid #E2E8F0;
  border-radius:6px;background:#fff;font-family:inherit;color:#0F172A}
.pp-scope .inp:focus{outline:none;border-color:#006BA6;box-shadow:0 0 0 3px rgba(0,107,166,.12)}
.pp-scope .chk{display:flex;align-items:flex-start;gap:7px;font-size:12.5px;
  padding:4px 0;cursor:pointer}
/* The app's global sheets set appearance:none on every checkbox and paint it
   solid, which leaves ticked and unticked engines looking identical. Restoring
   the native control is what makes the selection readable. */
.pp-scope .chk input[type=checkbox]{margin:2px 0 0;flex-shrink:0;accent-color:#006BA6;
  -webkit-appearance:checkbox;appearance:auto;background:none;border:none;
  width:13px;height:13px;box-shadow:none;border-radius:0}
.pp-scope .chk.off{cursor:not-allowed;opacity:.55}
.pp-scope .chk .nm{font-weight:600}
.pp-scope .chk .ds{font-size:11px;color:#94A3B8;margin:2px 0 0;line-height:1.5}
.pp-scope .chkbox{border:1px solid #E2E8F0;border-radius:6px;padding:9px 12px;background:#FBFCFD}
.pp-scope .seclabel{font-size:11px;font-weight:700;letter-spacing:.6px;text-transform:uppercase;
  color:#006BA6;margin:0 0 10px;padding-bottom:6px;border-bottom:1px solid #E2E8F0}
.pp-scope .note{background:#F8FAFC;border-left:3px solid #00AEEF;padding:9px 12px;
  font-size:11px;color:#475569;border-radius:0 5px 5px 0;line-height:1.55}
.pp-scope .note.warn{background:#FFFBEB;border-left-color:#F97316}
.pp-scope .badge{display:inline-block;font-size:9.5px;font-weight:700;padding:2px 7px;
  border-radius:9px;letter-spacing:.3px}
.pp-scope .b-info{background:#E6F1F8;color:#006BA6}
.pp-scope .b-mute{background:#F1F5F9;color:#64748B}
.pp-scope .tbtn{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:600;
  padding:5px 11px;border-radius:5px;border:1px solid #E2E8F0;background:#fff;
  color:#0F172A;cursor:pointer;transition:.12s;white-space:nowrap;font-family:inherit;
  text-decoration:none}
/* The global sheets stretch every input to the full row; the prototype's
   button hugs its label. */
.pp-scope input.tbtn{display:inline-flex;width:auto;flex:0 0 auto}
.pp-scope .tbtn:hover:not(:disabled){background:#F8FAFC;border-color:#CBD5E1}
.pp-scope .tbtn-lg{font-size:12.5px;padding:9px 20px;border-radius:6px}
.pp-scope .tbtn-primary{background:#006BA6;border-color:#006BA6;color:#fff}
.pp-scope .tbtn-primary:hover:not(:disabled){background:#005A8C;border-color:#005A8C}
.pp-scope .tbtn:disabled{opacity:.42;cursor:not-allowed}
.pp-scope .pp-title{margin:0;font-size:20px;font-weight:700;letter-spacing:-.2px}
.pp-scope .pp-lead{font-size:11.5px;color:#94A3B8;margin:3px 0 0}
.pp-scope .pp-eyebrow{font-size:9.5px;letter-spacing:1.1px;text-transform:uppercase;
  color:#006BA6;font-weight:700;margin:0}
.pp-scope .pp-grid{display:grid;gap:14px}
.pp-scope .pp-foot{display:flex;justify-content:space-between;align-items:center;gap:12px;
  padding:13px 15px;border-top:1px solid #E2E8F0;background:#FBFCFD;border-radius:0 0 8px 8px}
.pp-scope .scroll{max-height:210px;overflow-y:auto}
"""


def piping_analysis_assets() -> tuple:
    """Return the scoped prototype stylesheet.

    Separate from the form so a page places it once, and so rendering the form
    twice cannot load the rules twice.
    """
    return (Style(_PROTO_CSS),)


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------


def _card(title: str, subtitle: str, *body) -> Div:
    """Render one prototype card with a header and body."""
    return Div(
        Div(
            Div(
                P(title, cls="ttl"),
                *([P(subtitle, cls="sub")] if subtitle else []),
            ),
            cls="card-h",
        ),
        Div(*body, cls="card-b"),
        cls="card",
    )


def _field(label: str, control, help_text: str = "", required: bool = False) -> Div:
    """Render one labelled control with optional helper copy."""
    caption = [label] + ([Span(" *", cls="req")] if required else [])
    return Div(
        Label(*caption, cls="fld"),
        control,
        *([P(help_text, cls="note", style="margin-top:6px")] if help_text else []),
    )


def _checkbox_row(
    *,
    name: str,
    value: str,
    label: str,
    detail: str = "",
    checked: bool = False,
    disabled: bool = False,
    suffix=None,
) -> Label:
    """Render one checkbox as a full-width clickable row.

    A ``Label`` wrapping the input rather than a ``for``-linked pair: the row
    carries a description as well as a name, and wrapping makes the whole block
    the hit target without needing an id per engine.
    """
    caption = [Span(label, cls="nm")]
    if suffix is not None:
        caption.append(suffix)
    return Label(
        Input(
            type="checkbox",
            name=name,
            value=value,
            checked=checked,
            disabled=disabled,
        ),
        Div(
            Div(*caption, style="display:flex;align-items:center;gap:7px;flex-wrap:wrap"),
            *([P(detail, cls="ds")] if detail else []),
        ),
        cls="chk off" if disabled else "chk",
    )


# ---------------------------------------------------------------------------
# Form sections
# ---------------------------------------------------------------------------


def _project_field(projects: list[dict], project_id: int) -> Div:
    """Render the project picker, preselecting the project in the URL."""
    options = [Option("- select a project -", value="", disabled=True, selected=not project_id)]
    for project in projects:
        pid = project.get("id")
        options.append(
            Option(
                project.get("name") or f"Project {pid}",
                value=str(pid),
                selected=pid == project_id,
            )
        )
    return _field(
        "Project (IFC Model)",
        Select(*options, id="project_id", name="project_id", required=True, cls="inp"),
        required=True,
    )


def _rule_folder_field(folders: list[dict]) -> Div:
    """Render the saved-ruleset picker."""
    options = [Option("All folders", value="", selected=True)] + [
        Option(f"{f['ruleset_id']} ({f['count']})", value=f["ruleset_id"]) for f in folders
    ]
    return _field(
        "Rule Folder",
        Select(*options, id="rule_folder", name="rule_folder", cls="inp"),
        help_text=(
            "Narrow the check to one saved corrosion ruleset - for example "
            "BIMGUARD-GC-001. Leave on 'All folders' to run against every "
            "corrosion rule in the library, including the seeded defaults."
        ),
    )


def _documents_field(documents: list[dict]) -> Div:
    """Render the client-document multi-select."""
    if documents:
        body = Div(
            *[
                _checkbox_row(
                    name="document_ids",
                    value=str(doc["id"]),
                    label=doc.get("filename") or f"Document {doc['id']}",
                )
                for doc in documents
            ],
            cls="chkbox scroll",
        )
    else:
        body = Div(
            P(
                "No documents have been uploaded yet. The check still runs - it "
                "just has no client specification to read alongside the model.",
                style="margin:0;font-size:11.5px;color:#94A3B8",
            ),
            cls="chkbox",
        )
    return _field("Documents", body)


def _engines_field(engines: tuple[EngineOption, ...]) -> Div:
    """Render the five-engine selector.

    Flag-gated engines are disabled and badged rather than hidden: knowing the
    comparator exists and is switched off is more useful than an absence.
    """
    rows = []
    for engine in engines:
        disabled = not engine.flag_enabled
        rows.append(
            _checkbox_row(
                name="engines",
                value=engine.code,
                label=f"{engine.code} - {engine.label}",
                detail=engine.detail,
                checked=engine.default_checked and engine.flag_enabled,
                disabled=disabled,
                suffix=Span(
                    "Feature flag off" if disabled else "Available",
                    cls="badge b-mute" if disabled else "badge b-info",
                ),
            )
        )

    gated = [engine.code for engine in engines if not engine.flag_enabled]
    always_on = (
        "GC-001, CC-001 and MC-001 run on every corrosion pass, so clearing one "
        "records a narrower request but does not yet stop that engine computing."
    )
    if gated:
        note = P(
            f"{' and '.join(gated)} sit behind the Path B feature flags and are "
            f"switched off in this deployment. {always_on}",
            cls="note warn",
            style="margin-top:8px",
        )
    else:
        note = P(always_on, cls="note", style="margin-top:8px")

    return Div(Label("Corrosion Engines", cls="fld"), Div(*rows, cls="chkbox"), note)


def _count_options_field() -> Div:
    """Render the IFC count filters."""
    return Div(
        Label("Count Options", cls="fld"),
        Div(
            *[
                _checkbox_row(name=name, value="1", label=label, checked=checked)
                for name, label, checked in COUNT_OPTIONS
            ],
            cls="chkbox",
        ),
    )


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def piping_analysis_form(
    project_id: int,
    projects: list[dict],
    folders: list[dict],
    documents: list[dict],
) -> Div:
    """Build the Piping (Corrosion) run form.

    Args:
        project_id: Project to preselect. ``0`` leaves the picker empty.
        projects: Rows from :meth:`ProjectsService.list_projects`.
        folders: Rows from :meth:`RuleService.list_folders`.
        documents: Rows from :meth:`DocumentService.list_documents`.

    Returns:
        The card containing the form. A plain POST, not an HTMX swap: the run
        is dispatched to a background thread and answered with a redirect to
        the live dashboard, so there is no fragment to swap in.
    """
    return _card(
        "Piping (Corrosion) Analysis",
        "Select the model, the rules to check it against, and the engines to queue.",
        Form(
            P("Inputs", cls="seclabel"),
            Div(
                _project_field(projects, project_id),
                _rule_folder_field(folders),
                _documents_field(documents),
                cls="pp-grid",
            ),
            P("Engines", cls="seclabel", style="margin-top:20px"),
            Div(_engines_field(engine_options()), _count_options_field(), cls="pp-grid"),
            Div(
                Span(
                    "The run starts in the background - you are taken straight "
                    "to the live workflow dashboard.",
                    style="font-size:11px;color:#94A3B8",
                ),
                Input(
                    type="submit",
                    value="Run Piping Analysis",
                    cls="tbtn tbtn-lg tbtn-primary",
                ),
                cls="pp-foot",
                style="margin:20px -15px -15px",
            ),
            method="post",
            action=RUN_ENDPOINT,
        ),
    )


def piping_analysis_page(project_id: int):
    """Render ``GET /analysis/piping/{project_id}``.

    Args:
        project_id: Project to run against.

    Returns:
        The ``(Title, *assets, DashboardLayout)`` tuple the route returns, or a
        not-found block when the project does not exist.
    """
    project = _projects_service.get_project(project_id)
    if project is None:
        logger.warning("Piping analysis page project not found project_id=%d", project_id)
        return Title("Piping Analysis - BIM Guard"), DashboardLayout(
            NotFoundBlock("Project", "/projects/archive", "Back to projects")
        )

    projects = _projects_service.list_projects()
    documents = _documents_service.list_documents()
    folders = _rule_service.list_folders()

    logger.info(
        "Piping analysis page rendered project_id=%d projects=%d documents=%d folders=%d",
        project_id,
        len(projects),
        len(documents),
        len(folders),
    )

    project_label = project.get("name") or f"project {project_id}"
    return (
        Title("Piping Analysis - BIM Guard"),
        *piping_analysis_assets(),
        DashboardLayout(
            Div(
                Div(
                    P("Analysis", cls="pp-eyebrow"),
                    P("Piping (Corrosion)", cls="pp-title"),
                    P(
                        f"Galvanic, crevice and microbial checks across {project_label}.",
                        cls="pp-lead",
                    ),
                    style="margin-bottom:16px",
                ),
                piping_analysis_form(project_id, projects, folders, documents),
                cls="pp-scope",
            )
        ),
    )
