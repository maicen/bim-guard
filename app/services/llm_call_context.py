"""Ambient tagging for the LLM call logger.

The LLM logging callback (`app.services.llm_logging_callback`) is registered
once, globally, on `litellm.callbacks` -- but the extraction/agent code that
triggers a call goes through LlamaIndex's `LLMTextCompletionProgram` or
LangGraph's `create_react_agent`, neither of which exposes a per-call
metadata hook. A contextvar lets a call site say "everything invoked while
this block runs belongs to rule_extraction for organization 42" without
threading a new parameter through either library's API.

Contextvars propagate through `await` within one task, which is exactly the
span a `with llm_call_context(...):` block needs to cover.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

_current: ContextVar[dict[str, Any]] = ContextVar("llm_call_context", default={})


@contextmanager
def llm_call_context(
    *,
    context: str = "unknown",
    organization_id: int | None = None,
    project_id: int | None = None,
    run_key: str | None = None,
    metadata: dict[str, Any] | None = None,
    source: str | None = None,
    **extra: Any,
) -> Iterator[None]:
    """Tag every LLM call made within this block for the logging callback."""
    meta = dict(metadata or {})
    if extra:
        meta.update(extra)
    tag_context = source or context
    token = _current.set(
        {
            "context": tag_context,
            "organization_id": organization_id,
            "project_id": project_id,
            "run_key": run_key,
            "metadata": meta,
        }
    )
    try:
        yield
    finally:
        _current.reset(token)


def current() -> dict[str, Any]:
    """Return the active tag, or an 'unknown' default when no block is active."""
    tag = _current.get()
    if not tag:
        return {"context": "unknown", "organization_id": None, "project_id": None, "run_key": None, "metadata": {}}
    return tag
