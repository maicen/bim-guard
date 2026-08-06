from pathlib import Path

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

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX platforms
    fcntl = None

load_env_file()

from app.routes import (
    analyze,
    dashboard,
    library,
    modeling_manual,
    projects,
    revit_sync,
    settings,
    viewer,
)

APP_HEADERS = SiteTheme()

app, rt = fast_app(
    hdrs=APP_HEADERS,
    cls="antialiased",
)

_ROUTE_INSTALLERS = (
    viewer.setup_routes,
    analyze.setup_routes,
    dashboard.setup_routes,
    library.setup_routes,
    modeling_manual.setup_routes,
    projects.setup_routes,
    revit_sync.setup_routes,
    settings.setup_routes,
)
_ROUTES_REGISTERED = False


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


def _backfill_code_metadata(svc) -> None:
    """Add mechanism/ruleset metadata to legacy seed rules that predate meta columns."""
    for rule in svc.list_rules():
        if rule.get("extraction_method") == "seed" and not rule.get("ruleset_id"):
            svc._rules.update(
                updates={
                    "mechanism": "CODE",
                    "ruleset_id": "BUILDING-CODE-PART9",
                    "rule_category": "property_check",
                },
                pk_values=rule["id"],
            )


def _seed_library() -> None:
    """Populate the rule library with baseline code rules and engine rulesets."""
    try:
        from app.services.rules_service import RuleService
        from app.services.ruleset_seeder import (
            seed_default_code_rulesets,
            seed_engine_rulesets,
        )

        svc = RuleService()

        # Backfill any legacy seed rules that lack classification metadata.
        _backfill_code_metadata(svc)

        # Seed baseline property-check rules from canonical JSON rulesets.
        seed_default_code_rulesets(svc)

        # Seed GC-001 / CC-001 / MC-001 engine rulesets (each idempotent)
        seed_engine_rulesets(svc)

    except Exception:
        pass  # never crash startup over seeding


def _seed_library_once_per_host() -> None:
    """Run startup seeding in only one process when multiple workers boot."""
    lock_path = Path("data") / ".seed_library.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with lock_path.open("a+") as lock_file:
            if fcntl is not None:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    return
            _seed_library()
    except Exception:
        pass


def _setup_routes() -> None:
    """Register all routes exactly once during process startup."""
    global _ROUTES_REGISTERED
    if _ROUTES_REGISTERED:
        return
    for installer in _ROUTE_INSTALLERS:
        installer(rt)
    _ROUTES_REGISTERED = True


_seed_library_once_per_host()
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
