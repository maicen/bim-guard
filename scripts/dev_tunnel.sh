#!/usr/bin/env bash
# =============================================================================
# BIM Guard — Dev Tunnel Launcher
# Exposes the local Vite dev server (localhost:5173) to the internet via
# Cloudflare Tunnel for cross-device development access.
#
# Two modes:
#   Named tunnel  (recommended) — uses the TUNNEL_TOKEN in your .env and a
#                                  public hostname you configure in the Zero
#                                  Trust dashboard (e.g. dev.bim-guard.xyz).
#   Quick tunnel  (no config)   — generates a temporary *.trycloudflare.com
#                                  URL, no account or token required.
#
# Usage:
#   ./scripts/dev_tunnel.sh                 # named tunnel (reads TUNNEL_TOKEN)
#   ./scripts/dev_tunnel.sh --quick         # anonymous quick tunnel
#   ./scripts/dev_tunnel.sh --port 8000     # tunnel straight to the backend
#
# Zero Trust dashboard (add the public hostname before starting named tunnel):
#   https://one.dash.cloudflare.com → Networks → Tunnels → bim-guard → Edit
#   Add public hostname:
#     Subdomain : dev
#     Domain    : bim-guard.xyz
#     Type      : HTTP
#     URL       : localhost:5173
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── Defaults ──────────────────────────────────────────────────────────────────
QUICK_MODE=false
LOCAL_PORT="${PORT:-5173}"

# ── Parse args ────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --quick|-q)
            QUICK_MODE=true
            shift
            ;;
        --port|-p)
            LOCAL_PORT="$2"
            shift 2
            ;;
        --help|-h)
            sed -n '3,25p' "$0" | sed 's/^# //'
            exit 0
            ;;
        *)
            echo "Unknown option: $1  (use --help)" >&2
            exit 1
            ;;
    esac
done

# ── Locate cloudflared ────────────────────────────────────────────────────────
if ! command -v cloudflared &>/dev/null; then
    echo "❌  cloudflared not found. Install with: brew install cloudflared" >&2
    exit 1
fi

# ── Load .env for TUNNEL_TOKEN ────────────────────────────────────────────────
ENV_FILE="$PROJECT_ROOT/.env"
if [[ -f "$ENV_FILE" ]]; then
    # Export only the vars we need — don't pollute the whole shell.
    TUNNEL_TOKEN="${TUNNEL_TOKEN:-$(grep -E '^TUNNEL_TOKEN=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'" || true)}"
fi

# ── Launch ────────────────────────────────────────────────────────────────────
if [[ "$QUICK_MODE" == "true" ]]; then
    echo ""
    echo "🌐  Starting Cloudflare Quick Tunnel → localhost:${LOCAL_PORT}"
    echo "    A temporary *.trycloudflare.com URL will appear below."
    echo "    The URL changes every restart — share it with your colleagues."
    echo ""
    echo "    ⚠  CORS: The backend will block API calls from this hostname"
    echo "       unless BIM_GUARD_ALLOWED_ORIGINS=* is set in your .env."
    echo "       For quick testing, set it temporarily:"
    echo "         BIM_GUARD_ALLOWED_ORIGINS=* uv run uvicorn main:app --reload"
    echo ""
    exec cloudflared tunnel --url "http://localhost:${LOCAL_PORT}"
else
    # Named tunnel via TUNNEL_TOKEN
    if [[ -z "${TUNNEL_TOKEN:-}" ]]; then
        echo ""
        echo "❌  TUNNEL_TOKEN is not set."
        echo ""
        echo "    For a named tunnel, set TUNNEL_TOKEN in your .env."
        echo "    Get the token from: Cloudflare Zero Trust → Networks → Tunnels"
        echo ""
        echo "    Or use --quick for a zero-config anonymous tunnel:"
        echo "      ./scripts/dev_tunnel.sh --quick"
        echo ""
        exit 1
    fi

    echo ""
    echo "🌐  Starting named Cloudflare Tunnel (token) → localhost:${LOCAL_PORT}"
    echo ""
    echo "    Prerequisite: you must have added a public hostname in the"
    echo "    Zero Trust dashboard pointing at localhost:${LOCAL_PORT}."
    echo "    See the script header comment for instructions."
    echo ""
    echo "    If dev.bim-guard.xyz is configured, it will be live shortly."
    echo ""
    exec cloudflared tunnel --no-autoupdate run --token "${TUNNEL_TOKEN}" \
        --url "http://localhost:${LOCAL_PORT}"
fi
