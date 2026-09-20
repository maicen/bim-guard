"""Append-only record of every LLM API call, for R&D purposes.

Model comparison, prompt/output inspection, cost and latency analysis.
Written exclusively by `LLMCallLoggingCallback`, which is registered on
`litellm.callbacks` at bootstrap and fires for every completion made through
litellm -- directly, via LlamaIndex's `LiteLLM` binding, or via LangChain's
`ChatLiteLLM` -- so every call site is covered without being touched
individually. `record` never raises: a logging failure must not block the
LLM call it's describing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.logging_config import get_logger
from app.services.db_adapters import DatabaseAdapter

logger = get_logger(__name__)


class LLMCallLogService:
    """Domain service for writing and reading the llm_calls table."""

    def __init__(self, llm_call_log_repo: DatabaseAdapter):
        self._repo = llm_call_log_repo

    def record(
        self,
        *,
        context: str,
        model: str,
        input: list[dict[str, Any]],
        provider: str | None = None,
        output: str | None = None,
        status: str = "success",
        error: str | None = None,
        organization_id: int | None = None,
        project_id: int | None = None,
        run_key: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
        cost: float | None = None,
        latency_ms: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Append one LLM call record. Never raises -- logs and swallows on failure."""
        try:
            self._repo.insert(
                {
                    "occurred_at": datetime.now(timezone.utc).isoformat(),
                    "organization_id": organization_id,
                    "project_id": project_id,
                    "run_key": run_key,
                    "context": context,
                    "provider": provider,
                    "model": model,
                    "input": input,
                    "output": output,
                    "status": status,
                    "error": error,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "cost": cost,
                    "latency_ms": latency_ms,
                    "metadata": metadata or {},
                }
            )
        except Exception:
            logger.warning(
                "Failed to write LLM call log entry (context=%s model=%s)",
                context,
                model,
                exc_info=True,
            )

    def list_entries(
        self,
        *,
        organization_id: int | None = None,
        project_id: int | None = None,
        context: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return the most recent entries, optionally filtered."""
        rows = list(self._repo.rows)
        if organization_id is not None:
            rows = [r for r in rows if r.get("organization_id") == organization_id]
        if project_id is not None:
            rows = [r for r in rows if r.get("project_id") == project_id]
        if context is not None:
            rows = [r for r in rows if r.get("context") == context]
        rows.sort(key=lambda r: r.get("occurred_at") or "", reverse=True)
        return rows[:limit]
