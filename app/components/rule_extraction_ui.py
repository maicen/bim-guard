from fasthtml.common import Div, P, Span
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
    fragments = []
    for rule in rules:
        fragments.append(
            Card(
                CardContent(
                    Div(
                        Span(rule.get("ref", "REQ"), cls="font-semibold text-sm"),
                        Span(
                            "New",
                            cls="inline-flex items-center rounded-md bg-muted px-2 py-0.5 text-xs",
                        ),
                        cls="flex justify-between items-center mb-1",
                    ),
                    P(rule.get("desc", ""), cls="text-sm text-muted-foreground mb-2"),
                    Div(
                        f"Target: {rule.get('target', '-')}",
                        cls="font-mono text-xs bg-muted p-1.5 rounded",
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
    return Div(success_msg, *fragments)


def rule_extraction_empty_file_result():
    return Alert("Uploaded file is empty.")
