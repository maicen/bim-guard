:; exec bash "$(dirname "$0")/run_server.sh" "$@"; exit $?
@echo off
title BIM Guard Development Server
echo ============================================================
echo Starting BIM Guard (FastAPI Backend + Svelte 5 Frontend)
echo ============================================================

if not exist "frontend\node_modules\" (
    echo Installing frontend dependencies...
    cd frontend
    call npm install
    cd ..
)

:: Start FastAPI Backend Server in a new window
echo [1/2] Launching FastAPI Backend on http://127.0.0.1:8000 ...
start "BIM Guard Backend (FastAPI)" cmd /k "uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000"

:: Start Svelte Frontend Dev Server in a new window
echo [2/2] Launching Svelte 5 Frontend on http://localhost:5173 ...
start "BIM Guard Frontend (Vite)" cmd /k "cd frontend && npm run dev"

echo.
echo ============================================================
echo Development servers started successfully!
echo - Frontend: http://localhost:5173
echo - Backend:  http://127.0.0.1:8000
echo - API Docs: http://127.0.0.1:8000/api/docs
echo ============================================================
echo Press any key to close this launcher window (servers remain running).
pause >nul