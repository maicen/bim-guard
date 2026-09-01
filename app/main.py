"""BIM Guard Application Entrypoint — FastAPI Gateway & Svelte 5 SPA."""

from __future__ import annotations

import os
from pathlib import Path
from threading import Thread
from time import perf_counter

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import (
    analyze as api_analyze,
)
from app.api import (
    bcf_routes as api_bcf,
)
from app.api import (
    cde_integration as api_cde,
)
from app.api import (
    dashboard as api_dashboard,
)
from app.api import (
    documents as api_documents,
)
from app.api import (
    events as api_events,
)
from app.api import (
    naming_config as api_naming_config,
)
from app.api import (
    projects as api_projects,
)
from app.api import (
    repositories as api_repositories,
)
from app.api import (
    rules as api_rules,
)
from app.api import (
    settings as api_settings,
)
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
        from app.bootstrap import get_container
        from app.logging_config import set_log_level

        level = get_container().settings_service.get("BIM_GUARD_LOG_LEVEL", "")
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
    """Populate the rule library with engine rulesets and building-code rulesets."""
    try:
        from app.bootstrap import get_container
        from app.services.ruleset_seeder import (
            seed_default_code_rulesets,
            seed_engine_rulesets,
        )

        svc = get_container().rules_service
        _backfill_code_metadata(svc)
        seed_engine_rulesets(svc)
        # BUILDING-CODE-PART9 and its extension back the Architecture theme,
        # which reads them through RuleService.list_code_rules(). The seeder
        # existed but nothing called it, so the thresholds the theme checks
        # against came from its hardcoded fallbacks on any database where the
        # rules had not been loaded by hand. seed_default_code_rulesets() also
        # calls seed_architectural_code_rules(), which this replaces.
        seed_default_code_rulesets(svc)
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
# Main FastAPI Gateway & Routing
# ==============================================================================
app = FastAPI(
    title="BIM Guard",
    description="OpenBIM Compliance Gateway & Decoupled Svelte 5 SPA Architecture",
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
        if not path.startswith("/static/") and not path.startswith("/assets/"):
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
app.include_router(api_dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(api_projects.router, prefix="/api/projects", tags=["Projects"])
app.include_router(api_repositories.router, prefix="/api/repositories", tags=["Repositories"])
app.include_router(api_rules.router, prefix="/api/rules", tags=["Rules"])
app.include_router(api_analyze.router, prefix="/api/analyze", tags=["Analysis"])
app.include_router(api_documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(api_cde.router, prefix="/api/cde", tags=["OpenCDE"])
app.include_router(api_bcf.router, prefix="/api/bcf", tags=["BCF API"])
app.include_router(api_settings.router, prefix="/api/settings", tags=["Settings"])
app.include_router(
    api_naming_config.router, prefix="/api/naming-config", tags=["ISO 19650 Naming"]
)
app.include_router(api_events.router, prefix="/api", tags=["Events"])



@app.get("/api/health", tags=["Health"], summary="API Gateway Health Check")
def health_check() -> dict:
    """Return API gateway operational status."""
    return {"status": "ok", "service": "bim-guard-api", "version": "1.0.0"}


@app.get("/download/{fmt}/{project_id}", tags=["Analysis"], summary="Download report endpoint alias")
def download_report_alias(
    fmt: str,
    project_id: int,
    slug: str = "corrosion",
):
    """Download analysis report in CSV, JSON, or BCF format."""
    from fastapi import Response
    from app.modules.phase_6.phase_6e_export import export
    from app.services.analysis_runner import RUNNABLE_SLUGS, run_analysis

    if project_id <= 0:
        raise HTTPException(status_code=400, detail="project_id must be a positive integer")

    if fmt not in ("csv", "json", "bcf"):
        raise HTTPException(status_code=404, detail=f"Unsupported export format '{fmt}'")

    if slug not in RUNNABLE_SLUGS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown slug '{slug}'. Must be one of: {', '.join(RUNNABLE_SLUGS)}",
        )

    result = run_analysis(slug, project_id)
    if result.get("compliance_error"):
        raise HTTPException(status_code=409, detail=result["compliance_error"])

    content, media_type, extension = export(result, fmt)
    filename = f"bimguard-{slug}-project-{project_id}.{extension}"
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "Content-Length": str(len(content)),
        },
    )


# Mount static assets directory
static_dir = Path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Production SPA Client Serving & Fallback
frontend_dist = Path("frontend/dist")
if (frontend_dist / "index.html").exists():
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def serve_spa(full_path: str):
        """Serve Svelte 5 Single Page Application client-side routing."""
        if full_path.startswith("api/") or full_path.startswith("static/") or full_path.startswith("download/"):
            raise HTTPException(status_code=404, detail="Endpoint not found.")
        file_candidate = frontend_dist / full_path
        if full_path and file_candidate.is_file():
            return FileResponse(file_candidate)
        return FileResponse(frontend_dist / "index.html")
else:
    @app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
    def root_dev():
        """Development fallback when frontend is not built."""
        return {
            "name": "BIM Guard API Gateway",
            "version": "1.0.0",
            "docs": "/api/docs",
            "frontend_dev_server": "http://localhost:5173",
            "status": "ready",
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
