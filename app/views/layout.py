from fasthtml.common import A, Aside, Div, Main, Nav


def Sidebar():
    return Aside(
        Nav(
            A(
                "Dashboard",
                href="/dashboard",
                cls="block px-4 py-2 text-gray-700 hover:bg-gray-100",
            ),
            A(
                "Library",
                href="/library/documents",
                cls="block px-4 py-2 text-gray-700 hover:bg-gray-100",
            ),
            A(
                "Rules",
                href="/library/rules",
                cls="block px-4 py-2 text-gray-700 hover:bg-gray-100",
            ),
            A(
                "Reports",
                href="/reports",
                cls="block px-4 py-2 text-gray-700 hover:bg-gray-100",
            ),
            cls="space-y-2",
        ),
        cls="w-64 min-h-screen bg-white border-r",
    )


def DashboardLayout(*content):
    return Div(
        Sidebar(), Main(*content, cls="flex-1 p-8 bg-gray-50"), cls="flex min-h-screen"
    )
