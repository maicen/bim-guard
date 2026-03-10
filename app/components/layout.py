from fasthtml.common import *
from shad4fast import Button, Lucide, Separator

def NavItem(title, url, icon):
    return Li(
        A(
            Lucide(icon, cls="w-4 h-4 mr-2"),
            Span(title),
            href=url,
            cls="flex items-center px-3 py-2 text-sm font-medium rounded-md text-muted-foreground hover:text-foreground hover:bg-accent"
        )
    )

def AppSidebar():
    return Aside(
        Div(
            Div(
                Lucide("scale", cls="w-5 h-5 text-primary-foreground"),
                cls="flex h-8 w-8 items-center justify-center rounded-lg bg-primary"
            ),
            Span("BIMGuard AI", cls="font-bold text-lg ml-2"),
            cls="flex items-center gap-2 px-4 py-4 border-b"
        ),
        Nav(
            Div(
                H3("Platform", cls="px-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider mt-4 mb-2"),
                Ul(
                    NavItem("Dashboard", "/dashboard", "layout-dashboard"),
                    NavItem("New Project", "/projects/new", "folder-plus"),
                    NavItem("Viewer", "/viewer", "box"),
                    cls="space-y-1 px-2"
                ),
            ),
            Div(
                H3("Analysis", cls="px-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider mt-4 mb-2"),
                Ul(
                    NavItem("Run Analysis", "/analysis/run", "play"),
                    NavItem("Reports", "/reports", "file-text"),
                    cls="space-y-1 px-2"
                ),
            ),
            Div(
                H3("Library", cls="px-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider mt-4 mb-2"),
                Ul(
                    NavItem("Documents", "/library/documents", "book-open"),
                    NavItem("Rules", "/library/rules", "scale"),
                    cls="space-y-1 px-2"
                ),
            ),
            cls="flex-1 overflow-y-auto"
        ),
        Div(
            Ul(
                NavItem("Settings", "#", "settings"),
                cls="space-y-1 px-2 mb-4"
            ),
            cls="mt-auto border-t pt-4"
        ),
        cls="w-64 bg-muted/30 border-r flex flex-col h-full"
    )

def AppHeader():
    return Header(
        Div(
            Button(
                Lucide("menu", cls="w-5 h-5"),
                variant="ghost", size="icon", cls="text-muted-foreground"
            ),
            Separator(orientation="vertical", cls="h-6 mx-4"),
            H2("Compliance Dashboard", cls="text-lg font-semibold flex-1 text-foreground"),
            Div(
                Span("v1.0.0", cls="text-sm text-muted-foreground"),
                cls="flex items-center gap-4"
            ),
            cls="flex items-center h-14 px-4 sm:px-6"
        ),
        cls="bg-background border-b z-30 sticky top-0"
    )

def DashboardLayout(*content):
    return Div(
        AppSidebar(),
        Div(
            AppHeader(),
            Main(
                *content,
                cls="flex-1 overflow-auto bg-muted/10 p-6"
            ),
            cls="flex-1 flex flex-col h-full overflow-hidden"
        ),
        Script("lucide.createIcons();"),
        cls="flex h-screen w-full font-sans text-foreground bg-background"
    )
