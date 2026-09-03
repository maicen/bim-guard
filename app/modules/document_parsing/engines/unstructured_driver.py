"""ParsingEngineDriver registrations for the Unstructured backend.

Two kinds, one shared UnstructuredExtractor implementation
(app/modules/document_parsing/unstructured_extractor.py) parameterized by
`kind="local"|"hosted"` — see that module for why the two need different
request shapes under the hood (classic sync partition vs. Workflow/Jobs).
"""

from __future__ import annotations

from app.modules.document_parsing.engines.base import (
    EngineConnectionResult,
    ParsingEngine,
    ParsingEngineDriver,
    ParsingEngineRegistry,
)


class _UnstructuredDriverBase(ParsingEngineDriver):
    family = "unstructured"
    supports_strategy = True

    def build(self, *, api_key: str, api_url: str, strategy: str, name: str) -> ParsingEngine:
        from app.modules.document_parsing.unstructured_extractor import UnstructuredExtractor

        return UnstructuredExtractor(
            api_key=api_key or None,
            api_url=api_url or None,
            strategy=strategy or None,
            kind=self.kind,
            name=name,
        )


class UnstructuredLocalDriver(_UnstructuredDriverBase):
    kind = "local"
    display_name = "Local (self-hosted Unstructured Docker container)"
    description = "Open-source unstructured-api container's synchronous partition endpoint."
    requires_api_key = False
    url_placeholder = "http://localhost:8001"

    def test_connection(self, *, api_key: str, api_url: str) -> EngineConnectionResult:
        import httpx

        try:
            # The open-source unstructured-api server exposes a plain
            # GET /healthcheck (no auth) — see the Docker installation docs.
            response = httpx.get(f"{api_url.rstrip('/')}/healthcheck", timeout=5.0)
            response.raise_for_status()
            return EngineConnectionResult(ok=True, detail=response.text.strip())
        except Exception as exc:
            return EngineConnectionResult(ok=False, detail=str(exc))


class UnstructuredHostedDriver(_UnstructuredDriverBase):
    kind = "hosted"
    display_name = "Hosted (Unstructured Platform API)"
    description = "Unstructured's Workflow/Jobs API — an async job per document."
    requires_api_key = True
    url_placeholder = "https://api.unstructuredapp.io"

    def test_connection(self, *, api_key: str, api_url: str) -> EngineConnectionResult:
        try:
            extractor = self.build(api_key=api_key, api_url=api_url, strategy="auto", name=self.kind)
            extractor._ensure_workflow()
            return EngineConnectionResult(ok=True, detail="Workflow API reachable.")
        except Exception as exc:
            return EngineConnectionResult(ok=False, detail=str(exc))


ParsingEngineRegistry.register(UnstructuredLocalDriver())
ParsingEngineRegistry.register(UnstructuredHostedDriver())
