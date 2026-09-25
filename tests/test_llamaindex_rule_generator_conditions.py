"""_candidate_to_draft's applies_when mapping (conditional/scoped rule extraction)."""

from app.modules.contracts import ClauseMetadata, DocumentNodeContract
from app.modules.rule_builder.llamaindex_rule_generator import (
    _candidate_to_draft,
    _format_kg_context,
    _kg_calibrated_confidence,
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


def test_kg_candidate_used_is_carried_onto_proposed_rule():
    candidate = _LLMRuleCandidate(
        rule_id="REQ-4",
        description="Doors shall be wide enough",
        target_ifc_class="IfcDoor",
        kg_candidate_used="urn:bsdd:ifcdoor",
    )

    draft = _candidate_to_draft(candidate, _node())

    assert draft is not None
    assert draft.proposed_rule.kg_candidate_used == "urn:bsdd:ifcdoor"


def test_empty_kg_candidate_used_becomes_none():
    candidate = _LLMRuleCandidate(rule_id="REQ-5", description="Doors shall be wide enough", target_ifc_class="IfcDoor")

    draft = _candidate_to_draft(candidate, _node())

    assert draft is not None
    assert draft.proposed_rule.kg_candidate_used is None


def test_relative_bound_scale_and_offset_carried_onto_proposed_rule():
    """'riser height <= 0.5x tread going' extracts as a scaled property-relative bound."""
    candidate = _LLMRuleCandidate(
        rule_id="REQ-RISE",
        description="Riser height shall not exceed one-half of the tread going",
        target_ifc_class="IfcStairFlight",
        property_name="RiserHeight",
        operator="<=",
        value_max_property="TreadGoing",
        value_max_scale="0.5",
    )

    draft = _candidate_to_draft(candidate, _node())

    assert draft is not None
    assert draft.proposed_rule.value_max_property == "TreadGoing"
    assert draft.proposed_rule.value_max_scale == "0.5"
    assert draft.proposed_rule.value_min_property is None
    assert draft.proposed_rule.value_min_scale is None


def test_no_relative_bound_leaves_scale_and_offset_none():
    candidate = _LLMRuleCandidate(rule_id="REQ-10", description="Doors shall be wide enough", target_ifc_class="IfcDoor")

    draft = _candidate_to_draft(candidate, _node())

    assert draft is not None
    assert draft.proposed_rule.value_min_property is None
    assert draft.proposed_rule.value_min_scale is None
    assert draft.proposed_rule.value_min_offset is None


def test_confidence_calibrated_up_when_used_candidate_is_trusted_tier():
    candidate = _LLMRuleCandidate(
        rule_id="REQ-6", description="Doors shall be wide enough", target_ifc_class="IfcDoor",
        confidence=0.7, kg_candidate_used="urn:bsdd:ifcdoor",
    )
    class_candidates = [{"uri": "urn:bsdd:ifcdoor", "source": "llm_verified"}]

    draft = _candidate_to_draft(candidate, _node(), class_candidates=class_candidates)

    assert draft is not None
    assert draft.confidence == 0.75
    assert draft.proposed_rule.confidence == "0.75"


def test_confidence_untouched_when_used_candidate_is_lexical_only():
    candidate = _LLMRuleCandidate(
        rule_id="REQ-7", description="Doors shall be wide enough", target_ifc_class="IfcDoor",
        confidence=0.7, kg_candidate_used="urn:bsdd:ifcdoor",
    )
    class_candidates = [{"uri": "urn:bsdd:ifcdoor", "source": "lexical_high_confidence"}]

    assert _kg_calibrated_confidence(candidate, class_candidates) == 0.7


def test_confidence_untouched_when_no_candidate_used():
    candidate = _LLMRuleCandidate(rule_id="REQ-8", description="Doors shall be wide enough", confidence=0.7)

    assert _kg_calibrated_confidence(candidate, []) == 0.7


def test_confidence_capped_at_point_nine_nine():
    candidate = _LLMRuleCandidate(
        rule_id="REQ-9", description="Doors shall be wide enough", target_ifc_class="IfcDoor",
        confidence=0.98, kg_candidate_used="urn:bsdd:ifcdoor",
    )
    class_candidates = [{"uri": "urn:bsdd:ifcdoor", "source": "human_verified"}]

    assert _kg_calibrated_confidence(candidate, class_candidates) == 0.99


class TestFormatKgContext:
    def test_empty_when_nothing_to_show(self):
        assert _format_kg_context(class_candidates=[], property_hints=[], dependencies=[]) == ""

    def test_includes_class_candidates(self):
        block = _format_kg_context(
            class_candidates=[{"name": "IfcStairFlight", "code": "STAIR", "uri": "urn:a"}],
            property_hints=[],
            dependencies=[],
        )
        assert "KNOWN-GOOD CANDIDATES" in block
        assert "IfcStairFlight" in block
        assert "urn:a" in block

    def test_includes_dependencies(self):
        block = _format_kg_context(
            class_candidates=[],
            property_hints=[],
            dependencies=[
                {
                    "edge_type": "depends_on:exception",
                    "target_ref": "9.8.4.2",
                    "target_text_excerpt": "Sprinklered stairs are exempt.",
                }
            ],
        )
        assert "RELATED CLAUSES" in block
        assert "9.8.4.2" in block
        assert "Sprinklered stairs are exempt." in block
