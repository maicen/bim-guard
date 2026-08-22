from fasthtml.common import FileResponse, Title, fast_app
from monsterui.all import (
    H1,
    Container,
    DivLAligned,
    Subtitle,
)

from app.components.layout import DashboardLayout
from app.components.themed_ui import SiteTheme
from app.components.ui import ViewAction
from app.services.pipeline_dependencies import warm_optional_rule_pipeline_dependencies
from app.utils import load_env_file

load_env_file()

from app.routes import analyze, dashboard, library, modeling_manual, projects, revit_sync, viewer

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


def _backfill_obc_metadata(svc) -> None:
    """Add mechanism/ruleset metadata to legacy OBC seed rules that predate the meta columns."""
    for rule in svc.list_rules():
        if rule.get("extraction_method") == "seed" and not rule.get("ruleset_id"):
            svc._rules.update(
                updates={
                    "mechanism": "OBC",
                    "ruleset_id": "OBC-PART9",
                    "rule_category": "property_check",
                },
                pk_values=rule["id"],
            )


def _seed_library() -> None:
    """Populate the rule library with engine rulesets (corrosion mechanisms).

    Does not seed any building-code rules — those only ever come from a
    user-uploaded PDF (via AI extraction or the free offline pipeline).
    """
    try:
        from app.services.rules_service import RuleService
        from app.services.ruleset_seeder import seed_engine_rulesets

        svc = RuleService()

        # Backfill classification metadata on legacy OBC rules from before
        # auto-seeding was removed, if any still exist in this database.
        _backfill_obc_metadata(svc)

        # Seed GC-001 / CC-001 / MC-001 engine rulesets (each idempotent)
        seed_engine_rulesets(svc)

    except Exception:
        pass  # never crash startup over seeding


def _setup_routes() -> None:
    viewer.setup_routes(rt)
    analyze.setup_routes(rt)
    dashboard.setup_routes(rt)
    library.setup_routes(rt)
    modeling_manual.setup_routes(rt)
    projects.setup_routes(rt)
    revit_sync.setup_routes(rt)


_seed_library()
try:
    warm_optional_rule_pipeline_dependencies()
except Exception:
    pass
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
