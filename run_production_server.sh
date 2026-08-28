#!/usr/bin/env bash
# ============================================================
# BIM Guard Production Server Launcher (Linux / macOS / WSL)
# Interactive, dynamic, and robust launcher for compiled SPA + API
# ============================================================

set -euo pipefail

# Resolve project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Ensure local user paths are available for uv / node
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

# Defaults
BACKEND_HOST="${HOST:-0.0.0.0}"
BACKEND_PORT="${PORT:-8000}"
WORKERS="${WORKERS:-8}"
SKIP_BUILD=false
SKIP_SYNC=false
FORCE_SYNC=false
AUTO_YES=false

# ------------------------------------------------------------
# Styling & Colors (TTY-aware)
# ------------------------------------------------------------
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
    COLOR_RESET="\033[0m"
    COLOR_BOLD="\033[1m"
    COLOR_DIM="\033[2m"
    COLOR_CYAN="\033[36m"
    COLOR_GREEN="\033[32m"
    COLOR_YELLOW="\033[33m"
    COLOR_RED="\033[31m"
    COLOR_BLUE="\033[34m"
    COLOR_MAGENTA="\033[35m"
else
    COLOR_RESET=""
    COLOR_BOLD=""
    COLOR_DIM=""
    COLOR_CYAN=""
    COLOR_GREEN=""
    COLOR_YELLOW=""
    COLOR_RED=""
    COLOR_BLUE=""
    COLOR_MAGENTA=""
fi

log_header() {
    echo -e "${COLOR_CYAN}${COLOR_BOLD}============================================================${COLOR_RESET}"
    echo -e "${COLOR_CYAN}${COLOR_BOLD}  $1${COLOR_RESET}"
    echo -e "${COLOR_CYAN}${COLOR_BOLD}============================================================${COLOR_RESET}"
}

log_step() {
    echo -e "${COLOR_BLUE}${COLOR_BOLD}[$1]${COLOR_RESET} $2"
}

log_success() {
    echo -e " ${COLOR_GREEN}✓${COLOR_RESET} $1"
}

log_warn() {
    echo -e " ${COLOR_YELLOW}⚠${COLOR_RESET} ${COLOR_YELLOW}$1${COLOR_RESET}"
}

log_error() {
    echo -e " ${COLOR_RED}✗${COLOR_RESET} ${COLOR_RED}$1${COLOR_RESET}" >&2
}

log_info() {
    echo -e " ${COLOR_DIM}ℹ${COLOR_RESET} $1"
}

# ------------------------------------------------------------
# CLI Help & Arguments
# ------------------------------------------------------------
show_help() {
    echo -e "${COLOR_BOLD}Usage:${COLOR_RESET} ./run_production_server.sh [options]"
    echo ""
    echo -e "${COLOR_BOLD}Options:${COLOR_RESET}"
    echo "  -p, --port <port>             Production server port (default: 8000, or \$PORT)"
    echo "  -H, --host <host>             Production bind host (default: 0.0.0.0, or \$HOST)"
    echo "  -w, --workers <num>           Number of Uvicorn worker processes (default: 8, or \$WORKERS)"
    echo "  --skip-build                  Skip rebuilding frontend SPA distribution"
    echo "  -s, --skip-sync               Skip backend/frontend dependency checks"
    echo "  --sync                        Force dependency synchronization/installation"
    echo "  -y, --yes                     Non-interactive mode; auto-accept default prompts"
    echo "  -h, --help                    Show this help message and exit"
    echo ""
    echo -e "${COLOR_BOLD}Environment Variables:${COLOR_RESET}"
    echo "  PORT                          Override production server port"
    echo "  HOST                          Override bind host"
    echo "  WORKERS                       Override worker count"
    echo "  NO_COLOR                      Disable colored terminal output"
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--port)
            BACKEND_PORT="$2"
            shift 2
            ;;
        -H|--host)
            BACKEND_HOST="$2"
            shift 2
            ;;
        -w|--workers)
            WORKERS="$2"
            shift 2
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        -s|--skip-sync)
            SKIP_SYNC=true
            shift
            ;;
        --sync)
            FORCE_SYNC=true
            shift
            ;;
        -y|--yes)
            AUTO_YES=true
            shift
            ;;
        -h|--help)
            show_help
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Use './run_production_server.sh --help' for usage instructions."
            exit 1
            ;;
    esac
