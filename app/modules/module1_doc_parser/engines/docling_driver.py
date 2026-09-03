"""ParsingEngineDriver registrations for the Docling backend.

Two kinds, one shared DoclingExtractor implementation
(app/modules/module1_doc_parser/docling_extractor.py) parameterized by
`kind="docling"|"docling-local"` — both speak the same DoclingServiceClient
protocol, hosted vs. self-hosted docling-serve.
"""

from __future__ import annotations

from app.modules.module1_doc_parser.engines.base import (
    EngineConnectionResult,
    ParsingEngine,
    ParsingEngineDriver,
    ParsingEngineRegistry,
)


class _DoclingDriverBase(ParsingEngineDriver):
    family = "docling"
    supports_strategy = False

    def build(self, *, api_key: str, api_url: str, strategy: str, name: str) -> ParsingEngine:
        from app.modules.module1_doc_parser.docling_extractor import DoclingExtractor

        return DoclingExtractor(
            api_key=api_key or None,
            api_url=api_url or None,
            kind=self.kind,
            name=name,
        )

    def test_connection(self, *, api_key: str, api_url: str) -> EngineConnectionResult:
        from docling.service_client import DoclingServiceClient

        try:
            with DoclingServiceClient(url=api_url, api_key=api_key or "") as client:
                health = client.health()
            return EngineConnectionResult(ok=True, detail=str(health))
        except Exception as exc:
            return EngineConnectionResult(ok=False, detail=str(exc))


class DoclingHostedDriver(_DoclingDriverBase):
    kind = "docling"
    display_name = "Docling (hosted Docling Serve instance)"
    description = "Hosted Docling Serve account, e.g. IBM's managed offering."
    requires_api_key = True
    url_placeholder = "https://api.aws-c1.dcls.saas.ibm.com/<instance-id>"


class DoclingLocalDriver(_DoclingDriverBase):
    kind = "docling-local"
    display_name = "Docling Local (self-hosted docling-serve container)"
    description = "Self-hosted docling-serve Docker container — no API key by default."
    requires_api_key = False
    url_placeholder = "http://localhost:5001"


ParsingEngineRegistry.register(DoclingHostedDriver())
ParsingEngineRegistry.register(DoclingLocalDriver())
