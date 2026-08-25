import json
from pathlib import Path

from fasthtml.common import Button, Details, Div, Label, Option, P, Pre, Span, Summary
from monsterui.all import H1, H3, Alert, Form, FormLabel, Input, Select, UkIcon

from app.components.rules_ui import IFC_CLASS_OPTIONS
from app.components.ui import Card, CardContent, CardHeader, CardTitle, HtmxSpinner

# ── Provider catalogue ───────────────────────────────────────────────────────────

PROVIDER_LABELS: dict[str, str] = {
    "openrouter": "OpenRouter",
    "openai": "OpenAI",
    "gemini": "Google Gemini",
    "anthropic": "Anthropic",
    "ollama": "Ollama (Local)",
}


def _model_select(
    models: list[tuple[str, str]] | None = None, selected_model: str = ""
):
    models = models or []
    return Select(
        Option("Select a model", value="", selected=True),
        *[
            Option(label, value=value, selected=value == selected_model)
            for value, label in models
        ],
        id="model-select",
        name="model",
        cls="w-full",
    )


def provider_model_select_fragment(
    models: list[tuple[str, str]] | None = None,
    error: str = "",
    selected_model: str = "",
):
    """Render the dynamically discovered model selector HTMX fragment."""
    return Div(
        _model_select(models, selected_model),
        P(
            error or (f"{len(models)} model(s) available." if models else "No models found."),
            cls=(
                "text-xs mt-1 text-destructive"
                if error
                else "text-xs mt-1 text-muted-foreground"
            ),
        ),
        id="model-select-container",
    )


