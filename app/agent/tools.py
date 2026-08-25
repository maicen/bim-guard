"""Workspace-local tools exposed to the BIM Guard agent."""

import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

WORKSPACE_ROOT = Path.cwd().resolve()
MAX_OUTPUT_CHARS = 20_000


def _schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


TOOL_SCHEMAS = [
    _schema(
        "file_read",
        "Read a UTF-8 text file inside the repository with line pagination.",
        {
            "path": {"type": "string"},
            "offset": {"type": "integer", "minimum": 1},
            "limit": {"type": "integer", "minimum": 1, "maximum": 2000},
        },
        ["path"],
    ),
    _schema(
        "file_write",
        "Create or replace a UTF-8 text file inside the repository.",
        {"path": {"type": "string"}, "content": {"type": "string"}},
        ["path", "content"],
    ),
    _schema(
        "file_edit",
        "Replace one exact, unique string in a repository text file.",
        {
            "path": {"type": "string"},
            "old_text": {"type": "string"},
            "new_text": {"type": "string"},
        },
        ["path", "old_text", "new_text"],
    ),
    _schema(
        "glob",
        "Find repository files using a glob pattern.",
        {"pattern": {"type": "string"}},
        ["pattern"],
    ),
    _schema(
        "grep",
        "Search repository text files using a regular expression.",
        {"pattern": {"type": "string"}, "glob": {"type": "string"}},
        ["pattern"],
    ),
    _schema(
        "list_dir",
        "List entries in a repository directory.",
        {"path": {"type": "string"}},
        [],
    ),
    _schema(
        "shell",
        "Run a non-interactive PowerShell command in the repository with a timeout.",
        {
            "command": {"type": "string"},
            "timeout": {"type": "integer", "minimum": 1, "maximum": 120},
        },
        ["command"],
    ),
    _schema(
        "datetime",
        "Return the current UTC date and time.",
        {},
        [],
    ),
]


def _path(value: str = ".") -> Path:
    candidate = (WORKSPACE_ROOT / value).resolve()
    if candidate != WORKSPACE_ROOT and WORKSPACE_ROOT not in candidate.parents:
        raise ValueError("Path must stay inside the repository.")
    return candidate


def _trim(value: str) -> str:
    if len(value) <= MAX_OUTPUT_CHARS:
        return value
    return value[:MAX_OUTPUT_CHARS] + "\n[output truncated]"


def execute_tool(name: str, arguments: dict) -> str:
    """Execute a named local tool and return a JSON result string."""
    try:
        result = _execute_tool(name, arguments)
    except Exception as exc:
        result = {"error": f"{type(exc).__name__}: {exc}"}
    return _trim(json.dumps(result, ensure_ascii=True, default=str))


def _execute_tool(name: str, arguments: dict):
    if name == "file_read":
        path = _path(arguments["path"])
        lines = path.read_text(encoding="utf-8").splitlines()
        start = max(arguments.get("offset", 1) - 1, 0)
        end = min(start + arguments.get("limit", 2000), len(lines))
        return {"content": "\n".join(lines[start:end]), "lines": [start + 1, end]}
    if name == "file_write":
        path = _path(arguments["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(arguments["content"], encoding="utf-8")
        return {"path": str(path.relative_to(WORKSPACE_ROOT)), "written": True}
    if name == "file_edit":
        path = _path(arguments["path"])
        content = path.read_text(encoding="utf-8")
        count = content.count(arguments["old_text"])
        if count != 1:
            raise ValueError(f"old_text must occur exactly once; found {count}")
        path.write_text(
            content.replace(arguments["old_text"], arguments["new_text"]),
            encoding="utf-8",
        )
        return {"path": str(path.relative_to(WORKSPACE_ROOT)), "edited": True}
    if name == "glob":
        matches = [
            str(path.relative_to(WORKSPACE_ROOT))
            for path in WORKSPACE_ROOT.glob(arguments["pattern"])
            if path.is_file()
        ]
        return {"matches": matches[:1000], "truncated": len(matches) > 1000}
    if name == "grep":
        pattern = re.compile(arguments["pattern"], re.IGNORECASE)
        matches = []
        for path in WORKSPACE_ROOT.glob(arguments.get("glob", "**/*")):
            if not path.is_file() or ".git" in path.parts:
                continue
            try:
                for line_number, line in enumerate(
                    path.read_text(encoding="utf-8").splitlines(), start=1
                ):
                    if pattern.search(line):
                        matches.append(
                            f"{path.relative_to(WORKSPACE_ROOT)}:{line_number}:{line[:500]}"
                        )
                        if len(matches) == 500:
                            return {"matches": matches, "truncated": True}
            except (OSError, UnicodeDecodeError):
                continue
        return {"matches": matches, "truncated": False}
    if name == "list_dir":
        path = _path(arguments.get("path", "."))
        return {
            "entries": [
                f"{item.name}/" if item.is_dir() else item.name
                for item in sorted(path.iterdir(), key=lambda item: item.name.casefold())
            ]
        }
    if name == "shell":
        completed = subprocess.run(
            ["pwsh", "-NoProfile", "-Command", arguments["command"]],
            cwd=WORKSPACE_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=arguments.get("timeout", 30),
            check=False,
        )
        return {
            "exit_code": completed.returncode,
            "stdout": _trim(completed.stdout),
            "stderr": _trim(completed.stderr),
        }
    if name == "datetime":
        return {"utc": datetime.now(UTC).isoformat()}
    raise ValueError(f"Unknown tool: {name}")