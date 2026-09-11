from app.modules.contracts import ClauseMetadata, DocumentNodeContract
from app.modules.rule_builder.llamaindex_rule_generator import (
    _candidate_to_draft,
    _LLMRuleCandidate,
)


def test_llm_rule_candidate_rase_fields():
    candidate = _LLMRuleCandidate(
        rule_id="C2.2",
        description="Test rule",
        target_ifc_class="IfcDoor",
        rase_requirement="Doors shall have a clear width",
        rase_applicability={"occupancy": "residential"},
        rase_selection={"capacity_gt": 100},
        rase_exception={"has_sprinkler": True},
    )

    node = DocumentNodeContract(
        node_id="node-1",
        text="Doors shall have a clear width",
        metadata=ClauseMetadata(source_document_id=1),
    )

    draft = _candidate_to_draft(candidate, node)

    assert draft is not None
    assert draft.proposed_rule.rase_requirement == "Doors shall have a clear width"
    assert draft.proposed_rule.rase_applicability == {"occupancy": "residential"}
    assert draft.proposed_rule.rase_selection == {"capacity_gt": 100}
    assert draft.proposed_rule.rase_exception == {"has_sprinkler": True}
