"""Five-step project setup wizard: UI, state and validation only.

    Step 1  Project details -- eight fields on one screen
    Step 2  IFC model -- dropped, stored immediately, carried as a reference
    Step 3  Documents -- at least one
    Step 4  Settings -- standards and config, all optional
    Step 5  Review -- read-only summary, then Create Project

WHAT THIS MODULE DOES NOT DO

    It does not write anything. No persistence import, no create call, no POST
    to a create endpoint. Step 5 builds a dict via :func:`emit_form_data` and
    hands it to the ``on_submit`` callback the caller supplies;
    :mod:`app.routes.wizard_routes` is what turns that into a project row.

    The two things the wizard cannot do for itself are supplied the same way:
    the document rows for step 3 are passed into :func:`handle_wizard_get` and
    :func:`handle_wizard_post`, and the model dropped at step 2 is stored by
    the endpoint named in :data:`UPLOAD_ENDPOINT`.

WHY IT KEEPS NO STATE

    Each step posts the whole form and the answers so far come back as hidden
    inputs. Nothing is held between requests, so a reload cannot resurrect a
    half-finished project and two tabs cannot overwrite each other.

    One field cannot travel that way: an ``<input type=file>`` value is not
    settable from script, so a model chosen at step 2 would be gone by step 3.
    It is stored the moment it is dropped and only the returned reference rides
    forward, in ``ifc_file_reference``.

WHAT "UNLOCKED" MEANS

    Two layers, and the server one is the real one. The server renders exactly
    one step and refuses to advance past a step that does not validate, so a
    hand-made POST cannot skip ahead. The browser re-checks the same fields as
    you type and enables Next only when they pass. :func:`validate_step` is the
    single definition of valid; the script only decides whether a button looks
    pressable.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping

from fasthtml.common import (
    Button,
    Div,
    Form,
    Input,
    Label,
    NotStr,
    Option,
    P,
    Script,
    Select,
    Span,
    Textarea,
)

from app.components.ui import (
    Card,
    CardContent,
    CardHeader,
    CardTitle,
    Checkbox,
)
from app.constants import (
    ANALYSIS_TYPES,
    COUNTRIES,
    DEFAULT_COUNTRY,
    NOTEBOOK_STANDARDS,
    PROJECT_TYPES,
)
from app.logging_config import get_logger

logger = get_logger(__name__)

#: Where step 2's drop zone sends the file. Stored the instant it is dropped,
#: because a file input cannot be carried forward as a hidden value.
UPLOAD_ENDPOINT = "/wizard/upload"

#: Where every step posts.
FORM_ENDPOINT = "/wizard"

TOTAL_STEPS = 5

#: Step number -> (title, one-line lead).
STEP_TITLES: dict[int, tuple[str, str]] = {
    1: ("Project details", "Tell us about the project. Everything here is needed."),
    2: ("IFC model", "Drop the model in. It uploads as soon as you do."),
    3: ("Documents", "Which uploaded documents should the analysis read?"),
    4: ("Settings", "Standards and configuration. All optional — you can skip this."),
    5: ("Review", "Check it over, then create the project."),
}

#: Scalar fields, in the order step 1 renders them.
_SCALAR_KEYS: tuple[str, ...] = (
    "project_name",
    "description",
    "location",
    "project_size_sqm",
    "buildings",
    "floors",
    "project_type",
    "ifc_file_reference",
    "ifc_filename",
    "ifc_size_bytes",
    "status",
)

#: Multi-valued fields, which carry one hidden input per selected value.
_MULTI_KEYS: tuple[str, ...] = ("analysis_types", "document_ids", "standards_codes")

#: Optional analysis configuration collected on step 4, with its defaults.
#: These are the same filters the analysis pages offer, so a project set up
#: here starts from the same place a run would.
SETTINGS_FLAGS: tuple[tuple[str, str, bool], ...] = (
    ("include_openings", "Include openings (IfcOpeningElement)", True),
    ("include_spaces", "Include spaces (IfcSpace)", True),
    ("include_type_definitions", "Include type definitions (IfcElementType)", False),
)

#: Statuses a new project may be created in.
STATUS_CHOICES: tuple[str, ...] = ("Draft", "Active")


# ---------------------------------------------------------------------------
# Validation -- the single definition of "valid"
# ---------------------------------------------------------------------------


def _as_list(value: Any) -> list[str]:
    """Coerce a possibly-missing, possibly-scalar field to a list of strings."""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(v) for v in value if str(v).strip()]
    text = str(value).strip()
    return [text] if text else []


def _positive_number(raw: Any) -> float | None:
    """Return ``raw`` as a positive number, or ``None`` when it is not one."""
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    return value if value > 0 else None


def _positive_int(raw: Any) -> int | None:
    """Return ``raw`` as a positive whole number, or ``None``."""
    value = _positive_number(raw)
    if value is None or value != int(value):
        return None
    return int(value)


def validate_step(step: int, form_data: Mapping[str, Any]) -> list[str]:
    """Return the reasons ``step`` cannot be left, or an empty list.

    The one place a step's rules are written. The browser re-checks the same
    fields to enable Next, and the handler calls this before advancing, so a
    hand-made POST is held to the same standard as the UI.

    Args:
        step: Step number, 1-5.
        form_data: Everything collected so far.

    Returns:
        Human-readable reasons, empty when the step is satisfied.
    """
    problems: list[str] = []

    if step == 1:
        if not str(form_data.get("project_name") or "").strip():
            problems.append("Project name is required.")
        location = str(form_data.get("location") or "").strip()
        if not location:
            problems.append("Location is required.")
        elif location not in COUNTRIES:
            problems.append("Choose a location from the list.")
        if _positive_number(form_data.get("project_size_sqm")) is None:
            problems.append("Project size must be a number greater than zero.")
        if _positive_int(form_data.get("buildings")) is None:
            problems.append("Enter a whole number of buildings, greater than zero.")
        if _positive_int(form_data.get("floors")) is None:
            problems.append("Enter a whole number of floors, greater than zero.")
        project_type = str(form_data.get("project_type") or "").strip()
        if not project_type:
            problems.append("Choose a project type.")
        elif project_type not in PROJECT_TYPES:
            problems.append("Choose one of the listed project types.")
        chosen = _as_list(form_data.get("analysis_types"))
        if not chosen:
            problems.append("Choose at least one analysis type.")
        else:
            unknown = [a for a in chosen if a not in ANALYSIS_TYPES]
            if unknown:
                problems.append(f"Unrecognised analysis type: {', '.join(unknown)}.")

    elif step == 2:
        if not str(form_data.get("ifc_file_reference") or "").strip():
            problems.append("Upload an IFC model to continue.")

    elif step == 3:
        if not _as_list(form_data.get("document_ids")):
            problems.append("Select at least one document.")

    elif step == 4:
        # Optional by definition: an empty step 4 is a complete step 4. Only a
        # value that is present and wrong is worth reporting.
        known = {s["id"] for s in NOTEBOOK_STANDARDS}
        unknown = [s for s in _as_list(form_data.get("standards_codes")) if s not in known]
        if unknown:
            problems.append(f"Unrecognised standard: {', '.join(unknown)}.")
        status = str(form_data.get("status") or "").strip()
        if status and status not in STATUS_CHOICES:
            problems.append("Choose a valid status.")

    elif step == 5:
        # The review re-checks everything behind it: reaching step 5 with an
        # earlier answer edited away should not be submittable.
        for earlier in range(1, TOTAL_STEPS):
            problems.extend(validate_step(earlier, form_data))

    else:
        problems.append(f"Step {step} does not exist.")

    return problems


def validate_all_steps(form_data: Mapping[str, Any]) -> list[str]:
    """Return every reason the wizard cannot be submitted."""
    problems: list[str] = []
    for step in range(1, TOTAL_STEPS):
        problems.extend(validate_step(step, form_data))
    return problems


def first_incomplete_step(form_data: Mapping[str, Any]) -> int:
    """Return the earliest step still blocking submission.

    ``TOTAL_STEPS`` when every step is satisfied -- step 5 is the review, which
    is reachable exactly when nothing before it is outstanding.
    """
    for step in range(1, TOTAL_STEPS):
        if validate_step(step, form_data):
            return step
    return TOTAL_STEPS


def clamp_step(requested: int, form_data: Mapping[str, Any]) -> int:
    """Hold ``requested`` to a step the answers so far actually permit.

    Bounds into 1..TOTAL_STEPS, then refuses to jump past the first unanswered
    step. Going *back* is always allowed -- editing an earlier answer is the
    point of Previous.
    """
    try:
        target = int(requested)
    except (TypeError, ValueError):
        target = 1
    target = max(1, min(target, TOTAL_STEPS))
    return min(target, first_incomplete_step(form_data))


def collect_form_data(request_data: Any) -> dict[str, Any]:
    """Read one POST into the wizard's own shape.

    Multi-valued fields are read with ``getlist`` so a three-analysis selection
    does not collapse to its last entry, which is what ``FormData.get`` would
    do.
    """
    getlist: Callable[[str], list[str]] = getattr(
        request_data, "getlist", lambda key: _as_list(request_data.get(key))
    )

    data: dict[str, Any] = {
        key: str(request_data.get(key) or "").strip() for key in _SCALAR_KEYS
    }
    for key in _MULTI_KEYS:
        data[key] = [v for v in getlist(key) if str(v).strip()]
    for flag, _, _ in SETTINGS_FLAGS:
        data[flag] = bool(request_data.get(flag))
    if not data.get("location"):
        data["location"] = DEFAULT_COUNTRY
    if not data.get("status"):
        data["status"] = STATUS_CHOICES[0]
    return data


def emit_form_data(form_data: Mapping[str, Any]) -> dict[str, Any]:
    """Return the completed answers as the dict the wizard exists to produce.

    Numbers come back as numbers rather than the strings the form carried, so
    the caller is not left re-parsing what has already been validated. Nothing
    here writes: turning this into a project row is the caller's job.

    Args:
        form_data: Collected answers. Call :func:`validate_all_steps` first --
            this converts, it does not re-validate.

    Returns:
        ``project_name``, ``description``, ``location``, ``project_size_sqm``,
        ``buildings``, ``floors``, ``project_type``, ``analysis_types``,
        ``ifc_file_reference``, ``document_ids``, ``standards_codes`` and a
        ``settings`` dict.
    """
    size = _positive_number(form_data.get("project_size_sqm"))
    raw_bytes = str(form_data.get("ifc_size_bytes") or "").strip()

    return {
        "project_name": str(form_data.get("project_name") or "").strip(),
        "description": str(form_data.get("description") or "").strip(),
        "location": str(form_data.get("location") or DEFAULT_COUNTRY).strip(),
        "project_size_sqm": int(size) if size is not None else None,
        "buildings": _positive_int(form_data.get("buildings")),
        "floors": _positive_int(form_data.get("floors")),
        "project_type": str(form_data.get("project_type") or "").strip(),
        "analysis_types": _as_list(form_data.get("analysis_types")),
        "ifc_file_reference": str(form_data.get("ifc_file_reference") or "").strip(),
        "document_ids": [
            int(v) for v in _as_list(form_data.get("document_ids")) if str(v).isdigit()
        ],
        "standards_codes": _as_list(form_data.get("standards_codes")),
        "settings": {
            "status": str(form_data.get("status") or STATUS_CHOICES[0]).strip(),
            **{flag: bool(form_data.get(flag)) for flag, _, _ in SETTINGS_FLAGS},
            "ifc_filename": str(form_data.get("ifc_filename") or "").strip(),
            "ifc_size_bytes": int(raw_bytes) if raw_bytes.isdigit() else None,
        },
    }


# ---------------------------------------------------------------------------
# Project-type icons
# ---------------------------------------------------------------------------

#: One glyph per :data:`app.constants.PROJECT_TYPES` entry, drawn rather than
#: imported so the grid needs no icon font and no network request. Each is a
#: 48x48 line drawing on ``currentColor``, so a selected card recolours its own
#: icon with the rest of its text.
_TYPE_ICONS: dict[str, str] = {
    "Commercial Office": (
        '<rect x="10" y="8" width="28" height="34" rx="2"/>'
        '<path d="M17 15h4M27 15h4M17 22h4M27 22h4M17 29h4M27 29h4"/>'
        '<path d="M20 42v-6h8v6"/>'
    ),
    "Residential": (
        '<path d="M8 22 24 9l16 13"/><path d="M12 22v20h24V22"/><path d="M20 42V31h8v11"/>'
    ),
    "Healthcare": (
        '<rect x="9" y="12" width="30" height="30" rx="3"/>'
        '<path d="M24 20v14M17 27h14"/><path d="M17 12V7h14v5"/>'
    ),
    "Educational": (
        '<path d="M6 19 24 11l18 8-18 8z"/>'
        '<path d="M14 23v10c0 2 4.5 4 10 4s10-2 10-4V23"/><path d="M40 20v10"/>'
    ),
    "Industrial": (
        '<path d="M7 42V22l10 6V22l10 6V22l10 6v14z"/>'
        '<path d="M13 34h4M23 34h4M33 34h4"/><path d="M37 22V9h5v19"/>'
    ),
    "Retail": (
        '<path d="M8 17h32l-2 25H10z"/>'
        '<path d="M17 17V12a7 7 0 0 1 14 0v5"/><path d="M17 25h14"/>'
    ),
    "Mixed-Use": (
        '<rect x="7" y="18" width="15" height="24" rx="2"/>'
        '<rect x="26" y="8" width="15" height="34" rx="2"/>'
        '<path d="M12 25h5M12 32h5M31 15h5M31 22h5M31 29h5"/>'
    ),
    "Infrastructure": (
        '<path d="M5 32h38"/><path d="M12 32V16M36 32V16"/>'
        '<path d="M5 20h38"/><path d="M12 20 24 32l12-12"/>'
    ),
}


def _type_icon(project_type: str) -> NotStr:
    """Return the inline SVG for one project type.

    A type with no drawing yet falls back to a plain frame rather than a broken
    box, so adding a PROJECT_TYPES entry cannot break the grid.
    """
    body = _TYPE_ICONS.get(project_type, '<rect x="10" y="10" width="28" height="28" rx="3"/>')
    return NotStr(
        '<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round" class="w-10 h-10" '
        f'aria-hidden="true">{body}</svg>'
    )


# ---------------------------------------------------------------------------
# Shared Tailwind class strings
# ---------------------------------------------------------------------------

_INPUT = (
    "w-full rounded-md border border-input bg-background px-3 py-2 text-sm "
    "text-foreground placeholder:text-muted-foreground focus:outline-none "
    "focus:ring-2 focus:ring-ring focus:border-ring"
)
_LABEL = "block text-xs font-semibold text-muted-foreground mb-1.5"
#: The app's global sheets set a width on ``button[type=submit]`` (0,1,1),
#: which outranks a ``w-auto`` utility (0,1,0) and stretches every control to
#: the full row. :data:`_BTN_STYLE` is applied inline to win that outright.
_BTN = (
    "inline-flex w-auto items-center justify-center gap-1.5 rounded-md border "
    "border-border bg-background px-4 py-2 text-sm font-medium text-foreground "
    "transition-colors hover:bg-muted disabled:opacity-40 disabled:pointer-events-none"
)
_BTN_PRIMARY = (
    "inline-flex w-auto items-center justify-center gap-1.5 rounded-md bg-primary "
    "px-5 py-2 text-sm font-semibold text-primary-foreground transition-colors "
    "hover:bg-primary/90 disabled:opacity-40 disabled:pointer-events-none"
)
#: Applied inline to every button, for the specificity reason above.
_BTN_STYLE = "width:auto;flex:0 0 auto"

_CHK_ROW = "flex items-start gap-2.5 py-1.5 cursor-pointer text-sm"
_PANEL = "rounded-md border border-border bg-muted/30 p-3"

#: Client-side mirror of step 1-3's rules, so Next enables as you type rather
#: than after a round trip. The server re-checks everything regardless -- this
#: only decides whether a button looks pressable.
_WIZARD_JS = """
(function(){
  var form = document.getElementById('wiz-form');
  if (!form || form.dataset.wired === '1') return;
  form.dataset.wired = '1';

  var step = Number(form.dataset.step);
  var next = form.querySelector('[data-role=next]');

  function val(name){
    var el = form.querySelector('[name="' + name + '"]');
    return el ? String(el.value || '').trim() : '';
  }
  function checkedCount(name){
    return form.querySelectorAll('[name="' + name + '"]:checked').length;
  }
  function positive(name, whole){
    var n = Number(val(name));
    if (!val(name) || !isFinite(n) || n <= 0) return false;
    return whole ? n === Math.floor(n) : true;
  }

  function valid(){
    if (step === 1){
      return !!val('project_name') && !!val('location')
        && positive('project_size_sqm', false)
        && positive('buildings', true) && positive('floors', true)
        && checkedCount('project_type') === 1
        && checkedCount('analysis_types') >= 1;
    }
    if (step === 2) return !!val('ifc_file_reference');
    if (step === 3) return checkedCount('document_ids') >= 1;
    return true;  // step 4 is optional, step 5 submits
  }

  function sync(){ if (next) next.disabled = !valid(); }
  form.addEventListener('input', sync);
  form.addEventListener('change', sync);
  sync();

  // ---- step 1: reflect the chosen type card ----
  form.querySelectorAll('[data-role=typecard]').forEach(function(card){
    card.addEventListener('click', function(){
      form.querySelectorAll('[data-role=typecard]').forEach(function(c){
        c.classList.remove('border-primary','bg-primary/10');
        c.classList.add('border-border');
      });
      card.classList.remove('border-border');
      card.classList.add('border-primary','bg-primary/10');
    });
  });

  // ---- step 2: store the model on drop, carry only its reference ----
  var drop = form.querySelector('[data-role=drop]');
  if (drop){
    var picker = drop.querySelector('input[type=file]');
    var state  = form.querySelector('[data-role=upstate]');
    var refEl  = form.querySelector('input[name=ifc_file_reference]');
    var nameEl = form.querySelector('input[name=ifc_filename]');
    var sizeEl = form.querySelector('input[name=ifc_size_bytes]');

    function say(msg, bad){
      if (!state) return;
      state.textContent = msg;
      state.className = 'mt-3 text-xs ' + (bad ? 'text-destructive' : 'text-muted-foreground');
    }

    function send(file){
      if (!file) return;
      if (!/\\.ifc$/i.test(file.name)){
        say('That is not an .ifc file.', true);
        return;
      }
      say('Uploading ' + file.name + '\\u2026');
      if (next) next.disabled = true;
      var body = new FormData();
      body.append('ifc_file', file);
      fetch(form.dataset.uploadEndpoint, {method:'POST', body:body})
        .then(function(r){ return r.json(); })
        .then(function(d){
          if (!d.ok){ say(d.error || 'The upload failed.', true); sync(); return; }
          refEl.value = d.storage_ref;
          nameEl.value = d.filename;
          sizeEl.value = String(d.size_bytes);
          say('Stored ' + d.filename + '.');
          sync();
        })
        .catch(function(){ say('The upload could not be sent.', true); sync(); });
    }

    picker.addEventListener('change', function(){ send(picker.files[0]); });
    ['dragenter','dragover'].forEach(function(e){
      drop.addEventListener(e, function(ev){
        ev.preventDefault(); drop.classList.add('border-primary','bg-primary/5');
      });
    });
    ['dragleave','drop'].forEach(function(e){
      drop.addEventListener(e, function(ev){
        ev.preventDefault(); drop.classList.remove('border-primary','bg-primary/5');
      });
    });
    drop.addEventListener('drop', function(ev){
      send(ev.dataTransfer && ev.dataTransfer.files[0]);
    });
  }
})();
"""


def human_size(num_bytes: int) -> str:
    """Render a byte count the way the staged-file row shows it."""
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


class ProjectSetupWizard:
    """Renders the wizard. Holds no state between requests."""

    #: How many steps there are, for callers that iterate.
    total_steps = TOTAL_STEPS

    # -- pieces ------------------------------------------------------------

    def render_progress(self, current_step: int) -> Div:
        """Render the bar, the ``Step X of 5`` counter and the Reset button."""
        shown = max(1, min(current_step, TOTAL_STEPS))
        percent = round(shown / TOTAL_STEPS * 100)
        title, _ = STEP_TITLES[shown]
        return Div(
            Div(
                Div(
                    Span(f"Step {shown} of {TOTAL_STEPS}", cls="text-primary font-semibold"),
                    Span(" · ", cls="text-muted-foreground"),
                    Span(title, cls="text-muted-foreground"),
                    cls="text-xs",
                ),
                Button(
                    "Reset",
                    type="submit",
                    name="action",
                    value="reset",
                    cls=(
                        "inline-flex w-auto border-0 bg-transparent p-0 text-xs font-medium "
                        "text-muted-foreground underline hover:text-foreground"
                    ),
                    style=_BTN_STYLE,
                ),
                cls="flex items-center justify-between mb-2",
            ),
            Div(
                Div(
                    cls="h-full rounded-full bg-primary transition-all duration-300",
                    style=f"width:{percent}%",
                ),
                cls="h-1.5 w-full rounded-full bg-muted overflow-hidden",
            ),
            cls="mb-6",
        )

    def _field(self, label: str, control, *, required: bool = False, help_text: str = "") -> Div:
        """Render one labelled control."""
        caption: list[Any] = [label]
        if required:
            caption.append(Span(" *", cls="text-destructive"))
        return Div(
            Label(*caption, cls=_LABEL),
            control,
            *(
                [P(help_text, cls="mt-1 text-xs text-muted-foreground")]
                if help_text
                else []
            ),
            cls="space-y-0",
        )

    def _checkbox_row(
        self, name: str, value: str, label: str, detail: str, checked: bool
    ) -> Label:
        """Render one checkbox as a full-width clickable row."""
        return Label(
            Checkbox(name=name, value=value, checked=checked, cls="mt-0.5 shrink-0"),
            Div(
                Span(label, cls="font-medium text-foreground"),
                *(
                    [P(detail, cls="text-xs text-muted-foreground mt-0.5")]
                    if detail
                    else []
                ),
            ),
            cls=_CHK_ROW,
        )

    # -- steps -------------------------------------------------------------

    def render_step_1_details(self, fd: Mapping[str, Any]) -> Div:
        """Eight fields on one screen."""
        location = str(fd.get("location") or DEFAULT_COUNTRY)
        selected_type = str(fd.get("project_type") or "")
        chosen_analyses = set(_as_list(fd.get("analysis_types")))
        analysis_details = {
            "Piping (Corrosive)": "Galvanic, crevice and microbial corrosion across the piping.",
            "Halo": "Seismic bracing clearance and restraint checks.",
            "Architecture": "Architectural code compliance across the model.",
        }

        return Div(
            Div(
                self._field(
                    "Project name",
                    Input(
                        type="text",
                        name="project_name",
                        value=str(fd.get("project_name") or ""),
                        cls=_INPUT,
                    ),
                    required=True,
                ),
                self._field(
                    "Location",
                    Select(
                        *[
                            Option(c, value=c, selected=c == location)
                            for c in COUNTRIES
                        ],
                        name="location",
                        cls=_INPUT,
                    ),
                    required=True,
                ),
                cls="grid gap-4 md:grid-cols-2",
            ),
            self._field(
                "Description",
                Textarea(
                    str(fd.get("description") or ""),
                    name="description",
                    rows="3",
                    cls=_INPUT,
                ),
                help_text="Optional.",
            ),
            Div(
                self._field(
                    "Project size (m²)",
                    Input(
                        type="number",
                        name="project_size_sqm",
                        value=str(fd.get("project_size_sqm") or ""),
                        min="1",
                        step="any",
                        cls=_INPUT,
                    ),
                    required=True,
                ),
                self._field(
                    "Buildings",
                    Input(
                        type="number",
                        name="buildings",
                        value=str(fd.get("buildings") or ""),
                        min="1",
                        step="1",
                        cls=_INPUT,
                    ),
                    required=True,
                ),
                self._field(
                    "Floors",
                    Input(
                        type="number",
                        name="floors",
                        value=str(fd.get("floors") or ""),
                        min="1",
                        step="1",
                        cls=_INPUT,
                    ),
                    required=True,
                ),
                cls="grid gap-4 sm:grid-cols-3",
            ),
            Div(
                Label("Project type", Span(" *", cls="text-destructive"), cls=_LABEL),
                Div(
                    *[
                        Label(
                            Input(
                                type="radio",
                                name="project_type",
                                value=ptype,
                                checked=ptype == selected_type,
                                cls="sr-only",
                            ),
                            Div(_type_icon(ptype), cls="flex justify-center mb-2"),
                            Span(ptype, cls="block text-xs font-semibold"),
                            cls=(
                                "cursor-pointer rounded-lg border-2 p-3 text-center "
                                "transition-colors hover:border-primary/60 "
                                + (
                                    "border-primary bg-primary/10"
                                    if ptype == selected_type
                                    else "border-border"
                                )
                            ),
                            data_role="typecard",
                        )
                        for ptype in PROJECT_TYPES
                    ],
                    cls="grid gap-3 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4",
                ),
            ),
            Div(
                Label("Analysis type", Span(" *", cls="text-destructive"), cls=_LABEL),
                Div(
                    *[
                        self._checkbox_row(
                            "analysis_types",
                            a,
                            a,
                            analysis_details.get(a, ""),
                            a in chosen_analyses,
                        )
                        for a in ANALYSIS_TYPES
                    ],
                    cls=_PANEL,
                ),
            ),
            cls="space-y-5",
        )

    def render_step_2_ifc(self, fd: Mapping[str, Any]) -> Div:
        """Drag-drop upload; only the returned reference travels on."""
        ref = str(fd.get("ifc_file_reference") or "")
        filename = str(fd.get("ifc_filename") or "")
        raw_size = str(fd.get("ifc_size_bytes") or "")

        staged = (
            Div(
                Span(filename or "Model stored", cls="text-sm font-medium truncate"),
                Span(
                    human_size(int(raw_size)) if raw_size.isdigit() else "",
                    cls="text-xs text-muted-foreground shrink-0",
                ),
                cls=(
                    "mt-3 flex items-center justify-between gap-3 rounded-md "
                    "border border-primary/40 bg-primary/10 px-3 py-2"
                ),
            )
            if ref
            else None
        )

        return Div(
            Label(
                Input(type="file", accept=".ifc", cls="hidden"),
                Div("Drop an IFC model here", cls="text-sm font-semibold"),
                Div(
                    "or click to choose one. Only .ifc is accepted, and it "
                    "uploads immediately.",
                    cls="mt-1 text-xs text-muted-foreground",
                ),
                cls=(
                    "block cursor-pointer rounded-lg border-2 border-dashed border-border "
                    "bg-muted/20 px-6 py-10 text-center transition-colors hover:border-primary"
                ),
                data_role="drop",
            ),
            *([staged] if staged else []),
            Div(
                "" if ref else "No model uploaded yet.",
                cls="mt-3 text-xs text-muted-foreground",
                data_role="upstate",
            ),
            # The reference, not the file: an <input type=file> value cannot be
            # set from script, so only what the upload returned can travel on.
            Input(type="hidden", name="ifc_file_reference", value=ref),
            Input(type="hidden", name="ifc_filename", value=filename),
            Input(type="hidden", name="ifc_size_bytes", value=raw_size),
        )

    def render_step_3_documents(
        self, fd: Mapping[str, Any], documents: Iterable[Mapping[str, Any]]
    ) -> Div:
        """Multi-select over rows the caller supplies.

        Passed in rather than looked up, which is what keeps this module free
        of the persistence layer.
        """
        chosen = set(_as_list(fd.get("document_ids")))
        rows = [
            self._checkbox_row(
                "document_ids",
                str(doc.get("id")),
                str(doc.get("filename") or f"Document {doc.get('id')}"),
                "",
                str(doc.get("id")) in chosen,
            )
            for doc in documents
        ]
        if not rows:
            return Div(
                P(
                    "No documents have been uploaded yet. Upload one from the "
                    "Documents page, then come back to this step.",
                    cls="text-sm text-muted-foreground",
                ),
                cls=_PANEL,
            )
        return Div(*rows, cls=f"{_PANEL} max-h-72 overflow-y-auto")

    def render_step_4_settings(self, fd: Mapping[str, Any]) -> Div:
        """Standards and optional configuration."""
        chosen = set(_as_list(fd.get("standards_codes")))
        status = str(fd.get("status") or STATUS_CHOICES[0])

        by_domain: dict[str, list[Mapping[str, Any]]] = {}
        for std in NOTEBOOK_STANDARDS:
            by_domain.setdefault(str(std.get("domain") or "Other"), []).append(std)

        standards: list[Any] = []
        for domain in sorted(by_domain):
            standards.append(
                P(
                    domain,
                    cls="text-[10px] font-bold uppercase tracking-wide text-muted-foreground mt-3 first:mt-0",
                )
            )
            standards.extend(
                self._checkbox_row(
                    "standards_codes",
                    str(std["id"]),
                    str(std.get("name") or std["id"]),
                    str(std.get("description") or ""),
                    str(std["id"]) in chosen,
                )
                for std in by_domain[domain]
            )

        return Div(
            Div(
                Label("Standards and codes", cls=_LABEL),
                Div(*standards, cls=f"{_PANEL} max-h-72 overflow-y-auto"),
                P(
                    "Optional. Leave everything unticked to decide later.",
                    cls="mt-1 text-xs text-muted-foreground",
                ),
            ),
            Div(
                self._field(
                    "Status",
                    Select(
                        *[
                            Option(s, value=s, selected=s == status)
                            for s in STATUS_CHOICES
                        ],
                        name="status",
                        cls=_INPUT,
                    ),
                ),
                Div(
                    Label("Analysis defaults", cls=_LABEL),
                    Div(
                        *[
                            self._checkbox_row(
                                flag, "1", label, "", bool(fd.get(flag, default))
                            )
                            for flag, label, default in SETTINGS_FLAGS
                        ],
                        cls=_PANEL,
                    ),
                ),
                cls="grid gap-4 md:grid-cols-2 mt-5",
            ),
        )

    def render_step_5_review(
        self, fd: Mapping[str, Any], documents: Iterable[Mapping[str, Any]]
    ) -> Div:
        """Read-only summary of everything collected."""
        emitted = emit_form_data(fd)
        by_id = {str(doc.get("id")): doc for doc in documents}
        doc_names = [
            str(by_id[str(i)].get("filename") or i)
            for i in emitted["document_ids"]
            if str(i) in by_id
        ]
        settings = emitted["settings"]
        flags_on = [
            label for flag, label, _ in SETTINGS_FLAGS if settings.get(flag)
        ]

        pairs: list[tuple[str, Any]] = [
            ("Project name", emitted["project_name"]),
            ("Description", emitted["description"]),
            ("Location", emitted["location"]),
            ("Project size", f"{emitted['project_size_sqm']} m²" if emitted["project_size_sqm"] else ""),
            ("Buildings", emitted["buildings"]),
            ("Floors", emitted["floors"]),
            ("Project type", emitted["project_type"]),
            ("Analysis types", ", ".join(emitted["analysis_types"])),
            ("IFC model", settings.get("ifc_filename") or emitted["ifc_file_reference"]),
            ("Documents", ", ".join(doc_names) or len(emitted["document_ids"])),
            ("Standards", len(emitted["standards_codes"]) or "None selected"),
            ("Status", settings.get("status")),
            ("Analysis defaults", ", ".join(flags_on) or "None"),
        ]

        rows = [
            Div(
                Span(label, cls="text-xs font-semibold text-muted-foreground"),
                Span(
                    str(value) if value not in (None, "", 0) else "—",
                    cls="text-sm text-foreground break-words",
                ),
                cls="grid grid-cols-[10rem_1fr] gap-4 py-2 border-b border-border last:border-0",
            )
            for label, value in pairs
        ]
        return Div(*rows, cls=_PANEL)

    # -- assembly ----------------------------------------------------------

    def render_form(
        self,
        current_step: int = 1,
        form_data: Mapping[str, Any] | None = None,
        *,
        documents: Iterable[Mapping[str, Any]] = (),
        errors: Iterable[str] = (),
    ) -> Form:
        """Render one step, carrying every other answer as hidden inputs."""
        fd = dict(form_data or {})
        shown = max(1, min(int(current_step), TOTAL_STEPS))
        docs = list(documents)
        problems = list(errors)
        title, lead = STEP_TITLES[shown]

        bodies: dict[int, Callable[[], Any]] = {
            1: lambda: self.render_step_1_details(fd),
            2: lambda: self.render_step_2_ifc(fd),
            3: lambda: self.render_step_3_documents(fd, docs),
            4: lambda: self.render_step_4_settings(fd),
            5: lambda: self.render_step_5_review(fd, docs),
        }

        footer_right: list[Any] = []
        if shown == TOTAL_STEPS:
            footer_right.append(
                Button(
                    "Cancel",
                    type="submit",
                    name="action",
                    value="reset",
                    cls=_BTN,
                    style=_BTN_STYLE,
                )
            )
            footer_right.append(
                Button(
                    "Create Project",
                    type="submit",
                    name="action",
                    value="submit",
                    cls=_BTN_PRIMARY,
                    style=_BTN_STYLE,
                    data_role="next",
                )
            )
        else:
            footer_right.append(
                Button(
                    "Next →",
                    type="submit",
                    name="action",
                    value="next",
                    cls=_BTN_PRIMARY,
                    style=_BTN_STYLE,
                    data_role="next",
                )
            )

        return Form(
            self.render_progress(shown),
            Card(
                CardHeader(
                    CardTitle(title, cls="text-lg"),
                    P(lead, cls="text-sm text-muted-foreground"),
                ),
                CardContent(
                    *(
                        [
                            Div(
                                *[P(p, cls="text-sm text-destructive") for p in problems],
                                cls=(
                                    "mb-4 rounded-md border border-destructive/40 "
                                    "bg-destructive/10 p-3 space-y-1"
                                ),
                            )
                        ]
                        if problems
                        else []
                    ),
                    bodies[shown](),
                ),
            ),
            *self._hidden_carry_over(shown, fd),
            Input(type="hidden", name="wizard_step", value=str(shown)),
            Div(
                # Rendered on every step and disabled on the first, rather than
                # omitted there: a control that appears once you are past step 1
                # makes the footer jump.
                Button(
                    "← Previous",
                    type="submit",
                    name="action",
                    value="prev",
                    cls=_BTN,
                    style=_BTN_STYLE,
                    disabled=shown == 1,
                ),
                Div(*footer_right, cls="flex items-center gap-2"),
                cls="wiz-foot flex items-center justify-between gap-3 mt-6",
            ),
            id="wiz-form",
            method="POST",
            enctype="multipart/form-data",
            hx_post=FORM_ENDPOINT,
            hx_target="#wizard",
            hx_swap="outerHTML",
            data_step=str(shown),
            data_upload_endpoint=UPLOAD_ENDPOINT,
        )

    def _hidden_carry_over(self, shown: int, fd: Mapping[str, Any]) -> list[Any]:
        """Re-emit every answer the visible step does not own.

        A duplicate name would shadow the real value: Starlette's
        ``FormData.get`` returns the LAST match and these are emitted after the
        step body, so anything the step renders itself is skipped here.
        """
        owned: dict[int, set[str]] = {
            1: {
                "project_name",
                "description",
                "location",
                "project_size_sqm",
                "buildings",
                "floors",
                "project_type",
                "analysis_types",
            },
            2: {"ifc_file_reference", "ifc_filename", "ifc_size_bytes"},
            3: {"document_ids"},
            4: {"standards_codes", "status", *(f for f, _, _ in SETTINGS_FLAGS)},
            5: set(),
        }[shown]

        hidden: list[Any] = []
        for key in _SCALAR_KEYS:
            if key in owned:
                continue
            value = str(fd.get(key) or "").strip()
            if value:
                hidden.append(Input(type="hidden", name=key, value=value))
        for key in _MULTI_KEYS:
            if key in owned:
                continue
            hidden.extend(
                Input(type="hidden", name=key, value=v) for v in _as_list(fd.get(key))
            )
        for flag, _, _ in SETTINGS_FLAGS:
            if flag in owned:
                continue
            if fd.get(flag):
                hidden.append(Input(type="hidden", name=flag, value="1"))
        return hidden

    def render(
        self,
        current_step: int = 1,
        form_data: Mapping[str, Any] | None = None,
        *,
        documents: Iterable[Mapping[str, Any]] = (),
        errors: Iterable[str] = (),
    ) -> Div:
        """Render the whole wizard: the current step and its script."""
        return Div(
            self.render_form(current_step, form_data, documents=documents, errors=errors),
            Script(_WIZARD_JS),
            id="wizard",
        )


# ---------------------------------------------------------------------------
# Request handling
# ---------------------------------------------------------------------------


def handle_wizard_get(documents: Iterable[Mapping[str, Any]] = ()) -> Div:
    """Render the wizard at step 1."""
    return ProjectSetupWizard().render(current_step=1, form_data={}, documents=documents)


async def handle_wizard_post(
    request_data: Any,
    *,
    documents: Iterable[Mapping[str, Any]] = (),
    on_submit: Callable[[dict[str, Any]], Any] | None = None,
) -> Any:
    """Advance, retreat, reset or submit.

    Args:
        request_data: The parsed form.
        documents: Rows for step 3, supplied by the caller.
        on_submit: Called with the emitted dict when step 5 submits and every
            step validates. Whatever it returns is returned to the caller --
            which is how the wizard hands off without importing persistence.
            When omitted, the review is re-rendered instead.

    Returns:
        The wizard node for the step to show, or ``on_submit``'s return value.
    """
    data = collect_form_data(request_data)
    action = str(request_data.get("action") or "next")
    wizard = ProjectSetupWizard()
    docs = list(documents)

    if action == "reset":
        logger.info("Wizard reset to step 1")
        return wizard.render(current_step=1, form_data={}, documents=docs)

    # Clamp before doing anything else. The step number arrives in the POST
    # body, so a hand-made request can claim to be on step 5 with step 1 blank;
    # without this the handler would validate step 5 and render step 5.
    current = clamp_step(request_data.get("wizard_step") or 1, data)

    if action == "prev":
        return wizard.render(
            current_step=max(1, current - 1), form_data=data, documents=docs
        )

    if action == "submit":
        problems = validate_all_steps(data)
        if problems:
            blocking = first_incomplete_step(data)
            logger.info("Wizard submit blocked at step=%d", blocking)
            return wizard.render(
                current_step=blocking,
                form_data=data,
                documents=docs,
                errors=validate_step(blocking, data),
            )
        emitted = emit_form_data(data)
        logger.info(
            "Wizard emitted name=%r type=%s analyses=%s documents=%d standards=%d ifc=%s",
            emitted["project_name"],
            emitted["project_type"],
            ",".join(emitted["analysis_types"]),
            len(emitted["document_ids"]),
            len(emitted["standards_codes"]),
            emitted["ifc_file_reference"] or "none",
        )
        if on_submit is not None:
            return on_submit(emitted)
        return wizard.render(current_step=TOTAL_STEPS, form_data=data, documents=docs)

    problems = validate_step(current, data)
    if problems:
        return wizard.render(
            current_step=current, form_data=data, documents=docs, errors=problems
        )
    return wizard.render(
        current_step=clamp_step(current + 1, data), form_data=data, documents=docs
    )
