:; exec bash "$(dirname "$0")/run_server.sh" "$@"; exit $?
@echo off
setlocal enabledelayedexpansion
title BIM Guard Development Server

echo ============================================================
echo Starting BIM Guard (FastAPI Backend + Svelte 5 Frontend)
echo ============================================================

:: Add local user path for uv if present
if exist "%USERPROFILE%\.local\bin" set "PATH=%USERPROFILE%\.local\bin;%PATH%"
if exist "%USERPROFILE%\.cargo\bin" set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"

:: 1. Check uv
where uv >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] 'uv' is not installed or not in PATH.
    echo BIM-Guard requires Astral uv for fast Python package management.
    echo.
    echo To install uv on Windows, run:
    echo   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    echo   or: winget install astral-sh.uv
    echo.
    pause
    exit /b 1
)

:: 2. Check Node.js & npm
where node >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Node.js is not installed or not in PATH.
    echo Please install Node.js (v18 or newer):
    echo   winget install OpenJS.NodeJS
    echo   or download from: https://nodejs.org/
    echo.
    pause
    exit /b 1
)

where npm >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] npm is not installed or not in PATH.
    echo Please ensure Node.js is properly installed with npm included.
    echo.
    pause
    exit /b 1
)

:: 3. Backend dependencies
if not exist ".venv\" (
    echo [INFO] Backend virtual environment not found. Running 'uv sync'...
    uv sync
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to sync backend dependencies.
        pause
        exit /b %ERRORLEVEL%
    )
)

:: 4. Frontend dependencies
if not exist "frontend\node_modules\" (
    echo [INFO] Frontend node_modules not found. Installing via 'npm install'...
    cd frontend
    call npm install
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to install frontend dependencies.
        cd ..
        pause
        exit /b %ERRORLEVEL%
    )
    cd ..
)

:: 5. Launch FastAPI Backend Server in a new window
echo [1/2] Launching FastAPI Backend on http://127.0.0.1:8000 ...
start "BIM Guard Backend (FastAPI)" cmd /k "uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000"

:: 6. Launch Svelte Frontend Dev Server in a new window
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