done

log_header "BIM Guard Production Server (FastAPI + Svelte 5 SPA)"

# ------------------------------------------------------------
# Interactive Prompt Helper
# ------------------------------------------------------------
prompt_user_yn() {
    local prompt_msg="$1"
    local default_val="${2:-Y}"
    
    if [[ "$AUTO_YES" == "true" || ! -t 0 ]]; then
        if [[ "$default_val" == "Y" || "$default_val" == "y" ]]; then
            return 0
        else
            return 1
        fi
    fi

    local choice_hint="[Y/n]"
    [[ "$default_val" =~ ^[Nn]$ ]] && choice_hint="[y/N]"

    read -r -p "$(echo -e " ${COLOR_YELLOW}?${COLOR_RESET} ${prompt_msg} ${COLOR_DIM}${choice_hint}${COLOR_RESET}: ")" response
    response="${response:-$default_val}"
    case "$response" in
        [yY][eE][sS]|[yY])
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# ------------------------------------------------------------
# 1. Prerequisite Checks: uv, Python, Node.js, npm
# ------------------------------------------------------------
log_step "1/4" "Checking environment prerequisites..."

# Check uv
if ! command -v uv >/dev/null 2>&1; then
    log_warn "'uv' is not installed or not in PATH."
    echo ""
    echo -e "${COLOR_BOLD}BIM-Guard requires Astral uv for fast Python package & runtime management.${COLOR_RESET}"
    echo "Installation instructions:"
    echo "  - macOS / Linux / WSL:  curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "  - macOS (Homebrew):     brew install uv"
    echo "  - Windows:              powershell -ExecutionPolicy ByPass -c \"irm https://astral.sh/uv/install.ps1 | iex\""
    echo ""

    if [[ -t 0 ]] && command -v curl >/dev/null 2>&1; then
        if prompt_user_yn "Would you like to install 'uv' automatically right now?" "Y"; then
            log_info "Installing uv via official installer (https://astral.sh/uv/install.sh)..."
            curl -LsSf https://astral.sh/uv/install.sh | sh
            export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
            if ! command -v uv >/dev/null 2>&1; then
                log_error "uv was installed but is not found in PATH. Please restart your terminal or add ~/.local/bin to PATH."
                exit 1
            fi
            log_success "uv installed successfully: $(uv --version)"
        else
            log_error "Cannot proceed without 'uv'. Please install uv and run again."
            exit 1
        fi
    else
        log_error "Cannot proceed without 'uv'. Please install uv and run again."
        exit 1
    fi
else
    log_success "uv found: $(uv --version | head -n 1)"
fi

# Check Python (via uv or system)
if command -v python3 >/dev/null 2>&1; then
    PY_VER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")' 2>/dev/null || echo "unknown")"
    log_success "Python found: ${PY_VER}"
else
    log_info "System python3 binary not in PATH. uv will automatically manage Python (>= 3.12)."
fi

# Check Node.js and npm (needed to build frontend bundle)
MISSING_NODE=false
if ! command -v node >/dev/null 2>&1; then
    log_warn "Node.js ('node') is not installed or not in PATH."
    MISSING_NODE=true
fi

if ! command -v npm >/dev/null 2>&1; then
    log_warn "Node package manager ('npm') is not installed or not in PATH."
    MISSING_NODE=true
fi

