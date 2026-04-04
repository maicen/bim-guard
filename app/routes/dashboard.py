from fasthtml.common import A, Div, Li, P, Title, Ul
from monsterui.all import (
    ButtonT,
    Card,
    CardT,
    Container,
    DivFullySpaced,
    Grid,
    H1,
    H3,
    NavContainer,
    Subtitle,
)
from app.components.layout import DashboardLayout
from app.components.ui import CreateAction, ViewAction
from app.services.projects_service import ProjectsService

_projects_service = ProjectsService()


def StatsCard(title, value, description):
    return Card(
        H3(title),
        P(value, cls="text-3xl"),
        Subtitle(description),
        cls=CardT.default,
    )


def setup_routes(rt):
    @rt("/dashboard")
    def dashboard_page():
        total_projects = _projects_service.total_projects()
        return Title("Dashboard - BIM Guard"), DashboardLayout(
            Container(
                DivFullySpaced(
                    H1("Dashboard"),
                    CreateAction(href="/projects/new", title="New Compliance Check"),
                ),
                Grid(
                    StatsCard(
                        "Total Projects", str(total_projects), "From project registry"
                    ),
                    StatsCard("Active Checks", "5", "3 require attention"),
                    StatsCard("Compliance Rate", "94%", "+2.1% improvement"),
                    StatsCard("Issues Found", "34", "-12 from last week"),
                    cols=1,
                    cols_md=2,
                    cols_lg=4,
                ),
                Grid(
                    Card(
                        P("No recent activity found."),
                        header=DivFullySpaced(
                            Div(
                                H3("Recent Activity"),
                                Subtitle("Recent transactions and system updates."),
                            ),
                            ViewAction(
                                href="/reports",
                                title="View All",
                                cls=ButtonT.secondary,
                            ),
                        ),
                    ),
                    Card(
                        H3("Quick Actions"),
                        NavContainer(
                            Ul(
                                Li(A("Upload IFC Model", href="/viewer")),
                                Li(A("Upload BEP Document", href="#")),
                                Li(A("Review Flagged Issues", href="#")),
                                Li(A("Generate Weekly Report", href="#")),
                            ),
                        ),
                    ),
                    cols=1,
                    cols_lg=3,
                    cls="gap-4",
                ),
                cls="space-y-4",
            )
        )
