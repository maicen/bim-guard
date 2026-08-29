@echo off
setlocal enabledelayedexpansion
title BIM Guard Production Server

echo ============================================================
echo Starting BIM Guard Production (FastAPI + Svelte 5 SPA)
echo ============================================================

REM Add local user path for uv if present
if exist "%USERPROFILE%\.local\bin" set "PATH=%USERPROFILE%\.local\bin;%PATH%"
if exist "%USERPROFILE%\.cargo\bin" set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"

REM 1. Check uv
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

REM 2. Check Node.js & npm
where node >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Node.js is not installed or not in PATH.
    echo Please install Node.js v18 or newer to build the frontend:
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

REM 3. Backend dependencies
if not exist ".venv\" (
    echo [INFO] Backend virtual environment not found. Running 'uv sync'...
    uv sync
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to sync backend dependencies.
        pause
        exit /b %ERRORLEVEL%
    )
)

REM 4. Frontend dependencies
if not exist "frontend\node_modules\.bin\vite" if not exist "frontend\node_modules\.bin\vite.cmd" (
    echo [INFO] Frontend dependencies incomplete or missing. Running 'npm install'...
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

REM 5. Build Svelte 5 frontend distribution
echo [1/2] Building Svelte frontend production bundle...
cd frontend
call npm run build
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Error building frontend bundle.
    cd ..
    pause
    exit /b %ERRORLEVEL%
)
cd ..

echo [2/2] Launching production server on http://0.0.0.0:8000 ...
echo - App / SPA: http://localhost:8000/
echo - API Docs:  http://localhost:8000/api/docs
echo.
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --workers 8
