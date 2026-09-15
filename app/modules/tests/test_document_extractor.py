"""Unit tests for document_parsing.document_extractor's fail-loud behavior.

No dependency-light fallback exists anymore: extract_document_text() must
raise NoParsingEngineConfiguredError rather than silently degrading when no
engine is configured, or when the configured engine fails/returns nothing.
"""

import pytest
from document_parsing.document_extractor import (
    NoParsingEngineConfiguredError,
    extract_document_text,
)


def test_raises_when_no_instance_configured():
    with pytest.raises(NoParsingEngineConfiguredError) as exc_info:
        extract_document_text("code.pdf", b"content", instance=None)
    assert exc_info.value.had_instance is False


def test_raises_when_configured_instance_fails():
    from app.modules.document_parsing.engines import ParsingEngineRegistry
    from app.modules.document_parsing.engines.base import (
        EngineConnectionResult,
        ParsingEngineDriver,
    )

    class _FailingEngine:
        def extract_bytes(self, content, filename, return_doclang=False):
            raise RuntimeError("boom")

    class _FailingDriver(ParsingEngineDriver):
        kind = "test-failing"
        family = "test-failing"
        display_name = "Test Failing"

        def build(self, *, api_key, api_url, strategy, name):
            return _FailingEngine()

        def test_connection(self, *, api_key, api_url):
            return EngineConnectionResult(ok=False, detail="n/a")

    ParsingEngineRegistry.register(_FailingDriver())

    with pytest.raises(NoParsingEngineConfiguredError) as exc_info:
        extract_document_text(
            "code.pdf", b"content", instance={"kind": "test-failing", "name": "flaky"}
        )
    assert exc_info.value.had_instance is True
    assert exc_info.value.instance_name == "flaky"


def test_raises_when_configured_instance_returns_empty_text():
    from app.modules.document_parsing.engines import ParsingEngineRegistry
    from app.modules.document_parsing.engines.base import (
        EngineConnectionResult,
        ParsingEngineDriver,
    )

    class _EmptyEngine:
        def extract_bytes(self, content, filename, return_doclang=False):
            return "", [], []

    class _EmptyDriver(ParsingEngineDriver):
        kind = "test-empty"
        family = "test-empty"
        display_name = "Test Empty"

        def build(self, *, api_key, api_url, strategy, name):
            return _EmptyEngine()

        def test_connection(self, *, api_key, api_url):
            return EngineConnectionResult(ok=False, detail="n/a")

    ParsingEngineRegistry.register(_EmptyDriver())

    with pytest.raises(NoParsingEngineConfiguredError) as exc_info:
        extract_document_text("code.pdf", b"content", instance={"kind": "test-empty", "name": "quiet"})
    assert exc_info.value.had_instance is True


def test_invalid_parser_raises_value_error():
    with pytest.raises(ValueError):
        extract_document_text("code.pdf", b"content", parser="not-a-real-parser")
