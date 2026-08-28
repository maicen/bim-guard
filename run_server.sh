#!/usr/bin/env bash
# ============================================================
# BIM Guard Development Server Launcher (Linux / macOS / WSL)
# ============================================================

set -euo pipefail

# Resolve project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================================"
echo "Starting BIM Guard (FastAPI Backend + Svelte 5 Frontend)"
echo "============================================================"

# Check prerequisites
if ! command -v uv >/dev/null 2>&1; then
    echo "Error: 'uv' is not installed or not in PATH."
    echo "Please install uv: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
    echo "Error: 'npm' is not installed or not in PATH."
    echo "Please install Node.js and npm to run the frontend."
    exit 1
fi

# Ensure frontend dependencies are installed
if [[ ! -d "frontend/node_modules" ]]; then
    echo "Frontend dependencies not found. Installing via 'npm install'..."
    (cd frontend && npm install)
fi

# Track child PIDs for clean termination
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
    trap - INT TERM EXIT
    echo ""
    echo "Shutting down development servers..."
    if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
        kill -TERM "$FRONTEND_PID" 2>/dev/null || true
    fi
    if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        kill -TERM "$BACKEND_PID" 2>/dev/null || true
    fi
    sleep 0.5 2>/dev/null || true
    wait 2>/dev/null || true
    echo "Servers stopped."
    exit 0
}

trap cleanup INT TERM EXIT

# 1. Launch FastAPI Backend Server
echo "[1/2] Launching FastAPI Backend on http://127.0.0.1:8000 ..."
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# 2. Launch Svelte Frontend Dev Server
echo "[2/2] Launching Svelte 5 Frontend on http://localhost:5173 ..."
(cd frontend && npm run dev) &
FRONTEND_PID=$!

echo ""
echo "============================================================"
echo "Development servers started successfully!"
echo "- Frontend: http://localhost:5173"
echo "- Backend:  http://127.0.0.1:8000"
echo "- API Docs: http://127.0.0.1:8000/api/docs"
echo "============================================================"
echo "Press Ctrl+C to stop all servers."
echo ""

# Wait for background processes
wait

