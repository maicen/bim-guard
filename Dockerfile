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

# Install frontend dependencies
RUN npm install

# Copy frontend source files
COPY frontend/ ./

# Build production bundle into /frontend/dist
RUN npm run build


# ── Stage 2: Python Backend Builder ───────────────────────────────────────────
FROM python:3.12-slim AS backend-builder

# Install Astral uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency specifications
COPY pyproject.toml uv.lock ./

# Install dependencies into /app/.venv without project installation
RUN uv sync --no-install-project --no-dev


# ── Stage 3: Production Runtime ───────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# System dependencies:
# - libgomp1: required by IfcOpenShell OpenCASCADE native bindings
# - curl: required for container healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy virtualenv from backend builder
COPY --from=backend-builder /app/.venv /app/.venv

# Copy compiled Svelte 5 SPA from frontend builder
COPY --from=frontend-builder /frontend/dist ./frontend/dist

# Copy application source & assets
COPY main.py ./
COPY app/ ./app/
COPY static/ ./static/
COPY data/ ./data/

# Create runtime directories for Supabase Storage cache, agent sessions, and logs
RUN mkdir -p data/cache/supabase-storage data/agent-sessions data/logs

# Runtime environment settings
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    BIM_GUARD_STORAGE_BACKEND=supabase \
    PORT=8000 \
    HOST=0.0.0.0

EXPOSE 8000

# Security: Non-root user
RUN useradd -m -u 1000 bimguard && chown -R bimguard:bimguard /app
USER bimguard

# Healthcheck targeting FastAPI gateway health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

# Production command: 4 worker processes
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
