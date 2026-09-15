"""ParsingEngineDriver registrations for the Docling backend.

Two kinds, one shared DoclingExtractor implementation
(app/modules/document_parsing/docling_extractor.py) parameterized by
`kind="docling"|"docling-local"` — both speak the same DoclingServiceClient
protocol, hosted vs. self-hosted docling-serve.
"""

from __future__ import annotations

from app.modules.document_parsing.engines.base import (
    EngineConnectionResult,
    ParsingEngine,
    ParsingEngineDriver,
    ParsingEngineRegistry,
)


class _DoclingDriverBase(ParsingEngineDriver):
    family = "docling"
    supports_strategy = False

    def build(self, *, api_key: str, api_url: str, strategy: str, name: str) -> ParsingEngine:
        from app.modules.document_parsing.docling_extractor import DoclingExtractor

        return DoclingExtractor(
            api_key=api_key or None,
            api_url=api_url or None,
            kind=self.kind,
            name=name,
        )

    def test_connection(self, *, api_key: str, api_url: str) -> EngineConnectionResult:
        from docling.service_client import DoclingServiceClient

        from app.modules.config import DOCLING_LOCAL_URL

        target_url = api_url
        if self.kind == "docling-local" and DOCLING_LOCAL_URL and (not target_url or "localhost" in target_url or "127.0.0.1" in target_url):
            target_url = DOCLING_LOCAL_URL

        try:
            with DoclingServiceClient(url=target_url, api_key=api_key or "") as client:
                health = client.health()
            return EngineConnectionResult(ok=True, detail=str(health))
        except Exception as exc:
            return EngineConnectionResult(ok=False, detail=str(exc))


class DoclingHostedDriver(_DoclingDriverBase):
    kind = "docling"
    display_name = "Docling (hosted Docling Serve instance)"
    description = (
        "Hosted Docling Serve account, e.g. IBM's managed offering "
        "(https://developer.dcls.saas.ibm.com) — sign up there and copy the "
        "instance URL and API key it gives you into the fields below."
    )
    requires_api_key = True
    url_placeholder = "https://api.aws-c1.dcls.saas.ibm.com/<instance-id>"
    docs_url = "https://developer.dcls.saas.ibm.com"


class DoclingLocalDriver(_DoclingDriverBase):
    kind = "docling-local"
    display_name = "Docling Local (self-hosted docling-serve container)"
    description = (
        "Self-hosted docling-serve Docker container — no API key by default. "
        "Run `docker compose up -d docling-serve` (already part of this "
        "project's docker-compose.yml) and point the URL below at it, e.g. "
        "http://localhost:5001."
    )
    requires_api_key = False
    url_placeholder = "http://localhost:5001"
    docs_url = "https://github.com/docling-project/docling-serve"


ParsingEngineRegistry.register(DoclingHostedDriver())
ParsingEngineRegistry.register(DoclingLocalDriver())
