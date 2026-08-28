"""
app/routes/revit_sync.py
--------------------------
Receives element data pushed by the pyRevit button inside Revit,
runs it through Module 4 + 5, and renders the same compliance
results card used by the IFC analysis route.

Endpoints:
    GET  /revit-sync          — landing page with connection instructions
    POST /revit-sync          — accepts pyRevit JSON, returns results page
    POST /revit-sync/api      — same but returns JSON (for testing/debugging)

pyRevit script POSTs this shape:
    {
        "project_name": "My Revit Model",   (optional label)
        "theme":        "Architecture",      (optional, default Architecture)
        "elements": [
            {
                "ifc_class":  "IfcStairFlight",
                "name":       "Stair 1",
                "guid":       "abc-123",
                "storey":     "Level 1",
                "properties": { "Width": 900.0, "RiserHeight": 175.0 }
            }
        ]
    }
"""

from __future__ import annotations

from fasthtml.common import (
    A,
    Code,
    Div,
    H2,
    Li,
    P,
    Pre,
    Request,
    Span,
    Title,
    Ul,
)
from monsterui.all import Container, H1

from app.components.layout import DashboardLayout
from app.components.ui import Alert, AlertT, Card, CardContent, CardHeader, CardTitle
from app.services.pipeline_services import PipelineOrchestratorService
from app.routes.analyze import _rule_compliance_card
from app.services.revit_sync_service import RevitSyncService

_sync_service = RevitSyncService()


def setup_routes(rt):

    @rt("/revit-sync")
    def revit_sync_landing():
        """Landing page — shows pyRevit connection instructions."""
        endpoint = "http://localhost:8000/revit-sync"
        example = """\
import requests

data = {
    "project_name": "My Building",
    "theme": "Architecture",
    "elements": [
        {
            "ifc_class": "IfcStairFlight",
            "name": stair.Name,
            "guid": stair.UniqueId,
            "storey": level_name,
            "properties": {
                "Width":       width_mm,
                "RiserHeight": riser_mm,
                "TreadLength": tread_mm,
            }
        }
        # ... add more elements
    ]
}

requests.post("http://localhost:8000/revit-sync", json=data)
"""
        return Title("Revit Sync - BIM Guard"), DashboardLayout(
            Container(
                H1("Revit Direct Sync"),
                P(
                    "Push element data directly from Revit using pyRevit — "
                    "no IFC export needed.",
                    cls="text-muted-foreground mb-6",
                ),
                Card(
                    CardHeader(CardTitle("How to connect")),
                    CardContent(
                        Ul(
                            Li("Install pyRevit from pyrevitlabs.io (free)"),
                            Li("Create a BIMGuard.extension folder with your script.py"),
                            Li(
                                Span("POST element data to: "),
                                Code(endpoint, cls="font-mono text-sm bg-muted px-1 rounded"),
                            ),
                            Li("Results appear here instantly"),
                            cls="list-disc list-inside space-y-2 text-sm mb-4",
                        ),
                        P("pyRevit script template:", cls="text-sm font-semibold mb-2"),
                        Pre(
                            Code(example, cls="text-xs"),
                            cls="bg-muted rounded p-4 overflow-auto text-xs",
                        ),
                    ),
                ),
                cls="space-y-4",
            )
        )

    @rt("/revit-sync", methods=["POST"])
    async def revit_sync_post(req: Request):
        """Receive pyRevit data, run compliance check, render results page."""
        try:
            body = await req.json()
        except Exception:
            return DashboardLayout(
                Container(
                    Alert("Invalid JSON body — check your pyRevit script.", typ=AlertT.error)
                )
            )

        elements = body.get("elements", [])
        theme = str(body.get("theme") or "Architecture").strip()
        project_name = str(body.get("project_name") or "Revit Model").strip()

        if not elements:
            return DashboardLayout(
                Container(
                    Alert(
                        "No elements received. Make sure your pyRevit script "
                        "includes the 'elements' list in the payload.",
                        typ=AlertT.warning,
                    )
                )
            )

        # Build Module 4 input from pyRevit data
        extraction = _sync_service.build_extraction_results(elements, theme)

        # Run Module 4 via service facade — same comparator used by IFC path
        compliance = PipelineOrchestratorService.validate_metadata(extraction)

        # Run Module 5 via service facade — summary stats
        summary = PipelineOrchestratorService.render_visual_report(compliance)

        # Element count breakdown by IFC class
        class_counts: dict[str, int] = {}
        for el in elements:
            cls = el.get("ifc_class", "Unknown")
            class_counts[cls] = class_counts.get(cls, 0) + 1

        count_badges = Div(
            *[
                Span(
                    f"{cls}: {n}",
                    cls="inline-block px-2 py-0.5 rounded-full text-xs bg-muted font-mono",
                )
                for cls, n in sorted(class_counts.items())
            ],
            cls="flex flex-wrap gap-2 mb-4",
        )

        source_card = Card(
            CardHeader(CardTitle(f"{project_name} — Revit Direct Sync")),
            CardContent(
                P(
                    f"{len(elements)} element(s) received from pyRevit  |  Theme: {theme}",
                    cls="text-sm text-muted-foreground mb-2",
                ),
                count_badges,
                A(
                    "Run again / send new data",
                    href="/revit-sync",
                    cls="text-xs text-blue-600 underline",
                ),
            ),
        )

        compliance_card = _rule_compliance_card(compliance, summary, None, theme)

        return Title("Revit Sync Results - BIM Guard"), DashboardLayout(
            Container(
                H2("Compliance Results", cls="text-xl font-bold mb-4"),
                source_card,
                compliance_card or Alert("No rules matched the received elements.", typ=AlertT.warning),
                cls="space-y-4",
            )
        )

    @rt("/revit-sync/api", methods=["POST"])
    async def revit_sync_api(req: Request):
        """JSON endpoint — returns raw compliance results (useful for debugging pyRevit scripts)."""
        from starlette.responses import JSONResponse

        try:
            body = await req.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

        elements = body.get("elements", [])
        theme = str(body.get("theme") or "Architecture").strip()

        extraction = _sync_service.build_extraction_results(elements, theme)
        compliance = PipelineOrchestratorService.validate_metadata(extraction)
        summary    = PipelineOrchestratorService.render_visual_report(compliance)

        return JSONResponse({
            "element_count": len(elements),
            "theme": theme,
            "summary": summary,
            "results": [
                {
                    "rule_ref":      r.get("rule_ref"),
                    "rule_desc":     r.get("rule_desc"),
                    "target":        r.get("target"),
                    "property_name": r.get("property_name"),
                    "status":        r.get("status"),
                    "pass_count":    r.get("pass_count"),
                    "fail_count":    r.get("fail_count"),
                    "missing_count": r.get("missing_count"),
                    "failures":      r.get("failures", []),
                }
                for r in compliance
            ],
        })
