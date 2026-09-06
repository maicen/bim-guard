"""Regenerate editor/agent dev-server launch configs from one source of truth.

BIM-Guard runs two dev servers (FastAPI backend, Vite/Svelte frontend) via
``run_server.sh`` / ``run_server.bat``. Claude Code, VS Code, and Antigravity
each read their own launch-config format to start those same servers for
previews and debugging. This script is the single source of truth for the
command/port pairs and writes all three formats so they never drift.

Usage:
    uv run python scripts/generate_launch_configs.py
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

BACKEND = {
    "name": "backend",
    # "python main.py" rather than the uvicorn CLI: main.py reads the PORT
    # env var (defaulting to 8000) via os.environ, so a launcher that assigns
    # a different free port (autoPort) can pass it along without needing
    # shell-level env-var expansion in runtimeArgs, which this array doesn't get.
    "runtimeExecutable": "uv",
    "runtimeArgs": ["run", "python", "main.py"],
    "port": 8000,
    "autoPort": True,
}

FRONTEND = {
    "name": "frontend",
    "runtimeExecutable": "npm",
    "runtimeArgs": ["--prefix", "frontend", "run", "dev"],
    "port": 5173,
}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(REPO_ROOT)}")


def generate_agent_launch_json() -> dict:
    return {"version": "0.0.1", "configurations": [BACKEND, FRONTEND]}


def generate_vscode_launch_json() -> dict:
    return {
        "version": "0.2.0",
        "configurations": [
            {
                "name": "Backend: FastAPI (uvicorn)",
                "type": "debugpy",
                "request": "launch",
                "module": "uvicorn",
                "args": ["main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
                "cwd": "${workspaceFolder}",
                "console": "integratedTerminal",
            },
            {
                "name": "Frontend: Vite Dev Server",
                "type": "node-terminal",
                "request": "launch",
                "command": "npm run dev",
                "cwd": "${workspaceFolder}/frontend",
            },
        ],
        "compounds": [
            {
                "name": "Full Stack (Backend + Frontend)",
                "configurations": ["Backend: FastAPI (uvicorn)", "Frontend: Vite Dev Server"],
            }
        ],
    }


def main() -> None:
    agent_config = generate_agent_launch_json()
    _write_json(REPO_ROOT / ".claude" / "launch.json", agent_config)
    _write_json(REPO_ROOT / ".antigravity" / "launch.json", agent_config)
    _write_json(REPO_ROOT / ".vscode" / "launch.json", generate_vscode_launch_json())


if __name__ == "__main__":
    main()
