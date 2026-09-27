"""rule_builder/llamaindex_rule_generator.py.

Structured, Pydantic-validated rule generation from LlamaIndex document
nodes (Module 3). This is BIM-Guard's single LLM-based rule-extraction
engine: a typed LlamaIndex Pydantic program whose output schema validates
every extracted rule field, so a malformed LLM response fails Pydantic
validation instead of being silently coerced (the failure mode of the
legacy hand-rolled `json.loads` + defensive-dict-coercion approach this
replaced).

One clause/section (a `DocumentNodeContract`, already section-scoped by
SectionChunker) commonly expresses more than one checkable requirement
(e.g. a table-driven threshold plus its sprinkler exception), so the
program's output schema is a `rules` array, not a single candidate —
generate_drafts_from_node() returns zero or more drafts per node.

Prompt content lives in the sibling module ``_extraction_prompts``.
Keeping prompts as Python (not external text files) preserves format-string
escaping semantics and lets the schema/prompt contract be reviewed together.
"""

from pydantic import BaseModel, Field

from app.logging_config import get_logger
from app.modules.contracts import (
    ClauseMetadata,
    DeonticStatement,
    DocumentNodeContract,
    RuleCreateRequest,
    RuleExtractionDraft,
)
from app.modules.document_parsing.llamaindex_program import build_llm
from app.modules.rule_builder._extraction_prompts import (
    RULE_PROMPT,
    SYSTEM_PROMPT,
    format_kg_context,
)
from app.services.clause_grounding_index import ClauseGroundingIndex, get_clause_grounding_index

logger = get_logger(__name__)

# Backward-compatibility alias for tests
_format_kg_context = format_kg_context


class _LLMRuleCandidate(BaseModel):
    """One extracted rule — an item in the Pydantic program's output array."""

    rule_id: str = ""
    description: str = ""
    mechanism: str = "CODE"
    target_ifc_class: str = ""
    property_set: str = ""
    property_name: str = ""
    rule_type: str = "numeric_range"
    operator: str = "=="
    check_value: str = ""
    value_min: str = ""
    value_max: str = ""
    value_min_property: str = ""
    value_max_property: str = ""
    value_min_scale: str = ""
    value_max_scale: str = ""
    value_min_offset: str = ""
    value_max_offset: str = ""
    unit: str = ""
    severity: str = "recommended"
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    needs_review: int = 0
    applies_when_materials: list[str] = Field(
        default_factory=list,
        description=(
            "If the clause narrows this rule to elements of a specific "
            "material (e.g. 'gypsum board partitions', 'steel pipework'), "
            "list the material keyword(s) here. Leave empty when the rule "
            "applies to every element of target_ifc_class."
        ),
    )
    rase_requirement: str = Field(default="", description="Core obligation text")
    rase_applicability: dict = Field(
        default_factory=dict,
        description=(
            "Conditions that activate this rule. Building-code tables express tiered ranges, "
            "not exact point values. Always use range-bound keys ending in _min / _max "
            "(e.g. {\"projection_mm_min\": 305, \"projection_mm_max\": 610}). "
            "Never use bare exact-match keys like {\"projection_mm\": 1520}."
        ),
    )
    rase_selection: dict = Field(default_factory=dict, description="Criteria for targets")
    rase_exception: dict = Field(default_factory=dict, description="Conditions excusing the requirement")
    kg_candidate_used: str = Field(
        default="",
        description=(
            "uri of the shown KNOWN-GOOD CANDIDATE that target_ifc_class came "
            "from, or '' if none were shown or none were used -- makes the "
            "model's use of grounded candidates explicit and auditable, "
            "instead of only inferable from a post-hoc string match."
        ),
    )


class _LLMRuleExtractionResult(BaseModel):
    """Structured LLM output schema — a Pydantic program target, not a dict."""

    rules: list[_LLMRuleCandidate] = Field(default_factory=list)


_TRUSTED_KG_TIERS = ("llm_verified", "human_verified")


