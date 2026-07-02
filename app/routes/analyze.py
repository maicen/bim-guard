"""Analysis routes for orchestrating compliance checks and rendering results."""

import os

from fasthtml.common import (
    A,
    Details,
    Div,
    Form,
    H3,
    Option,
    P,
    Script,
    Summary,
    Request,
    Span,
    Table,
    Tbody,
    Td,
    Th,
    Thead,
    Title,
    Tr,
)
from monsterui.all import H1, Container

from app.components.layout import DashboardLayout
from app.components.ui import (
    Alert,
    AlertT,
    Card,
    CardContent,
    CardHeader,
    CardTitle,
    Checkbox,
    CountTableItemSpec,
    FormLabel,
    ItemsCountDataTable,
    Label,
    Select,
    SubmitButton,
)
from app.modules.orchestrator import BIMGuard_App
from app.services.documents_service import DocumentService
from app.services.projects_service import ProjectsService

_bim_guard_app = BIMGuard_App()
_projects_service = ProjectsService()
_documents_service = DocumentService()

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")


def _analysis_form(projects, documents, mode: str):
    """Build the analysis form for the requested workflow mode."""
    is_simple = mode == "simple"
    is_initial = mode == "initial"
    project_options = [Option("— select a project —", value="", disabled=True, selected=True)] + [
        Option(p.get("name", f"Project {p['id']}"), value=str(p["id"])) for p in projects
    ]

    form_sections = [
        Div(
            FormLabel("Project (IFC Model)", fr="project_id"),
            Select(
                *project_options,
                id="project_id",
                name="project_id",
                required=True,
            ),
        ),
    ]

    if not is_simple:
        form_sections.append(
            Div(
                FormLabel("Analysis Theme", fr="analysis_theme"),
                Select(
                    Option("Architecture", value="Architecture", selected=True),
                    Option("MEP", value="MEP"),
                    id="analysis_theme",
                    name="analysis_theme",
                    required=True,
                ),
            )
        )

    if not is_initial and not is_simple:
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
            doc_checkboxes = [P("No documents uploaded yet.", cls="text-sm text-muted-foreground")]

        form_sections.append(
            Div(
                FormLabel("Documents"),
                Div(
                    *doc_checkboxes,
                    cls="space-y-2 border rounded-md p-3 bg-muted/30",
                ),
            )
        )

    if not is_simple:
        form_sections.append(
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
            )
        )

    if mode == "simple":
        submit_label = "Run Simple Analysis"
        results_id = "simple-analysis-results"
        hx_post = "/analysis/simple/results"
        card_title = "Simple Analysis"
        helper_copy = (
            "Check the IFC model against OBC Part 9 building code categories: "
            "Windows, Doors, Stairs, Egress, Fire Protection, Garage, and more."
        )
    elif is_initial:
        submit_label = "Run Initial Analysis"
        results_id = "initial-analysis-results"
        hx_post = "/analysis/initial/results"
        card_title = "Initial Analysis"
        helper_copy = "Inspect the IFC model structure, counts, and quality signals before checking rules."
    else:
        submit_label = "Run Model Vs Rules Analysis"
        results_id = "model-rules-results"
        hx_post = "/analysis/results"
        card_title = "Model Vs Rules Analysis"
        helper_copy = "Compare the selected IFC model against the saved rules in the library."

    loader_id = f"{results_id}-loader"

    # JS: on submit → copy loading card into results area + disable button
    before_js = (
        f"var r=document.getElementById('{results_id}'),"
        f"l=document.getElementById('{loader_id}');"
        "if(r&&l)r.innerHTML=l.innerHTML;"
        "var b=this.querySelector('[type=submit]');"
        "if(b){{b.disabled=true;b.dataset.orig=b.textContent;b.textContent='Analysing…';}}"
    )
    after_js = (
        "var b=this.querySelector('[type=submit]');"
        "if(b){{b.disabled=false;if(b.dataset.orig)b.textContent=b.dataset.orig;}}"
    )

    return Div(
        Card(
            CardHeader(
                Div(
                    CardTitle(card_title),
                    P(helper_copy, cls="text-sm text-muted-foreground mt-1"),
                )
            ),
            CardContent(
                Form(
                    Div(
                        *form_sections,
                        Div(
                            SubmitButton(submit_label, variant="primary"),
                            cls="flex items-center gap-4",
                        ),
                    ),
                    method="post",
                    action=hx_post,
                    hx_post=hx_post,
                    hx_target=f"#{results_id}",
                    hx_swap="innerHTML",
                    **{"hx-on:htmx:before-request": before_js,
                       "hx-on:htmx:after-request": after_js},
                ),
            ),
        ),
        # Hidden loading card — cloned into results area when request starts
        Div(
            Div(
                Div(style=(
                    "width:40px;height:40px;border-radius:50%;"
                    "border:4px solid #e2e8f0;border-top-color:#3b82f6;"
                    "animation:bimguard-spin .75s linear infinite;"
                    "margin:0 auto 16px;"
                )),
                P("Analysing model…", cls="text-base font-semibold"),
                P(
                    "Loading IFC · Extracting properties · Running compliance checks",
                    cls="text-xs text-muted-foreground mt-1",
                ),
                cls="text-center py-14",
            ),
            cls="border rounded-lg shadow-sm bg-card",
            id=loader_id,
            style="display:none",
        ),
        Script("(function(){var s=document.createElement('style');"
               "s.textContent='@keyframes bimguard-spin{to{transform:rotate(360deg)}}';"
               "document.head.appendChild(s);})();"),
        Div(id=results_id),
    )


async def _run_analysis_request(req: Request):
    """Parse and validate the analysis request, then run the orchestrator."""
    form = await req.form()
    project_id_raw = form.get("project_id") or ""
    if not project_id_raw:
        return None, Alert("Please select a project.", cls=AlertT.error)
    try:
        project_id = int(project_id_raw)
    except ValueError:
        return None, Alert("Invalid project selection.", cls=AlertT.error)

    doc_ids = [int(v) for v in form.getlist("document_ids") if v]
    analysis_theme = (form.get("analysis_theme") or "Architecture").strip()
    include_openings = bool(form.get("include_openings"))
    include_spaces = bool(form.get("include_spaces"))
    include_type_definitions = bool(form.get("include_type_definitions"))
    result = _bim_guard_app.orchestrate_workflow(
        project_id,
        doc_ids,
        analysis_theme=analysis_theme,
        include_openings=include_openings,
        include_spaces=include_spaces,
        include_type_definitions=include_type_definitions,
    )

    if "error" in result:
        return None, Alert(result["error"], cls=AlertT.error)

    return {"project_id": project_id, "result": result}, None


def _build_ifc_summary_content(result: dict, project_id: int):
    """Build the IFC detail block shared by the initial analysis page."""
    ifc_count = result["ifc_element_count"]
    ifc_type_counts = result.get("ifc_type_counts") or {}
    ifc_totals = result.get("ifc_totals") or {}
    ifc_error = result["ifc_error"]
    ifc_quality = result.get("ifc_quality_report") or {}
    ifc_quality_warnings = result.get("ifc_quality_warnings") or []
    ifc_quality_improvements = result.get("ifc_quality_improvements") or []
    ifc_schema_note = result.get("ifc_schema_note")

    if ifc_error:
        return P(f"IFC parsing error: {ifc_error}", cls="text-sm text-destructive")
    if not _projects_service.resolve_ifc_file(project_id):
        return P(
            "No IFC file attached to this project.",
            cls="text-sm text-muted-foreground",
        )

    filters = ifc_totals.get("filters") or {}
    deltas = ifc_totals.get("excluded_or_added") or {}
    overall = ifc_quality.get("overall") or {}
    labeling = ifc_quality.get("labeling") or {}
    guids = ifc_quality.get("guids") or {}
    properties = ifc_quality.get("properties") or {}

    quality_alerts = [
        Alert(msg, cls=AlertT.warning if hasattr(AlertT, "warning") else "")
        for msg in ifc_quality_warnings
    ]
    if ifc_schema_note:
        quality_alerts.append(
            Alert(
                ifc_schema_note,
                cls=AlertT.info if hasattr(AlertT, "info") else "",
            )
        )

    quality_block = (
        _collapsible_card(
            "IFC Quality",
            P(f"Overall score: {overall.get('score', 0):.1f}%", cls="text-sm font-medium"),
            Div(
                P(f"Labeling: {labeling.get('score', 0):.1f}%", cls="text-xs text-muted-foreground"),
                P(f"GUIDs: {guids.get('score', 0):.1f}%", cls="text-xs text-muted-foreground"),
                P(f"Properties: {properties.get('score', 0):.1f}%", cls="text-xs text-muted-foreground"),
                cls="space-y-1 mt-2",
            ),
            *quality_alerts,
            open=False,
        )
        if ifc_quality
        else ""
    )

    improvement_block = (
        _collapsible_card(
            "Improvement Summary",
            Div(
                *[P(message, cls="text-sm text-muted-foreground") for message in ifc_quality_improvements],
                cls="space-y-1",
            ),
            open=False,
        )
        if ifc_quality_improvements
        else ""
    )

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
                subtotal=int(ifc_totals.get("adjusted_physical_elements", ifc_count)),
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

    return Div(
        quality_block,
        improvement_block,
        counts_table,
        cls="space-y-1",
    )