def rule_extraction_page_content(documents: list[dict]):
    spinner, spinner_style = HtmxSpinner(
        "extract-spinner", "Scanning document and building rules via AI..."
    )

    document_options = [
        Option(doc.get("filename", f"Document {doc.get('id', '')}"), value=str(doc["id"]))
        for doc in documents
        if doc.get("id") is not None
    ]
    has_documents = len(document_options) > 0

    provider_options = [
        Option(label, value=slug, selected=(slug == "openrouter"))
        for slug, label in PROVIDER_LABELS.items()
    ]

    return Div(
        Div(
            Div(
                H1(
                    "Rule Extraction Studio",
                    cls="text-lg font-semibold tracking-tight",
                ),
                P(
                    "Choose a provider and document, then extract compliance rules via AI.",
                    cls="text-xs text-muted-foreground",
                ),
            ),
            cls="flex items-center justify-between px-6 py-3 border-b bg-background",
        ),
        Div(
            Div(
                Form(
                    # ── AI Provider card ─────────────────────────────────────
                    Card(
                        CardHeader(CardTitle("AI Provider")),
                        CardContent(
                            Div(
                                FormLabel("Provider", fr="provider-select"),
                                Select(
                                    *provider_options,
                                    id="provider-select",
                                    name="provider",
                                    cls="w-full",
                                    hx_post="/api/rules/provider-models",
                                    hx_target="#model-select-container",
                                    hx_swap="outerHTML",
                                    hx_trigger="change",
                                    hx_include="#api-key,#api-base",
                                ),
                                cls="space-y-1",
                            ),
                            Div(
                                FormLabel("Model", fr="model-select"),
                                Div(
                                    P(
                                        "Loading available OpenRouter models...",
                                        cls="text-xs text-muted-foreground mt-1",
                                    ),
                                    id="model-select-container",
                                    hx_post="/api/rules/provider-models",
                                    hx_trigger="load",
                                    hx_target="this",
                                    hx_swap="outerHTML",
                                    hx_include="#provider-select,#api-key,#api-base",
                                ),
                                cls="space-y-1",
                            ),
                            Div(
                                FormLabel("Provider Endpoint", fr="api-base"),
                                Input(
                                    id="api-base",
                                    name="api_base",
                                    type="url",
                                    placeholder="Ollama defaults to http://localhost:11434",
                                    cls="w-full",
                                ),
                                P(
                                    "Optional. Use this for Ollama or another provider endpoint.",
                                    cls="text-xs text-muted-foreground mt-1",
                                ),
                                cls="space-y-1",
                            ),
                            Div(
                                FormLabel("API Key", fr="api-key"),
                                Input(
                                    id="api-key",
                                    name="api_key",
                                    type="password",
                                    placeholder="Leave blank to use server environment key",
                                    cls="w-full",
                                ),
                                P(
                                    "Key is sent only to your server and forwarded to the provider. "
                                    "Never stored.",
                                    cls="text-xs text-muted-foreground mt-1",
                                ),
                                cls="space-y-1",
                            ),
                            Button(
                                UkIcon("refresh-cw", cls="h-4 w-4"),
                                "Refresh Models",
                                type="button",
                                title="Fetch available models from the provider",
                                hx_post="/api/rules/provider-models",
                                hx_target="#model-select-container",
                                hx_swap="outerHTML",
                                hx_include="#provider-select,#api-key,#api-base",
                                cls=(
                                    "inline-flex items-center gap-2 rounded-md border px-3 py-2 "
                                    "text-sm font-medium hover:bg-muted"
                                ),
                            ),
                            cls="space-y-4",
                        ),
                    ),
                    # ── Document selection card ───────────────────────────────
                    Card(
                        CardHeader(CardTitle("Select Document")),
                        CardContent(
                            Div(
                                FormLabel("Choose uploaded document", fr="extract-document-id"),
                                Select(
                                    Option(
                                        "Select a document"
                                        if has_documents
                                        else "No uploaded documents available",
                                        value="",
                                        selected=True,
                                    ),
                                    *document_options,
                                    id="extract-document-id",
                                    name="document_id",
                                    required=True,
                                    cls="w-full",
                                ),
                                cls="space-y-1",
                            ),
                            P(
                                "Only documents already uploaded in /library/documents are listed.",
                                cls="text-xs text-muted-foreground mt-2",
                            ),
                        ),
                    ),
                    # ── Submit ────────────────────────────────────────────────
                    Button(
                        "Extract Rules",
                        type="submit",
                        disabled=not has_documents,
                        cls=(
                            "inline-flex items-center justify-center gap-2 rounded-md px-4 py-2 "
                            "text-sm font-medium transition-colors bg-primary text-primary-foreground "
                            "hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                        ),
                    ),
                    spinner,
                    spinner_style,
                    hx_post="/api/rules/extract",
                    hx_target="#extracted-rules-container",
                    hx_indicator="#extract-spinner",
                    cls="space-y-4",
                ),
                cls="flex-1 bg-muted/30 p-6 overflow-auto space-y-4",
            ),
            Div(cls="w-px bg-border"),
            Div(
                Div(
                    H3("Extracted Rules", cls="text-lg font-semibold"),
                    cls="flex items-center justify-between px-6 py-3 border-b bg-background",
                ),
                Div(
                    P(
                        "Select a document and click 'Extract' to see results here.",
                        cls="text-sm text-muted-foreground text-center py-10",
                    ),
                    id="extracted-rules-container",
                    cls="px-6 pb-6 space-y-4 overflow-y-auto flex-1",
                ),
                cls="w-full md:w-[400px] lg:w-[500px] bg-background border-l flex flex-col",
            ),
            cls="flex flex-1 overflow-hidden",
        ),
        cls="flex flex-col h-[calc(100vh-4rem)] -m-6",
    )


def rule_extraction_results(
    rules: list[dict],
    filename: str | None,
    *,
    warnings: list[str] | None = None,
):
    warning_banners = [
        Alert(
            UkIcon("alert-triangle", cls="h-4 w-4"),
            Span(w),
            cls="mb-3 text-amber-700 border-amber-400 [&>svg]:text-amber-700",
        )
        for w in (warnings or [])
    ]

    if not rules:
        return Div(
            *warning_banners,
            Alert(
                UkIcon("info", cls="h-4 w-4"),
                Span(
                    f"No compliance rules were found in {filename or 'the selected document'}. "
                    "Try a document that contains explicit BIM or building code requirements."
                ),
                cls="mb-4 text-yellow-700 border-yellow-500 [&>svg]:text-yellow-700",
            ),
        )

    fragments = []
    for rule in rules:
        ref = rule.get("ref", "REQ")
        desc = rule.get("desc", "")
        target = rule.get("target", "Unspecified")
        operator = rule.get("operator", "")
        value = rule.get("value")
        value_min = rule.get("value_min")
        value_max = rule.get("value_max")
        unit = rule.get("unit", "")
        severity = rule.get("severity", "")
        prop = rule.get("property_name", "")
        prop_set = rule.get("property_set", "")
        source_text = rule.get("source_text", "")
        related_refs = rule.get("related_refs") or []
        conf = rule.get("confidence")
        needs_review = rule.get("needs_review", False)
        method = rule.get("extraction_method", "llm")
        compliance_type = rule.get("compliance_type", "")

        # Condition string: handle between vs single value
        if operator == "between" and value_min is not None and value_max is not None:
            condition = f"{prop} between {value_min}–{value_max} {unit}".strip()
        else:
            parts = []
            if prop:
                parts.append(prop)
            if operator:
                parts.append(operator)
            if value is not None:
                parts.append(str(value))
            if unit:
                parts.append(unit)
            condition = " ".join(parts) if parts else None

        severity_cls = {
            "mandatory": "bg-red-100 text-red-800",
            "recommended": "bg-yellow-100 text-yellow-800",
            "informational": "bg-blue-100 text-blue-800",
        }.get(severity, "bg-muted text-muted-foreground")

        method_cls = (
            "bg-emerald-100 text-emerald-800"
            if method == "table"
            else "bg-purple-100 text-purple-800"
        )
        method_label = "table" if method == "table" else "AI"

        badges = Div(
            Span(
                severity or "mandatory",
                cls=f"inline-block px-1.5 py-0.5 rounded text-xs font-medium {severity_cls} mr-1",
            )
            if severity
            else "",
            Span(
                method_label,
                cls=f"inline-block px-1.5 py-0.5 rounded text-xs font-medium {method_cls} mr-1",
            ),
            Span(
                f"{int(conf * 100)}% conf",
                cls="inline-block px-1.5 py-0.5 rounded text-xs bg-muted text-muted-foreground mr-1",
            )
            if conf is not None
            else "",
            Span(
                "⚠ Review",
                cls="inline-block px-1.5 py-0.5 rounded text-xs bg-orange-100 text-orange-700",
            )
            if needs_review
            else "",
            cls="flex flex-wrap gap-1 mb-2",
        )

        # Rule structure block
        structure_rows = [
            ("Target", target),
            ("Check", condition) if condition else None,
            ("Property Set", prop_set) if prop_set else None,
            ("Type", f"{rule.get('rule_type', '')} · {compliance_type}")
            if compliance_type
            else ("Type", rule.get("rule_type", "")),
            ("Refs", ", ".join(related_refs)) if related_refs else None,
        ]
        structure = Div(
            *[
                Div(
                    Span(label + ":", cls="text-muted-foreground w-20 shrink-0"),
                    Span(val, cls="font-mono text-xs text-blue-700 break-all"),
                    cls="flex gap-2",
                )
                for row in structure_rows
                if row is not None
                for label, val in [row]
                if val
            ],
            cls="bg-muted p-1.5 rounded mb-2 space-y-0.5 text-xs",
        )

        # Source text collapsible
        source_block = (
            Details(
                Summary(
                    "Source text", cls="text-xs text-muted-foreground cursor-pointer select-none"
                ),
                P(source_text, cls="text-xs text-muted-foreground mt-1 italic"),
                cls="mb-2",
            )
            if source_text
            else ""
        )

        # JSON collapsible
        json_block = Details(
            Summary("View JSON", cls="text-xs text-muted-foreground cursor-pointer select-none"),
            Pre(
                json.dumps(rule, indent=2),
                cls="text-xs bg-muted p-2 rounded overflow-x-auto mt-1 max-h-48",
            ),
            cls="mb-2",
        )

        # Inline editor — lets user correct target/property before saving
        ifc_options = [
            Option(c, value=c, selected=(c == target)) for c in IFC_CLASS_OPTIONS
        ]
        if target and target not in IFC_CLASS_OPTIONS:
            ifc_options.insert(0, Option(target, value=target, selected=True))

        inline_editor = Details(
            Summary(
                "Edit before saving",
                cls="text-xs text-muted-foreground cursor-pointer select-none mb-1",
            ),
            Div(
                Div(
                    Label("Target IFC Class", fr=f"ov-target-{ref}", cls="text-xs font-medium"),
                    Select(
                        *ifc_options,
                        id=f"ov-target-{ref}",
                        name="override_target",
                        cls="w-full text-xs mt-0.5",
                    ),
                    cls="space-y-0.5",
                ),
                Div(
                    Label("Property Name", fr=f"ov-prop-{ref}", cls="text-xs font-medium"),
                    Input(
                        id=f"ov-prop-{ref}",
                        name="override_property",
                        value=prop,
                        placeholder="e.g. FireRating",
                        cls="w-full text-xs mt-0.5",
                    ),
                    cls="space-y-0.5",
                ),
                Div(
                    Label("Property Set", fr=f"ov-pset-{ref}", cls="text-xs font-medium"),
                    Input(
                        id=f"ov-pset-{ref}",
                        name="override_property_set",
                        value=prop_set,
                        placeholder="e.g. Pset_DoorCommon",
                        cls="w-full text-xs mt-0.5",
                    ),
                    cls="space-y-0.5",
                ),
                cls="grid grid-cols-1 gap-2 p-2 bg-muted/50 rounded mt-1",
            ),
            cls="mb-2",
        )

        fragments.append(
            Card(
                CardContent(
                    Div(
                        Span(ref, cls="font-semibold text-sm"),
                        Span(
                            "New",
                            cls="inline-flex items-center rounded-md bg-muted px-2 py-0.5 text-xs",
                        ),
                        cls="flex justify-between items-center mb-1",
                    ),
                    badges,
                    P(desc, cls="text-sm text-muted-foreground mb-2"),
                    structure,
                    source_block,
                    json_block,
                    Form(
                        Input(type="hidden", name="rule_json", value=json.dumps(rule)),
                        inline_editor,
                        Button(
                            "Save to Library",
                            type="submit",
                            cls="text-xs px-3 py-1 rounded bg-primary text-primary-foreground hover:bg-primary/90",
                        ),
                        hx_post="/api/rules/save-extracted",
                        hx_target="this",
                        hx_swap="outerHTML",
                        hx_include="#extract-folder-name",
                    ),
                    cls="space-y-2",
                ),
                cls="mb-4",
            )
        )

    llm_count = sum(1 for r in rules if r.get("extraction_method") != "table")
    table_count = sum(1 for r in rules if r.get("extraction_method") == "table")
    summary_parts = [f"{len(rules)} rules"]
    if table_count:
        summary_parts.append(f"{table_count} from tables")
    if llm_count:
        summary_parts.append(f"{llm_count} via AI")

    success_msg = Alert(
        UkIcon("check-circle", cls="h-4 w-4"),
        Span(f"Extracted {' · '.join(summary_parts)} from {filename or 'selected document'}"),
        cls="mb-3 text-emerald-600 border-emerald-600 [&>svg]:text-emerald-600",
    )

    _btn = (
        "display:inline-flex;align-items:center;gap:5px;"
        "font-size:12px;font-weight:500;padding:6px 14px;"
        "border-radius:6px;border:none;cursor:pointer;"
        "background:#1e293b;color:#ffffff;"
    )

    # Folder name — shared by every "Save to Library" form and "Save All" below
    # via hx-include, so all rules from this extraction land in one folder.
    suggested_folder = Path(filename or "").stem or "Extracted Rules"
    folder_field = Div(
        Label("Save to folder", fr="extract-folder-name", cls="text-xs font-medium mr-1"),
        Input(
            id="extract-folder-name",
            name="folder_name",
            value=suggested_folder,
            cls="text-xs w-48 inline-block",
            style="padding:4px 8px;border-radius:6px;",
        ),
        cls="flex items-center gap-1",
    )

    # Save All — HTMX POST including the folder field (server reads its own
    # rule cache). Export JSON — plain browser navigation to a download endpoint
    action_bar = Div(
        folder_field,
        Button(
            UkIcon("save", cls="h-3.5 w-3.5"),
            "Save All",
            type="button",
            style=_btn,
            hx_post="/api/rules/save-all-extracted",
            hx_target="#save-all-msg",
            hx_swap="innerHTML",
            hx_include="#extract-folder-name",
        ),
        Button(
            UkIcon("download", cls="h-3.5 w-3.5"),
            "Export JSON",
            type="button",
            style=_btn,
            onclick="window.location='/api/rules/export-json'",
        ),
        Span("", id="save-all-msg", cls="text-xs text-emerald-700 ml-1"),
        cls="sticky top-0 z-10 bg-background border-b py-2 mb-3 -mx-6 px-6 flex flex-wrap gap-2 items-center",
    )

    return Div(*warning_banners, success_msg, action_bar, *fragments)


def rule_extraction_empty_file_result():
    return Alert("Selected document has no extractable text.")
