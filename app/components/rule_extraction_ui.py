from fasthtml.common import Div, P, Span, Style
from monsterui.all import Alert, Button, Form, H1, H3, Input, Label, UkIcon


def rule_extraction_page_content():
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
                Form(
                    Label("Upload BEP Document (PDF)", cls="mb-2"),
                    Input(
                        type="file",
                        name="document",
                        accept=".pdf",
                        cls="mb-4 mt-2",
                    ),
                    Button("Extract Rules", type="submit", cls="mt-2"),
                    hx_post="/api/rules/extract",
                    hx_target="#extracted-rules-container",
                    hx_indicator="#extract-spinner",
                    enctype="multipart/form-data",
                    cls="bg-background p-6 rounded-lg shadow-sm border",
                ),
                cls="flex-1 bg-muted/30 p-6 overflow-auto",
            ),
            Div(style="width:1px; background:#e5e7eb;"),
            Div(
                H3(
                    "Extracted Rules",
                    cls="text-lg font-semibold mb-4 px-6 pt-6",
                ),
                Div(
                    UkIcon("loader-2", cls="w-6 h-6 animate-spin text-primary"),
                    Span(
                        "Scanning document and building rules via AI...",
                        cls="ml-2 text-sm text-muted-foreground",
                    ),
                    id="extract-spinner",
                    cls="htmx-indicator flex items-center justify-center p-6 hidden",
                ),
                Style(
                    ".htmx-indicator.hidden { display: none; } .htmx-request .htmx-indicator { display: flex !important; } .htmx-request.htmx-indicator { display: flex !important; }"
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
    fragments = []
    for rule in rules:
        fragments.append(
            Div(
                Div(
                    Span(rule.get("ref", "REQ"), cls="font-semibold text-sm"),
                    Label("New"),
                    cls="flex justify-between items-center mb-1",
                ),
                P(rule.get("desc", ""), cls="text-sm text-muted-foreground mb-2"),
                Div(
                    f"Target: {rule.get('target', '-')}",
                    cls="font-mono text-xs bg-muted p-1.5 rounded",
                ),
                cls="p-4 border rounded-md shadow-sm mb-4",
            )
        )

    success_msg = Alert(
        UkIcon("check-circle", cls="h-4 w-4"),
        Span(f"Extracted {len(rules)} rules from {filename or 'uploaded file'}"),
        cls="mb-4 text-emerald-600 border-emerald-600 [&>svg]:text-emerald-600",
    )
    return Div(success_msg, *fragments)


def rule_extraction_empty_file_result():
    return Alert("Uploaded file is empty.")
