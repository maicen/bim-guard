"""BIM Guard Application Entrypoint — FastAPI Gateway & Static SPA Server."""

from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Thread
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import api_app
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


# --- Main FastAPI Application ---
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
from app.api import analyze, events, projects, rules

app.include_router(projects.router, prefix="/api/projects", tags=["Projects"])
app.include_router(rules.router, prefix="/api/rules", tags=["Rules"])
app.include_router(analyze.router, prefix="/api/analyze", tags=["Analysis"])
app.include_router(events.router, prefix="/api", tags=["Events"])


@app.get("/api/health", tags=["Health"], summary="API Gateway Health Check")
def health_check() -> dict:
    """Return API gateway operational status."""
    return {"status": "ok", "service": "bim-guard-api", "version": "1.0.0"}

# Mount static files
static_dir = Path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/viewer", response_class=HTMLResponse, summary="3D OpenBIM Viewer Viewport")
def viewer_page(project_id: int | None = None, element_guid: str | None = None):
    """Standalone 3D IFC Viewer embedding web-ifc and ThatOpenCompany components."""
    ifc_url = f"/api/projects/{project_id}/ifc" if project_id else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>3D Viewer — BIM Guard</title>
  <script type="importmap">
    {{"imports":{{"web-ifc":"https://unpkg.com/web-ifc@0.0.77/web-ifc-api.js"}}}}
  </script>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ background: #020617; color: #f8fafc; font-family: system-ui, sans-serif; overflow: hidden; width: 100vw; height: 100vh; }}
    #viewer-container {{ width: 100%; height: 100%; position: relative; }}
    .bimguard-viewport {{ width: 100%; height: 100%; display: block; }}
    .overlay {{ position: absolute; top: 12px; left: 12px; z-index: 10; background: rgba(15, 23, 42, 0.85); backdrop-filter: blur(8px); padding: 8px 14px; border-radius: 8px; border: 1px solid #334155; font-size: 12px; font-weight: 500; display: flex; align-items: center; gap: 8px; }}
    .dot {{ width: 8px; height: 8px; border-radius: 50%; background: #10b981; }}
  </style>
</head>
<body>
  <div class="overlay">
    <span class="dot"></span>
    <span>BIM Guard 3D Viewport {f"• Project #{project_id}" if project_id else ""}</span>
  </div>
  <div id="viewer-container"></div>
  <script type="module">
    import {{ initViewer }} from '/static/js/viewer/ifc-viewer.js?v=error-highlight-2';
    window.addEventListener('DOMContentLoaded', async () => {{
      const viewerAPI = await initViewer('viewer-container');
      if (viewerAPI) {{
        const ifcUrl = {json.dumps(ifc_url)};
        if (ifcUrl) {{
          await viewerAPI.loadIfc(ifcUrl);
        }}
      }}
    }});
  </script>
</body>
</html>"""


# Frontend SPA mount or landing page
frontend_dist = Path("frontend/dist")
if frontend_dist.exists() and (frontend_dist / "index.html").exists():
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="spa")
else:

    @app.get("/", response_class=HTMLResponse)
    def root_landing():
        """Welcome landing page directing to Svelte 5 dev server and FastAPI docs."""
        return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>BIM Guard — FastAPI & Svelte 5</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex items-center justify-center p-6 antialiased">
  <div class="max-w-xl w-full p-8 rounded-2xl border border-slate-800 bg-slate-900/60 shadow-2xl backdrop-blur space-y-6 text-center">
    <div class="w-16 h-16 rounded-2xl bg-gradient-to-tr from-emerald-600 to-teal-400 mx-auto flex items-center justify-center font-black text-2xl text-white shadow-lg shadow-emerald-500/20">
      BG
    </div>
    <div>
      <h1 class="text-2xl font-bold tracking-tight text-white">BIM Guard Platform</h1>
      <p class="text-sm text-slate-400 mt-1">FastAPI Gateway & Decoupled Svelte 5 SPA Architecture</p>
    </div>
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
      <a href="/api/docs" class="p-4 rounded-xl border border-slate-800 bg-slate-950/60 hover:border-emerald-500/50 hover:bg-slate-900 transition-all text-left group">
        <div class="text-xs uppercase tracking-wider font-semibold text-emerald-400">REST & SSE API</div>
        <div class="text-sm font-semibold text-white mt-1 group-hover:text-emerald-300">FastAPI Swagger UI ↗</div>
        <div class="text-xs text-slate-400 mt-1">Explore endpoints, contracts, and events.</div>
      </a>
      <a href="http://localhost:5173" target="_blank" class="p-4 rounded-xl border border-slate-800 bg-slate-950/60 hover:border-emerald-500/50 hover:bg-slate-900 transition-all text-left group">
        <div class="text-xs uppercase tracking-wider font-semibold text-teal-400">Svelte 5 Client</div>
        <div class="text-sm font-semibold text-white mt-1 group-hover:text-teal-300">Svelte SPA (Port 5173) ↗</div>
        <div class="text-xs text-slate-400 mt-1">Launch Vite development server.</div>
      </a>
    </div>
    <p class="text-xs text-slate-500 pt-2 border-t border-slate-800/80">
      Backend active at port 8000 • Run <code class="text-slate-300 font-mono">cd frontend && npm run dev</code> for the Svelte client.
    </p>
  </div>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
