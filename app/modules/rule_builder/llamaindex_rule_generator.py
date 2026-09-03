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

logger = get_logger(__name__)

_RULE_PROMPT = """\
You are a BIM compliance rule extraction engine for building regulations.

Read the clause text below and extract every discrete, checkable
requirement it expresses (a numeric limit, a required property, a
classification, a presence check, or a required count of elements) against
an IFC element. A single clause commonly expresses more than one rule (for
example a base threshold plus an exception that changes it) — extract each
as its own entry in "rules". If the text expresses no checkable requirement
at all (e.g. it is a definition, example, or purely descriptive text),
return an empty "rules" array.

For each rule found, fill in:
- rule_id: a short identifier, e.g. the clause reference if present, else
  "REQ-AI-<short-slug>"
- description: short plain-English rule description
- mechanism: "CODE" unless the text is clearly about corrosion (GC-001,
  CC-001, MC-001)
- target_ifc_class: the IFC entity type the rule applies to, e.g. "IfcDoor",
  "IfcSpace", "IfcStairFlight" — required for every rule, since it is what
  lets a rule be checked against a model and exported to IDS
- property_set: IFC Pset name, e.g. "Pset_StairFlightCommon", or empty
- property_name: IFC property to measure, e.g. "TreadLength", or empty
- rule_type: "numeric_range" | "exists_check" | "count_check" | "classification"
  — use "count_check" for requirements on how many of an element are present
  (e.g. "two exits shall be provided"), not "numeric_range"
- operator: one of ">=", "<=", "==", "!=", "between", "exists", "matches"
- check_value: the target value as a string (numeric values as their string form), or empty
- value_min / value_max: string bounds for "between", or empty
- unit: "mm" | "m" | "m2" | "deg" | "ratio" | "" (empty if not applicable)
- severity: "mandatory" if the clause uses "shall"/"must", "recommended" if
  "should", else "recommended"
- confidence: 0.0-1.0, your confidence this rule is correctly extracted
- needs_review: 1 if the text is ambiguous, if the threshold is looked up in
  a table you cannot see in full, or if the bound is computed from a
  building-level metric (e.g. "one-half of the diagonal dimension of the
  area served") rather than a fixed value or a same-element property — else 0

CLAUSE TEXT:
{clause_text}
"""


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
    unit: str = ""
    severity: str = "recommended"
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    needs_review: int = 0


class _LLMRuleExtractionResult(BaseModel):
    """Structured LLM output schema — a Pydantic program target, not a dict."""

    rules: list[_LLMRuleCandidate] = Field(default_factory=list)


def _candidate_to_draft(
    candidate: _LLMRuleCandidate,
    node: DocumentNodeContract,
    *,
    deontic: DeonticStatement | None = None,
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


class LlamaIndexRuleGenerator:
    """Generates Pydantic-validated rule drafts from document nodes.

    Implements RuleExtractionProvider (app.services.rule_extraction_service)
    via extract_rules_from_text() so it is usable both for the draft-review
    workflow (generate_drafts_from_node) and the free-text/file extraction
    endpoint.
    """

    async def generate_drafts_from_node(
        self, node: DocumentNodeContract, *, deontic: DeonticStatement | None = None
    ) -> list[RuleExtractionDraft]:
        """Run the Pydantic program over one node's text; [] if no rule found.

        Args:
            node: A clause-annotated document node (Module 1 output).
            deontic: The node's associated deontic statement, if any — used
                only to bias severity when the LLM leaves it ambiguous.
        """
        from llama_index.core.program import LLMTextCompletionProgram

        program = LLMTextCompletionProgram.from_defaults(
            output_cls=_LLMRuleExtractionResult,
            prompt_template_str=_RULE_PROMPT,
            llm=build_llm(),
        )
        result: _LLMRuleExtractionResult = await program.acall(clause_text=node.text)

        drafts = [_candidate_to_draft(candidate, node, deontic=deontic) for candidate in result.rules]
        return [draft for draft in drafts if draft is not None]

    # ── RuleExtractionProvider conformance ──────────────────────────────────

    async def extract_rules_from_text(
        self, text: str, *, chunk_index: int = 1, total_chunks: int = 1
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
        drafts = await self.generate_drafts_from_node(node)
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
