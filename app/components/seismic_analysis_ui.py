"""Form and page for the Seismic (Blue Halo) bracing analysis.

    GET /analysis/seismic/{project_id}

The counterpart to :mod:`app.components.piping_analysis_ui`, built the same way
and styled from the same prototype. The scoped stylesheet is duplicated rather
than shared: the two pages are expected to diverge as each analysis grows its
own controls, and a shared style module would make every change to one a change
to both. Both emit their rules under ``.pp-scope`` and are never on the same
page, so the duplication costs nothing at runtime.

WHAT THE CLEARANCE FIELD CAN AND CANNOT DO

    Blue Halo takes its clearance from the jurisdiction config on disk
    (``data/config_en_1998_1_din_4149.json``), where it is recorded per brace
    type in **millimetres** -- 200.0mm for the config currently shipped.
    :func:`app.services.analysis_runner.run_analysis` exposes no override, and
    neither does :func:`run_seismic_analysis`, whose parameters are the config
    path, brace type, seismic zone and building type.

    So the field is offered in millimetres, not metres: millimetres is the unit
    the engine, the config and the reported findings all use, and a metres box
    invites a 1.5 that means 1500mm. It is prefilled from the config actually
    loaded, and the value is recorded with the run. The note under it says it
    does not yet change the envelope, rather than implying it does.
"""

from __future__ import annotations

import json
from pathlib import Path

from fasthtml.common import Div, Form, Input, Label, Option, P, Select, Span, Style, Title

from app.components.layout import DashboardLayout
from app.components.ui import NotFoundBlock
from app.logging_config import get_logger
from app.services.projects_service import ProjectsService

logger = get_logger(__name__)

_projects_service = ProjectsService()

#: Where the form posts. Kept here so the route module and the form cannot
#: drift apart.
RUN_ENDPOINT = "/analysis/seismic/run"

#: The jurisdiction config Blue Halo reads when nothing overrides it. Mirrors
#: ``phase_6d_seismic.DEFAULT_CONFIG_PATH``; imported as a path rather than from
#: that module so rendering the form does not pull in the engine.
DEFAULT_CONFIG_PATH = Path("data/config_en_1998_1_din_4149.json")

#: Shown when the config cannot be read, so the form still renders.
FALLBACK_CLEARANCE_MM = 200.0
FALLBACK_JURISDICTION = "EN 1998-1 + DIN 4149"


def active_clearance_config() -> tuple[str, float]:
    """Return the loaded config's ``(jurisdiction, clearance_mm)``.

    Read straight from the JSON rather than through
    :func:`load_clearance_config`, which builds the full envelope model and
    pulls the producer package in with it. The form needs two scalars.

    Returns:
        The jurisdiction label and the base clearance in millimetres. Falls back
        to the shipped defaults when the file is missing or malformed -- a form
        that cannot state the current clearance is still more useful than a 500.
    """
    try:
        raw = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("Seismic clearance config unreadable path=%s error=%s", DEFAULT_CONFIG_PATH, exc)
        return FALLBACK_JURISDICTION, FALLBACK_CLEARANCE_MM

    jurisdiction = str(raw.get("metadata", {}).get("jurisdiction") or FALLBACK_JURISDICTION)
    rules = raw.get("clearance_rules", {})
    try:
        clearance = float(rules.get("base_from_structure_mm", FALLBACK_CLEARANCE_MM))
    except (TypeError, ValueError):
        clearance = FALLBACK_CLEARANCE_MM
    return jurisdiction, clearance


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
#: Values are lifted from ``docs/experimental/bimguard-frontend-prototype-v1.html``
#: rather than re-derived: --primary #006BA6, --border #E2E8F0, --text-muted
#: #94A3B8, cards on #fff. Scoping matters because the app loads MonsterUI and
#: Basecoat globally; an unscoped ``.card`` here would collide with both.
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
.pp-scope textarea.inp{min-height:78px;resize:vertical}
.pp-scope .chk{display:flex;align-items:flex-start;gap:7px;font-size:12.5px;
  padding:4px 0;cursor:pointer}