def _build_document_cards(result: dict):
    """Build document summary cards for the model-vs-rules page."""
    cards = []
    for doc in result["documents"]:
        cards.append(
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
    return cards


def _build_ifc_graph_card(result: dict, project_id: int):
    """Return a temporary placeholder while graph visualization is disabled."""
    # TODO: Re-enable the PyVis IFC graph after the initial-analysis UI flow is stabilized.
    del result, project_id
    return Card(
        CardHeader(CardTitle("IFC Relationship Graph")),
        CardContent(
            P(
                "Graph visualization is temporarily disabled.",
                cls="text-sm text-muted-foreground",
            ),
            P(
                "TODO: re-enable the PyVis-based IFC relationship graph once the initial-analysis UI flow is finalized.",
                cls="text-xs text-muted-foreground mt-1",
            ),
        ),
    )


def _band_badge(band: str):
    colours = {
        "Critical": "bg-red-600 text-white",
        "High": "bg-orange-500 text-white",
        "Medium": "bg-yellow-400 text-black",
        "Low": "bg-green-600 text-white",
    }
    return Span(
        band,
        cls=f"inline-block px-2 py-0.5 rounded text-xs font-semibold {colours.get(band, 'bg-gray-400 text-white')}",
    )


def _compliance_card(results, cost_impact, issue_stats, is_demo, project_id, error):
    """Build the corrosion compliance results card for the analysis results page."""
    if error:
        return Card(
            CardHeader(CardTitle("Corrosion Compliance — GC-001 / CC-001")),
            CardContent(P(f"Compliance engine error: {error}", cls="text-sm text-destructive")),
        )

    if not results:
        return None

    bands = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for r in results:
        b = r.get("risk_band", "Low")
        if b in bands:
            bands[b] += 1

    badge_row = Div(
        *[
            Div(
                _band_badge(b),
                Span(f" {bands[b]}", cls="text-sm font-medium ml-1"),
                cls="flex items-center",
            )
            for b in ("Critical", "High", "Medium", "Low")
        ],
        cls="flex items-center gap-4 flex-wrap",
    )

    cost_line = (
        P(
            f"Estimated remediation: £{cost_impact.total_cost_gbp:,.0f}  |  "
            f"Programme impact: {cost_impact.total_days} days",
            cls="text-sm text-muted-foreground mt-2",
        )
        if cost_impact
        else ""
    )

    tracker_line = (
        P(
            f"Issue history: {issue_stats.get('new', 0)} new, "
            f"{issue_stats.get('updated', 0)} updated, "
            f"{issue_stats.get('resolved', 0)} resolved.",
            cls="text-xs text-muted-foreground mt-1",
        )
        if issue_stats
        else ""
    )

    demo_notice = (
        Alert(
            "No IFC file found — showing synthetic demo data (25 representative MEP elements).",
            cls=AlertT.info if hasattr(AlertT, "info") else "",
        )
        if is_demo
        else ""
    )

    flagged = [r for r in results if r.get("risk_band", "Low") != "Low"]

    if flagged:
        header_cells = [
            Th(h, cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted")
            for h in ("Element", "Floor", "Material", "Band", "Score", "Required Action")
        ]
        data_rows = []
        for r in flagged[:20]:
            data_rows.append(
                Tr(
                    Td(r.get("name", "—")[:40], cls="px-3 py-2 text-sm"),
                    Td(r.get("floor", "—"), cls="px-3 py-2 text-sm"),
                    Td(r.get("material_a", "—")[:22], cls="px-3 py-2 text-sm"),
                    Td(_band_badge(r.get("risk_band", "Low")), cls="px-3 py-2"),
                    Td(f"{r.get('overall_score', 0):.3f}", cls="px-3 py-2 text-sm font-mono"),
                    Td(r.get("action", "—")[:70], cls="px-3 py-2 text-xs"),
                    cls="border-b border-muted last:border-0",
                )
            )
        if len(flagged) > 20:
            data_rows.append(
                Tr(
                    Td(
                        f"… and {len(flagged) - 20} more flagged elements",
                        cls="px-3 py-2 text-xs text-muted-foreground italic",
                        colspan="6",
                    )
                )
            )
        results_table = Div(
            Table(
                Thead(Tr(*header_cells)),
                Tbody(*data_rows),
                cls="w-full text-sm",
            ),
            cls="overflow-auto mt-4 border rounded-md",
        )
    else:
        results_table = P(
            "No elements flagged at Medium risk or above.",
            cls="text-sm text-muted-foreground mt-3",
        )

    bcf_btn = (
        Div(
            A(
                "Download BCF Report",
                href=f"/reports/bcf/{project_id}",
                cls="inline-block mt-4 px-4 py-2 bg-primary text-primary-foreground text-sm rounded-md hover:opacity-90",
            ),
        )
        if project_id
        else ""
    )

    return _collapsible_card(
        "Corrosion Compliance — GC-001 / CC-001",
        demo_notice,
        badge_row,
        cost_line,
        tracker_line,
        results_table,
        bcf_btn,
    )


def _rule_validation_card(rule_validations: list[dict], analysis_theme: str):
    """Build the Module 3 rule validation card for the analysis results page."""
    if not rule_validations:
        return Card(
            CardHeader(CardTitle(f"Rule Validation — Module 3 ({analysis_theme})")),
            CardContent(
                P(
                    f"No {analysis_theme} rules found in the library. "
                    "Go to Library → Rule Extraction Studio to extract and save rules first.",
                    cls="text-sm text-muted-foreground",
                )
            ),
        )

    present = sum(1 for r in rule_validations if r["status"] == "present")
    not_found = len(rule_validations) - present

    summary = Div(
        Div(
            Span(str(len(rule_validations)), cls="text-2xl font-bold"),
            Span(" rules checked", cls="text-sm text-muted-foreground ml-1"),
            cls="flex items-baseline",
        ),
        Div(
            Span(
                f"{present} matched",
                cls="inline-block px-2 py-0.5 rounded text-xs font-semibold bg-green-100 text-green-800 mr-2",
            ),
            Span(
                f"{not_found} no elements",
                cls="inline-block px-2 py-0.5 rounded text-xs font-semibold bg-yellow-100 text-yellow-800",
            ),
            cls="mt-1",
        ),
        cls="mb-4",
    )

    header_cells = [
        Th(h, cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted")
        for h in ("Reference", "Description", "Target IFC Class", "Elements in Model", "Status")
    ]

    def _status_badge(status: str, count: int):
        if status == "present":
            return Span(
                f"✓ {count} found",
                cls="inline-block px-2 py-0.5 rounded text-xs font-semibold bg-green-100 text-green-800",
            )
        return Span(
            "No elements",
            cls="inline-block px-2 py-0.5 rounded text-xs font-semibold bg-yellow-100 text-yellow-800",
        )

    data_rows = []
    for r in rule_validations:
        data_rows.append(
            Tr(
                Td(r.get("reference", "—"), cls="px-3 py-2 text-xs font-mono"),
                Td(
                    r.get("description", "")[:80]
                    + ("…" if len(r.get("description", "")) > 80 else ""),
                    cls="px-3 py-2 text-sm",
                ),
                Td(r.get("target_ifc_class", "—"), cls="px-3 py-2 text-xs font-mono text-blue-700"),
                Td(str(r.get("element_count", 0)), cls="px-3 py-2 text-sm text-center"),
                Td(_status_badge(r["status"], r["element_count"]), cls="px-3 py-2"),
                cls="border-b border-muted last:border-0",
            )
        )

    return _collapsible_card(
        f"Rule Validation — Module 3 ({analysis_theme})",
        summary,
        Div(
            Table(
                Thead(Tr(*header_cells)),
                Tbody(*data_rows),
                cls="w-full text-sm",
            ),
            cls="overflow-auto border rounded-md",
        ),
        open=False,
    )


def _rule_compliance_card(
    compliance_results: list[dict], summary: dict, error: str | None, analysis_theme: str
):
    """Module 4 rule compliance card — shows PASS/FAIL per rule with element details."""
    title = f"Rule Compliance Check — Module 4 ({analysis_theme})"

    if error:
        return Card(
            CardHeader(CardTitle(title)),
            CardContent(P(f"Compliance check error: {error}", cls="text-sm text-destructive")),
        )

    if not compliance_results:
        return None

    total = summary.get("total_rules", 0)
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)
    missing = summary.get("missing_data", 0)
    no_elem = summary.get("no_elements", 0)
    rate = summary.get("pass_rate", 0)
    mand_f = summary.get("mandatory_failed", 0)

    # Colour the pass-rate pill
    rate_cls = (
        "bg-green-100 text-green-800"
        if rate >= 80
        else "bg-yellow-100 text-yellow-800"
        if rate >= 50
        else "bg-red-100 text-red-800"
    )

    summary_bar = Div(
        Span(
            f"{rate:.0f}% pass rate",
            cls=f"inline-block px-3 py-1 rounded-full text-sm font-semibold {rate_cls} mr-3",
        ),
        Span(f"✓ {passed} passed", cls="text-xs text-green-700 mr-2"),
        Span(f"✗ {failed} failed", cls="text-xs text-red-700 mr-2"),
        Span(f"~ {missing} missing data", cls="text-xs text-yellow-700 mr-2") if missing else "",
        Span(f"○ {no_elem} no elements", cls="text-xs text-muted-foreground") if no_elem else "",
        Span(f"  ⚠ {mand_f} mandatory failures", cls="text-xs text-red-600 font-semibold ml-2")
        if mand_f
        else "",
        cls="flex flex-wrap items-center gap-1 mb-4",
    )

    _STATUS_CLS = {
        "PASS": "bg-green-100 text-green-800",
        "FAIL": "bg-red-100 text-red-800",
        "MISSING_DATA": "bg-yellow-100 text-yellow-800",
        "PARTIAL": "bg-orange-100 text-orange-800",
        "NO_ELEMENTS": "bg-gray-100 text-gray-600",
    }

    _IFC_LABELS = {
        "IfcStairFlight": "Stairs",
        "IfcDoor":        "Doors",
        "IfcWindow":      "Windows",
        "IfcRailing":     "Railings & Guards",
        "IfcRamp":        "Ramps",
        "IfcSlab":        "Slabs & Landings",
        "IfcWall":        "Walls",
        "IfcSpace":       "Spaces & Rooms",
        "IfcZone":        "Zones",
        "IfcColumn":      "Columns",
        "IfcBeam":        "Beams",
        "IfcFooting":     "Footings & Foundations",
        "IfcPipeSegment":      "Pipes",
        "IfcDuctSegment":      "Ducts",
        "IfcSanitaryTerminal": "Plumbing Fixtures",
        "IfcAlarm":            "Alarms & Detectors",
    }

    # Group results by IFC class, preserving order of first appearance
    from collections import defaultdict
    grouped: dict[str, list[dict]] = defaultdict(list)
    seen_targets: list[str] = []
    for r in compliance_results:
        t = r.get("target", "Other")
        if t not in grouped:
            seen_targets.append(t)
        grouped[t].append(r)

    header_cells = [
        Th(h, cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted")
        for h in ("Ref", "Description", "Property", "Rule", "Status", "Pass / Fail / Miss")
    ]

    rows = []
    for target in seen_targets:
        label = _IFC_LABELS.get(target, target)
        group_results = grouped[target]

        # Count group-level status summary
        g_pass   = sum(1 for r in group_results if r.get("status") == "PASS")
        g_fail   = sum(1 for r in group_results if r.get("status") == "FAIL")
        g_miss   = sum(1 for r in group_results if r.get("status") in ("MISSING_DATA", "PARTIAL"))
        g_noelem = sum(1 for r in group_results if r.get("status") == "NO_ELEMENTS")

        badge_cls = (
            "bg-red-100 text-red-700" if g_fail
            else "bg-yellow-100 text-yellow-700" if g_miss
            else "bg-gray-100 text-gray-500" if g_noelem
            else "bg-green-100 text-green-700"
        )
        badge_txt = (
            f"{g_fail} failed" if g_fail
            else f"{g_miss} missing" if g_miss
            else "no elements" if g_noelem
            else "all pass"
        )

        rows.append(
            Tr(
                Td(
                    Div(
                        Span(label, cls="font-semibold text-sm text-foreground"),
                        Span(target, cls="text-xs text-muted-foreground font-mono ml-2"),
                        Span(badge_txt, cls=f"ml-auto text-xs px-2 py-0.5 rounded-full font-medium {badge_cls}"),
                        cls="flex items-center gap-2",
                    ),
                    colspan="6",
                    cls="px-3 py-2 bg-muted/60 border-t-2 border-border",
                ),
                cls="",
            )
        )

        for r in group_results:
            op = r.get("operator", "")
            if op == "between":
                rule_str = f"between {r.get('value_min')}–{r.get('value_max')} {r.get('unit', '')}"
            elif op == "exists":
                rule_str = "exists"
            else:
                rule_str = f"{op} {r.get('check_value', '')} {r.get('unit', '')}".strip()

            status = r.get("status", "")
            s_cls = _STATUS_CLS.get(status, "bg-gray-100 text-gray-600")

            counts = Span(
                f"{r.get('pass_count', 0)} / {r.get('fail_count', 0)} / {r.get('missing_count', 0)}",
                cls="font-mono text-xs",
            )

            # Collapsible failure details
            failures = r.get("failures", [])
            fail_detail = ""
            if failures:
                def _fmt_actual(v):
                    if isinstance(v, float):
                        return f"{v:,.2f}" if v >= 1 else f"{v:.4f}"
                    return str(v) if v is not None else "—"

                fail_rows = [
                    Tr(
                        Td(f.get("element_name", "—")[:35], cls="px-2 py-1 text-xs font-mono"),
                        Td(
                            Span(f.get("storey") or "—", cls="block text-xs"),
                            Span(f.get("space") or "", cls="block text-xs text-muted-foreground"),
                            cls="px-2 py-1",
                        ),
                        Td(_fmt_actual(f.get("actual")), cls="px-2 py-1 text-xs font-mono"),
                        Td(f.get("reason", ""), cls="px-2 py-1 text-xs text-red-700"),
                        Td(
                            Span((f.get("guid") or "")[:12], cls="text-xs text-muted-foreground font-mono"),
                            cls="px-2 py-1",
                        ),
                    )
                    for f in failures[:20]
                ]
                fail_detail = Details(
                    Summary(
                        f"{len(failures)} failing element(s) — click to expand",
                        cls="text-xs text-red-600 cursor-pointer font-semibold mt-1",
                    ),
                    Div(
                        Table(
                            Thead(
                                Tr(
                                    Th("Element", cls="px-2 py-1 text-xs bg-muted"),
                                    Th("Floor / Room", cls="px-2 py-1 text-xs bg-muted"),
                                    Th("Actual value", cls="px-2 py-1 text-xs bg-muted"),
                                    Th("Reason", cls="px-2 py-1 text-xs bg-muted"),
                                    Th("GUID", cls="px-2 py-1 text-xs bg-muted"),
                                )
                            ),
                            Tbody(*fail_rows),
                            cls="w-full text-xs border rounded mt-1",
                        ),
                        cls="max-h-48 overflow-y-auto",
                    ),
                )

            # Collapsible missing-data details
            missing_elements = r.get("missing_elements", [])
            missing_detail = ""
            if missing_elements:
                missing_rows = [
                    Tr(
                        Td(m.get("element_name", "")[:35], cls="px-2 py-1 text-xs font-mono"),
                        Td(m.get("storey") or "—", cls="px-2 py-1 text-xs"),
                        Td(m.get("space") or "—", cls="px-2 py-1 text-xs text-muted-foreground"),
                        Td(m.get("guid", "")[:16], cls="px-2 py-1 text-xs text-muted-foreground font-mono"),
                    )
                    for m in missing_elements[:20]
                ]
                overflow_note = (
                    Div(
                        f"... and {len(missing_elements) - 20} more elements",
                        cls="text-xs text-muted-foreground px-2 py-1",
                    )
                    if len(missing_elements) > 20 else ""
                )
                missing_detail = Details(
                    Summary(
                        f"{len(missing_elements)} element(s) missing this property — click to expand",
                        cls="text-xs text-yellow-700 cursor-pointer font-semibold mt-1",
                    ),
                    Div(
                        Table(
                            Thead(
                                Tr(
                                    Th("Element", cls="px-2 py-1 text-xs bg-muted"),
                                    Th("Floor", cls="px-2 py-1 text-xs bg-muted"),
                                    Th("Room", cls="px-2 py-1 text-xs bg-muted"),
                                    Th("GUID", cls="px-2 py-1 text-xs bg-muted"),
                                )
                            ),
                            Tbody(*missing_rows),
                            cls="w-full text-xs border rounded mt-1",
                        ),
                        overflow_note,
                        cls="max-h-48 overflow-y-auto",
                    ),
                )

            rows.append(
                Tr(
                    Td(r.get("rule_ref", "—"), cls="px-3 py-2 text-xs font-mono"),
                    Td(
                        Div(
                            (r.get("rule_desc", "") or "")[:70]
                            + ("..." if len(r.get("rule_desc", "") or "") > 70 else ""),
                            fail_detail,
                            missing_detail,
                        ),
                        cls="px-3 py-2 text-xs",
                    ),
                    Td(r.get("property_name", ""), cls="px-3 py-2 text-xs font-mono"),
                    Td(rule_str, cls="px-3 py-2 text-xs font-mono"),
                    Td(
                        Span(
                            status,
                            cls=f"inline-block px-1.5 py-0.5 rounded text-xs font-semibold {s_cls}",
                        ),
                        cls="px-3 py-2",
                    ),
                    Td(counts, cls="px-3 py-2"),
                    cls="border-b border-muted last:border-0",
                )
            )

    csv_btn = A(
        "Download CSV",
        href="/reports/compliance-csv",
        cls="inline-block px-3 py-1.5 rounded text-xs font-medium bg-slate-800 text-white hover:bg-slate-600 mt-3",
    )

    return _collapsible_card(
        title,
        summary_bar,
        Div(
            Table(Thead(Tr(*header_cells)), Tbody(*rows), cls="w-full text-sm"),
            cls="overflow-auto border rounded-md",
        ),
        csv_btn,
    )


_ELEM_LABELS = {
    "IfcDoor":             "Doors",
    "IfcWindow":           "Windows",
    "IfcWall":             "Walls",
    "IfcCurtainWall":      "Curtain Walls",
    "IfcSlab":             "Slabs",
    "IfcRoof":             "Roofs",
    "IfcCovering":         "Ceilings",
    "IfcStairFlight":      "Stair Flights",
    "IfcRamp":             "Ramps",
    "IfcRampFlight":       "Ramp Flights",
    "IfcRailing":          "Railings",
    "IfcColumn":           "Columns",
    "IfcBeam":             "Beams",
    "IfcMember":           "Structural Members",
    "IfcSanitaryTerminal": "Fixtures",
    "IfcAlarm":            "Alarms",
    "IfcSensor":           "Sensors",
    "IfcFurnishingElement":"Furniture",
}


def _collapsible_card(title: str, *content, subtitle: str = "", open: bool = True):
    """Top-level collapsible result card with a clickable header."""
    return Details(
        Summary(
            Div(
                Span(title, cls="font-semibold text-base"),
                Span(subtitle, cls="text-xs text-muted-foreground ml-2") if subtitle else "",
                cls="flex items-center gap-1",
            ),
            cls="px-6 py-4 border-b bg-muted/30 cursor-pointer select-none list-none",
        ),
        Div(*content, cls="px-6 py-5 space-y-4 bg-card"),
        cls="border rounded-lg shadow-sm overflow-hidden",
        open=open,
    )


def _collapsible_section(title: str, *content, badge: str = "", open: bool = True):
    """Collapsible sub-section inside a card (smaller heading)."""
    return Details(
        Summary(
            Div(
                Span(title, cls="text-sm font-semibold"),
                Span(badge, cls="ml-2 text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground") if badge else "",
                cls="flex items-center",
            ),
            cls="cursor-pointer select-none py-1 list-none",
        ),
        Div(*content, cls="mt-2"),
        open=open,
    )


def _building_summary_card(summary: dict):
    """Render a Building Overview card from extract_building_summary() output."""
    if not summary:
        return ""

    storey_count   = summary.get("storey_count", 0)
    room_count     = summary.get("room_count", 0)
    gfa            = summary.get("total_gfa_m2", 0.0)
    ext_doors      = summary.get("external_door_count", 0)
    element_counts = summary.get("element_counts", {})
    fixture_counts = summary.get("fixture_counts", {})
    alarm_counts   = summary.get("alarm_counts", {})
    floor_heights  = summary.get("floor_heights", [])
    rooms_per_storey = summary.get("rooms_per_storey", {})
    storeys        = summary.get("storeys", [])
    unplaced       = summary.get("unplaced_rooms", [])
    unnamed        = summary.get("unnamed_elements", [])

    # ── Stat strip ────────────────────────────────────────────────────────────
    def _stat(label, value):
        return Div(
            Span(str(value), cls="text-2xl font-bold block"),
            Span(label, cls="text-xs text-muted-foreground"),
            cls="text-center px-4 py-3 bg-muted rounded-lg",
        )

    stat_strip = Div(
        _stat("Storeys", storey_count),
        _stat("Rooms / Spaces", room_count),
        _stat("GFA m²", f"{gfa:,.1f}" if gfa else "—"),
        _stat("Exit Doors", ext_doors),
        cls="grid grid-cols-4 gap-3 mb-5",
    )

    # ── Floor breakdown table ─────────────────────────────────────────────────
    floor_table = ""
    if storeys:
        fh_by_from = {h["from"]: h["height_mm"] for h in floor_heights}
        floor_rows = []
        for s in storeys:
            name   = s["name"]
            ri     = rooms_per_storey.get(name, {})
            r_cnt  = ri.get("count", 0)
            r_area = ri.get("total_area_m2", 0.0)
            h_mm   = fh_by_from.get(name)
            floor_rows.append(
                Tr(
                    Td(name, cls="px-3 py-2 text-sm font-medium"),
                    Td(
                        (f"{h_mm / 1000:.2f} m" if h_mm >= 1000 else f"{h_mm:,} mm")
                        if h_mm else "—",
                        cls="px-3 py-2 text-sm font-mono",
                    ),
                    Td(str(r_cnt) if r_cnt else "—", cls="px-3 py-2 text-sm text-center"),
                    Td(f"{r_area:,.1f}" if r_area else "—", cls="px-3 py-2 text-sm font-mono text-right"),
                    cls="border-b border-muted last:border-0",
                )
            )
        floor_table = Div(
            H3("Floor Breakdown", cls="text-sm font-semibold mb-2"),
            Div(
                Table(
                    Thead(Tr(
                        Th("Storey",          cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted"),
                        Th("Floor-to-Floor",  cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted"),
                        Th("Rooms",           cls="px-3 py-2 text-center text-xs font-semibold text-muted-foreground bg-muted"),
                        Th("Area m²",         cls="px-3 py-2 text-right text-xs font-semibold text-muted-foreground bg-muted"),
                    )),
                    Tbody(*floor_rows),
                    cls="w-full text-sm",
                ),
                cls="overflow-auto border rounded-md mb-5",
            ),
        )

    # ── Element count badges ──────────────────────────────────────────────────
    elem_badges = ""
    if element_counts:
        elem_badges = Div(
            H3("Elements Found", cls="text-sm font-semibold mb-2"),
            Div(
                *[
                    Span(
                        f"{_ELEM_LABELS.get(k, k)}: {v}",
                        cls="inline-block px-2 py-1 rounded-full text-xs bg-blue-50 text-blue-800 border border-blue-200 font-medium",
                    )
                    for k, v in sorted(element_counts.items(), key=lambda x: _ELEM_LABELS.get(x[0], x[0]))
                ],
                cls="flex flex-wrap gap-2 mb-5",
            ),
        )

    # ── Plumbing fixture badges ───────────────────────────────────────────────
    fixture_badges = ""
    if fixture_counts:
        fixture_badges = Div(
            H3("Plumbing Fixtures", cls="text-sm font-semibold mb-2"),
            Div(
                *[
                    Span(f"{k}: {v}",
                         cls="inline-block px-2 py-1 rounded-full text-xs bg-cyan-50 text-cyan-800 border border-cyan-200 font-medium")
                    for k, v in sorted(fixture_counts.items())
                ],
                cls="flex flex-wrap gap-2 mb-5",
            ),
        )

    # ── Alarm badges ─────────────────────────────────────────────────────────
    alarm_badges = ""
    if alarm_counts:
        alarm_badges = Div(
            H3("Fire / CO Alarms", cls="text-sm font-semibold mb-2"),
            Div(
                *[
                    Span(f"{k}: {v}",
                         cls="inline-block px-2 py-1 rounded-full text-xs bg-red-50 text-red-800 border border-red-200 font-medium")
                    for k, v in sorted(alarm_counts.items())
                ],
                cls="flex flex-wrap gap-2 mb-5",
            ),
        )

    # ── QA issues ─────────────────────────────────────────────────────────────
    qa_items = []
    if unplaced:
        qa_items.append(
            P(f"⚠ {len(unplaced)} unplaced room(s) — not assigned to any storey",
              cls="text-xs text-yellow-700")
        )
    for u in unnamed:
        qa_items.append(
            P(f"⚠ {u['count']} {_ELEM_LABELS.get(u['type'], u['type'])} element(s) missing Name property",
              cls="text-xs text-yellow-700")
        )
    qa_block = ""
    if qa_items:
        qa_block = Div(
            H3("Model QA", cls="text-sm font-semibold mb-2"),
            Div(*qa_items, cls="space-y-1 p-3 bg-yellow-50 rounded-md border border-yellow-200"),
        )

    return _collapsible_card(
        "Building Overview",
        stat_strip,
        _collapsible_section("Floor Breakdown", floor_table) if floor_table else "",
        _collapsible_section("Elements Found", elem_badges) if elem_badges else "",
        _collapsible_section("Plumbing Fixtures", fixture_badges) if fixture_badges else "",
        _collapsible_section("Fire / CO Alarms", alarm_badges) if alarm_badges else "",
        qa_block,
    )


def _spatial_checks_card(spatial: dict):
    """Render Tier 2 spatial compliance results — daylight ratios and fire separation."""
    if not spatial:
        return ""

    has_boundaries = spatial.get("has_boundaries", False)
    warnings = spatial.get("warnings", [])
    daylight = spatial.get("daylight", [])
    fire_sep = spatial.get("fire_separation", [])
    garage_sep = spatial.get("garage_separation", {})

    if not has_boundaries:
        msg = (warnings[0] if warnings else
               "No IfcRelSpaceBoundary data — re-export with Space Boundaries enabled.")
        return _collapsible_card(
            "Spatial Compliance — Tier 2",
            Span(msg, cls="text-sm text-yellow-700"),
        )

    warning_items = [
        Span(w, cls="block text-xs text-yellow-700") for w in warnings
    ]

    # ── Daylight ratio table ──────────────────────────────────────────────────
    daylight_section = ""
    if daylight:
        d_pass = sum(1 for r in daylight if r["passes"])
        d_fail = len(daylight) - d_pass
        rate_cls = "bg-green-100 text-green-800" if d_fail == 0 else "bg-red-100 text-red-800"
        d_rows = []
        for r in sorted(daylight, key=lambda x: x["passes"]):
            status_cls = "text-green-700 font-semibold" if r["passes"] else "text-red-700 font-semibold"
            d_rows.append(
                Tr(
                    Td(r.get("storey_name") or "—", cls="px-3 py-2 text-xs text-muted-foreground"),
                    Td(r["space_name"][:35], cls="px-3 py-2 text-xs"),
                    Td(f"{r['floor_area_m2']:.1f}", cls="px-3 py-2 text-xs font-mono text-right"),
                    Td(f"{r['total_window_area_m2']:.2f}", cls="px-3 py-2 text-xs font-mono text-right"),
                    Td(f"{r['daylight_ratio']:.3f}", cls="px-3 py-2 text-xs font-mono text-right"),
                    Td("✓ Pass" if r["passes"] else "✗ Fail", cls=f"px-3 py-2 text-xs {status_cls}"),
                    cls="border-b border-muted last:border-0",
                )
            )
        daylight_section = _collapsible_section(
            "Daylight Ratio — OBC 9.7.2",
            Div(
                Table(
                    Thead(Tr(
                        Th("Floor", cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted"),
                        Th("Room", cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted"),
                        Th("Floor m²", cls="px-3 py-2 text-right text-xs font-semibold text-muted-foreground bg-muted"),
                        Th("Window m²", cls="px-3 py-2 text-right text-xs font-semibold text-muted-foreground bg-muted"),
                        Th("Ratio", cls="px-3 py-2 text-right text-xs font-semibold text-muted-foreground bg-muted"),
                        Th("Status", cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted"),
                    )),
                    Tbody(*d_rows),
                    cls="w-full text-sm",
                ),
                cls="overflow-auto border rounded-md",
            ),
            badge=f"{d_pass}/{len(daylight)} pass",
        )

    # ── Fire separation table ─────────────────────────────────────────────────
    fire_section = ""
    if fire_sep:
        f_pass = sum(1 for r in fire_sep if r["passes"])
        f_fail = len(fire_sep) - f_pass
        f_rate_cls = "bg-green-100 text-green-800" if f_fail == 0 else "bg-red-100 text-red-800"
        f_rows = []
        for r in sorted(fire_sep, key=lambda x: x["passes"]):
            rating_txt = r["fire_rating_raw"] or "⚠ Not declared"
            rating_cls = "text-red-700" if r["missing_rating"] else (
                "text-green-700" if r["passes"] else "text-orange-700"
            )
            spaces_txt = ", ".join(r["adjacent_spaces"][:2])
            if len(r["adjacent_spaces"]) > 2:
                spaces_txt += f" +{len(r['adjacent_spaces']) - 2}"
            f_rows.append(
                Tr(
                    Td(r["wall_name"][:35], cls="px-3 py-2 text-xs font-mono"),
                    Td(spaces_txt[:50], cls="px-3 py-2 text-xs"),
                    Td(rating_txt, cls=f"px-3 py-2 text-xs font-mono {rating_cls}"),
                    Td("✓ Pass" if r["passes"] else "✗ Fail", cls=f"px-3 py-2 text-xs {rating_cls}"),
                    cls="border-b border-muted last:border-0",
                )
            )
        fire_section = _collapsible_section(
            "Fire Separation — OBC 9.10.9",
            Div(
                Table(
                    Thead(Tr(
                        Th("Wall", cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted"),
                        Th("Between Spaces", cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted"),
                        Th("Fire Rating", cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted"),
                        Th("Status", cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted"),
                    )),
                    Tbody(*f_rows),
                    cls="w-full text-sm",
                ),
                cls="overflow-auto border rounded-md",
            ),
            badge=f"{f_pass}/{len(fire_sep)} pass",
        )

    # ── Garage separation section ─────────────────────────────────────────────
    garage_section = ""
    if garage_sep:
        g_results = garage_sep.get("results", [])
        g_warnings = garage_sep.get("warnings", [])
        g_found = garage_sep.get("garage_spaces_found", 0)

        if g_results:
            g_pass = sum(1 for r in g_results if r["passes"])
            g_rows = []
            for r in sorted(g_results, key=lambda x: x["passes"]):
                rating_txt = r["fire_rating_raw"] or "⚠ Not declared"
                rating_cls = "text-red-700" if r["missing_rating"] else (
                    "text-green-700" if r["passes"] else "text-orange-700"
                )
                req_txt = f"≥ {r['required_min']} min"
                g_rows.append(
                    Tr(
                        Td(r["element_type"], cls="px-3 py-2 text-xs font-semibold"),
                        Td(r["element_name"][:35], cls="px-3 py-2 text-xs font-mono"),
                        Td(r["garage_space"][:25], cls="px-3 py-2 text-xs"),
                        Td(r["adjacent_space"][:25], cls="px-3 py-2 text-xs"),
                        Td(rating_txt, cls=f"px-3 py-2 text-xs font-mono {rating_cls}"),
                        Td(req_txt, cls="px-3 py-2 text-xs font-mono"),
                        Td("✓ Pass" if r["passes"] else "✗ Fail",
                           cls=f"px-3 py-2 text-xs {rating_cls}"),
                        cls="border-b border-muted last:border-0",
                    )
                )
            garage_content = Div(
                Table(
                    Thead(Tr(
                        Th("Type", cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted"),
                        Th("Element", cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted"),
                        Th("Garage Space", cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted"),
                        Th("Adjacent Space", cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted"),
                        Th("Fire Rating", cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted"),
                        Th("Required", cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted"),
                        Th("Status", cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted"),
                    )),
                    Tbody(*g_rows),
                    cls="w-full text-sm",
                ),
                cls="overflow-auto border rounded-md",
            )
            badge = f"{g_pass}/{len(g_results)} pass"
        else:
            garage_content = Div(
                *[Span(w, cls="block text-xs text-yellow-700") for w in g_warnings],
                cls="space-y-1",
            )
            badge = f"{g_found} garage(s)"

        garage_section = _collapsible_section(
            "Garage Separation — OBC 9.10.14.2",
            garage_content,
            badge=badge,
        )

    subtitle = (
        f"{spatial.get('space_count', 0)} spaces · "
        f"{spatial.get('party_wall_count', 0)} party walls"
    )
    return _collapsible_card(
        "Spatial Compliance — Tier 2",
        Div(*[Span(w, cls="block text-xs text-yellow-700") for w in warnings], cls="space-y-1") if warnings else "",
        daylight_section,
        fire_section,
        garage_section,
        subtitle=subtitle,
    )


def _egress_checks_card(egress: dict):
    """Render Tier 3 egress compliance results — exit count and travel distances."""
    if not egress:
        return ""

    exit_data = egress.get("exit_count", {})
    travel = egress.get("travel_distance", [])
    has_graph = egress.get("has_graph", False)
    warnings = egress.get("warnings", [])

    total_exits = exit_data.get("total_exterior_doors", 0)
    exit_results = exit_data.get("results", [])
    exit_warnings = exit_data.get("warnings", [])
    all_warnings = exit_warnings + warnings

    # ── Exit count section ────────────────────────────────────────────────────
    exit_rows = []
    for r in exit_results:
        status_cls = "text-green-700 font-semibold" if r["passes"] else "text-red-700 font-semibold"
        exit_rows.append(
            Tr(
                Td(r["storey"], cls="px-3 py-2 text-xs"),
                Td(str(r["exit_count"]), cls="px-3 py-2 text-xs font-mono text-center"),
                Td(str(r["required_min"]), cls="px-3 py-2 text-xs font-mono text-center"),
                Td("✓ Pass" if r["passes"] else "✗ Fail", cls=f"px-3 py-2 text-xs {status_cls}"),
                cls="border-b border-muted last:border-0",
            )
        )

    exit_section = _collapsible_section(
        "Exit Count — OBC 9.9.4.1",
        Div(
            P(f"Total exterior doors detected: {total_exits}", cls="text-sm mb-2"),
            Div(
                Table(
                    Thead(Tr(
                        Th("Storey", cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted"),
                        Th("Exits", cls="px-3 py-2 text-center text-xs font-semibold text-muted-foreground bg-muted"),
                        Th("Required", cls="px-3 py-2 text-center text-xs font-semibold text-muted-foreground bg-muted"),
                        Th("Status", cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted"),
                    )),
                    Tbody(*exit_rows) if exit_rows else Tbody(
                        Tr(Td("No exterior doors found — tag doors as IsExternal=True",
                              cls="px-3 py-2 text-xs text-yellow-700", colspan="4"))
                    ),
                    cls="w-full text-sm",
                ),
                cls="overflow-auto border rounded-md",
            ),
        ) if exit_results else P(
            "No exterior doors found — tag doors as IsExternal=True in the authoring tool.",
            cls="text-sm text-yellow-700",
        ),
        badge=f"{total_exits} exit(s)",
    )

    # ── Travel distance section ───────────────────────────────────────────────
    travel_section = ""
    if travel:
        td_pass = sum(1 for r in travel if r["passes"])
        td_fail = len(travel) - td_pass
        td_rows = []
        for r in sorted(travel, key=lambda x: (x["passes"], -(x.get("travel_distance_m") or 0))):
            dist_txt = (
                f"{r['travel_distance_m']:.1f} m"
                if r.get("travel_distance_m") is not None
                else "No path"
            )
            status_cls = "text-green-700 font-semibold" if r["passes"] else "text-red-700 font-semibold"
            td_rows.append(
                Tr(
                    Td(r.get("storey_name") or "—", cls="px-3 py-2 text-xs text-muted-foreground"),
                    Td(r["space_name"][:35], cls="px-3 py-2 text-xs"),
                    Td(dist_txt, cls="px-3 py-2 text-xs font-mono text-right"),
                    Td(r.get("nearest_exit") or "—", cls="px-3 py-2 text-xs"),
                    Td("✓ Pass" if r["passes"] else ("✗ No path" if r.get("no_path") else "✗ Exceeds"),
                       cls=f"px-3 py-2 text-xs {status_cls}"),
                    cls="border-b border-muted last:border-0",
                )
            )
        travel_section = _collapsible_section(
            "Travel Distance — OBC 9.9.10.1",
            Div(
                Table(
                    Thead(Tr(
                        Th("Floor", cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted"),
                        Th("Room", cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted"),
                        Th("Distance", cls="px-3 py-2 text-right text-xs font-semibold text-muted-foreground bg-muted"),
                        Th("Nearest Exit", cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted"),
                        Th("Status", cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted"),
                    )),
                    Tbody(*td_rows),
                    cls="w-full text-sm",
                ),
                cls="overflow-auto border rounded-md",
            ),
            badge=f"{td_pass}/{len(travel)} pass",
        )
    elif not has_graph:
        travel_section = _collapsible_section(
            "Travel Distance — OBC 9.9.10.1",
            P(
                "Space boundary data required. Re-export the IFC model with "
                "Space Boundaries enabled to activate this check.",
                cls="text-sm text-yellow-700",
            ),
        )

    warning_items = [Span(w, cls="block text-xs text-yellow-700") for w in all_warnings]

    subtitle = f"{total_exits} exit(s) · {len(travel)} rooms checked"
    return _collapsible_card(
        "Egress Compliance — Tier 3",
        Div(*warning_items, cls="space-y-1") if warning_items else "",
        exit_section,
        travel_section,
        subtitle=subtitle,
    )


# Module-level cache for CSV export (populated in analysis_run_post)
_last_compliance_results: list[dict] = []


# ══════════════════════════════════════════════════════════════════════════════
# Simple Analysis — domain-based compliance card helpers
# ══════════════════════════════════════════════════════════════════════════════

def _fmt_val_s(v) -> str:
    """Format a numeric compliance value for display."""
    if isinstance(v, float):
        return f"{v:,.2f}" if v >= 1 else f"{v:.4f}"
    return str(v) if v is not None else "—"


def _domain_badge(rule_results: list) -> tuple:
    """Return (label, tailwind_cls) from a list of Module 4 rule result dicts."""
    if not rule_results:
        return "N/A", "bg-gray-100 text-gray-500"
    statuses = [r.get("status", "NO_ELEMENTS") for r in rule_results]
    real = [s for s in statuses if s != "NO_ELEMENTS"]
    if not real:
        return "N/A", "bg-gray-100 text-gray-500"
    n_fail = real.count("FAIL")
    if n_fail:
        return f"{n_fail} rule(s) failed", "bg-red-100 text-red-800"
    if any(s in ("MISSING_DATA", "PARTIAL") for s in real):
        return "Missing data", "bg-yellow-100 text-yellow-800"
    return "All pass", "bg-green-100 text-green-800"


def _simple_elem_tbl(elements: list, operator: str = "", check_val=None, unit: str = ""):
    """Scrollable element table with Floor/Room/GUID/Actual/Required/Issue columns."""
    if not elements:
        return P("No elements.", cls="text-xs text-muted-foreground")

    def _req(op, cv, u):
        if op == ">=" and cv is not None: return f"≥ {cv} {u}".strip()
        if op == "<=" and cv is not None: return f"≤ {cv} {u}".strip()
        if op == "between": return "in range"
        return f"{op} {cv} {u}".strip() if cv is not None else "—"

    rows = []
    for el in elements[:30]:
        actual = el.get("actual") if "actual" in el else el.get("actual_value")
        reason = el.get("reason") or ""
        storey = el.get("storey") or "—"
        space = el.get("space") or ""
        guid = (el.get("guid") or "")[:14]
        name = (el.get("element_name") or el.get("name") or "—")[:32]
        is_fail = bool(reason)
        rows.append(Tr(
            Td(Span(name, cls="text-xs font-mono"), cls="px-3 py-2"),
            Td(
                Span(storey, cls="text-xs block"),
                Span(space, cls="text-xs text-muted-foreground block") if space else "",
                cls="px-3 py-2",
            ),
            Td(Span(guid, cls="text-xs font-mono text-muted-foreground"), cls="px-3 py-2"),
            Td(
                _fmt_val_s(actual) + (f" {unit}" if unit and actual is not None else ""),
                cls="px-3 py-2 text-xs font-mono",
            ),
            Td(_req(operator, check_val, unit), cls="px-3 py-2 text-xs text-muted-foreground"),
            Td(
                Span(
                    reason if reason else "missing",
                    cls=f"text-xs font-semibold {'text-red-700' if is_fail else 'text-yellow-700'}",
                ),
                cls="px-3 py-2",
            ),
            cls="border-b border-muted last:border-0",
        ))
    if len(elements) > 30:
        rows.append(Tr(Td(
            f"… and {len(elements) - 30} more",
            cls="px-3 py-2 text-xs text-muted-foreground italic",
            colspan="6",
        )))
    return Div(
        Table(
            Thead(Tr(*[
                Th(h, cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted")
                for h in ("Element", "Floor / Room", "GUID", "Actual", "Required", "Issue")
            ])),
            Tbody(*rows),
            cls="w-full text-xs",
        ),
        cls="overflow-auto border rounded-md max-h-64",
    )


def _simple_rule_section(rule: dict):
    """Collapsible sub-section for one Module 4 rule check."""
    status = rule.get("status", "NO_ELEMENTS")
    if status == "NO_ELEMENTS":
        return ""
    ref = rule.get("rule_ref", "") or ""
    desc = (rule.get("rule_desc", "") or "")[:65]
    operator = rule.get("operator", "")
    check_val = rule.get("check_value")
    unit = rule.get("unit", "") or ""
    pass_c = rule.get("pass_count", 0)
    fail_c = rule.get("fail_count", 0)
    miss_c = rule.get("missing_count", 0)
    total = rule.get("total_count", 0)
    failures = rule.get("failures", [])
    missing_els = rule.get("missing_elements", [])

    if operator == ">=":        req_str = f"≥ {check_val} {unit}".strip()
    elif operator == "<=":      req_str = f"≤ {check_val} {unit}".strip()
    elif operator == "between": req_str = f"{rule.get('value_min')}–{rule.get('value_max')} {unit}".strip()
    elif operator == "exists":  req_str = "must be present"
    else:                       req_str = f"{operator} {check_val} {unit}".strip() if check_val is not None else "—"

    summary_txt = (
        f"{fail_c} fail · {pass_c} pass · {miss_c} missing"
        if fail_c or miss_c else f"{pass_c}/{total} pass"
    )
    label = f"{ref}  {desc}" if ref else desc

    parts = []
    if failures:
        parts.append(Div(
            P(f"{fail_c} element(s) failing:", cls="text-xs font-semibold text-red-700 mb-1"),
            _simple_elem_tbl(failures, operator, check_val, unit),
        ))
    if missing_els:
        parts.append(Div(
            P(f"{miss_c} element(s) missing this property:",
              cls="text-xs font-semibold text-yellow-700 mb-1 mt-3"),
            _simple_elem_tbl(missing_els),
        ))
    if not parts:
        parts = [P(f"✓ All {pass_c} elements pass.", cls="text-xs text-green-700")]

    return _collapsible_section(
        label, *parts,
        badge=f"{summary_txt}  ·  {req_str}",
        open=status in ("FAIL", "MISSING_DATA"),
    )


def _simple_domain_card(
    title: str,
    obc_ref: str,
    rule_results: list,
    extra_sections: list | None = None,
    override_badge: tuple | None = None,
):
    """Outer collapsible card for one building code domain."""
    status_label, badge_cls = _domain_badge(rule_results)
    if override_badge:
        status_label, badge_cls = override_badge

    rule_secs = [_simple_rule_section(r) for r in rule_results]
    all_content = [s for s in rule_secs if s] + (extra_sections or [])

    has_fail = any(r.get("status") == "FAIL" for r in rule_results)
    if override_badge and "fail" in (override_badge[0] or "").lower():
        has_fail = True

    if not all_content:
        all_content = [
            P("No applicable checks found in the rule library for this category.",
              cls="text-sm text-muted-foreground italic")
        ]

    return _collapsible_card(
        title,
        Div(
            Span(obc_ref, cls="text-xs text-muted-foreground mr-2"),
            Span(status_label,
                 cls=f"inline-block px-2 py-0.5 rounded text-xs font-semibold {badge_cls}"),
            cls="flex items-center mb-4",
        ),
        *all_content,
        open=has_fail,
    )


# ── Domain card builders ───────────────────────────────────────────────────────

def _simple_windows_card(by_class: dict, spatial_checks: dict):
    rules = by_class.get("IfcWindow", [])
    daylight = (spatial_checks or {}).get("daylight", [])
    extra = []
    override = None

    if daylight:
        d_pass = sum(1 for r in daylight if r["passes"])
        d_fail = len(daylight) - d_pass
        d_rows = []
        for r in sorted(daylight, key=lambda x: x["passes"]):
            sc = "text-green-700 font-semibold" if r["passes"] else "text-red-700 font-semibold"
            d_rows.append(Tr(
                Td(r.get("storey_name") or "—", cls="px-3 py-2 text-xs text-muted-foreground"),
                Td(r["space_name"][:35], cls="px-3 py-2 text-xs"),
                Td(f"{r['floor_area_m2']:.1f}", cls="px-3 py-2 text-xs font-mono text-right"),
                Td(f"{r['total_window_area_m2']:.2f}", cls="px-3 py-2 text-xs font-mono text-right"),
                Td(f"{r['daylight_ratio']:.3f}", cls="px-3 py-2 text-xs font-mono text-right"),
                Td("✓ Pass" if r["passes"] else "✗ Fail", cls=f"px-3 py-2 text-xs {sc}"),
                cls="border-b border-muted last:border-0",
            ))
        extra.append(_collapsible_section(
            "Daylight Ratio — OBC 9.7.2.1 (≥ 1/10 floor area)",
            Div(
                Table(
                    Thead(Tr(*[
                        Th(h, cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted")
                        for h in ("Floor", "Room", "Floor m²", "Window m²", "Ratio", "Status")
                    ])),
                    Tbody(*d_rows),
                    cls="w-full text-xs",
                ),
                cls="overflow-auto border rounded-md max-h-64",
            ),
            badge=f"{d_pass}/{len(daylight)} pass",
            open=d_fail > 0,
        ))
        if d_fail > 0 and not any(r.get("status") == "FAIL" for r in rules):
            override = (f"{d_fail} room(s) below daylight ratio", "bg-red-100 text-red-800")

    return _simple_domain_card("Windows & Glazing", "OBC 9.7 · 9.8", rules, extra, override)


def _simple_doors_card(by_class: dict):
    return _simple_domain_card("Doors", "OBC 9.5 · 9.9.5", by_class.get("IfcDoor", []))


def _simple_stairs_card(by_class: dict):
    rules = by_class.get("IfcStairFlight", []) + by_class.get("IfcRailing", [])
    return _simple_domain_card("Stairs, Guards & Handrails", "OBC 9.8.1 · 9.8.7", rules)


def _simple_ramps_card(by_class: dict):
    rules = by_class.get("IfcRamp", []) + by_class.get("IfcRampFlight", [])
    return _simple_domain_card("Ramps", "OBC 9.8.8", rules)


def _simple_egress_card(egress: dict):
    """Egress domain card built from Tier 3 egress check results."""
    if not egress:
        return _simple_domain_card("Means of Egress", "OBC 9.9 · 9.10", [])

    exit_data = egress.get("exit_count", {})
    travel = egress.get("travel_distance", [])
    total_exits = exit_data.get("total_exterior_doors", 0)
    exit_results = exit_data.get("results", [])

    all_passes = [r["passes"] for r in exit_results] + [r["passes"] for r in travel]
    if not all_passes:
        override = ("N/A", "bg-gray-100 text-gray-500")
    elif all(all_passes):
        override = ("All pass", "bg-green-100 text-green-800")
    else:
        fail_n = sum(1 for p in all_passes if not p)
        override = (f"{fail_n} check(s) failed", "bg-red-100 text-red-800")

    extra = []
    if exit_results:
        e_rows = []
        for r in exit_results:
            sc = "text-green-700 font-semibold" if r["passes"] else "text-red-700 font-semibold"
            e_rows.append(Tr(
                Td(r["storey"], cls="px-3 py-2 text-xs"),
                Td(str(r["exit_count"]), cls="px-3 py-2 text-xs font-mono text-center"),
                Td(str(r["required_min"]), cls="px-3 py-2 text-xs font-mono text-center"),
                Td("✓ Pass" if r["passes"] else "✗ Fail", cls=f"px-3 py-2 text-xs {sc}"),
                cls="border-b border-muted last:border-0",
            ))
        extra.append(_collapsible_section(
            f"Exit Count — OBC 9.9.4.1  ({total_exits} exterior door(s))",
            Div(
                Table(
                    Thead(Tr(*[
                        Th(h, cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted")
                        for h in ("Storey", "Exits", "Required", "Status")
                    ])),
                    Tbody(*e_rows),
                    cls="w-full text-xs",
                ),
                cls="overflow-auto border rounded-md",
            ),
            badge=f"{sum(1 for r in exit_results if r['passes'])}/{len(exit_results)} pass",
            open=any(not r["passes"] for r in exit_results),
        ))
    else:
        extra.append(_collapsible_section(
            "Exit Count — OBC 9.9.4.1",
            P("No exterior doors found. Tag doors as IsExternal=True in your authoring tool.",
              cls="text-xs text-yellow-700"),
            open=True,
        ))

    if travel:
        td_pass = sum(1 for r in travel if r["passes"])
        td_rows = []
        for r in sorted(travel, key=lambda x: (x["passes"], -(x.get("travel_distance_m") or 0))):
            dist = f"{r['travel_distance_m']:.1f} m" if r.get("travel_distance_m") is not None else "No path"
            sc = "text-green-700 font-semibold" if r["passes"] else "text-red-700 font-semibold"
            td_rows.append(Tr(
                Td(r.get("storey_name") or "—", cls="px-3 py-2 text-xs text-muted-foreground"),
                Td(r["space_name"][:35], cls="px-3 py-2 text-xs"),
                Td(dist, cls="px-3 py-2 text-xs font-mono text-right"),
                Td(r.get("nearest_exit") or "—", cls="px-3 py-2 text-xs"),
                Td(
                    "✓ Pass" if r["passes"] else ("✗ No path" if r.get("no_path") else "✗ Exceeds"),
                    cls=f"px-3 py-2 text-xs {sc}",
                ),
                cls="border-b border-muted last:border-0",
            ))
        extra.append(_collapsible_section(
            "Travel Distance — OBC 9.9.10.1",
            Div(
                Table(
                    Thead(Tr(*[
                        Th(h, cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted")
                        for h in ("Floor", "Room", "Distance", "Nearest Exit", "Status")
                    ])),
                    Tbody(*td_rows),
                    cls="w-full text-xs",
                ),
                cls="overflow-auto border rounded-md max-h-64",
            ),
            badge=f"{td_pass}/{len(travel)} pass",
            open=td_pass < len(travel),
        ))

    return _simple_domain_card("Means of Egress", "OBC 9.9 · 9.10", [], extra, override)


def _simple_washrooms_card(by_class: dict, building_summary: dict):
    rules = by_class.get("IfcSanitaryTerminal", [])
    return _simple_domain_card("Washrooms & Accessibility", "OBC 9.5 · 3.8.3", rules)


def _simple_plumbing_card(building_summary: dict):
    fixture_counts = (building_summary or {}).get("fixture_counts", {})
    if not fixture_counts:
        return _simple_domain_card(
            "Plumbing Fixture Counts", "OBC 9.32 · NBC", [],
            override_badge=("N/A — no fixtures found", "bg-gray-100 text-gray-500"),
        )
    badges = [
        Span(f"{k}: {v}",
             cls="inline-block px-2 py-1 rounded-full text-xs bg-cyan-50 text-cyan-800 border border-cyan-200 font-medium")
        for k, v in sorted(fixture_counts.items())
    ]
    return _simple_domain_card(
        "Plumbing Fixture Counts", "OBC 9.32 · NBC", [],
        extra_sections=[_collapsible_section(
            "Fixture Inventory",
            Div(*badges, cls="flex flex-wrap gap-2"),
            badge=f"{sum(fixture_counts.values())} fixtures",
            open=True,
        )],
        override_badge=("Inventory only", "bg-blue-100 text-blue-800"),
    )


def _simple_fire_card(by_class: dict, spatial_checks: dict, building_summary: dict):
    rules = by_class.get("IfcAlarm", [])
    spatial = spatial_checks or {}
    fire_sep = spatial.get("fire_separation", [])
    alarm_counts = (building_summary or {}).get("alarm_counts", {})
    extra = []
    override = None

    if fire_sep:
        f_pass = sum(1 for r in fire_sep if r["passes"])
        f_fail = len(fire_sep) - f_pass
        f_rows = []
        for r in sorted(fire_sep, key=lambda x: x["passes"]):
            rating_txt = r["fire_rating_raw"] or "⚠ Not declared"
            rc = "text-red-700" if r["missing_rating"] else (
                "text-green-700" if r["passes"] else "text-orange-700"
            )
            spaces_txt = ", ".join(r["adjacent_spaces"][:2])
            if len(r["adjacent_spaces"]) > 2:
                spaces_txt += f" +{len(r['adjacent_spaces']) - 2}"
            f_rows.append(Tr(
                Td(r["wall_name"][:35], cls="px-3 py-2 text-xs font-mono"),
                Td(spaces_txt[:50], cls="px-3 py-2 text-xs"),
                Td(rating_txt, cls=f"px-3 py-2 text-xs font-mono {rc}"),
                Td("✓ Pass" if r["passes"] else "✗ Fail", cls=f"px-3 py-2 text-xs {rc}"),
                cls="border-b border-muted last:border-0",
            ))
        extra.append(_collapsible_section(
            "Fire Separation — OBC 9.10.9",
            Div(
                Table(
                    Thead(Tr(*[
                        Th(h, cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted")
                        for h in ("Wall", "Between Spaces", "Fire Rating", "Status")
                    ])),
                    Tbody(*f_rows),
                    cls="w-full text-xs",
                ),
                cls="overflow-auto border rounded-md max-h-64",
            ),
            badge=f"{f_pass}/{len(fire_sep)} pass",
            open=f_fail > 0,
        ))
        if f_fail > 0:
            override = (f"{f_fail} separation issue(s)", "bg-red-100 text-red-800")

    if alarm_counts:
        alarm_badges = [
            Span(f"{k}: {v}",
                 cls="inline-block px-2 py-1 rounded-full text-xs bg-red-50 text-red-800 border border-red-200 font-medium")
            for k, v in sorted(alarm_counts.items())
        ]
        extra.append(_collapsible_section(
            "Alarm Inventory",
            Div(*alarm_badges, cls="flex flex-wrap gap-2"),
            badge=f"{sum(alarm_counts.values())} alarms",
            open=False,
        ))

    return _simple_domain_card("Fire Protection (House-Level)", "OBC 9.10 · NBC 3.2",
                                rules, extra, override)


def _simple_garage_card(spatial_checks: dict):
    spatial = spatial_checks or {}
    garage_sep = spatial.get("garage_separation", {})
    if not garage_sep:
        return _simple_domain_card(
            "Garage / Carport", "OBC 9.10.14", [],
            override_badge=("N/A — no garage detected", "bg-gray-100 text-gray-500"),
        )

    g_results = garage_sep.get("results", [])
    g_warnings = garage_sep.get("warnings", [])
    extra = []
    override = None

    if g_results:
        g_pass = sum(1 for r in g_results if r["passes"])
        g_fail = len(g_results) - g_pass
        g_rows = []
        for r in sorted(g_results, key=lambda x: x["passes"]):
            rating_txt = r["fire_rating_raw"] or "⚠ Not declared"
            rc = "text-red-700" if r["missing_rating"] else (
                "text-green-700" if r["passes"] else "text-orange-700"
            )
            g_rows.append(Tr(
                Td(r["element_type"], cls="px-3 py-2 text-xs font-semibold"),
                Td(r["element_name"][:35], cls="px-3 py-2 text-xs font-mono"),
                Td(r["garage_space"][:25], cls="px-3 py-2 text-xs"),
                Td(r["adjacent_space"][:25], cls="px-3 py-2 text-xs"),
                Td(rating_txt, cls=f"px-3 py-2 text-xs font-mono {rc}"),
                Td(f"≥ {r['required_min']} min", cls="px-3 py-2 text-xs font-mono"),
                Td("✓ Pass" if r["passes"] else "✗ Fail", cls=f"px-3 py-2 text-xs {rc}"),
                cls="border-b border-muted last:border-0",
            ))
        extra.append(_collapsible_section(
            "Garage Fire Separation — OBC 9.10.14.2",
            Div(
                Table(
                    Thead(Tr(*[
                        Th(h, cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted")
                        for h in ("Type", "Element", "Garage Space", "Adjacent", "Rating", "Required", "Status")
                    ])),
                    Tbody(*g_rows),
                    cls="w-full text-xs",
                ),
                cls="overflow-auto border rounded-md max-h-64",
            ),
            badge=f"{g_pass}/{len(g_results)} pass",
            open=g_fail > 0,
        ))
        if g_fail > 0:
            override = (f"{g_fail} separation issue(s)", "bg-red-100 text-red-800")
    elif g_warnings:
        extra.append(_collapsible_section(
            "Garage Fire Separation — OBC 9.10.14.2",
            Div(*[Span(w, cls="block text-xs text-yellow-700") for w in g_warnings]),
            open=True,
        ))

    return _simple_domain_card("Garage / Carport", "OBC 9.10.14", [], extra, override)


def setup_routes(rt):
    """Register analysis workflow routes."""

    @rt("/analysis/simple")
    def analysis_simple():
        projects = _projects_service.list_projects()
        documents = _documents_service.list_documents()
        return Title("Simple Analysis - BIM Guard"), DashboardLayout(
            Container(_analysis_form(projects, documents, mode="simple"), cls="space-y-4")
        )

    @rt("/analysis/simple/results", methods=["POST"])
    async def analysis_simple_post(req: Request):
        form = await req.form()
        project_id_raw = form.get("project_id") or ""
        if not project_id_raw:
            return Alert("Please select a project.", cls=AlertT.error)
        try:
            project_id = int(project_id_raw)
        except ValueError:
            return Alert("Invalid project selection.", cls=AlertT.error)

        result = _bim_guard_app.orchestrate_workflow(
            project_id,
            doc_ids=[],
            analysis_theme="Architecture",
            include_openings=True,
            include_spaces=True,
            include_type_definitions=False,
        )
        if "error" in result:
            return Alert(result["error"], cls=AlertT.error)

        from collections import defaultdict
        project = result["project"]
        rule_compliance = result.get("rule_compliance", [])
        spatial_checks = result.get("spatial_checks", {})
        egress_checks = result.get("egress_checks", {})
        building_summary = result.get("building_summary", {})

        by_class: dict = defaultdict(list)
        for r in rule_compliance:
            by_class[r.get("target", "")].append(r)

        bldg_card = _building_summary_card(building_summary)

        sections = [
            Card(
                CardHeader(CardTitle(f"{project.get('name', 'Project')} — Simple Analysis")),
                CardContent(P(
                    "Domain-based compliance check against OBC Part 9.",
                    cls="text-sm text-muted-foreground",
                )),
            ),
            *(([bldg_card]) if bldg_card else []),
            _simple_windows_card(by_class, spatial_checks),
            _simple_doors_card(by_class),
            _simple_stairs_card(by_class),
            _simple_ramps_card(by_class),
            _simple_egress_card(egress_checks),
            _simple_washrooms_card(by_class, building_summary),
            _simple_plumbing_card(building_summary),
            _simple_fire_card(by_class, spatial_checks, building_summary),
            _simple_garage_card(spatial_checks),
        ]
        return Div(*sections, cls="space-y-4")

    @rt("/analysis/initial")
    def analysis_initial():
        projects = _projects_service.list_projects()
        documents = _documents_service.list_documents()

        return Title("Initial Analysis - BIM Guard"), DashboardLayout(
            Container(_analysis_form(projects, documents, mode="initial"), cls="space-y-4")
        )

    @rt("/analysis/run")
    def analysis_run():
        projects = _projects_service.list_projects()
        documents = _documents_service.list_documents()

        return Title("Model Vs Rules Analysis - BIM Guard"), DashboardLayout(
            Container(_analysis_form(projects, documents, mode="model-rules"), cls="space-y-4")
        )

    @rt("/analysis/initial/results", methods=["POST"])
    async def analysis_initial_post(req: Request):
        analysis_data, error_response = await _run_analysis_request(req)
        if error_response:
            return error_response

        project_id = analysis_data["project_id"]
        result = analysis_data["result"]
        project = result["project"]
        selected_theme = result.get("analysis_theme", "Architecture")

        bldg_card = _building_summary_card(result.get("building_summary", {}))
        spatial_card = _spatial_checks_card(result.get("spatial_checks", {}))
        egress_card = _egress_checks_card(result.get("egress_checks", {}))

        sections = [
            Card(
                CardHeader(CardTitle(f"{project.get('name', 'Project')} — {selected_theme} Theme")),
                CardContent(_build_ifc_summary_content(result, project_id)),
            ),
            *(([bldg_card]) if bldg_card else []),
            *(([spatial_card]) if spatial_card else []),
            *(([egress_card]) if egress_card else []),
            _build_ifc_graph_card(result, project_id),
        ]

        return Div(*sections, cls="space-y-4")

    @rt("/analysis/results", methods=["POST"])
    async def analysis_run_post(req: Request):
        analysis_data, error_response = await _run_analysis_request(req)
        if error_response:
            return error_response

        result = analysis_data["result"]
        project = result["project"]
        selected_theme = result.get("analysis_theme", "Architecture")

        compliance_card = _compliance_card(
            results=result.get("compliance_results", []),
            cost_impact=result.get("cost_impact"),
            issue_stats=result.get("issue_stats", {}),
            is_demo=result.get("compliance_is_demo", False),
            project_id=result.get("bcf_project_id"),
            error=result.get("compliance_error"),
        )

        rule_validation_card = _rule_validation_card(
            result.get("rule_validations", []), selected_theme
        )

        rc = result.get("rule_compliance", [])
        rc_summary = result.get("rule_compliance_summary", {})
        rc_error = result.get("rule_compliance_error")

        # Cache for CSV download
        global _last_compliance_results
        _last_compliance_results = rc

        rule_compliance_card = _rule_compliance_card(rc, rc_summary, rc_error, selected_theme)

        bldg_card = _building_summary_card(result.get("building_summary", {}))
        spatial_card = _spatial_checks_card(result.get("spatial_checks", {}))
        egress_card = _egress_checks_card(result.get("egress_checks", {}))

        sections = [
            Card(
                CardHeader(CardTitle(f"{project.get('name', 'Project')} — {selected_theme} Theme")),
                CardContent(
                    P(
                        "Model loaded and ready for rule comparison against the saved library rules.",
                        cls="text-sm text-muted-foreground",
                    )
                ),
            ),
            *(([bldg_card]) if bldg_card else []),
            *(([spatial_card]) if spatial_card else []),
            *(([egress_card]) if egress_card else []),
            rule_validation_card,
        ]
        if rule_compliance_card:
            sections.append(rule_compliance_card)
        if selected_theme == "MEP" and compliance_card:
            sections.append(compliance_card)

        return Div(*sections, cls="space-y-4")

    @rt("/reports/compliance-csv")
    def compliance_csv_download():
        """Download the last rule compliance check as a CSV file."""
        from starlette.responses import Response as StarletteResponse
        from app.modules.module5_reporter import Module5_Reporter

        csv_content = Module5_Reporter().generate_csv_summary(_last_compliance_results)
        return StarletteResponse(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="compliance_results.csv"'},
        )

    @rt("/reports/bcf/{project_id}")
    def bcf_download(project_id: int):
        from starlette.responses import Response as StarletteResponse

        bcf_file = os.path.join(_DATA_DIR, f"compliance_project_{project_id}.bcf")
        if not os.path.exists(bcf_file):
            return Alert(
                "BCF file not found. Run the analysis first to generate the report.",
                cls=AlertT.error,
            )
        with open(bcf_file, "rb") as fh:
            bcf_bytes = fh.read()
        return StarletteResponse(
            content=bcf_bytes,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="compliance_project_{project_id}.bcf"'
                )
            },
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