if [[ "$MISSING_NODE" == "true" ]]; then
    echo ""
    echo -e "${COLOR_BOLD}BIM-Guard requires Node.js (>= 18) and npm to build the Svelte 5 frontend bundle.${COLOR_RESET}"
    echo "Installation instructions:"
    echo "  - macOS (Homebrew):     brew install node"
    echo "  - Ubuntu / Debian:      sudo apt update && sudo apt install -y nodejs npm"
    echo "  - Linux (NodeSource):   https://nodejs.org/en/download/package-manager"
    echo "  - Windows:              winget install OpenJS.NodeJS"
    echo "  - Official Download:    https://nodejs.org/"
    echo ""

    if [[ "$(uname)" == "Darwin" ]] && command -v brew >/dev/null 2>&1 && [[ -t 0 ]]; then
        if prompt_user_yn "Would you like to install Node.js via Homebrew now?" "Y"; then
            log_info "Running 'brew install node'..."
            brew install node
            export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
        else
            log_error "Cannot build frontend without Node.js and npm. Please install Node.js and try again."
            exit 1
        fi
    else
        log_error "Cannot build frontend without Node.js and npm. Please install Node.js and try again."
        exit 1
    fi
fi

NODE_VER="$(node -v 2>/dev/null || echo "unknown")"
NPM_VER="$(npm -v 2>/dev/null || echo "unknown")"
log_success "Node.js ${NODE_VER} & npm ${NPM_VER} verified."

# ------------------------------------------------------------
# 2. Dependency Management: Backend & Frontend
# ------------------------------------------------------------
log_step "2/4" "Verifying backend and frontend dependencies..."

if [[ "$SKIP_SYNC" != "true" ]]; then
    # Backend dependencies
    NEED_UV_SYNC=false
    if [[ "$FORCE_SYNC" == "true" || ! -d ".venv" ]]; then
        NEED_UV_SYNC=true
    elif ! uv run python -c "import fastapi, ifcopenshell" >/dev/null 2>&1; then
        NEED_UV_SYNC=true
    fi

    if [[ "$NEED_UV_SYNC" == "true" ]]; then
        log_info "Synchronizing backend dependencies with 'uv sync'..."
        if uv sync; then
            log_success "Backend dependencies synced."
        else
            log_error "uv sync encountered errors. Check output above."
            exit 1
        fi
    else
        log_success "Backend dependencies up to date."
    fi

    # Frontend dependencies
    NEED_NPM_INSTALL=false
    if [[ "$FORCE_SYNC" == "true" || ! -d "frontend/node_modules" ]]; then
        NEED_NPM_INSTALL=true
    elif [[ -f "frontend/package.json" && -d "frontend/node_modules" ]]; then
        if [[ "frontend/package.json" -nt "frontend/node_modules" ]]; then
            NEED_NPM_INSTALL=true
        fi
    fi

    if [[ "$NEED_NPM_INSTALL" == "true" ]]; then
        log_info "Installing frontend dependencies with 'npm install' in frontend/..."
        (cd frontend && npm install)
        log_success "Frontend dependencies installed."
    else
        log_success "Frontend dependencies up to date."
    fi
else
    log_info "Skipping dependency sync (--skip-sync provided)."
fi

# ------------------------------------------------------------
# 3. Build Svelte 5 Frontend Production Bundle
# ------------------------------------------------------------
log_step "3/4" "Preparing production frontend bundle..."

if [[ "$SKIP_BUILD" == "true" && -f "frontend/dist/index.html" ]]; then
    log_info "Skipping frontend build (--skip-build provided and dist exists)."
else
    log_info "Compiling Svelte 5 SPA via Vite ('npm run build')..."
    if (cd frontend && npm run build); then
        log_success "Frontend bundle compiled successfully in frontend/dist/."
    else
        log_error "Frontend build failed. Please resolve build errors and retry."
        exit 1
    fi
fi

# ------------------------------------------------------------
# 4. Dynamic Port Collision Detection & Launch Server
# ------------------------------------------------------------
log_step "4/4" "Checking port and launching production server..."

