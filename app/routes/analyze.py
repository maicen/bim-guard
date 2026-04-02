from fasthtml.common import Div, P, Title
from monsterui.all import Card, CardBody, CardHeader, CardTitle, H1

from app.components.layout import DashboardLayout


def _placeholder_page(title: str, description: str, next_step: str):
    return Title(f"{title} - BIM Guard"), DashboardLayout(
        Div(
            H1(title, cls="text-3xl font-bold mb-4 tracking-tight"),
            P(description, cls="text-muted-foreground mb-6"),
            Card(
                CardHeader(CardTitle("Placeholder")),
                CardBody(
                    P(next_step, cls="text-sm text-muted-foreground"),
                ),
            ),
            cls="container mx-auto py-6",
        )
    )


def setup_routes(rt):
    @rt("/analysis/run")
    def analysis_run():
        return _placeholder_page(
            "Run Analysis",
            "Analysis workflow placeholder. This page will orchestrate document parsing, IFC checks, and compliance validation.",
            "Add project selection, rule selection, and analysis execution controls here.",
        )

    @rt("/reports")
    def reports():
        return _placeholder_page(
            "Reports",
            "Reports placeholder. This page will show generated summaries, issue lists, and exportable compliance outputs.",
            "Add report filters, history, and export actions here.",
        )
