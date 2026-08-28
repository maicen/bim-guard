:; exec bash "$(dirname "$0")/run_production_server.sh" "$@"; exit $?
@echo off
title BIM Guard Production Server
echo ============================================================
echo Starting BIM Guard Production (FastAPI + Svelte 5 SPA)
echo ============================================================

if not exist "frontend\node_modules\" (
    echo Installing frontend dependencies...
    cd frontend
    call npm install
    cd ..
)

:: 1. Build Svelte 5 frontend distribution
echo [1/2] Building Svelte frontend production bundle...
cd frontend
call npm run build
if %ERRORLEVEL% neq 0 (
    echo Error building frontend bundle.
    pause
    exit /b %ERRORLEVEL%
)
cd ..

:: 2. Launch production backend (serving compiled SPA at / and API at /api)
echo [2/2] Launching production server on http://0.0.0.0:8000 ...
echo - App / SPA: http://localhost:8000/
echo - API Docs:  http://localhost:8000/api/docs
echo.
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --workers 8
