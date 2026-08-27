from pathlib import Path
from threading import Thread
from time import perf_counter

from fasthtml.common import FileResponse, Title, fast_app
from starlette.middleware.base import BaseHTTPMiddleware

from app.compat.monsterui import ensure_monsterui_compat
from app.environment import load_env_file

ensure_monsterui_compat()
from monsterui.all import (
    H1,
    Container,
    DivLAligned,
    Subtitle,
)

from app.components.layout import DashboardLayout
from app.components.project_setup_wizard import handle_wizard_get, handle_wizard_post
from app.components.themed_ui import SiteTheme
from app.components.ui import ViewAction
from app.logging_config import configure_logging, get_logger

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX platforms
    fcntl = None

load_env_file()
configure_logging()
logger = get_logger(__name__)


def _apply_persisted_log_level() -> None:
    """Let the DB-backed log level win when no env override is present."""
    import os

    if (
        os.environ.get("BIM_GUARD_LOG_LEVEL")
        or os.environ.get("LOG_LEVEL")
        or os.environ.get("BIM_GUARD_VERBOSITY")
    ):
        return
    try:
        from app.logging_config import set_log_level
        from app.services.settings_service import SettingsService

        level = SettingsService().get("BIM_GUARD_LOG_LEVEL", "")
        if level:
            set_log_level(level)
    except Exception:
        logger.debug("Could not load persisted log level", exc_info=True)


_apply_persisted_log_level()

from app.routes import (
    analyze,
    analyze_architecture,
    analyze_corrosion,
    analyze_download,
    analyze_pipeline,
    analyze_seismic,
    dashboard,
    library,
    modeling_manual,
    projects,
    revit_sync,
    settings,
    user_manual,
    viewer,
)

APP_HEADERS = SiteTheme()

app, rt = fast_app(
    hdrs=APP_HEADERS,
    cls="antialiased",
)


class PageLoadLoggingMiddleware(BaseHTTPMiddleware):
    """Log browser page responses at DEBUG level with status and latency."""

    async def dispatch(self, request, call_next):
        started = perf_counter()
        response = await call_next(request)

        if request.method != "GET":
            return response

        path = request.url.path
        if path.startswith("/static/") or path in {"/live-reload", "/favicon.ico"}:
            return response

        content_type = (response.headers.get("content-type") or "").lower()
        if "text/html" not in content_type:
            return response

        duration_ms = (perf_counter() - started) * 1000
        logger.debug(
            "Page loaded method=%s path=%s status=%d duration_ms=%.1f",
            request.method,
            path,
            response.status_code,
            duration_ms,
        )
        return response


app.add_middleware(PageLoadLoggingMiddleware)

_ROUTE_INSTALLERS = (
    viewer.setup_routes,
    analyze.setup_routes,
    # Wizard destinations — one per app.constants.ANALYSIS_ROUTES slug.
    analyze_corrosion.setup_routes,
    analyze_seismic.setup_routes,
    analyze_architecture.setup_routes,
    # Phase 6 pipeline endpoints (upload / run / export).
    analyze_pipeline.setup_routes,
    # GET /download/{fmt}/{project_id} file downloads.
    analyze_download.setup_routes,
    dashboard.setup_routes,
    library.setup_routes,
    modeling_manual.setup_routes,
    projects.setup_routes,
    revit_sync.setup_routes,
    settings.setup_routes,
    user_manual.setup_routes,
)
_ROUTES_REGISTERED = False


# Serve static files
@rt("/static/{path:path}")
def serve_static(path: str):
    return FileResponse(f"static/{path}")


# Project Setup Wizard Routes
@app.get("/wizard")
def wizard_get():
    """GET /wizard — Render project setup wizard."""
    return handle_wizard_get()


@app.post("/wizard")
async def wizard_post(request):
    """POST /wizard — Handle wizard navigation."""
    form_data = await request.form()
    return await handle_wizard_post(form_data)


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
    """Populate the rule library with engine rulesets (corrosion mechanisms).

    Does not seed any building-code rules — those only ever come from a
    user-uploaded PDF (via AI extraction or the free offline pipeline), or
    explicitly via seed_db_first=True / the code_seed_rules CLI command.
    """
    try:
        from app.services.rules_service import RuleService
        from app.services.ruleset_seeder import seed_engine_rulesets

        svc = RuleService()

        # Backfill classification metadata on legacy OBC rules from before
        # auto-seeding was removed, if any still exist in this database.
        _backfill_code_metadata(svc)

        # Seed GC-001 / CC-001 / MC-001 engine rulesets (each idempotent)
        seed_engine_rulesets(svc)

    except Exception:
        logger.warning("Rule library seeding failed; continuing startup", exc_info=True)


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
        logger.warning("Could not acquire seeding lock; skipping seed", exc_info=True)


def _schedule_seed_library_once_per_host() -> None:
    """Kick off library seeding in the background so startup can return quickly."""
    Thread(target=_seed_library_once_per_host, daemon=True).start()


def _setup_routes() -> None:
    """Register all routes exactly once during process startup."""
    global _ROUTES_REGISTERED
    if _ROUTES_REGISTERED:
        return
    for installer in _ROUTE_INSTALLERS:
        logger.debug("Registering routes from %s", installer.__module__)
        installer(rt)
    _ROUTES_REGISTERED = True


_schedule_seed_library_once_per_host()
_setup_routes()
logger.info("BIM Guard startup complete")


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

    uvicorn.run("app.main:app", host="0.0.0.0", reload=True, log_config=None)
