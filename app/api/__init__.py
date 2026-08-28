"""FastAPI Application Gateway for BIM Guard.

Exposes REST and SSE endpoints for projects, rules, analysis pipelines, and live tracking.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import analyze, events, projects, rules

api_app = FastAPI(
    title="BIM Guard API",
    description="REST & SSE API Gateway for OpenBIM compliance checking, rule validation, and live pipeline tracking.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configure CORS for local development with standalone Vite SPA
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

api_app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if "*" not in allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
api_app.include_router(projects.router, prefix="/projects", tags=["Projects"])
api_app.include_router(rules.router, prefix="/rules", tags=["Rules"])
api_app.include_router(analyze.router, prefix="/analyze", tags=["Analysis"])
api_app.include_router(events.router, prefix="", tags=["Events"])


@api_app.get("/health", tags=["Health"], summary="API Gateway Health Check")
def health_check() -> dict:
    """Return API gateway operational status."""
    return {"status": "ok", "service": "bim-guard-api", "version": "1.0.0"}


__all__ = ["api_app"]

