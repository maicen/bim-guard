"""
BIMGUARD AI — Project Setup Wizard (Phase 3b)
Complete 5-step wizard component with stateless POST state management.

File: app/components/project_setup_wizard.py
Copy this entire file into your repo.
"""

from fasthtml.common import (
    Div, Form, Input, Select, Option, Button, Label, H1, H2, H3, P, Span, Img,
    Textarea, Fieldset, Legend, Ul, Li, A, Script, Style
)
from typing import Dict, List, Any, Optional, Tuple

from app.constants import PROJECT_TYPES, ANALYSIS_TYPES, COUNTRIES, NOTEBOOK_STANDARDS

#: Wizard default. Must be a member of COUNTRIES, or no option renders as
#: selected. Deliberately not app.constants.DEFAULT_COUNTRY ("UK"), which
#: tracks the migration_001 column default for the legacy /projects/create form.
DEFAULT_COUNTRY = "United Kingdom"

WIZARD_STYLES = """
:root {
  --primary: #006BA6;
  --primary-light: #00AEEF;
  --accent: #6D5BD0;
  --error: #BE3A34;
  --success: #00B050;
  --bg: #F0F2F7;
  --card: #fff;
  --text-primary: #0F172A;
  --text-muted: #475569;
  --border: #E2E8F0;
}

/* ---- Shell ---- */
.wiz-container {
  background: #ffffff;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  max-width: 640px;
  margin: 0 auto;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.1);
}

.wiz-head {
  padding: 20px;
  border-bottom: 1px solid var(--border);
}

.wiz-body {
  padding: 20px;
  min-height: 300px;
}

.wiz-foot {
  padding: 16px 20px;
  border-top: 1px solid var(--border);
  display: flex;
  gap: 10px;
  justify-content: space-between;
}

/* One step is rendered per request, so no display toggle here -- the fade is
   purely cosmetic and must apply to every step, not just the "active" one. */
.wiz-step {
  animation: fadeIn 0.2s;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.wiz-fieldset {
  margin-bottom: 14px;
}

.wiz-group {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

/* ---- Progress + step indicator ---- */
.wiz-progress {
  height: 6px;
  background: #E8EDF3;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 16px;
}

.wiz-progress .wiz-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--primary), var(--primary-light));
  border-radius: 4px;
  transition: width 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}

.wiz-steps {
  display: flex;
  justify-content: space-between;
  margin-top: 12px;
}

.wiz-stepitem {
  flex: 1;
  text-align: center;
  position: relative;
}

.wiz-stepitem .dot {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: #E8EDF3;
  color: var(--text-muted);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  transition: 0.25s;
  border: 2px solid transparent;
}

.wiz-stepitem.done .dot {
  background: var(--success);
  color: #fff;
}

.wiz-stepitem.current .dot {
  background: var(--primary);
  color: #fff;
  border-color: rgba(0, 107, 166, 0.22);
}

.wiz-stepitem .nm {
  font-size: 10px;
  margin-top: 5px;
  color: #475569;
  font-weight: 600;
}

.wiz-stepitem.current .nm {
  color: #006BA6;
}

/* ---- Form fields ---- */
label.fld {
  display: block;
  font-size: 11px;
  font-weight: 600;
  margin-bottom: 4px;
  color: #0F172A;
}

label.fld .req {
  color: #BE3A34;
}

p {
  color: #0F172A;
}

.wiz-head p {
  color: #0F172A;
}

.inp {
  width: 100%;
  font-size: 12.5px;
  padding: 8px 10px;
  border: 1px solid #E2E8F0;
  border-radius: 6px;
  background: #fff;
  color: #0F172A;
  font-family: inherit;
  box-sizing: border-box;
}

.inp:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(0, 107, 166, 0.12);
}

.inp::placeholder {
  color: #94A3B8;
}

textarea.inp {
  min-height: 78px;
  resize: vertical;
}

/* ---- Buttons ---- */
.tbtn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  font-weight: 600;
  padding: 5px 11px;
  border-radius: 5px;
  border: 1px solid var(--border);
  background: #fff;
  color: var(--text-primary);
  cursor: pointer;
  transition: 0.12s;
  white-space: nowrap;
  font-family: inherit;
}

.tbtn:hover:not(:disabled) {
  background: #F8FAFC;
  border-color: #CBD5E1;
}

.tbtn-lg {
  font-size: 12.5px;
  padding: 9px 20px;
  border-radius: 6px;
}

.tbtn-primary {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
}

.tbtn-primary:hover:not(:disabled) {
  background: #005A8C;
}

/* The page also loads Pico / Franken UI / DaisyUI / Basecoat, which stretch bare
   <button>s. Scope these so the footer buttons stay their natural width. */
.wiz-foot .tbtn {
  width: auto;
  flex: 0 0 auto;
  display: inline-flex;
}

/* ---- Card selectors (project type / analysis type) ---- */
.card-selector {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.card-select-item {
  padding: 12px;
  border: 2px solid var(--border);
  border-radius: 6px;
  cursor: pointer;
  transition: 0.15s;
  text-align: center;
  background: #fff;
}

.card-select-item:hover {
  border-color: var(--primary);
  background: rgba(0, 107, 166, 0.03);
}

.card-select-item input[type="radio"] {
  display: none;
}

.card-select-item.selected {
  border-color: var(--primary);
  background: rgba(0, 107, 166, 0.06);
}

.card-select-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  color: #0F172A;
}

.card-select-item p {
  color: var(--text-muted);
  margin: 2px 0 0 0;
}

/* ---- IFC upload (step 4) ---- */
.file-input-wrapper input[type="file"] {
  display: none;
}

.file-input-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
  font-weight: 600;
  padding: 9px 20px;
  border: 1px dashed #CBD5E1;
  border-radius: 6px;
  background: #F8FAFC;
  color: var(--text-primary);
  cursor: pointer;
  transition: 0.12s;
}

.file-input-label:hover {
  border-color: var(--primary);
  background: rgba(0, 107, 166, 0.04);
}

/* ---- Notes ---- */
.note {
  background: #F8FAFC;
  border-left: 3px solid #00AEEF;
  padding: 9px 12px;
  font-size: 11px;
  color: #0F172A;
  border-radius: 0 5px 5px 0;
  margin-top: 12px;
}

/* ---- Standards picker (step 5A) ---- */
.standards-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
  max-height: 280px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px;
}

.standard-item {
  padding: 8px;
  border-radius: 4px;
}

.standard-item:hover {
  background: #F8FAFC;
}

.standard-item label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  margin-bottom: 2px;
  color: #0F172A;
}

.standard-item p {
  color: var(--text-muted);
  margin: 0;
}

/* ---- Review (step 5B) ---- */
.review-section {
  background: #F8FAFC;
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 12px;
}

.review-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  padding: 4px 0;
  border-bottom: 1px solid #E2E8F0;
}

.review-label {
  font-weight: 600;
  color: #0F172A;
}

.review-value {
  color: #475569;
}
"""


