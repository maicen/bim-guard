from fasthtml.common import *
from app.components.layout import DashboardLayout
from shad4fast import Card, CardHeader, CardTitle, CardDescription, CardContent, Button, Lucide

def StatsCard(title, value, description, icon):
    return Card(
        CardHeader(
            CardTitle(title, cls="text-sm font-medium leading-none tracking-tight"),
            Lucide(icon, cls="h-4 w-4 text-muted-foreground"),
            cls="flex flex-row items-center justify-between space-y-0 pb-2"
        ),
        CardContent(
            Div(value, cls="text-2xl font-bold"),
            P(description, cls="text-xs text-muted-foreground"),
        )
    )

def setup_routes(rt):
    @rt("/dashboard")
    def get():
        return Title("Dashboard - BIM Guard"), DashboardLayout(
            Div(
                # Header Section
                Div(
                    H1("Dashboard", cls="text-2xl font-bold tracking-tight"),
                    Div(
                        A(
                            Button(
                                Lucide("plus-circle", cls="h-3.5 w-3.5 mr-2"),
                                "New Compliance Check",
                                size="sm"
                            ),
                            href="/projects/new"
                        ),
                        cls="flex items-center gap-2"
                    ),
                    cls="flex items-center justify-between"
                ),

                # Stats Panel
                Div(
                    StatsCard("Total Projects", "12", "+2 from last month", "folder"),
                    StatsCard("Active Checks", "5", "3 require attention", "activity"),
                    StatsCard("Compliance Rate", "94%", "+2.1% improvement", "check-circle"),
                    StatsCard("Issues Found", "34", "-12 from last week", "alert-circle"),
                    cls="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mt-4"
                ),

                # Content Grid
                Div(
                    # Recent Activity
                    Card(
                        CardHeader(
                            Div(
                                CardTitle("Recent Activity"),
                                CardDescription("Recent transactions and system updates."),
                                cls="grid gap-2"
                            ),
                            A(
                                Button("View All", variant="outline", size="sm"),
                                href="/reports",
                                cls="ml-auto"
                            ),
                            cls="flex flex-row items-center"
                        ),
                        CardContent(
                            P("No recent activity found.", cls="text-sm text-muted-foreground text-center py-4"),
                        ),
                        cls="xl:col-span-2"
                    ),
                    
                    # Quick Actions
                    Card(
                        CardHeader(
                            CardTitle("Quick Actions"),
                        ),
                        CardContent(
                            A(Button("Upload IFC Model", variant="outline", cls="w-full justify-start font-normal mb-2"), href="/viewer"),
                            Button("Upload BEP Document", variant="outline", cls="w-full justify-start font-normal mb-2"),
                            Button("Review Flagged Issues", variant="outline", cls="w-full justify-start font-normal mb-2"),
                            Button("Generate Weekly Report", variant="outline", cls="w-full justify-start font-normal"),
                            cls="grid gap-2"
                        )
                    ),
                    cls="grid gap-4 md:gap-8 lg:grid-cols-2 xl:grid-cols-3 mt-4"
                ),
                cls="flex flex-col gap-4"
            )
        )