def _kg_calibrated_confidence(candidate: _LLMRuleCandidate, class_candidates: list[dict]) -> float:
    """Nudges confidence up when the model's chosen class matches a highly-trusted KG candidate.

    Only ever raises confidence, and only by a small, capped amount: this is
    a calibration signal on top of the model's own self-reported confidence,
    not a replacement for it, and a wrong needs_review=1 from the model is
    never overridden by KG agreement alone.
    """
    used_uri = candidate.kg_candidate_used.strip()
    if not used_uri:
        return candidate.confidence
    tier = next((c.get("source") for c in class_candidates if c.get("uri") == used_uri), None)
    if tier not in _TRUSTED_KG_TIERS:
        return candidate.confidence
    return min(candidate.confidence + 0.05, 0.99)


def _candidate_to_draft(
    candidate: _LLMRuleCandidate,
    node: DocumentNodeContract,
    *,
    deontic: DeonticStatement | None = None,
    class_candidates: list[dict] | None = None,
) -> RuleExtractionDraft | None:
    """Map a validated LLM candidate onto a RuleExtractionDraft, or None if empty.

    A pure function (no LLM call) so the candidate->draft mapping is directly
    unit-testable without mocking LlamaIndex's program machinery.
    """
    if not candidate.description.strip():
        return None

    severity = candidate.severity
    if deontic is not None and deontic.modality in ("shall", "must"):
        severity = "mandatory"

    materials = [m.strip() for m in candidate.applies_when_materials if m.strip()]
    applies_when = {"material_any_of": materials} if materials else None

    confidence = _kg_calibrated_confidence(candidate, class_candidates or [])

    proposed_rule = RuleCreateRequest(
        rule_id=candidate.rule_id.strip() or (node.metadata.clause_id or node.node_id[:8]),
        description=candidate.description.strip(),
        mechanism=candidate.mechanism.strip() or "CODE",
        rule_category="property_check",
        target_ifc_class=candidate.target_ifc_class.strip() or None,
        property_set=candidate.property_set.strip() or None,
        property_name=candidate.property_name.strip() or None,
        operator=candidate.operator.strip() or "==",
        check_value=candidate.check_value.strip() or None,
        value_min=candidate.value_min.strip() or None,
        value_max=candidate.value_max.strip() or None,
        value_min_property=candidate.value_min_property.strip() or None,
        value_max_property=candidate.value_max_property.strip() or None,
        value_min_scale=candidate.value_min_scale.strip() or None,
        value_max_scale=candidate.value_max_scale.strip() or None,
        value_min_offset=candidate.value_min_offset.strip() or None,
        value_max_offset=candidate.value_max_offset.strip() or None,
        unit=candidate.unit.strip() or None,
        severity=severity,
        confidence=str(confidence),
        extraction_method="llamaindex_pydantic",
        needs_review=candidate.needs_review,
        applies_when=applies_when,
        rase_requirement=candidate.rase_requirement.strip() or None,
        rase_applicability=candidate.rase_applicability or None,
        rase_selection=candidate.rase_selection or None,
        rase_exception=candidate.rase_exception or None,
        kg_candidate_used=candidate.kg_candidate_used.strip() or None,
    )

    return RuleExtractionDraft(
        source_document_id=node.metadata.source_document_id,
        source_node_id=node.node_id,
        source_element_id=node.metadata.element_id,
        source_snippet=node.text,
        clause=node.metadata,
        bbox=node.metadata.bbox,
        proposed_rule=proposed_rule,
        confidence=confidence,
        extraction_method="llamaindex_pydantic",
    )


