"""Runtime logging configuration with verbosity degrees and timestamps.

Verbosity degrees (``BIM_GUARD_VERBOSITY``)::

    0 -> ERROR     only failures
    1 -> WARNING   failures + warnings (default)
    2 -> INFO      pipeline progress
    3 -> DEBUG     detailed diagnostics
    4 -> TRACE     very chatty, per-item diagnostics

An explicit level name in ``BIM_GUARD_LOG_LEVEL`` (or ``LOG_LEVEL``) overrides
the numeric verbosity. Levels can also be changed while the app is running via
:func:`set_log_level` / :func:`set_verbosity`.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

__all__ = [
    "TRACE",
    "configure_logging",
    "current_level_name",
    "get_logger",
    "set_log_level",
    "set_verbosity",
    "trace",
]

TRACE = 5
logging.addLevelName(TRACE, "TRACE")

ROOT_LOGGER_NAME = "bimguard"

VERBOSITY_LEVELS = {
    0: logging.ERROR,
    1: logging.WARNING,
    2: logging.INFO,
    3: logging.DEBUG,
    4: TRACE,
}

DEFAULT_VERBOSITY = 1

_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
_PLAIN_FORMAT = "%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)s | %(message)s"
_VERBOSE_FORMAT = (
    "%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)s | "
    "%(module)s:%(funcName)s:%(lineno)d | %(message)s"
)

_configured = False


def _resolve_level(level: str | int | None = None) -> int:
    """Translate a level name, verbosity digit, or env configuration to a level int."""
    if level is None:
        level = os.environ.get("BIM_GUARD_LOG_LEVEL") or os.environ.get("LOG_LEVEL") or ""
        if not str(level).strip():
            level = os.environ.get("BIM_GUARD_VERBOSITY", str(DEFAULT_VERBOSITY))

    if isinstance(level, int):
        return VERBOSITY_LEVELS.get(level, level) if 0 <= level <= 4 else level

    text = str(level).strip()
    if text.isdigit():
        return VERBOSITY_LEVELS.get(int(text), VERBOSITY_LEVELS[DEFAULT_VERBOSITY])

    resolved = logging.getLevelName(text.upper())
    if isinstance(resolved, int):
        return resolved
    return VERBOSITY_LEVELS[DEFAULT_VERBOSITY]


def _build_formatter(level: int) -> logging.Formatter:
    """Use call-site details in the format once DEBUG or lower is active."""
    fmt = _VERBOSE_FORMAT if level <= logging.DEBUG else _PLAIN_FORMAT
    return logging.Formatter(fmt=fmt, datefmt=_TIMESTAMP_FORMAT)


def configure_logging(level: str | int | None = None, *, force: bool = False) -> int:
    """Install timestamped stream (and optional file) handlers on the root logger.

    Returns the effective numeric log level. Repeat calls are no-ops unless
    ``force`` is set or an explicit ``level`` is supplied.
    """
    global _configured

    effective = _resolve_level(level)
    root = logging.getLogger()

    if _configured and not force and level is None:
        return root.level

    if _configured or root.handlers:
        for handler in list(root.handlers):
            root.removeHandler(handler)
            handler.close()

    formatter = _build_formatter(effective)

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    log_file = os.environ.get("BIM_GUARD_LOG_FILE", "").strip()
    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    root.setLevel(effective)

    # Keep third-party chatter one degree quieter than the app itself.
    noisy_floor = max(effective, logging.INFO)
    for name in ("httpx", "httpcore", "urllib3", "litellm", "LiteLLM", "watchfiles"):
        logging.getLogger(name).setLevel(noisy_floor)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
        uvicorn_logger.setLevel(max(effective, logging.INFO))

    _configured = True
    return effective


def set_log_level(level: str | int) -> int:
    """Change the active log level while the application is running."""
    return configure_logging(level, force=True)


def set_verbosity(verbosity: int) -> int:
    """Change the active level using a verbosity degree (0-4)."""
    return set_log_level(VERBOSITY_LEVELS.get(verbosity, VERBOSITY_LEVELS[DEFAULT_VERBOSITY]))


def current_level_name() -> str:
    """Return the active root log level name."""
    return logging.getLevelName(logging.getLogger().level)


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a namespaced application logger, configuring logging on first use."""
    if not _configured:
        configure_logging()
    if not name or name == ROOT_LOGGER_NAME:
        return logging.getLogger(ROOT_LOGGER_NAME)
    if name.startswith(f"{ROOT_LOGGER_NAME}."):
        return logging.getLogger(name)
    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{name}")


def trace(logger: logging.Logger, msg: str, *args, **kwargs) -> None:
    """Log at the custom TRACE level (below DEBUG)."""
    if logger.isEnabledFor(TRACE):
        kwargs.setdefault("stacklevel", 2)
        logger.log(TRACE, msg, *args, **kwargs)
