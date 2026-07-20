"""3D Modeling Manual page — IFC-specific modeling reference material."""

from fasthtml.common import P, Title
from monsterui.all import H1

from app.components.layout import DashboardLayout
from app.components.ui import Card, CardContent, CardHeader, CardTitle


def setup_routes(rt):
    """Register the Modeling Manual route."""

    @rt("/modeling-manual")
    def modeling_manual_page():
        return Title("Modeling Manual - BIM Guard"), DashboardLayout(
            H1("3D Modeling Manual", cls="text-3xl font-bold tracking-tight mb-4"),
            Card(
                CardHeader(CardTitle("Modeling Manual")),
                CardContent(
                    P(
                        "IFC-specific modeling reference material will be published here — "
                        "guidance on how to correctly model elements (windows, doors, stairs, "
                        "walls, and more) so their properties are captured correctly for "
                        "compliance checking.",
                        cls="text-sm text-muted-foreground",
                    ),
                    P(
                        "No reference material has been uploaded yet.",
                        cls="text-sm text-muted-foreground italic mt-3",
                    ),
                ),
            ),
        )
