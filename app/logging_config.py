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

Every record carries the current request id (``rid=``), set per HTTP request by
the request-logging middleware, so one request's lines can be followed across
modules and threads. ``BIM_GUARD_LOG_FORMAT=json`` switches the output to one
JSON object per line for log shippers.
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
import sys
from pathlib import Path

from app.environment import load_env_file

load_env_file()

__all__ = [
    "TRACE",
    "configure_logging",
    "current_level_name",
    "get_logger",
    "get_request_id",
    "reset_request_id",
    "set_request_id",
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

DEFAULT_VERBOSITY = 2

_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
_PLAIN_FORMAT = "%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)s | rid=%(request_id)s | %(message)s"
_VERBOSE_FORMAT = (
    "%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)s | rid=%(request_id)s | "
    "%(module)s:%(funcName)s:%(lineno)d | %(message)s"
)

_configured = False

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("bimguard_request_id", default="-")


def set_request_id(value: str) -> contextvars.Token:
    """Bind *value* as the request id for log records in this context."""
    return _request_id.set(value)


def reset_request_id(token: contextvars.Token) -> None:
    _request_id.reset(token)


def get_request_id() -> str:
    return _request_id.get()


class _RequestIdFilter(logging.Filter):
    """Stamp every record with the current request id."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()
        return True


class _HealthAccessFilter(logging.Filter):
    """Drop successful health-probe lines from the uvicorn access log."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return not ("/api/health" in message and message.rstrip().endswith(" 200"))


class _JsonFormatter(logging.Formatter):
    """One JSON object per line: easy to ship to Loki/ELK/CloudWatch."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S") + f".{int(record.msecs):03d}",
            "level": record.levelname,
            "logger": record.name,
            "rid": getattr(record, "request_id", "-"),
            "msg": record.getMessage(),
            "src": f"{record.module}:{record.funcName}:{record.lineno}",
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


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
    if os.environ.get("BIM_GUARD_LOG_FORMAT", "").strip().lower() == "json":
        return _JsonFormatter(datefmt=_TIMESTAMP_FORMAT)
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
    stream_handler.addFilter(_RequestIdFilter())
    root.addHandler(stream_handler)

    log_file = os.environ.get("BIM_GUARD_LOG_FILE", "").strip()
    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.addFilter(_RequestIdFilter())
        root.addHandler(file_handler)

    root.setLevel(effective)

    # Keep third-party chatter one degree quieter than the app itself.
    noisy_floor = max(effective, logging.INFO)
    for name in (
        "httpx",
        "httpcore",
        "hpack",
        "hpack.hpack",
        "h2",
        "urllib3",
        #"litellm",
        #"LiteLLM",
        "watchfiles",
    ):
        logging.getLogger(name).setLevel(noisy_floor)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
        uvicorn_logger.setLevel(max(effective, logging.INFO))
    # Docker/Kubernetes probes hit /api/health every few seconds; keep them out
    # of the access log unless the level is DEBUG or lower.
    access = logging.getLogger("uvicorn.access")
    access.filters[:] = [f for f in access.filters if not isinstance(f, _HealthAccessFilter)]
    if effective > logging.DEBUG:
        access.addFilter(_HealthAccessFilter())

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
