"""Tests for LLMCallLoggingCallback and LLM call database persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.llm_call_context import llm_call_context
from app.services.llm_logging_callback import LLMCallLoggingCallback


def test_callback_sync_success_logs_to_service():
    service = MagicMock()
    callback = LLMCallLoggingCallback(service)

    start = datetime(2026, 9, 26, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 9, 26, 0, 0, 1, tzinfo=timezone.utc)

    mock_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Extracted rules JSON"))],
        usage=SimpleNamespace(prompt_tokens=100, completion_tokens=50, total_tokens=150),
    )

    with llm_call_context(context="rule_extraction", organization_id=1, project_id=2):
        callback.log_success_event(
            kwargs={"model": "gpt-4o", "messages": [{"role": "user", "content": "Extract rules"}]},
            response_obj=mock_resp,
            start_time=start,
            end_time=end,
        )

    service.record.assert_called_once()
    kwargs = service.record.call_args.kwargs
    assert kwargs["context"] == "rule_extraction"
    assert kwargs["organization_id"] == 1
    assert kwargs["project_id"] == 2
    assert kwargs["model"] == "gpt-4o"
    assert kwargs["status"] == "success"
    assert kwargs["output"] == "Extracted rules JSON"
    assert kwargs["input_tokens"] == 100
    assert kwargs["output_tokens"] == 50
    assert kwargs["total_tokens"] == 150
    assert kwargs["latency_ms"] == 1000


def test_callback_sync_failure_logs_to_service():
    service = MagicMock()
    callback = LLMCallLoggingCallback(service)

    start = datetime(2026, 9, 26, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 9, 26, 0, 0, 2, tzinfo=timezone.utc)

    with llm_call_context(context="digital_inspector"):
        callback.log_failure_event(
            kwargs={
                "model": "anthropic/claude-3-5-sonnet",
                "messages": [{"role": "user", "content": "Inspect"}] ,
                "exception": ValueError("Provider rate limit reached"),
            },
            response_obj=None,
            start_time=start,
            end_time=end,
        )

    service.record.assert_called_once()
    kwargs = service.record.call_args.kwargs
    assert kwargs["context"] == "digital_inspector"
    assert kwargs["status"] == "error"
    assert "Provider rate limit reached" in kwargs["error"]
    assert kwargs["latency_ms"] == 2000
