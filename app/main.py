from fasthtml.common import FileResponse, Title, fast_app
from monsterui.all import (
    Container,
    DivLAligned,
    H1,
    Subtitle,
    Theme,
    ThemeFont,
    ThemeRadii,
    ThemeShadows,
)
from app.components.ui import ViewAction
from app.routes import analyze, dashboard, library, projects, viewer
from app.components.layout import DashboardLayout

hdrs = Theme.gray.headers(
    radii=ThemeRadii.lg,
    shadows=ThemeShadows.lg,
    font=ThemeFont.default,
)

# Initialize FastHTML app with MonsterUI theme headers
app, rt = fast_app(
    hdrs=hdrs,
    # Uvicorn reload is already used in development; disabling FastHTML's
    # websocket-based live reload avoids disconnect exceptions in the logs.
    live=False,
)


# Serve static files
@rt("/static/{path:path}")
def serve_static(path: str):
    return FileResponse(f"static/{path}")


# Compatibility endpoint for stale browser tabs that still attempt FastHTML's
# old live-reload websocket. We keep Uvicorn reload as the actual dev reload
# mechanism and simply accept these connections to avoid repeated 403 noise.
@app.ws("/live-reload")
async def live_reload_compat(msg: str, send):
    return None


# Setup routes
viewer.setup_routes(rt)
analyze.setup_routes(rt)
dashboard.setup_routes(rt)
library.setup_routes(rt)
projects.setup_routes(rt)


@rt("/")
def get():
    return Title("BIM Guard"), DashboardLayout(
        Container(
            H1("Welcome to BIM Guard"),
            Subtitle("Open the IFC viewer to start a new compliance workflow."),
            DivLAligned(ViewAction(href="/viewer", title="Go to Viewer")),
        )
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", reload=True)
