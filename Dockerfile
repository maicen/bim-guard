# ── Build stage ──────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install core dependencies into /app/.venv (no editable install yet)
RUN uv sync --no-install-project --no-dev

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# System dependencies required by ifcopenshell and other native packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the virtualenv from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application source
COPY main.py ./
COPY app/ ./app/
COPY static/ ./static/

# Ensure the data directory exists so SQLite and uploads work
RUN mkdir -p data/uploads/ifc data/rulesets

# Copy default rulesets (non-secret config, safe to bake in)
COPY data/rulesets/ ./data/rulesets/

# Make sure the venv is on PATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Run as a non-root user for security (OWASP best practice)
RUN useradd -m -u 1000 bimguard && chown -R bimguard:bimguard /app
USER bimguard

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