class ProjectSetupWizard:
    """5-step project creation wizard with stateless POST state."""

    def __init__(self):
        self.steps = [
            {"n": 1, "name": "Details"},
            {"n": 2, "name": "Project Type"},
            {"n": 3, "name": "Analysis"},
            {"n": 4, "name": "IFC Upload"},
            {"n": 5, "name": "Standards & Review"}
        ]

    def render_progress_bar(self, current_step: int) -> Div:
        fill_width = (current_step - 1) * 20 + 20
        return Div(Div(style=f"width: {fill_width}%", cls="wiz-fill"), cls="wiz-progress")

    def render_step_indicator(self, current_step: int) -> Div:
        step_items = []
        for step in self.steps:
            n, name = step["n"], step["name"]
            if n < current_step:
                state, dot = "done", "✓"
            elif n == current_step:
                state, dot = "current", str(n)
            else:
                state, dot = "pending", str(n)
            step_items.append(Div(Div(dot, cls="dot"), Div(name, cls="nm"), cls=f"wiz-stepitem {state}"))
        return Div(*step_items, cls="wiz-steps")

    def render_step_1_details(self, fd: Dict = None) -> Div:
        fd = fd or {}
        return Div(
            Div(Label("Country", Span("*", style="color: var(--error)"), cls="fld"),
                Select(*[Option(c, value=c, selected=(c == fd.get("country", DEFAULT_COUNTRY))) for c in COUNTRIES],
                       name="country", cls="inp", required=True),
                cls="wiz-fieldset"),
            Div(Label("Project Name", Span("*", style="color: var(--error)"), cls="fld"),
                Input(type="text", name="name", value=fd.get("name", ""),
                      placeholder="e.g., Hospital MEP Services Phase 2",
                      cls="inp", required=True, minlength=3),
                cls="wiz-fieldset"),
            Div(Label("Description (optional)", cls="fld"),
                Textarea(fd.get("description", ""), name="description",
                         placeholder="Brief project overview...", cls="inp"),
                cls="wiz-fieldset"),
            Div(
                Div(Label("Building Size (m²)", cls="fld"),
                    Input(type="number", name="size", value=fd.get("size", ""), cls="inp"),
                    cls="wiz-fieldset"),
                Div(Label("Number of Buildings", cls="fld"),
                    Input(type="number", name="buildings", value=fd.get("buildings", ""), cls="inp"),
                    cls="wiz-fieldset"),
                Div(Label("Number of Floors", cls="fld"),
                    Input(type="number", name="floors", value=fd.get("floors", ""), cls="inp"),
                    cls="wiz-fieldset"),
                cls="wiz-group"),
            cls="wiz-step active")

    def render_step_2_project_type(self, fd: Dict = None) -> Div:
        fd = fd or {}
        selected = fd.get("project_type", "")
        cards = [Div(
            Input(type="radio", name="project_type", value=ptype, id=f"ptype-{ptype}"),
            Label(ptype, cls="card-select-label"),
            cls=f"card-select-item {'selected' if selected == ptype else ''}",
            onclick="selectCard(this)")
            for ptype in PROJECT_TYPES]
        return Div(
            P("Select project type:", style="font-size: 12px; margin: 0 0 12px 0;"),
            Div(*cards, cls="card-selector"),
            cls="wiz-step")

    def render_step_3_analysis_type(self, fd: Dict = None) -> Div:
        fd = fd or {}
        selected = fd.get("analysis_type", "")
        descs = {
            "Piping (Corrosive)": "Galvanic & crevice corrosion risk",
            "Halo": "Seismic bracing clearance (LOD 200/300)",
            "Architecture": "Architectural compliance (TBD)"
        }
        cards = [Div(
            Input(type="radio", name="analysis_type", value=atype, id=f"atype-{atype}"),
            Div(Label(atype, cls="card-select-label"),
                P(descs.get(atype, ""), style="font-size: 10px; color: var(--text-muted);")),
            cls=f"card-select-item {'selected' if selected == atype else ''}",
            onclick="selectCard(this)")
            for atype in ANALYSIS_TYPES]
        return Div(
            P("Select analysis type:", style="font-size: 12px; margin: 0 0 12px 0;"),
            Div(*cards, cls="card-selector"),
            cls="wiz-step")

    def render_step_4_ifc_upload(self, fd: Dict = None) -> Div:
        return Div(
            P("Upload IFC (optional):", style="font-size: 12px; margin: 0 0 12px 0;"),
            Div(Input(type="file", name="ifc_file", accept=".ifc", id="ifc-input"),
                Label("📁 Choose IFC file", _for="ifc-input", cls="file-input-label"),
                cls="file-input-wrapper"),
            Div("Models can be uploaded after project creation too.", cls="note"),
            cls="wiz-step")

    def render_step_5_standards_review(self, fd: Dict = None) -> Div:
        fd = fd or {}
        selected_standards = fd.get("standards", [])
        standards_by_domain = {}
        for std in NOTEBOOK_STANDARDS:
            domain = std.get("domain", "Other")
            if domain not in standards_by_domain:
                standards_by_domain[domain] = []
            standards_by_domain[domain].append(std)

        standards_items = []
        for domain in sorted(standards_by_domain.keys()):
            standards_items.append(
                Div(Div(domain, style="font-size: 10px; font-weight: 700; color: var(--text-muted);")))
            for std in standards_by_domain[domain]:
                is_checked = std["id"] in selected_standards
                standards_items.append(Div(
                    Input(type="checkbox", name="standards", value=std["id"], checked=is_checked),
                    Div(Label(std["name"]),
                        P(std["description"], style="font-size: 10px; color: var(--text-muted);")),
                    cls="standard-item"))

        country = fd.get("country", DEFAULT_COUNTRY)
        name = fd.get("name", "")
        project_type = fd.get("project_type", "")
        analysis_type = fd.get("analysis_type", "")

        return Div(
            Div(H3("Step 5A: Select Standards", style="font-size: 12px;"),
                P("Choose relevant standards:", style="font-size: 11px; color: var(--text-muted);"),
                Div(*standards_items, cls="standards-grid"),
                cls="wiz-fieldset"),
            Div(H3("Step 5B: Review", style="font-size: 12px;"),
                Div(
                    Div(Div("Project Details", style="font-size: 11px; font-weight: 700; color: var(--text-muted);"),
                        Div(Span("Country", cls="review-label"), Span(country or "—", cls="review-value"), cls="review-row"),
                        Div(Span("Name", cls="review-label"), Span(name or "—", cls="review-value"), cls="review-row"),
                        Div(Span("Type", cls="review-label"), Span(project_type or "—", cls="review-value"), cls="review-row"),
                        cls="review-section"),
                    Div(Div("Analysis", style="font-size: 11px; font-weight: 700; color: var(--text-muted);"),
                        Div(Span("Analysis Type", cls="review-label"), Span(analysis_type or "—", cls="review-value"), cls="review-row"),
                        Div(Span("Standards", cls="review-label"), Span(f"{len(selected_standards)} chosen", cls="review-value"), cls="review-row"),
                        cls="review-section")),
                Div("Review and click 'Create Project' to proceed.", cls="note"),
                cls="wiz-fieldset"),
            cls="wiz-step")

    #: Fields each step renders as visible inputs. They are omitted from the
    #: hidden carry-over block below: a duplicate name would shadow the real
    #: value, because Starlette's ``FormData.get()`` returns the LAST match and
    #: the hidden inputs are emitted after the step body.
    STEP_FIELDS = {
        1: ("country", "name", "description", "size", "buildings", "floors"),
        2: ("project_type",),
        3: ("analysis_type",),
        4: (),
        5: ("standards",),
    }

    def render_form(self, current_step: int = 1, form_data: Dict = None) -> Form:
        fd = form_data or {}
        owned = self.STEP_FIELDS.get(current_step, ())
        carry_over = [
            ("country", fd.get("country", DEFAULT_COUNTRY)),
            ("name", fd.get("name", "")),
            ("description", fd.get("description", "")),
            ("size", fd.get("size", "")),
            ("buildings", fd.get("buildings", "")),
            ("floors", fd.get("floors", "")),
            ("project_type", fd.get("project_type", "")),
            ("analysis_type", fd.get("analysis_type", "")),
        ]
        hidden_fields = [Input(type="hidden", name="wizard_step", value=str(current_step))]
        hidden_fields += [
            Input(type="hidden", name=key, value=value)
            for key, value in carry_over
            if key not in owned
        ]
        if "standards" not in owned:
            for std_id in fd.get("standards", []):
                hidden_fields.append(Input(type="hidden", name="standards", value=std_id))

        step_renderers = {
            1: self.render_step_1_details,
            2: self.render_step_2_project_type,
            3: self.render_step_3_analysis_type,
            4: self.render_step_4_ifc_upload,
            5: self.render_step_5_standards_review
        }
        step_body = step_renderers[current_step](fd)

        footer_buttons = []
        if current_step > 1:
            footer_buttons.append(Button("← Back", type="submit", name="action", value="prev", cls="tbtn tbtn-lg"))
        if current_step < 5:
            footer_buttons.append(Button("Next →", type="submit", name="action", value="next", cls="tbtn tbtn-lg tbtn-primary"))
        else:
            footer_buttons.append(Button("Create Project & Proceed", type="submit", name="action", value="submit", cls="tbtn tbtn-lg tbtn-primary"))

        return Form(
            Div(self.render_progress_bar(current_step), self.render_step_indicator(current_step), cls="wiz-head"),
            Div(step_body, cls="wiz-body"),
            *hidden_fields,
            Div(*footer_buttons, cls="wiz-foot"),
            method="POST",
            enctype="multipart/form-data",
            hx_post="/wizard",
            hx_target="#wizard",
            hx_swap="outerHTML"
        )

    def render(self, current_step: int = 1, form_data: Dict = None) -> Div:
        return Div(
            Style(WIZARD_STYLES),
            Div(self.render_form(current_step, form_data), cls="wiz-container"),
            Script("""function selectCard(el) {
              const radio = el.querySelector('input[type="radio"]');
              if (radio) {
                radio.checked = true;
                el.parentElement.querySelectorAll('.card-select-item').forEach(c => c.classList.remove('selected'));
                el.classList.add('selected');
              }
            }"""),
            id="wizard"
        )


