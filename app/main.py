from fasthtml.common import FileResponse, Title, fast_app
from monsterui.all import (
    Container,
    DivLAligned,
    H1,
    Subtitle,
)
from app.components.layout import DashboardLayout
from app.components.themed_ui import SiteTheme
from app.components.ui import ViewAction
from app.utils import load_env_file

load_env_file()

from app.routes import analyze, dashboard, library, projects, viewer


APP_HEADERS = SiteTheme()

app, rt = fast_app(
    hdrs=APP_HEADERS,
    cls="antialiased",
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


def _seed_library() -> None:
    """Populate the rule library with OBC baseline rules if it is empty."""
    try:
        from app.services.rules_service import RuleService
        from app.modules.module3_rule_builder.obc_seed_rules import OBC_SEED_RULES
        svc = RuleService()
        if svc.list_rules():
            return  # already has rules — don't overwrite
        for rule in OBC_SEED_RULES:
            svc.create_rule(
                reference=rule.get("section_ref", "OBC"),
                rule_type=rule.get("rule_type", "json_check"),
                description=rule.get("description", ""),
                target_ifc_class=rule.get("entity_type", "Unspecified"),
                parameters="{}",
            )
    except Exception:
        pass  # never crash startup over seeding


def _setup_routes() -> None:
    viewer.setup_routes(rt)
    analyze.setup_routes(rt)
    dashboard.setup_routes(rt)
    library.setup_routes(rt)
    projects.setup_routes(rt)


_seed_library()
_setup_routes()


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
