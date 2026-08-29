"""BIM Guard Application Entrypoint — Dual FastAPI Gateway & MonsterUI Monolith."""

from __future__ import annotations

import os
from pathlib import Path
from threading import Thread
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.compat.monsterui import ensure_monsterui_compat
from app.environment import load_env_file
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


# --- Database Seeding ---
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
    """Populate the rule library with engine rulesets (corrosion mechanisms)."""
    try:
        from app.services.rules_service import RuleService
        from app.services.ruleset_seeder import seed_engine_rulesets

        svc = RuleService()
        _backfill_code_metadata(svc)
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


_schedule_seed_library_once_per_host()


# ==============================================================================
# FastHTML / MonsterUI Legacy Monolith Setup
# ==============================================================================
ensure_monsterui_compat()
from fasthtml.common import FileResponse, Title, fast_app
from monsterui.all import Container, DivLAligned, H1, Subtitle

from app.components.layout import DashboardLayout
from app.components.project_setup_wizard import handle_wizard_get, handle_wizard_post
from app.components.themed_ui import SiteTheme
from app.components.ui import ViewAction
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
    viewer_routes,
    workflow_api,
    workflow_page,
)

APP_HEADERS = SiteTheme()

fasthtml_app, rt = fast_app(
    hdrs=APP_HEADERS,
    cls="antialiased",
)

_ROUTE_INSTALLERS = (
    viewer.setup_routes,
    viewer_routes.setup_routes,
    analyze.setup_routes,
    analyze_corrosion.setup_routes,
    analyze_seismic.setup_routes,
    analyze_architecture.setup_routes,
    analyze_pipeline.setup_routes,
    analyze_download.setup_routes,
    workflow_api.setup_routes,
    workflow_page.setup_routes,
    dashboard.setup_routes,
    library.setup_routes,
    modeling_manual.setup_routes,
    projects.setup_routes,
    revit_sync.setup_routes,
    settings.setup_routes,
    user_manual.setup_routes,
)

for installer in _ROUTE_INSTALLERS:
    logger.debug("Registering FastHTML routes from %s", installer.__module__)
    installer(rt)


@fasthtml_app.get("/wizard")
def wizard_get():
    """GET /wizard — Render project setup wizard."""
    return handle_wizard_get()


@fasthtml_app.post("/wizard")
async def wizard_post(request: Request):
    """POST /wizard — Handle wizard navigation."""
    form_data = await request.form()
    return await handle_wizard_post(form_data)


@rt("/")
def get():
    return Title("BIM Guard"), DashboardLayout(
        Container(
            H1("Welcome to BIM Guard"),
            Subtitle("Open the IFC viewer to start a new compliance workflow."),
            DivLAligned(ViewAction(href="/viewer", title="Go to Viewer")),
        )
    )


# ==============================================================================
# Main FastAPI Gateway & Routing
# ==============================================================================
app = FastAPI(
    title="BIM Guard",
    description="OpenBIM Compliance Gateway & Decoupled Svelte SPA Architecture",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Configure CORS
allowed_origins_env = os.getenv("BIM_GUARD_ALLOWED_ORIGINS", "")
allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
if not allowed_origins:
    allowed_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if "*" not in allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log API and page responses at DEBUG level with latency."""

    async def dispatch(self, request: Request, call_next):
        started = perf_counter()
        response = await call_next(request)
        path = request.url.path
        if not path.startswith("/static/"):
            duration_ms = (perf_counter() - started) * 1000
            logger.debug(
                "Request method=%s path=%s status=%d duration_ms=%.1f",
                request.method,
                path,
                response.status_code,
                duration_ms,
            )
        return response


app.add_middleware(RequestLoggingMiddleware)

# Register API Gateway routers directly under /api prefix
from app.api import (
    analyze as api_analyze,
    dashboard as api_dashboard,
    documents as api_documents,
    events as api_events,
    projects as api_projects,
    rules as api_rules,
    settings as api_settings,
)

app.include_router(api_dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(api_projects.router, prefix="/api/projects", tags=["Projects"])
app.include_router(api_rules.router, prefix="/api/rules", tags=["Rules"])
app.include_router(api_analyze.router, prefix="/api/analyze", tags=["Analysis"])
app.include_router(api_documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(api_settings.router, prefix="/api/settings", tags=["Settings"])
app.include_router(api_events.router, prefix="/api", tags=["Events"])


@app.get("/api/health", tags=["Health"], summary="API Gateway Health Check")
def health_check() -> dict:
    """Return API gateway operational status."""
    return {"status": "ok", "service": "bim-guard-api", "version": "1.0.0"}


# Mount static files for both FastAPI and FastHTML/Viewer
static_dir = Path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Mount FastHTML / MonsterUI Monolith at root to catch all browser routes
app.mount("/", fasthtml_app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
