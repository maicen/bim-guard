import json
from fasthtml.common import Button, Div, P, Span
from app.components.ui import (
    Card,
    CardContent,
    CardHeader,
    CardTitle,
    HtmxSpinner,
    SubmitButton,
)
from monsterui.all import Alert, Form, FormLabel, H1, H3, Input, UkIcon


def rule_extraction_page_content():
    spinner, spinner_style = HtmxSpinner(
        "extract-spinner", "Scanning document and building rules via AI..."
    )

    return Div(
        Div(
            Div(
                H1(
                    "Rule Extraction Studio",
                    cls="text-lg font-semibold tracking-tight",
                ),
                P(
                    "Upload a BEP document to extract rules via AI.",
                    cls="text-xs text-muted-foreground",
                ),
            ),
            cls="flex items-center justify-between px-6 py-3 border-b bg-background",
        ),
        Div(
            Div(
                Card(
                    CardHeader(CardTitle("Upload BEP Document")),
                    CardContent(
                        Form(
                            Div(
                                FormLabel(
                                    "Upload BEP Document (PDF)", fr="extract-document"
                                ),
                                Input(
                                    id="extract-document",
                                    type="file",
                                    name="document",
                                    accept=".pdf",
                                    required=True,
                                    cls="mt-2",
                                ),
                                cls="space-y-1",
                            ),
                            SubmitButton(
                                "Extract Rules", variant="primary", cls="mt-2"
                            ),
                            spinner,
                            spinner_style,
                            hx_post="/api/rules/extract",
                            hx_target="#extracted-rules-container",
                            hx_indicator="#extract-spinner",
                            enctype="multipart/form-data",
                            cls="space-y-4",
                        )
                    ),
                ),
                cls="flex-1 bg-muted/30 p-6 overflow-auto",
            ),
            Div(cls="w-px bg-border"),
            Div(
                H3(
                    "Extracted Rules",
                    cls="text-lg font-semibold mb-4 px-6 pt-6",
                ),
                Div(
                    P(
                        "Upload a document and click 'Extract' to see results here.",
                        cls="text-sm text-muted-foreground text-center py-10",
                    ),
                    id="extracted-rules-container",
                    cls="px-6 pb-6 space-y-4",
                ),
                cls="w-full md:w-[400px] lg:w-[450px] bg-background border-l overflow-y-auto",
            ),
            cls="flex flex-1 overflow-hidden",
        ),
        cls="flex flex-col h-[calc(100vh-4rem)] -m-6",
    )


def rule_extraction_results(rules: list[dict], filename: str | None):
    if not rules:
        return Alert(
            UkIcon("info", cls="h-4 w-4"),
            Span(
                f"No compliance rules were found in {filename or 'the uploaded file'}. "
                "Try a document that contains explicit BIM or building code requirements."
            ),
            cls="mb-4 text-yellow-700 border-yellow-500 [&>svg]:text-yellow-700",
        )

    fragments = []
    for rule in rules:
        ref      = rule.get("ref", "REQ")
        desc     = rule.get("desc", "")
        target   = rule.get("target", "Unspecified")
        operator = rule.get("operator", "")
        value    = rule.get("value")
        unit     = rule.get("unit", "")
        severity = rule.get("severity", "")
        prop     = rule.get("property_name", "")
        conf     = rule.get("confidence")
        needs_review = rule.get("needs_review", False)

        # Build inline condition string e.g. "Width >= 860 mm"
        condition_parts = []
        if prop:
            condition_parts.append(prop)
        if operator:
            condition_parts.append(operator)
        if value is not None:
            condition_parts.append(str(value))
        if unit:
            condition_parts.append(unit)
        condition = " ".join(condition_parts) if condition_parts else None

        severity_cls = {
            "mandatory":     "bg-red-100 text-red-800",
            "recommended":   "bg-yellow-100 text-yellow-800",
            "informational": "bg-blue-100 text-blue-800",
        }.get(severity, "bg-muted text-muted-foreground")

        badges = Div(
            Span(severity or "mandatory", cls=f"inline-block px-1.5 py-0.5 rounded text-xs font-medium {severity_cls} mr-1") if severity else "",
            Span(f"{int(conf * 100)}% confident", cls="inline-block px-1.5 py-0.5 rounded text-xs bg-muted text-muted-foreground") if conf is not None else "",
            Span("⚠ Review", cls="inline-block px-1.5 py-0.5 rounded text-xs bg-orange-100 text-orange-700 ml-1") if needs_review else "",
            cls="flex flex-wrap gap-1 mb-2",
        )

        fragments.append(
            Card(
                CardContent(
                    Div(
                        Span(ref, cls="font-semibold text-sm"),
                        Span("New", cls="inline-flex items-center rounded-md bg-muted px-2 py-0.5 text-xs"),
                        cls="flex justify-between items-center mb-1",
                    ),
                    badges,
                    P(desc, cls="text-sm text-muted-foreground mb-2"),
                    Div(
                        Div(f"Target: {target}", cls="font-mono text-xs"),
                        Div(f"Check: {condition}", cls="font-mono text-xs text-blue-700") if condition else "",
                        cls="bg-muted p-1.5 rounded mb-2 space-y-0.5",
                    ),
                    Form(
                        Input(type="hidden", name="rule_json", value=json.dumps(rule)),
                        Button(
                            "Save to Library",
                            type="submit",
                            cls="text-xs px-3 py-1 rounded bg-primary text-primary-foreground hover:bg-primary/90",
                        ),
                        hx_post="/api/rules/save-extracted",
                        hx_target="this",
                        hx_swap="outerHTML",
                    ),
                    cls="space-y-2",
                ),
                cls="mb-4",
            )
        )

    success_msg = Alert(
        UkIcon("check-circle", cls="h-4 w-4"),
        Span(f"Extracted {len(rules)} rules from {filename or 'uploaded file'}"),
        cls="mb-4 text-emerald-600 border-emerald-600 [&>svg]:text-emerald-600",
    )

    # "Save All" encodes all rules as JSON in a single hidden field
    save_all_btn = Form(
        Input(type="hidden", name="rules_json", value=json.dumps(rules)),
        Div(
            Button(
                "Save All to Library",
                type="submit",
                id="save-all-btn",
                cls="text-sm px-4 py-1.5 rounded bg-primary text-primary-foreground hover:bg-primary/90",
            ),
            id="save-all-container",
        ),
        hx_post="/api/rules/save-all-extracted",
        hx_target="#save-all-container",
        hx_swap="outerHTML",
        cls="mb-4",
    )

    return Div(success_msg, save_all_btn, *fragments)


def rule_extraction_empty_file_result():
    return Alert("Uploaded file is empty.")