class LlamaIndexRuleGenerator:
    """Generates Pydantic-validated rule drafts from document nodes.

    Implements RuleExtractionProvider (app.services.rule_extraction_service)
    via extract_rules_from_text() so it is usable both for the draft-review
    workflow (generate_drafts_from_node) and the free-text/file extraction
    endpoint.
    """

    async def generate_drafts_from_node(
        self,
        node: DocumentNodeContract,
        *,
        deontic: DeonticStatement | None = None,
        model: str | None = None,
        organization_id: int | None = None,
        clause_grounding: ClauseGroundingIndex | None = None,
    ) -> list[RuleExtractionDraft]:
        """Run the Pydantic program over one node's text; [] if no rule found.

        Args:
            node: A clause-annotated document node (Module 1 output).
            deontic: The node's associated deontic statement, if any — used
                only to bias severity when the LLM leaves it ambiguous.
            model: Extraction LLM override (e.g. from the UI's model
                selector); falls back to ``DEFAULT_LLM_MODEL`` when omitted.
            organization_id: Resolves the API key from that org's configured
                LLM provider instance first, falling back to the provider's
                env var — see ``build_llm``.
            clause_grounding: Injectable ClauseGroundingIndex -- when this
                node's clause_id is covered by a promoted knowledge-graph
                grounding index, its trusted bSDD class/property candidates
                and clause-dependency edges are shown to the LLM as part of
                the prompt (see _format_kg_context), instead of only being
                used to correct the LLM's answer after the fact.
        """
        from llama_index.core.llms import ChatMessage, MessageRole
        from llama_index.core.program import LLMTextCompletionProgram
        from llama_index.core.prompts import ChatPromptTemplate

        clause_grounding = clause_grounding or get_clause_grounding_index()
        clause_id = node.metadata.clause_id if node.metadata else None
        class_candidates = clause_grounding.class_candidates_for(clause_id)
        kg_context = format_kg_context(
            class_candidates=class_candidates,
            property_hints=clause_grounding.property_hints_for(clause_id),
            dependencies=clause_grounding.dependencies_for(clause_id),
        )

        chat_prompt = ChatPromptTemplate(
            message_templates=[
                ChatMessage(role=MessageRole.SYSTEM, content=SYSTEM_PROMPT),
                ChatMessage(role=MessageRole.USER, content=RULE_PROMPT),
            ]
        )
        program = LLMTextCompletionProgram.from_defaults(
            output_cls=_LLMRuleExtractionResult,
            prompt=chat_prompt,
            llm=build_llm(model, organization_id=organization_id),
        )
        result: _LLMRuleExtractionResult = await program.acall(clause_text=node.text, kg_context=kg_context)

        drafts = [
            _candidate_to_draft(candidate, node, deontic=deontic, class_candidates=class_candidates)
            for candidate in result.rules
        ]
        return [draft for draft in drafts if draft is not None]

    # ── RuleExtractionProvider conformance ──────────────────────────────────

    async def extract_rules_from_text(
        self,
        text: str,
        *,
        chunk_index: int = 1,
        total_chunks: int = 1,
        model: str | None = None,
        organization_id: int | None = None,
    ) -> list[dict]:
        """Drop-in RuleExtractionProvider method for the chunk-text extraction path.

        Wraps the raw text as a single ad-hoc node and returns 0+ normalised
        rule dicts, in the same shape the legacy extractor produced, so
        callers that dedupe/merge on ('desc', 'target') keep working
        unchanged.
        """
        if not text.strip():
            return []

        node = DocumentNodeContract(
            node_id=f"chunk-{chunk_index}",
            text=text,
            metadata=ClauseMetadata(node_type="paragraph", source_document_id=0),
        )
        drafts = await self.generate_drafts_from_node(node, model=model, organization_id=organization_id)
        if not drafts:
            return []

        results = []
        for draft in drafts:
            rule = draft.proposed_rule
            results.append(
                {
                    "ref": rule.rule_id,
                    "desc": rule.description,
                    "source_text": text[:500],
                    "target": rule.target_ifc_class or "Unspecified",
                    "property_set": rule.property_set or "",
                    "property_name": rule.property_name or "",
                    "rule_type": "numeric_range" if rule.operator in {">=", "<=", "between"} else "exists_check",
                    "operator": rule.operator,
                    "value": rule.check_value,
                    "check_value": rule.check_value,
                    "value_min": rule.value_min,
                    "value_max": rule.value_max,
                    "unit": rule.unit or "",
                    "severity": rule.severity,
                    "confidence": draft.confidence,
                    "extraction_method": "llamaindex_pydantic",
                    "needs_review": bool(rule.needs_review),
                }
            )
        return results