def handle_wizard_get():
    """GET /wizard — Render wizard at step 1."""
    wizard = ProjectSetupWizard()
    return wizard.render(current_step=1, form_data={})


async def handle_wizard_post(request_data) -> Div:
    """POST /wizard — Handle wizard navigation."""
    current_step = int(request_data.get("wizard_step", 1))
    action = request_data.get("action", "next")

    form_data = {
        "country": request_data.get("country", DEFAULT_COUNTRY),
        "name": request_data.get("name", ""),
        "description": request_data.get("description", ""),
        "size": request_data.get("size", ""),
        "buildings": request_data.get("buildings", ""),
        "floors": request_data.get("floors", ""),
        "project_type": request_data.get("project_type", ""),
        "analysis_type": request_data.get("analysis_type", ""),
        "standards": request_data.getlist("standards") if hasattr(request_data, 'getlist') else [],
    }

    if action == "next":
        errors = validate_step(current_step, form_data)
        if errors:
            wizard = ProjectSetupWizard()
            return wizard.render(current_step=current_step, form_data=form_data)
        current_step += 1
    elif action == "prev":
        current_step = max(1, current_step - 1)
    elif action == "submit":
        errors = validate_all_steps(form_data)
        if errors:
            wizard = ProjectSetupWizard()
            return wizard.render(current_step=5, form_data=form_data)
        project_id = create_project_from_wizard(form_data)
        analysis_route = get_analysis_route(form_data["analysis_type"])
        return Div(Script(f"window.location.href = '/analyze/{analysis_route}?project_id={project_id}'"))

    wizard = ProjectSetupWizard()
    return wizard.render(current_step=current_step, form_data=form_data)


def validate_step(step: int, form_data: Dict) -> List[str]:
    """Validate a specific step."""
    errors = []
    if step == 1:
        if not form_data.get("country"):
            errors.append("Country is required")
        if not form_data.get("name") or len(form_data.get("name", "")) < 3:
            errors.append("Project name must be at least 3 characters")
    elif step == 2:
        if not form_data.get("project_type"):
            errors.append("Project type is required")
    elif step == 3:
        if not form_data.get("analysis_type"):
            errors.append("Analysis type is required")
    elif step == 5:
        if not form_data.get("standards"):
            errors.append("At least one standard must be selected")
    return errors


def validate_all_steps(form_data: Dict) -> List[str]:
    """Validate all required fields before submission."""
    errors = []
    for step in range(1, 6):
        errors.extend(validate_step(step, form_data))
    return errors


def create_project_from_wizard(form_data: Dict) -> int:
    """TODO: Wire to projects_service.create_project() + set_standards_for_project()"""
    return 1


def get_analysis_route(analysis_type: str) -> str:
    """Map analysis type to route slug."""
    return {"Piping (Corrosive)": "corrosion", "Halo": "seismic", "Architecture": "architecture"}.get(analysis_type, "corrosion")
