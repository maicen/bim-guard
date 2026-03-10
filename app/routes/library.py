from fasthtml.common import *
from app.components.layout import DashboardLayout
from shad4fast import Card, CardHeader, CardTitle, CardDescription, CardContent, Badge, Button, Input, Label, Lucide, Separator, Alert, AlertDescription
import asyncio

def RuleCard(rule):
    return Div(
        Div(
            Span(rule["reference"], cls="font-semibold"),
            Badge(rule["type"], variant="outline"),
            cls="flex justify-between items-start mb-2"
        ),
        P(rule["description"], cls="mb-2 text-sm text-muted-foreground"),
        Div(
            f"Target: {rule['target_ifc_class']}", Br(),
            f"Params: {rule['parameters']}",
            cls="bg-background rounded p-2 border font-mono text-xs"
        ),
        cls="p-4 rounded-lg border bg-muted/40 text-sm mb-4"
    )

def setup_routes(rt):
    @rt("/library/rules")
    def get():
        # Mocking the rules fetched from the react-query endpoint
        mock_rule_doc = {
            "name": "ISO 19650 Naming Convention",
            "description": "Standard naming conventions for BIM models.",
            "categories": [
                {
                    "id": 1,
                    "name": "File Naming",
                    "rules": [
                        {
                            "id": 101,
                            "reference": "REQ-01",
                            "type": "Required",
                            "description": "File name must follow Project-Originator-Volume-Level-Type-Role-Number format.",
                            "target_ifc_class": "IfcProject",
                            "parameters": {"regex": "^[A-Z0-9]{2,6}-[A-Z0-9]{3}-.*$"}
                        }
                    ]
                }
            ]
        }
        
        cards = []
        for cat in mock_rule_doc["categories"]:
            rules = [RuleCard(r) for r in cat["rules"]]
            cards.append(Card(
                CardHeader(CardTitle(cat["name"], cls="text-lg")),
                CardContent(*rules, cls="flex flex-col gap-4")
            ))

        return Title("Rules Manager - BIM Guard"), DashboardLayout(
            Div(
                H1("Rule Manager", cls="text-3xl font-bold mb-4 tracking-tight"),
                P("View and edit extracted validation rules.", cls="text-muted-foreground mb-8"),
                Div(
                    Card(
                        CardHeader(
                            CardTitle(mock_rule_doc["name"]),
                            CardDescription(mock_rule_doc["description"])
                        )
                    ),
                    Div(*cards, cls="grid gap-4 md:grid-cols-2"),
                    cls="flex flex-col gap-6"
                ),
                cls="container mx-auto py-6"
            )
        )

    @rt("/library/rules/extract")
    def get():
        return Title("Rule Extraction - BIM Guard"), DashboardLayout(
            Div(
                Div(
                    Div(
                        H1("Rule Extraction Studio", cls="text-lg font-semibold tracking-tight"),
                        P("Upload a BEP document to extract rules via AI.", cls="text-xs text-muted-foreground"),
                    ),
                    cls="flex items-center justify-between px-6 py-3 border-b bg-background"
                ),
                Div(
                    # Left panel (File upload form using HTMX)
                    Div(
                        Form(
                            Label("Upload BEP Document (PDF)", cls="mb-2"),
                            Input(type="file", name="document", accept=".pdf", cls="mb-4 mt-2"),
                            Button(
                                "Extract Rules", 
                                type="submit", 
                                cls="mt-2"
                            ),
                            hx_post="/api/rules/extract",
                            hx_target="#extracted-rules-container",
                            hx_indicator="#extract-spinner",
                            enctype="multipart/form-data",
                            cls="bg-background p-6 rounded-lg shadow-sm border"
                        ),
                        cls="flex-1 bg-muted/30 p-6 overflow-auto"
                    ),
                    Separator(orientation="vertical"),
                    # Right panel (Results)
                    Div(
                        H3("Extracted Rules", cls="text-lg font-semibold mb-4 px-6 pt-6"),
                        # Spinner
                        Div(
                            Lucide("loader-2", cls="w-6 h-6 animate-spin text-primary"),
                            Span("Scanning document and building rules via AI...", cls="ml-2 text-sm text-muted-foreground"),
                            id="extract-spinner",
                            cls="htmx-indicator flex items-center justify-center p-6 hidden"
                        ),
                        Style(".htmx-indicator.hidden { display: none; } .htmx-request .htmx-indicator { display: flex !important; } .htmx-request.htmx-indicator { display: flex !important; }"),
                        # Target for HTMX
                        Div(
                            P("Upload a document and click 'Extract' to see results here.", cls="text-sm text-muted-foreground text-center py-10"),
                            id="extracted-rules-container", 
                            cls="px-6 pb-6 space-y-4"
                        ),
                        cls="w-full md:w-[400px] lg:w-[450px] bg-background border-l overflow-y-auto"
                    ),
                    cls="flex flex-1 overflow-hidden"
                ),
                cls="flex flex-col h-[calc(100vh-4rem)] -m-6" # offset layout padding to fill screen
            )
        )

    @rt("/api/rules/extract", methods=["POST"])
    async def post(document: UploadFile):
        # Simulate processing time 
        await asyncio.sleep(1.5)
        
        # Here we would normally call app.modules.orchestrator or module3_rule_builder
        # But for this port we just return extracted fragments
        rules = [
            {"ref": "REQ-DOC-01", "desc": "All files must start with Project ID", "target": "IfcProject"},
            {"ref": "REQ-DOC-02", "desc": "Columns must have LoadBearing property", "target": "IfcColumn"}
        ]
        
        fragments = []
        for r in rules:
            fragments.append(
                Div(
                    Div(
                        Span(r["ref"], cls="font-semibold text-sm"),
                        Badge("New"),
                        cls="flex justify-between items-center mb-1"
                    ),
                    P(r["desc"], cls="text-sm text-muted-foreground mb-2"),
                    Div(f"Target: {r['target']}", cls="font-mono text-xs bg-muted p-1.5 rounded"),
                    cls="p-4 border rounded-md shadow-sm mb-4"
                )
            )
            
        success_msg = Alert(
            Lucide("check-circle", cls="h-4 w-4"),
            AlertDescription(f"Extracted {len(rules)} rules from {document.filename}"),
            cls="mb-4 text-emerald-600 border-emerald-600 [&>svg]:text-emerald-600"
        )
        
        # We need to re-init lucide icons for new content swapped in by HTMX
        init_icons = Script("lucide.createIcons();")
        
        return Div(success_msg, *fragments, init_icons)
