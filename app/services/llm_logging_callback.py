"""litellm CustomLogger that persists every LLM call via LLMCallLogService.

litellm.acompletion is the transport underneath all four LLM call sites in
this app (the direct `litellm.acompletion` calls, LlamaIndex's `LiteLLM`
binding, and LangChain's `ChatLiteLLM`), so registering one logger on
`litellm.callbacks` (done once, in app.bootstrap) captures every completion
app-wide without touching any of those call sites individually. Per-call
tagging (which feature triggered the call, which org/project it belongs to)
comes from `app.services.llm_call_context`, read here rather than from
litellm's own kwargs, since neither LlamaIndex nor LangChain exposes a way
to thread custom metadata through to litellm's call.
"""

from __future__ import annotations

import asyncio
from typing import Any

from litellm.integrations.custom_logger import CustomLogger

from app.logging_config import get_logger
from app.services import llm_call_context
from app.services.llm_call_log_service import LLMCallLogService

logger = get_logger(__name__)


class LLMCallLoggingCallback(CustomLogger):
    """Writes one `llm_calls` row per litellm completion, success or failure."""

    def __init__(self, llm_call_log_service: LLMCallLogService) -> None:
        self._service = llm_call_log_service

    def log_success_event(self, kwargs: dict, response_obj: Any, start_time, end_time) -> None:
        self._log(kwargs, response_obj, start_time, end_time, status="success", error=None)

    def log_failure_event(self, kwargs: dict, response_obj: Any, start_time, end_time) -> None:
        exception = kwargs.get("exception")
        self._log(
            kwargs,
            response_obj,
            start_time,
            end_time,
            status="error",
            error=str(exception) if exception is not None else "unknown error",
        )

    # The async hooks run on the caller's event loop, and ``record`` is a
    # synchronous DB insert. ``asyncio.to_thread`` copies the current context,
    # so ``llm_call_context.current()`` still sees the caller's tag.
    async def async_log_success_event(self, kwargs: dict, response_obj: Any, start_time, end_time) -> None:
        await asyncio.to_thread(
            self._log, kwargs, response_obj, start_time, end_time, status="success", error=None
        )

    async def async_log_failure_event(self, kwargs: dict, response_obj: Any, start_time, end_time) -> None:
        exception = kwargs.get("exception")
        await asyncio.to_thread(
            self._log,
            kwargs,
            response_obj,
            start_time,
            end_time,
            status="error",
            error=str(exception) if exception is not None else "unknown error",
        )

    def _log(self, kwargs: dict, response_obj: Any, start_time, end_time, *, status: str, error: str | None) -> None:
        try:
            tag = llm_call_context.current()
            model = kwargs.get("model") or "unknown"
            provider = model.split("/", 1)[0] if "/" in model else None
            messages = kwargs.get("messages") or []

            output: str | None = None
            input_tokens = output_tokens = total_tokens = None
            if status == "success" and response_obj is not None:
                choices = getattr(response_obj, "choices", None) or []
                if choices:
                    output = getattr(choices[0].message, "content", None)
                usage = getattr(response_obj, "usage", None)
                if usage is not None:
                    input_tokens = getattr(usage, "prompt_tokens", None)
                    output_tokens = getattr(usage, "completion_tokens", None)
                    total_tokens = getattr(usage, "total_tokens", None)

            latency_ms = None
            if start_time is not None and end_time is not None:
                latency_ms = int((end_time - start_time).total_seconds() * 1000)

            self._service.record(
                context=tag["context"],
                organization_id=tag["organization_id"],
                project_id=tag["project_id"],
                run_key=tag["run_key"],
                provider=provider,
                model=model,
                input=messages,
                output=output,
                status=status,
                error=error,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost=kwargs.get("response_cost"),
                latency_ms=latency_ms,
                metadata=tag["metadata"],
            )
        except Exception:
            logger.warning("Failed to build LLM call log entry", exc_info=True)
