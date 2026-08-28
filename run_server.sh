#!/usr/bin/env bash
# ============================================================
# BIM Guard Development Server Launcher (Linux / macOS / WSL)
# Interactive, dynamic, and robust launcher for FastAPI + Svelte
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
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
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
    echo -e "${COLOR_BOLD}Usage:${COLOR_RESET} ./run_server.sh [options]"
    echo ""
    echo -e "${COLOR_BOLD}Options:${COLOR_RESET}"
    echo "  -p, --port <port>             Backend API port (default: 8000, or \$PORT)"
    echo "  -f, --frontend-port <port>    Frontend Vite port (default: 5173, or \$FRONTEND_PORT)"
    echo "  -H, --host <host>             Backend bind host (default: 0.0.0.0, or \$HOST)"
    echo "  -s, --skip-sync               Skip backend/frontend dependency checks"
    echo "  --sync                        Force dependency synchronization/installation"
    echo "  -y, --yes                     Non-interactive mode; auto-accept default prompts"
    echo "  -h, --help                    Show this help message and exit"
    echo ""
    echo -e "${COLOR_BOLD}Environment Variables:${COLOR_RESET}"
    echo "  PORT                          Override backend port"
    echo "  FRONTEND_PORT                 Override frontend port"
    echo "  HOST                          Override backend bind host"
    echo "  NO_COLOR                      Disable colored terminal output"
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--port)
            BACKEND_PORT="$2"
            shift 2
            ;;
        -f|--frontend-port)
            FRONTEND_PORT="$2"
            shift 2
            ;;
        -H|--host)
            BACKEND_HOST="$2"
            shift 2
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
            echo "Use './run_server.sh --help' for usage instructions."
            exit 1
            ;;
    esac
done

log_header "BIM Guard Development Server (FastAPI + Svelte 5)"

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

# Check Node.js and npm
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
    echo -e "${COLOR_BOLD}BIM-Guard requires Node.js (>= 18) and npm for the Svelte 5 frontend.${COLOR_RESET}"
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
            log_error "Cannot run frontend without Node.js and npm. Please install Node.js and try again."
            exit 1
        fi
    else
        log_error "Cannot run frontend without Node.js and npm. Please install Node.js and try again."
        exit 1
    fi
fi

NODE_VER="$(node -v 2>/dev/null || echo "unknown")"
NPM_VER="$(npm -v 2>/dev/null || echo "unknown")"
log_success "Node.js ${NODE_VER} & npm ${NPM_VER} verified."

# ------------------------------------------------------------
# 2. Dependency Management: Backend (uv sync) & Frontend (npm install)
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
# 3. Dynamic Port Collision Detection & Resolution
# ------------------------------------------------------------
log_step "3/4" "Checking port availability..."

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

handle_port_conflict() {
    local service_name="$1"
    local port_var_name="$2"
    local current_port="${!port_var_name}"
    
    local pid
    pid="$(get_pid_on_port "$current_port")"

    if [[ -n "$pid" ]]; then
        local pname="unknown"
        if command -v ps >/dev/null 2>&1; then
            pname="$(ps -p "$pid" -o comm= 2>/dev/null || echo "unknown")"
        fi

        log_warn "$service_name port $current_port is already in use by PID $pid ($pname)."

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
            echo "  [c] Change port for $service_name"
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
                    log_success "Port $current_port freed."
                    ;;
                [cC]*)
                    read -r -p "$(echo -e " ${COLOR_YELLOW}?${COLOR_RESET} Enter new port number for $service_name: ")" new_port
                    if [[ "$new_port" =~ ^[0-9]+$ ]] && [[ "$new_port" -ge 1024 && "$new_port" -le 65535 ]]; then
                        eval "$port_var_name=\"$new_port\""
                        log_info "Updated $service_name port to ${!port_var_name}"
                        handle_port_conflict "$service_name" "$port_var_name"
                    else
                        log_error "Invalid port: $new_port. Aborting."
                        exit 1
                    fi
                    ;;
                *)
                    log_error "Port $current_port conflict not resolved. Aborting."
                    exit 1
                    ;;
            esac
        fi
    fi
}

handle_port_conflict "FastAPI Backend" "BACKEND_PORT"
handle_port_conflict "Svelte Frontend" "FRONTEND_PORT"

log_success "Port $BACKEND_PORT reserved for Backend."
log_success "Port $FRONTEND_PORT reserved for Frontend."

# ------------------------------------------------------------
# 4. Process Launch & Graceful Lifecycle Management
# ------------------------------------------------------------
log_step "4/4" "Starting development servers..."

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
    trap - INT TERM EXIT HUP
    echo ""
    log_info "Shutting down development servers cleanly..."
    
    if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
        kill -TERM "$FRONTEND_PID" 2>/dev/null || true
    fi
    if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        kill -TERM "$BACKEND_PID" 2>/dev/null || true
    fi
    
    sleep 0.5 2>/dev/null || true

    # Force kill any lingering child processes if still active
    if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
        kill -9 "$FRONTEND_PID" 2>/dev/null || true
    fi
    if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        kill -9 "$BACKEND_PID" 2>/dev/null || true
    fi

    wait 2>/dev/null || true
    log_success "All servers stopped."
    exit 0
}

trap cleanup INT TERM EXIT HUP

# 1. Launch FastAPI Backend
log_info "Starting FastAPI Backend on http://${BACKEND_HOST}:${BACKEND_PORT} ..."
uv run uvicorn main:app --reload --host "$BACKEND_HOST" --port "$BACKEND_PORT" &
BACKEND_PID=$!

# 2. Launch Svelte Frontend Dev Server
log_info "Starting Svelte 5 Frontend on http://localhost:${FRONTEND_PORT} ..."
(cd frontend && npm run dev -- --port "$FRONTEND_PORT") &
FRONTEND_PID=$!

echo ""
echo -e "${COLOR_GREEN}${COLOR_BOLD}============================================================${COLOR_RESET}"
echo -e "${COLOR_GREEN}${COLOR_BOLD}  BIM Guard Development Servers Running!${COLOR_RESET}"
echo -e "${COLOR_GREEN}${COLOR_BOLD}============================================================${COLOR_RESET}"
echo -e "  ${COLOR_CYAN}➜${COLOR_RESET}  ${COLOR_BOLD}Frontend (SPA):${COLOR_RESET}    http://localhost:${FRONTEND_PORT}"
echo -e "  ${COLOR_CYAN}➜${COLOR_RESET}  ${COLOR_BOLD}Backend API:${COLOR_RESET}       http://127.0.0.1:${BACKEND_PORT}"
echo -e "  ${COLOR_CYAN}➜${COLOR_RESET}  ${COLOR_BOLD}Interactive Docs:${COLOR_RESET}  http://127.0.0.1:${BACKEND_PORT}/api/docs"
echo -e "${COLOR_GREEN}${COLOR_BOLD}============================================================${COLOR_RESET}"
echo -e "${COLOR_DIM}Press Ctrl+C to stop all servers.${COLOR_RESET}"
echo ""

# Wait for background processes
wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || wait
