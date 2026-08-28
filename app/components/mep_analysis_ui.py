"""FastHTML components for the legacy MEP analysis workflow."""

from fasthtml.common import (
    Div,
    Form,
    Option,
    P,
    Script,
    Span,
    Table,
    Tbody,
    Td,
    Th,
    Thead,
    Tr,
)

from app.components.ui import (
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


def mep_engine_rules_card(rule_counts: dict[str, int]):
    """Render MEP engine coverage from counts supplied by the route."""
    engines = [
        ("GC-001", "Galvanic Corrosion", "BIMGUARD-GC-001", "bg-blue-100 text-blue-800"),
        ("CC-001", "Crevice Corrosion", "BIMGUARD-CC-001", "bg-teal-100 text-teal-800"),
        (
            "MC-001",
            "Microbially Influenced Corrosion",
            "BIMGUARD-MC-001",
            "bg-indigo-100 text-indigo-800",
        ),
    ]
    rows = [
        Tr(
            Td(
                Span(code, cls=f"inline-block px-2 py-0.5 rounded text-xs font-semibold {badge_cls}"),
                cls="px-3 py-2",
            ),
            Td(label, cls="px-3 py-2 text-sm"),
            Td(ruleset_id, cls="px-3 py-2 text-xs font-mono"),
            Td(str(rule_counts.get(ruleset_id, 0)), cls="px-3 py-2 text-sm font-semibold"),
            cls="border-b border-muted last:border-0",
        )
        for code, label, ruleset_id, badge_cls in engines
    ]
    header = Tr(
        *[
            Th(
                label,
                cls="px-3 py-2 text-left text-xs font-semibold text-muted-foreground bg-muted",
            )
            for label in ("Engine", "Scope", "Ruleset", "Rules")
        ]
    )
    return Card(
        CardHeader(CardTitle("MEP Engines and Rule Coverage")),
        CardContent(
            P(
                "MEP analysis runs corrosion, crevice, and MIC engines using their saved rule libraries.",
                cls="text-sm text-muted-foreground mb-3",
            ),
            Div(
                Table(Thead(header), Tbody(*rows), cls="w-full text-sm"),
                cls="overflow-auto border rounded-md",
            ),
        ),
    )


def mep_analysis_form(projects, documents, folders):
    """Render the MEP analysis form without accessing application services."""
    project_options = [Option("— select a project —", value="", disabled=True, selected=True)] + [
        Option(project.get("name", f"Project {project['id']}"), value=str(project["id"]))
        for project in projects
    ]
    folder_options = [Option("All folders", value="", selected=True)] + [
        Option(f"{folder['ruleset_id']} ({folder['count']})", value=folder["ruleset_id"])
        for folder in folders
    ]
    document_checkboxes = [
        Div(
            Checkbox(
                id=f"doc_{document['id']}",
                name="document_ids",
                value=str(document["id"]),
                cls="mr-2",
            ),
            Label(
                document.get("filename", f"Document {document['id']}"),
                for_=f"doc_{document['id']}",
                cls="text-sm cursor-pointer",
            ),
            cls="flex items-center gap-1",
        )
        for document in documents
    ]
    if not document_checkboxes:
        document_checkboxes = [P("No documents uploaded yet.", cls="text-sm text-muted-foreground")]

    form_sections = [
        Div(
            FormLabel("Project (IFC Model)", fr="project_id"),
            Select(*project_options, id="project_id", name="project_id", required=True),
        ),
        Div(
            FormLabel("Rule Folder", fr="rule_folder"),
            Select(*folder_options, id="rule_folder", name="rule_folder"),
            P(
                "Narrow the check to one saved MEP ruleset folder (for example GC-001, CC-001, or MC-001). Leave on 'All folders' to run against all MEP rules available in the library.",
                cls="text-xs text-muted-foreground mt-1",
            ),
        ),
        Div(
            FormLabel("MEP Engines"),
            Div(
                Span("GC-001 Galvanic", cls="inline-block px-2 py-0.5 rounded text-xs font-semibold bg-blue-100 text-blue-800"),
                Span("CC-001 Crevice", cls="inline-block px-2 py-0.5 rounded text-xs font-semibold bg-teal-100 text-teal-800"),
                Span("MC-001 MIC", cls="inline-block px-2 py-0.5 rounded text-xs font-semibold bg-indigo-100 text-indigo-800"),
                cls="flex flex-wrap items-center gap-2",
            ),
            P("All three MEP corrosion engines are included in this workflow.", cls="text-xs text-muted-foreground mt-1"),
        ),
        Div(
            FormLabel("Documents"),
            Div(*document_checkboxes, cls="space-y-2 border rounded-md p-3 bg-muted/30"),
        ),
        Div(
            FormLabel("Count Options"),
            Div(
                *[
                    Div(
                        Checkbox(id=field_id, name=field_id, value="1", checked=checked, cls="mr-2"),
                        Label(label, for_=field_id, cls="text-sm cursor-pointer"),
                        cls="flex items-center gap-1",
                    )
                    for field_id, label, checked in (
                        ("include_openings", "Include openings (IfcOpeningElement)", True),
                        ("include_spaces", "Include spaces (IfcSpace)", True),
                        ("include_type_definitions", "Include type definitions (IfcElementType)", False),
                    )
                ],
                cls="space-y-2 border rounded-md p-3 bg-muted/30",
            ),
        ),
    ]
    results_id = "model-rules-results"
    loader_id = f"{results_id}-loader"
    before_js = (
        f"var r=document.getElementById('{results_id}'),l=document.getElementById('{loader_id}');"
        "if(r&&l)r.innerHTML=l.innerHTML;"
        "var b=this.querySelector('[type=submit]');"
        "if(b){b.disabled=true;b.dataset.orig=b.textContent;b.textContent='Analysing...';}"
    )
    after_js = (
        "var b=this.querySelector('[type=submit]');"
        "if(b){b.disabled=false;if(b.dataset.orig)b.textContent=b.dataset.orig;}"
    )
    return Div(
        Card(
            CardHeader(
                Div(
                    CardTitle("MEP"),
                    P(
                        "Run MEP corrosion-focused analysis using the saved MEP rules in the library (GC-001, CC-001, and MC-001).",
                        cls="text-sm text-muted-foreground mt-1",
                    ),
                )
            ),
            CardContent(
                Form(
                    Div(
                        *form_sections,
                        Div(SubmitButton("Run MEP Analysis", variant="primary"), cls="flex items-center gap-4"),
                    ),
                    method="post",
                    action="/analysis/results",
                    hx_post="/analysis/results",
                    hx_target=f"#{results_id}",
                    hx_swap="innerHTML",
                    **{
                        "hx-on:htmx:before-request": before_js,
                        "hx-on:htmx:after-request": after_js,
                    },
                )
            ),
        ),
        Div(
            Div(
                Div(style="width:40px;height:40px;border-radius:50%;border:4px solid #e2e8f0;border-top-color:#3b82f6;animation:bimguard-spin .75s linear infinite;margin:0 auto 16px;"),
                P("Analysing model...", cls="text-base font-semibold"),
                P("Loading IFC · Extracting properties · Running compliance checks", cls="text-xs text-muted-foreground mt-1"),
                cls="text-center py-14",
            ),
            cls="border rounded-lg shadow-sm bg-card",
            id=loader_id,
            style="display:none",
        ),
        Script(
            "(function(){var s=document.createElement('style');s.textContent='@keyframes bimguard-spin{to{transform:rotate(360deg)}}';document.head.appendChild(s);})();"
        ),
        Div(id=results_id),
    )
