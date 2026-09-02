"""
module3_rule_builder/llamaindex_rule_generator.py
---------------------------------------------------
Structured, Pydantic-validated rule generation from LlamaIndex document
nodes (Module 3), replacing the hand-rolled JSON parsing/normalisation in
`app.services.rule_extractor.LiteLLMRuleExtractor` with a typed LlamaIndex
Pydantic program whose output schema *is* `RuleCreateRequest` — so a
malformed LLM response fails Pydantic validation instead of being silently
coerced.

Implements the existing `RuleExtractionProvider` Protocol
(app.services.rule_extractor) so it is a drop-in alternative to
`LiteLLMRuleExtractor` wherever a provider is accepted, selected via the
`BIM_GUARD_RULE_EXTRACTION_PROVIDER` setting.

One clause/section (a `DocumentNodeContract`, already section-scoped by
SectionChunker) is assumed to express at most one checkable rule — a
simplification relative to the legacy extractor's per-chunk multi-rule
extraction, appropriate because Module 1's nodes are already fine-grained.
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
from app.modules.module1_doc_parser.llamaindex_program import build_llm

logger = get_logger(__name__)

_RULE_PROMPT = """\
You are a BIM compliance rule extraction engine for building regulations.

Read the clause text below and determine whether it expresses a single,
discrete, checkable requirement (a numeric limit, a required property, a
classification, or presence check) against an IFC element.

If it does NOT express a checkable requirement (e.g. it is a definition,
example, or purely descriptive text), set found=false and leave the other
fields at their defaults.

If it DOES, set found=true and fill in:
- rule_id: a short identifier, e.g. the clause reference if present, else
  "REQ-AI-<short-slug>"
- description: short plain-English rule description
- mechanism: "CODE" unless the text is clearly about corrosion (GC-001,
  CC-001, MC-001)
- property_set: IFC Pset name, e.g. "Pset_StairFlightCommon", or empty
- property_name: IFC property to measure, e.g. "TreadLength", or empty
- operator: one of ">=", "<=", "==", "!=", "between", "exists", "matches"
- check_value: the target value as a string (numeric values as their string form), or empty
- value_min / value_max: string bounds for "between", or empty
- unit: "mm" | "m" | "m2" | "deg" | "ratio" | "" (empty if not applicable)
- severity: "mandatory" if the clause uses "shall"/"must", "recommended" if
  "should", else "recommended"
- confidence: 0.0-1.0, your confidence this rule is correctly extracted
- needs_review: 1 if the text is ambiguous or you are unsure, else 0

CLAUSE TEXT:
{clause_text}
"""


class _LLMRuleCandidate(BaseModel):
    """Structured LLM output schema — a Pydantic program target, not a dict."""

    found: bool = False
    rule_id: str = ""
    description: str = ""
    mechanism: str = "CODE"
    property_set: str = ""
    property_name: str = ""
    operator: str = "=="
    check_value: str = ""
    value_min: str = ""
    value_max: str = ""
    unit: str = ""
    severity: str = "recommended"
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    needs_review: int = 0


class LlamaIndexRuleGenerator:
    """Generates Pydantic-validated rule drafts from document nodes.

    Implements RuleExtractionProvider (app.services.rule_extractor) for
    drop-in compatibility with the legacy chunk-text extraction path.
    """

    async def generate_draft_from_node(
        self, node: DocumentNodeContract, *, deontic: DeonticStatement | None = None
    ) -> RuleExtractionDraft | None:
        """Run the Pydantic program over one node's text; None if no rule found.

        Args:
            node: A clause-annotated document node (Module 1 output).
            deontic: The node's associated deontic statement, if any — used
                only to bias severity when the LLM leaves it ambiguous.
        """
        from llama_index.core.program import LLMTextCompletionProgram

        program = LLMTextCompletionProgram.from_defaults(
            output_cls=_LLMRuleCandidate,
            prompt_template_str=_RULE_PROMPT,
            llm=build_llm(),
        )
        candidate: _LLMRuleCandidate = await program.acall(clause_text=node.text)

        if not candidate.found or not candidate.description.strip():
            return None

        severity = candidate.severity
        if deontic is not None and deontic.modality in ("shall", "must"):
            severity = "mandatory"

        proposed_rule = RuleCreateRequest(
            rule_id=candidate.rule_id.strip() or (node.metadata.clause_id or node.node_id[:8]),
            description=candidate.description.strip(),
            mechanism=candidate.mechanism.strip() or "CODE",
            rule_category="property_check",
            property_set=candidate.property_set.strip() or None,
            property_name=candidate.property_name.strip() or None,
            operator=candidate.operator.strip() or "==",
            check_value=candidate.check_value.strip() or None,
            value_min=candidate.value_min.strip() or None,
            value_max=candidate.value_max.strip() or None,
            unit=candidate.unit.strip() or None,
            severity=severity,
            confidence=str(candidate.confidence),
            extraction_method="llamaindex_pydantic",
            needs_review=candidate.needs_review,
        )

        return RuleExtractionDraft(
            source_document_id=node.metadata.source_document_id,
            source_node_id=node.node_id,
            clause=node.metadata,
            proposed_rule=proposed_rule,
            confidence=candidate.confidence,
            extraction_method="llamaindex_pydantic",
        )

    # ── RuleExtractionProvider conformance ──────────────────────────────────

    async def extract_rules_from_text(
        self, text: str, *, chunk_index: int = 1, total_chunks: int = 1
    ) -> list[dict]:
        """Drop-in RuleExtractionProvider method for the legacy chunk-text path.

        Wraps the raw text as a single ad-hoc node and returns 0 or 1
        normalised rule dicts, in the same shape LiteLLMRuleExtractor
        produces, so callers that dedupe/merge on ('desc', 'target') keep
        working unchanged.
        """
        if not text.strip():
            return []

        node = DocumentNodeContract(
            node_id=f"chunk-{chunk_index}",
            text=text,
            metadata=ClauseMetadata(node_type="paragraph", source_document_id=0),
        )
        draft = await self.generate_draft_from_node(node)
        if draft is None:
            return []

        rule = draft.proposed_rule
        return [
            {
                "ref": rule.rule_id,
                "desc": rule.description,
                "source_text": text[:500],
                "target": "Unspecified",
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
        ]
