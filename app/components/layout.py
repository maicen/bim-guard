from fasthtml.common import A, Div, H2, H3, Li, Small, Span
from monsterui.all import (
    DivFullySpaced,
    DivLAligned,
    NavContainer,
    NavDividerLi,
    NavHeaderLi,
    NavT,
    TextT,
    UkIcon,
)


NAV_ICONS = {
    "Dashboard": "layout-dashboard",
    "New Project": "folder-plus",
    "Viewer": "scan-eye",
    "Run Analysis": "cpu",
    "Reports": "file-text",
    "Documents": "book-open",
    "Rules": "list-checks",
    "Settings": "settings",
}


def NavItem(title, url):
    icon = NAV_ICONS.get(title, "circle")
    return Li(
        A(
            DivLAligned(
                UkIcon(icon, height=16, width=16, cls="text-muted-foreground"),
                Span(title),
                cls="gap-2 justify-start w-full",
            ),
            href=url,
            cls=f"{TextT.sm} hover:underline block w-full text-left",
        ),
        cls="px-1 py-0.5 w-full",
    )


def NavSection(title, items):
    return [
        NavHeaderLi(H3(title, cls="text-left w-full")),
        *[NavItem(label, href) for label, href in items],
    ]


def AppSidebar():
    nav_sections = [
        (
            "Platform",
            [
                ("Dashboard", "/dashboard"),
                ("New Project", "/projects/new"),
                ("Viewer", "/viewer"),
            ],
        ),
        ("Analysis", [("Run Analysis", "/analysis/run"), ("Reports", "/reports")]),
        ("Library", [("Documents", "/library/documents"), ("Rules", "/library/rules")]),
    ]
    nav_items = [frag for s in nav_sections for frag in (NavDividerLi(), *NavSection(*s))]

    return Div(
        Div(H2("BIM Guard"), cls="pb-2"),
        NavContainer(
            *nav_items,
            cls=(NavT.primary, "w-full text-left"),
        ),
        Div(
            NavContainer(
                NavDividerLi(),
                NavItem("Settings", "#"),
                cls=(NavT.primary, "w-full text-left"),
            ),
            cls="mt-auto pt-3",
        ),
        cls="border-r h-screen flex flex-col gap-4 p-4 bg-background",
    )


def AppHeader():
    return Div(
        DivFullySpaced(H2("Compliance Dashboard"), Small("v1.0.0")),
        cls="sticky top-0 z-10 min-h-14 px-4 border-b bg-background",
    )


def DashboardLayout(*content):
    return Div(
        AppSidebar(),
        Div(
            AppHeader(),
            Div(*content, cls="flex-1 w-full p-6 overflow-auto"),
            cls="flex-1 flex flex-col h-screen overflow-hidden gap-0",
        ),
        cls="flex min-h-screen w-full",
    )
