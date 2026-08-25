"""LLM-only rule extraction service contracts."""

import asyncio
import subprocess
import sys

from app.services.rule_extraction_service import RuleExtractionService


class FakeProvider:
    """Return duplicate rules while recording received source chunks."""

    def __init__(self) -> None:
        self.chunks = []

    async def extract_rules_from_text(
        self, text: str, *, chunk_index: int = 1, total_chunks: int = 1
    ) -> list[dict]:
        self.chunks.append((text, chunk_index, total_chunks))
        return [
            {"desc": "Wall shall comply", "target": "IfcWall"},
            {"desc": "Wall shall comply", "target": "IfcWall"},
        ]


def test_text_extraction_uses_only_provider_rules_and_deduplicates():
    provider = FakeProvider()

    result = asyncio.run(
        RuleExtractionService(provider=provider).extract_rules_from_text(
            "Walls shall comply."
        )
    )

    assert provider.chunks
    assert result.rules == [
        {
            "desc": "Wall shall comply",
            "target": "IfcWall",
            "ref": "REQ-AI-001",
        }
    ]
    assert result.warnings == []


def test_empty_text_does_not_call_provider():
    provider = FakeProvider()

    result = asyncio.run(
        RuleExtractionService(provider=provider).extract_rules_from_text("  ")
    )

    assert provider.chunks == []
    assert result.rules == []


def test_service_import_does_not_load_legacy_extraction_modules():
    source = """
import json
import sys
import app.services.rule_extraction_service
legacy = [
    name for name in sys.modules
    if name.endswith((
        "docling_extractor",
        "table_rule_builder",
        "keyword_filter",
        "dependency_parser",
        "confidence_scorer",
        "tfidf_analyzer",
        "bert_classifier",
        "module1b_nlp_annotator",
    ))
]
print(json.dumps(legacy))
"""

    result = subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )

    assert result.stdout.strip().splitlines()[-1] == "[]"