/* The app's global sheets set appearance:none on every checkbox and paint it
   solid, which leaves ticked and unticked options looking identical. Restoring
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


def seismic_analysis_assets() -> tuple:
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
    can carry a description as well as a name, and wrapping makes the whole
    block the hit target without needing an id per option.
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


def _codes_field(jurisdiction: str) -> Div:
    """Render the standards / specification reference for this run."""
    return _field(
        "Seismic Rules, Specs and Codes",
        Input(
            type="text",
            id="seismic_codes",
            name="seismic_codes",
            value=jurisdiction,
            cls="inp",
        ),
        help_text=(
            "Prefilled from the jurisdiction config Blue Halo currently loads "
            f"({DEFAULT_CONFIG_PATH.as_posix()}). Findings cite the standards that "
            "config declares, so editing this records the reference for the run "
            "without changing which config is read."
        ),
    )


def _clearance_field(clearance_mm: float) -> Div:
    """Render the clearance threshold, in the millimetres the engine uses."""
    return _field(
        "Clearance Distance Threshold (mm)",
        Input(
            type="number",
            id="clearance_mm",
            name="clearance_mm",
            value=str(clearance_mm),
            min="0",
            step="1",
            cls="inp",
        ),
        help_text=(
            "Millimetres, the unit the config and every reported finding use. "
            f"The loaded config applies {clearance_mm:g}mm from structure. Blue Halo "
            "reads this from the config rather than the request, so the value is "
            "recorded with the run but does not yet resize the envelope."
        ),
    )


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


def seismic_analysis_form(project_id: int, projects: list[dict]) -> Div:
    """Build the Seismic (Blue Halo) run form.

    Args:
        project_id: Project to preselect. ``0`` leaves the picker empty.
        projects: Rows from :meth:`ProjectsService.list_projects`.

    Returns:
        The card containing the form. A plain POST, not an HTMX swap: the run
        is dispatched to a background thread and answered with a redirect, so
        there is no fragment to swap in.
    """
    jurisdiction, clearance_mm = active_clearance_config()
    return _card(
        "Seismic (Blue Halo) Analysis",
        "Select the model, the standards to cite, and the clearance to report against.",
        Form(
            P("Inputs", cls="seclabel"),
            Div(
                _project_field(projects, project_id),
                _codes_field(jurisdiction),
                cls="pp-grid",
            ),
            P("Clearance", cls="seclabel", style="margin-top:20px"),
            Div(_clearance_field(clearance_mm), _count_options_field(), cls="pp-grid"),
            Div(
                Span(
                    "The run starts in the background - you are taken straight "
                    "to the live workflow dashboard.",
                    style="font-size:11px;color:#94A3B8",
                ),
                Input(
                    type="submit",
                    value="Run Seismic Analysis",
                    cls="tbtn tbtn-lg tbtn-primary",
                ),
                cls="pp-foot",
                style="margin:20px -15px -15px",
            ),
            method="post",
            action=RUN_ENDPOINT,
        ),
    )


def seismic_analysis_page(project_id: int):
    """Render ``GET /analysis/seismic/{project_id}``.

    Args:
        project_id: Project to run against.

    Returns:
        The ``(Title, *assets, DashboardLayout)`` tuple the route returns, or a
        not-found block when the project does not exist.
    """
    project = _projects_service.get_project(project_id)
    if project is None:
        logger.warning("Seismic analysis page project not found project_id=%d", project_id)
        return Title("Seismic Analysis - BIM Guard"), DashboardLayout(
            NotFoundBlock("Project", "/projects", "Back to projects")
        )

    projects = _projects_service.list_projects()

    logger.info(
        "Seismic analysis page rendered project_id=%d projects=%d",
        project_id,
        len(projects),
    )

    project_label = project.get("name") or f"project {project_id}"
    return (
        Title("Seismic Analysis - BIM Guard"),
        *seismic_analysis_assets(),
        DashboardLayout(
            Div(
                Div(
                    P("Analysis", cls="pp-eyebrow"),
                    P("Seismic (Blue Halo)", cls="pp-title"),
                    P(
                        f"Bracing clearance and restraint checks across {project_label}.",
                        cls="pp-lead",
                    ),
                    style="margin-bottom:16px",
                ),
                seismic_analysis_form(project_id, projects),
                cls="pp-scope",
            )
        ),
    )
