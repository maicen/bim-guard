"""Rule extraction exercised against a real code document.

Source: SBC Section 8.14 Exit and Exit Access Doorways, from
`data/cache/supabase-storage/uploads/..._sbc_mock_EXIT AND EXIT ACCESS
DOORWAYS.pdf`; its extracted text is checked in at
tests/schemas/sbc_exit_access_doorways.txt so this test doesn't depend on the
transient upload cache.
"""

import asyncio
from pathlib import Path

from app.modules.contracts import (
    ClauseMetadata,
    DeonticStatement,
    DocumentNodeContract,
)
from app.modules.rule_builder.llamaindex_rule_generator import (
    _candidate_to_draft,
    _LLMRuleCandidate,
)
from app.services.rule_extraction_service import RuleExtractionService

FIXTURE_PATH = Path(__file__).parent / "schemas" / "sbc_exit_access_doorways.txt"


def _load_fixture_text() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


class FakeProvider:
    """Records the chunks it was asked to extract rules from."""

    def __init__(self) -> None:
        self.chunks: list[tuple[str, int, int]] = []

    async def extract_rules_from_text(
        self, text: str, *, chunk_index: int = 1, total_chunks: int = 1
    ) -> list[dict]:
        self.chunks.append((text, chunk_index, total_chunks))
        return [
            {
                "desc": f"Extracted from chunk {chunk_index}",
                "target": "IfcSpace",
            }
        ]


def test_fixture_text_is_present_and_matches_expected_section():
    text = _load_fixture_text()
    assert "EXIT AND EXIT ACCESS DOORWAYS" in text
    assert "8.14.1" in text


def test_pipeline_chunks_and_extracts_real_document_text():
    text = _load_fixture_text()
    provider = FakeProvider()

    result = asyncio.run(
        RuleExtractionService(provider=provider).extract_rules_from_text(text)
    )

    assert provider.chunks, "SectionChunker should have produced at least one chunk"
    assert result.rules
    # Each chunk sent to the provider should carry real clause text, not be empty.
    for chunk_text, _idx, _total in provider.chunks:
        assert chunk_text.strip()


def test_candidate_to_draft_maps_target_ifc_class_for_ids_export():
    """Regression test for a dropped field.

    generate_draft_from_node used to drop target_ifc_class entirely,
    silently making every LlamaIndex-extracted draft unexportable to IDS
    (ids_exporter.filter_exportable_rules requires it).
    """
    node = DocumentNodeContract(
        node_id="node-8.14.1",
        text="Two exits or exit access doorways from any space shall be provided...",
        metadata=ClauseMetadata(
            clause_id="8.14.1", node_type="paragraph", source_document_id=1
        ),
    )
    candidate = _LLMRuleCandidate(
        found=True,
        rule_id="8.14.1",
        description="Space must have two exits when occupant load exceeds Table 8.14.1",
        target_ifc_class="IfcSpace",
        property_name="NumberOfExits",
        rule_type="count_check",
        operator=">=",
        check_value="2",
        severity="recommended",
        confidence=0.7,
        needs_review=1,
    )

    draft = _candidate_to_draft(candidate, node)

    assert draft is not None
    assert draft.proposed_rule.target_ifc_class == "IfcSpace"
    assert draft.proposed_rule.property_name == "NumberOfExits"
    assert draft.proposed_rule.check_value == "2"
    assert draft.proposed_rule.needs_review == 1


def test_candidate_to_draft_upgrades_severity_from_shall_deontic():
    node = DocumentNodeContract(
        node_id="node-8.14.2",
        text="Exits shall be unobstructed at all times.",
        metadata=ClauseMetadata(clause_id="8.14.2", node_type="paragraph", source_document_id=1),
    )
    candidate = _LLMRuleCandidate(
        found=True,
        rule_id="8.14.2",
        description="Exits must remain unobstructed",
        target_ifc_class="IfcDoor",
        severity="recommended",
    )
    deontic = DeonticStatement(
        text="Exits shall be unobstructed at all times.",
        modality="shall",
        subject="IfcDoor",
        clause=node.metadata,
    )

    draft = _candidate_to_draft(candidate, node, deontic=deontic)

    assert draft is not None
    assert draft.proposed_rule.severity == "mandatory"


def test_candidate_to_draft_returns_none_when_not_found():
    node = DocumentNodeContract(
        node_id="node-def",
        text="This section defines the term 'exit access'.",
        metadata=ClauseMetadata(node_type="paragraph", source_document_id=1),
    )
    candidate = _LLMRuleCandidate(found=False)

    assert _candidate_to_draft(candidate, node) is None
