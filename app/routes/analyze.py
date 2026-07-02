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
        Div(
            FormLabel("Analysis Theme", fr="analysis_theme"),
            Select(
                Option("Architecture", value="Architecture", selected=True),
                Option("MEP", value="MEP"),
                id="analysis_theme",
                name="analysis_theme",
                required=True,
            ),
        ),
    ]

    if not is_initial:
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

    submit_label = "Run Initial Analysis" if is_initial else "Run Model Vs Rules Analysis"
    spinner_id = "initial-analysis-spinner" if is_initial else "model-rules-spinner"
    results_id = "initial-analysis-results" if is_initial else "model-rules-results"
    hx_post = "/analysis/initial/results" if is_initial else "/analysis/results"
    card_title = "Initial Analysis" if is_initial else "Model Vs Rules Analysis"
    helper_copy = (
        "Inspect the IFC model structure, counts, and quality signals before checking rules."
        if is_initial
        else "Compare the selected IFC model against the saved rules in the library."
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
                            Div(
                                P(
                                    "Running analysis…",
                                    cls="text-sm text-muted-foreground",
                                ),
                                id=spinner_id,
                                cls="htmx-indicator",
                                style="display:none",
                            ),
                            cls="flex items-center gap-4",
                        ),
                    ),
                    method="post",
                    action=hx_post,
                    hx_post=hx_post,
                    hx_target=f"#{results_id}",
                    hx_swap="innerHTML",
                    hx_indicator=f"#{spinner_id}",
                ),
            ),
        ),
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
        Card(
            CardHeader(CardTitle("IFC Quality")),
            CardContent(
                P(
                    f"Overall score: {overall.get('score', 0):.1f}%",
                    cls="text-sm font-medium",
                ),
                Div(
                    P(
                        f"Labeling: {labeling.get('score', 0):.1f}%",
                        cls="text-xs text-muted-foreground",
                    ),
                    P(
                        f"GUIDs: {guids.get('score', 0):.1f}%",
                        cls="text-xs text-muted-foreground",
                    ),
                    P(
                        f"Properties: {properties.get('score', 0):.1f}%",
                        cls="text-xs text-muted-foreground",
                    ),
                    cls="space-y-1 mt-2",
                ),
                *quality_alerts,
            ),
        )
        if ifc_quality
        else ""
    )

    improvement_block = (
        Card(
            CardHeader(
                Div(
                    CardTitle("Improvement Summary"),
                    P(
                        "Automatic fixes applied while preparing this IFC file for analysis.",
                        cls="text-xs text-muted-foreground mt-0.5",
                    ),
                )
            ),
            CardContent(
                Div(
                    *[
                        P(message, cls="text-sm text-muted-foreground")
                        for message in ifc_quality_improvements
                    ],
                    cls="space-y-1",
                )
            ),
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

    return Card(
        CardHeader(CardTitle("Corrosion Compliance — GC-001 / CC-001")),
        CardContent(
            demo_notice,
            badge_row,
            cost_line,
            tracker_line,
            results_table,
            bcf_btn,
        ),
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

    return Card(
        CardHeader(
            Div(
                CardTitle(f"Rule Validation — Module 3 ({analysis_theme})"),
                P(
                    "Each library rule is checked against the IFC model. "
                    "'No elements' means that IFC class is absent from this model.",
                    cls="text-xs text-muted-foreground mt-0.5",
                ),
            )
        ),
        CardContent(
            summary,
            Div(
                Table(
                    Thead(Tr(*header_cells)),
                    Tbody(*data_rows),
                    cls="w-full text-sm",
                ),
                cls="overflow-auto border rounded-md",
            ),
        ),
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
                fail_rows = [
                    Tr(
                        Td(f.get("element_name", "")[:40], cls="px-2 py-1 text-xs font-mono"),
                        Td(str(f.get("actual", "")), cls="px-2 py-1 text-xs"),
                        Td(f.get("reason", ""), cls="px-2 py-1 text-xs text-red-700"),
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
                                    Th("Actual value", cls="px-2 py-1 text-xs bg-muted"),
                                    Th("Reason", cls="px-2 py-1 text-xs bg-muted"),
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
                        Td(m.get("element_name", "")[:40], cls="px-2 py-1 text-xs font-mono"),
                        Td(m.get("storey", "—"), cls="px-2 py-1 text-xs"),
                        Td(m.get("guid", "")[:20], cls="px-2 py-1 text-xs text-muted-foreground font-mono"),
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
                                    Th("Storey", cls="px-2 py-1 text-xs bg-muted"),
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

    return Card(
        CardHeader(
            Div(
                CardTitle(title),
                P(
                    "Full property-level compliance check against every rule in the library.",
                    cls="text-xs text-muted-foreground mt-0.5",
                ),
            )
        ),
        CardContent(
            summary_bar,
            Div(
                Table(Thead(Tr(*header_cells)), Tbody(*rows), cls="w-full text-sm"),
                cls="overflow-auto border rounded-md",
            ),
            csv_btn,
        ),
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
                    Td(f"{h_mm:,} mm" if h_mm else "—", cls="px-3 py-2 text-sm font-mono"),
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

    return Card(
        CardHeader(CardTitle("Building Overview")),
        CardContent(
            stat_strip,
            floor_table,
            elem_badges,
            fixture_badges,
            alarm_badges,
            qa_block,
        ),
    )


def _spatial_checks_card(spatial: dict):
    """Render Tier 2 spatial compliance results — daylight ratios and fire separation."""
    if not spatial:
        return ""

    has_boundaries = spatial.get("has_boundaries", False)
    warnings = spatial.get("warnings", [])
    daylight = spatial.get("daylight", [])
    fire_sep = spatial.get("fire_separation", [])

    if not has_boundaries:
        msg = (warnings[0] if warnings else
               "No IfcRelSpaceBoundary data — re-export with Space Boundaries enabled.")
        return Card(
            CardHeader(CardTitle("Spatial Compliance — Tier 2")),
            CardContent(
                Span(
                    msg,
                    cls="text-sm text-yellow-700",
                )
            ),
        )

    warning_items = [
        Span(w, cls="block text-xs text-yellow-700") for w in warnings
    ]

    # ── Daylight ratio table ──────────────────────────────────────────────────
    daylight_block = ""
    if daylight:
        d_pass = sum(1 for r in daylight if r["passes"])
        d_fail = len(daylight) - d_pass
        rate_cls = "bg-green-100 text-green-800" if d_fail == 0 else "bg-red-100 text-red-800"
        d_rows = []
        for r in sorted(daylight, key=lambda x: x["passes"]):
            status_cls = "text-green-700 font-semibold" if r["passes"] else "text-red-700 font-semibold"
            d_rows.append(
                Tr(
                    Td(r["space_name"][:40], cls="px-3 py-2 text-xs"),
                    Td(f"{r['floor_area_m2']:.1f}", cls="px-3 py-2 text-xs font-mono text-right"),
                    Td(f"{r['total_window_area_m2']:.2f}", cls="px-3 py-2 text-xs font-mono text-right"),
                    Td(f"{r['daylight_ratio']:.3f}", cls="px-3 py-2 text-xs font-mono text-right"),
                    Td("✓ Pass" if r["passes"] else "✗ Fail", cls=f"px-3 py-2 text-xs {status_cls}"),
                    cls="border-b border-muted last:border-0",
                )
            )
        daylight_block = Div(
            Div(
                H3("Daylight Ratio — OBC 9.7.2", cls="text-sm font-semibold"),
                Span(
                    f"{d_pass}/{len(daylight)} pass",
                    cls=f"text-xs px-2 py-0.5 rounded-full font-medium {rate_cls}",
                ),
                cls="flex items-center justify-between mb-2",
            ),
            Div(
                Table(
                    Thead(Tr(
                        Th("Room", cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted"),
                        Th("Floor m²", cls="px-3 py-2 text-right text-xs font-semibold text-muted-foreground bg-muted"),
                        Th("Window m²", cls="px-3 py-2 text-right text-xs font-semibold text-muted-foreground bg-muted"),
                        Th("Ratio", cls="px-3 py-2 text-right text-xs font-semibold text-muted-foreground bg-muted"),
                        Th("Status", cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted"),
                    )),
                    Tbody(*d_rows),
                    cls="w-full text-sm",
                ),
                cls="overflow-auto border rounded-md mb-4",
            ),
        )

    # ── Fire separation table ─────────────────────────────────────────────────
    fire_block = ""
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
        fire_block = Div(
            Div(
                H3("Fire Separation — OBC 9.10.9", cls="text-sm font-semibold"),
                Span(
                    f"{f_pass}/{len(fire_sep)} pass",
                    cls=f"text-xs px-2 py-0.5 rounded-full font-medium {f_rate_cls}",
                ),
                cls="flex items-center justify-between mb-2",
            ),
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
        )

    return Card(
        CardHeader(
            Div(
                CardTitle("Spatial Compliance — Tier 2"),
                P(
                    f"{spatial.get('space_count', 0)} spaces · "
                    f"{spatial.get('party_wall_count', 0)} party walls detected",
                    cls="text-xs text-muted-foreground mt-0.5",
                ),
            )
        ),
        CardContent(
            Div(*warning_items, cls="space-y-1 mb-4") if warning_items else "",
            daylight_block,
            fire_block,
        ),
    )


# Module-level cache for CSV export (populated in analysis_run_post)
_last_compliance_results: list[dict] = []


def setup_routes(rt):
    """Register analysis workflow routes."""

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

        sections = [
            Card(
                CardHeader(CardTitle(f"{project.get('name', 'Project')} — {selected_theme} Theme")),
                CardContent(_build_ifc_summary_content(result, project_id)),
            ),
            *(([bldg_card]) if bldg_card else []),
            *(([spatial_card]) if spatial_card else []),
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
        doc_cards = _build_document_cards(result)

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
            *(doc_cards or [P("No documents selected.", cls="text-sm text-muted-foreground")]),
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
