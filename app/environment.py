"""Deterministic project environment loading."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def load_env_file(env_path: str | Path = ".env") -> Path | None:
    """Load a project environment file without overriding process variables."""
    candidate = Path(env_path).expanduser()
    if candidate.is_absolute():
        candidates = [candidate]
    else:
        repo_root = Path(__file__).resolve().parents[1]
        candidates = [repo_root / candidate, Path.cwd() / candidate]

    seen: set[Path] = set()
    for path in candidates:
        normalized = path.resolve(strict=False)
        if normalized in seen:
            continue
        seen.add(normalized)
        if normalized.is_file():
            load_dotenv(dotenv_path=normalized, override=False)
            return normalized
    return None