get_pid_on_port() {
    local port="$1"
    if command -v lsof >/dev/null 2>&1; then
        lsof -ti ":$port" 2>/dev/null | head -n 1 || true
    elif command -v fuser >/dev/null 2>&1; then
        fuser "$port/tcp" 2>/dev/null | awk '{print $1}' || true
    elif command -v ss >/dev/null 2>&1; then
        ss -tlpn "sport = :$port" 2>/dev/null | grep -o 'pid=[0-9]*' | cut -d= -f2 | head -n 1 || true
    else
        echo ""
    fi
}

pid="$(get_pid_on_port "$BACKEND_PORT")"
if [[ -n "$pid" ]]; then
    pname="unknown"
    if command -v ps >/dev/null 2>&1; then
        pname="$(ps -p "$pid" -o comm= 2>/dev/null || echo "unknown")"
    fi

    log_warn "Production server port $BACKEND_PORT is already in use by PID $pid ($pname)."

    if [[ "$AUTO_YES" == "true" || ! -t 0 ]]; then
        log_info "Non-interactive mode: terminating conflicting process PID $pid..."
        kill -TERM "$pid" 2>/dev/null || true
        sleep 1
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null || true
        fi
    else
        echo ""
        echo "Options to resolve port collision:"
        echo "  [k] Kill conflicting process (PID $pid)"
        echo "  [c] Change port for production server"
        echo "  [a] Abort launcher"
        read -r -p "$(echo -e " ${COLOR_YELLOW}?${COLOR_RESET} Choose action [k/c/a] (default: k): ")" conflict_choice
        conflict_choice="${conflict_choice:-k}"

        case "$conflict_choice" in
            [kK]*)
                log_info "Terminating process PID $pid..."
                kill -TERM "$pid" 2>/dev/null || true
                sleep 1
                if kill -0 "$pid" 2>/dev/null; then
                    kill -9 "$pid" 2>/dev/null || true
                fi
                log_success "Port $BACKEND_PORT freed."
                ;;
            [cC]*)
                read -r -p "$(echo -e " ${COLOR_YELLOW}?${COLOR_RESET} Enter new port number: ")" new_port
                if [[ "$new_port" =~ ^[0-9]+$ ]] && [[ "$new_port" -ge 1024 && "$new_port" -le 65535 ]]; then
                    BACKEND_PORT="$new_port"
                    log_info "Updated production port to $BACKEND_PORT"
                else
                    log_error "Invalid port: $new_port. Aborting."
                    exit 1
                fi
                ;;
            *)
                log_error "Port $BACKEND_PORT conflict not resolved. Aborting."
                exit 1
                ;;
        esac
    fi
fi

echo ""
echo -e "${COLOR_GREEN}${COLOR_BOLD}============================================================${COLOR_RESET}"
echo -e "${COLOR_GREEN}${COLOR_BOLD}  BIM Guard Production Server Starting${COLOR_RESET}"
echo -e "${COLOR_GREEN}${COLOR_BOLD}============================================================${COLOR_RESET}"
echo -e "  ${COLOR_CYAN}➜${COLOR_RESET}  ${COLOR_BOLD}Production App (SPA):${COLOR_RESET} http://localhost:${BACKEND_PORT}/"
echo -e "  ${COLOR_CYAN}➜${COLOR_RESET}  ${COLOR_BOLD}API Docs:${COLOR_RESET}             http://localhost:${BACKEND_PORT}/api/docs"
echo -e "  ${COLOR_CYAN}➜${COLOR_RESET}  ${COLOR_BOLD}Host / Bind:${COLOR_RESET}          ${BACKEND_HOST}:${BACKEND_PORT}"
echo -e "  ${COLOR_CYAN}➜${COLOR_RESET}  ${COLOR_BOLD}Worker Processes:${COLOR_RESET}     ${WORKERS}"
echo -e "${COLOR_GREEN}${COLOR_BOLD}============================================================${COLOR_RESET}"
echo ""

exec uv run uvicorn main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" --workers "$WORKERS"
