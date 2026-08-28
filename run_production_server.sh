#!/usr/bin/env bash
# ============================================================
# BIM Guard Production Server Launcher (Linux / macOS / WSL)
# ============================================================

set -euo pipefail

# Resolve project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================================"
echo "Starting BIM Guard Production (FastAPI + Svelte 5 SPA)"
echo "============================================================"

# Check prerequisites
if ! command -v uv >/dev/null 2>&1; then
    echo "Error: 'uv' is not installed or not in PATH."
    echo "Please install uv: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
    echo "Error: 'npm' is not installed or not in PATH."
    echo "Please install Node.js and npm to build the frontend."
    exit 1
fi

# Ensure frontend dependencies are installed
if [[ ! -d "frontend/node_modules" ]]; then
    echo "Frontend dependencies not found. Installing via 'npm install'..."
    (cd frontend && npm install)
fi

# 1. Build Svelte 5 frontend distribution
echo "[1/2] Building Svelte frontend production bundle..."
(cd frontend && npm run build)

# 2. Launch production backend (serving compiled SPA at / and API at /api)
echo "[2/2] Launching production server on http://0.0.0.0:8000 ..."
echo "- App / SPA: http://localhost:8000/"
echo "- API Docs:  http://localhost:8000/api/docs"
echo ""

exec uv run uvicorn main:app --host 0.0.0.0 --port 8000 --workers 8

