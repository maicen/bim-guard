"""LLM-only rule extraction service contracts."""

import asyncio
import subprocess
import sys

from app.modules.contracts import BSDDPropertyItem, RuleCreateRequest, RuleExtractionDraft
from app.services.rule_extraction_service import RuleExtractionService


class FakeProvider:
    """Return duplicate rules while recording received source chunks."""

    def __init__(self) -> None:
        self.chunks = []

    async def extract_rules_from_text(
        self, text: str, *, chunk_index: int = 1, total_chunks: int = 1, model: str | None = None
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
        "unstructured_extractor",
        "table_rule_builder",
        "keyword_filter",
        "dependency_parser",
        "confidence_scorer",
        "tfidf_analyzer",
        "bert_classifier",
        "nlp_annotation",
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


class FakeBSDDClient:
    """Returns a fixed set of property matches, recording the query received."""

    def __init__(self, matches: list[BSDDPropertyItem]) -> None:
        self.matches = matches
        self.queries: list[str] = []

    def search_properties(self, query: str, dictionary_uri=None, limit: int = 8):
        self.queries.append(query)
        return self.matches


def _draft(property_set: str | None, property_name: str | None) -> RuleExtractionDraft:
    return RuleExtractionDraft(
        source_document_id=1,
        proposed_rule=RuleCreateRequest(
            rule_id="REQ-1",
            description="Doors shall be wide enough",
            target_ifc_class="IfcDoor",
            property_set=property_set,
            property_name=property_name,
            severity="mandatory",
        ),
    )


def test_bsdd_grounding_corrects_invented_property_set():
    bsdd = FakeBSDDClient(
        [BSDDPropertyItem(uri="urn:x", name="OverallWidth", property_set="Pset_DoorCommon")]
    )
    service = RuleExtractionService(bsdd_client=bsdd)
    draft = _draft(property_set="Pset_Door", property_name="OverallWidth")

    grounded = service._ground_draft_with_bsdd(draft)

    assert grounded.proposed_rule.property_set == "Pset_DoorCommon"
    assert grounded.proposed_rule.property_name == "OverallWidth"
    assert "bSDD grounding" in (grounded.review_notes or "")
    assert bsdd.queries == ["OverallWidth"]


def test_bsdd_grounding_leaves_already_correct_rule_untouched():
    bsdd = FakeBSDDClient(
        [BSDDPropertyItem(uri="urn:x", name="OverallWidth", property_set="Pset_DoorCommon")]
    )
    service = RuleExtractionService(bsdd_client=bsdd)
    draft = _draft(property_set="Pset_DoorCommon", property_name="OverallWidth")

    grounded = service._ground_draft_with_bsdd(draft)

    assert grounded is draft
    assert grounded.review_notes is None


def test_bsdd_grounding_skips_when_no_match_found():
    bsdd = FakeBSDDClient([])
    service = RuleExtractionService(bsdd_client=bsdd)
    draft = _draft(property_set="Pset_Door", property_name="TotallyMadeUpProperty")

    grounded = service._ground_draft_with_bsdd(draft)

    assert grounded is draft


def test_bsdd_grounding_survives_lookup_failure():
    class ExplodingBSDDClient:
        def search_properties(self, *args, **kwargs):
            raise RuntimeError("bSDD unreachable")

    service = RuleExtractionService(bsdd_client=ExplodingBSDDClient())
    draft = _draft(property_set="Pset_Door", property_name="OverallWidth")

    grounded = service._ground_draft_with_bsdd(draft)

    assert grounded is draft


def test_bsdd_grounding_skips_when_no_property_name():
    service = RuleExtractionService(bsdd_client=FakeBSDDClient([]))
    draft = _draft(property_set=None, property_name=None)

    grounded = service._ground_draft_with_bsdd(draft)

    assert grounded is draft