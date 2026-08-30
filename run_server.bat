@echo off
setlocal enabledelayedexpansion
title BIM Guard Development Server

echo ============================================================
echo Starting BIM Guard (FastAPI Backend + Svelte 5 Frontend)
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
    echo Please install Node.js v18 or newer:
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

REM 5. Launch FastAPI Backend Server in a new window
echo [1/2] Launching FastAPI Backend on http://127.0.0.1:8000 ...
start "BIM Guard Backend (FastAPI)" cmd /k "uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000"

REM Poll until port 8000 is actually listening (up to 60 s)
echo     Waiting for backend to become ready...
:WAIT_BACKEND
powershell -NoProfile -Command "try{$c=New-Object Net.Sockets.TcpClient('127.0.0.1',8000);$c.Close();exit 0}catch{exit 1}" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    timeout /t 1 /nobreak >nul
    goto WAIT_BACKEND
)
echo     Backend is ready.

REM 6. Launch Svelte Frontend Dev Server in a new window
echo [2/2] Launching Svelte 5 Frontend on http://localhost:5173 ...
start "BIM Guard Frontend (Vite)" cmd /k "cd frontend && npm run dev"

echo.
echo ============================================================
echo Development servers started successfully
echo - Frontend: http://localhost:5173
echo - Backend:  http://127.0.0.1:8000
echo - API Docs: http://127.0.0.1:8000/api/docs
echo ============================================================
echo Press any key to exit this launcher - servers will remain running.
pause >nul