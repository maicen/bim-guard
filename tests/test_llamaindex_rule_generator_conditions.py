"""_candidate_to_draft's applies_when mapping (conditional/scoped rule extraction)."""

from app.modules.contracts import ClauseMetadata, DocumentNodeContract
from app.modules.rule_builder.llamaindex_rule_generator import (
    _candidate_to_draft,
    _LLMRuleCandidate,
)


def _node() -> DocumentNodeContract:
    return DocumentNodeContract(
        node_id="node-1",
        text="Gypsum board partitions shall have a fire rating of at least 45 minutes.",
        metadata=ClauseMetadata(node_type="paragraph", source_document_id=1),
    )


def test_applies_when_materials_becomes_material_any_of_predicate():
    candidate = _LLMRuleCandidate(
        rule_id="REQ-1",
        description="Gypsum partitions shall be fire-rated",
        target_ifc_class="IfcWall",
        applies_when_materials=["gypsum", "gypsum board"],
    )

    draft = _candidate_to_draft(candidate, _node())

    assert draft is not None
    assert draft.proposed_rule.applies_when == {"material_any_of": ["gypsum", "gypsum board"]}


def test_no_applies_when_materials_leaves_applies_when_none():
    candidate = _LLMRuleCandidate(
        rule_id="REQ-2",
        description="Doors shall be wide enough",
        target_ifc_class="IfcDoor",
    )

    draft = _candidate_to_draft(candidate, _node())

    assert draft is not None
    assert draft.proposed_rule.applies_when is None


def test_blank_material_entries_are_dropped():
    candidate = _LLMRuleCandidate(
        rule_id="REQ-3",
        description="Some rule",
        target_ifc_class="IfcWall",
        applies_when_materials=["  ", "steel", ""],
    )

    draft = _candidate_to_draft(candidate, _node())

    assert draft is not None
    assert draft.proposed_rule.applies_when == {"material_any_of": ["steel"]}
