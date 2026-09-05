# ==============================================================================
# BIM Guard Multi-Stage Production Dockerfile
# Stage 1: Build Svelte 5 SPA Frontend
# Stage 2: Install Python Backend Virtualenv via Astral uv
# Stage 3: Minimal, Secure Production Runtime
# ==============================================================================

# ── Stage 1: Frontend SPA Builder ─────────────────────────────────────────────
FROM node:22-slim AS frontend-builder

WORKDIR /frontend

# Copy package manifests for efficient layer caching
COPY frontend/package.json frontend/package-lock.json* ./

# Cache-mounted install (npm cache never lands in an image layer).
# npm ci is avoided: this lockfile has pre-existing nested-optional-dependency
# drift (picomatch via tailwind vs vite) that npm's strict ci check rejects
# even right after a clean `npm install` — a lockfile quirk, not a Docker issue.
RUN --mount=type=cache,target=/root/.npm \
    npm install --no-audit --no-fund

# Copy frontend source files
COPY frontend/ ./

# Supabase Auth is browser-side (VITE_ vars get baked into the bundle at
# build time, not read at runtime) — Render passes dashboard env vars in as
# matching build args for Docker services. See render.yaml.
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ENV VITE_SUPABASE_URL=${VITE_SUPABASE_URL}
ENV VITE_SUPABASE_ANON_KEY=${VITE_SUPABASE_ANON_KEY}

# Build production bundle into /frontend/dist
RUN npm run build


# ── Stage 2: Python Backend Builder ───────────────────────────────────────────
FROM python:3.12-slim-bookworm AS backend-builder

# Install Astral uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

ENV UV_LINK_MODE=copy

# Copy dependency specifications
COPY pyproject.toml uv.lock ./

# Install dependencies into /app/.venv without project installation.
# --frozen refuses to resolve/update the lockfile; cache mount keeps the
# uv download cache out of the image layers entirely. No bytecode
# precompilation, since PYTHONDONTWRITEBYTECODE=1 at runtime never uses it.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev


# ── Stage 3: Production Runtime ───────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS runtime

# System dependencies:
# - libgomp1: required by IfcOpenShell OpenCASCADE native bindings
# Non-root user is created before the app payload is copied in, so ownership
# is set by COPY --chown at copy time instead of a later `chown -R` layer —
# a chown after the fact would copy-on-write the entire ~1GB venv again.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 bimguard

WORKDIR /app

# Copy virtualenv from backend builder
COPY --from=backend-builder --chown=bimguard:bimguard /app/.venv /app/.venv

# Copy compiled Svelte 5 SPA from frontend builder
COPY --from=frontend-builder --chown=bimguard:bimguard /frontend/dist ./frontend/dist

# Copy application source & assets
COPY --chown=bimguard:bimguard main.py ./
COPY --chown=bimguard:bimguard app/ ./app/
COPY --chown=bimguard:bimguard static/ ./static/
COPY --chown=bimguard:bimguard data/ ./data/

# Create runtime directories for Supabase Storage cache, agent sessions, and logs
RUN mkdir -p data/cache/supabase-storage data/agent-sessions data/logs \
    && chown -R bimguard:bimguard data/

# Runtime environment settings
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    BIM_GUARD_STORAGE_BACKEND=supabase \
    PORT=8000 \
    HOST=0.0.0.0

EXPOSE 8000

USER bimguard

# Healthcheck targeting FastAPI gateway health endpoint (no curl dependency)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=5)" || exit 1

# Production command: 4 worker processes
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
