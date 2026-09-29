"""Architectural compliance rules, folders, drafts, reliability, and conflict models."""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, computed_field, field_validator

from app.modules.contracts.base import TimestampFields
from app.modules.contracts.documents import ClauseMetadata, DocumentElementBbox
from app.modules.rule_reliability import assess_rule

__all__ = ['RuleReliability', 'build_rule_reliability', 'RuleReliabilityRequest', 'RuleReliabilityResponse', 'RuleCreateRequest', 'RuleUpdateRequest', 'RuleResponse', 'RuleDraftStatus', 'RuleExtractionDraft', 'RuleExtractionDraftListResponse', 'RuleAlignmentIssue', 'RuleConflictWarning', 'RuleDraftConflictDetectionRequest', 'RuleDraftConflictDetectionResponse', 'RulePromotionResponse', 'DraftSourceSummary', 'DocumentElementWithDrafts', 'DraftSourceMapResponse', 'RuleDraftExtractionRequest', 'RuleExtractionProgressResponse', 'RuleSourceResponse', 'RuleShaclShapeResponse', 'RuleDraftReviewRequest', 'DraftRelinkRequest', 'RuleFolderResponse', 'RuleFolderCreateRequest', 'RuleFolderUpdateRequest', 'RuleBulkUpdateRequest', 'RuleBulkDeleteRequest', 'RuleBulkActionResponse', 'RuleFolderBulkUpdateRequest', 'RuleFolderBulkDeleteRequest', 'RuleFolderBulkActionResponse', 'RuleSnapshotCreateRequest', 'RuleSnapshotResponse', 'IdsImportResponse', 'RuleExtractionResponse', 'RuleSeedResponse', 'RuleBulkCreateResponse', 'RuleFolderDeleteResponse']

# ---------------------------------------------------------------------------
# Rule & Ruleset Contracts
# ---------------------------------------------------------------------------


class RuleReliability(BaseModel):
    """How reliably a rule can be checked against a real IFC model, and why.

    Graded from the IFC property the rule reads (see ``app.modules.rule_reliability``),
    not from the source document, so extracted and hand-written rules are treated alike.
    """

    level: Literal["high", "medium", "low"]
    category: str = Field(description="Machine-readable basis, e.g. 'standard_attribute', 'custom', 'derived'")
    reason: str = Field(description="Plain-language explanation shown to the user")
    bsdd_defined: Optional[bool] = Field(
        default=None,
        description="Whether the buildingSMART Data Dictionary defines the property; null when it can't be checked",
    )

def build_rule_reliability(rule: Any) -> Optional[RuleReliability]:
    """Grade *rule* (a model or a dict), or ``None`` when it names no IFC property to grade."""
    assessment = assess_rule(rule)
    if assessment is None:
        return None
    return RuleReliability(
        level=assessment.level,
        category=assessment.category,
        reason=assessment.reason,
        bsdd_defined=assessment.bsdd_defined,
    )

class RuleReliabilityRequest(BaseModel):
    """The rule fields that decide reliability, for grading a rule before it is saved."""

    property_set: Optional[str] = None
    property_name: Optional[str] = None
    compare_property: Optional[str] = None
    value_min_property: Optional[str] = None
    value_max_property: Optional[str] = None

class RuleReliabilityResponse(BaseModel):
    """Result of grading a rule; ``reliability`` is null when no property is named yet."""

    reliability: Optional[RuleReliability] = None

class RuleCreateRequest(BaseModel):
    """Payload for creating or registering a rule."""

    rule_id: str = Field(..., description="Unique rule identifier (e.g. ARCH-EGRESS-001.01)")
    description: Optional[str] = Field(default="", description="Rule human description")
    mechanism: Optional[str] = Field(default="CODE", description="Domain or mechanism (e.g. IFC, CODE)")
    ruleset_id: Optional[str] = Field(default=None, description="Group or folder ruleset identifier")
    rule_category: Optional[str] = Field(default="property_check", description="Rule classification")
    category: Optional[str] = Field(default=None, description="Domain category: Arch")
    check_category: Optional[str] = Field(
        default=None,
        description=(
            "Name of the rule_check_categories entry (e.g. 'Fire and Smoke "
            "Protection') this rule's results are grouped under; null = uncategorized."
        ),
    )
    target_ifc_class: Optional[str] = Field(
        default=None, description="Target IFC entity type (e.g. IfcDoor, IfcWindow), often bSDD-sourced"
    )
    property_set: Optional[str] = None
    property_name: Optional[str] = None
    operator: Optional[str] = Field(default="==", description="Evaluation operator")
    check_value: Optional[str] = None
    value_min: Optional[str] = None
    value_max: Optional[str] = None
    value_min_property: Optional[str] = None
    value_max_property: Optional[str] = None
    value_min_offset: Optional[str] = None
    value_max_offset: Optional[str] = None
    value_min_scale: Optional[str] = None
    value_max_scale: Optional[str] = None
    compare_property: Optional[str] = None
    name_pattern: Optional[str] = None
    uniqueness_scope: Optional[str] = None
    unit: Optional[str] = None
    severity: str = Field(default="recommended", description="Severity (mandatory, recommended)")
    confidence: Optional[str] = None
    extraction_method: Optional[str] = "manual"
    needs_review: int = Field(default=0, description="1 if flag for review")
    applies_when: Optional[dict] = Field(
        default=None,
        description=(
            "Scope predicate narrowing which elements this rule governs "
            "(e.g. {'material_any_of': ['gypsum']}) -- evaluated by "
            "app.modules.comparator against each element; an unrecognised or "
            "untestable key leaves scope UNDETERMINED, never silently narrowed. "
            "Room scope: room_type_any_of / room_type_all_of / room_type_none_of "
            "(types from app.modules.room_types, e.g. {'room_type_any_of': "
            "['bedroom']}) and room_name_any_of match against the rooms the "
            "element connects to; an untyped or unlinked room leaves it "
            "UNDETERMINED."
        ),
    )
    exceptions: Optional[list] = Field(
        default=None,
        description=(
            "Waiver predicates that excuse an otherwise-failing element, each "
            "referencing another rule's applies_when by reference. See "
            "app.modules.comparator._waiver_for."
        ),
    )
    rase_requirement: Optional[str] = Field(default=None, description="Regulatory text representing the core obligation")
    rase_applicability: Optional[dict] = Field(default=None, description="Condition defining when the requirement applies")
    rase_selection: Optional[dict] = Field(default=None, description="Criteria for selecting specific targets")
    rase_exception: Optional[dict] = Field(default=None, description="Condition excusing the requirement")
    kg_candidate_used: Optional[str] = Field(
        default=None,
        description=(
            "uri of the clause-grounding knowledge-graph candidate the "
            "extraction LLM was shown and picked for target_ifc_class, if "
            "any -- extraction-time audit signal only (see "
            "llamaindex_rule_generator._LLMRuleCandidate.kg_candidate_used); "
            "not written to public.rules on promotion."
        ),
    )

class RuleUpdateRequest(BaseModel):
    """Payload for updating an existing rule."""

    description: Optional[str] = None
    target_ifc_class: Optional[str] = None
    property_set: Optional[str] = None
    property_name: Optional[str] = None
    operator: Optional[str] = None
    check_value: Optional[str] = None
    value_min: Optional[str] = None
    value_max: Optional[str] = None
    value_min_property: Optional[str] = None
    value_max_property: Optional[str] = None
    value_min_offset: Optional[str] = None
    value_max_offset: Optional[str] = None
    value_min_scale: Optional[str] = None
    value_max_scale: Optional[str] = None
    compare_property: Optional[str] = None
    name_pattern: Optional[str] = None
    uniqueness_scope: Optional[str] = None
    unit: Optional[str] = None
    severity: Optional[str] = None
    needs_review: Optional[int] = None
    category: Optional[str] = None
    check_category: Optional[str] = Field(
        default=None,
        description="Check category name; omit to leave unchanged, '' to clear.",
    )
    applies_when: Optional[dict] = Field(
        default=None,
        description=(
            "Replaces the rule's whole scope predicate when supplied ({} clears "
            "it); omit to leave the scope unchanged. See RuleCreateRequest."
        ),
    )
    rase_requirement: Optional[str] = None
    rase_applicability: Optional[dict] = None
    rase_selection: Optional[dict] = None
    rase_exception: Optional[dict] = None

class RuleResponse(TimestampFields):
    """Detailed response model for a rule."""

    id: int
    rule_id: Optional[str] = None
    description: Optional[str] = None
    source_text: Optional[str] = None
    source_document_id: Optional[int] = Field(
        default=None, description="FK to documents.id — the document this rule was extracted from, when known"
    )
    source_node_id: Optional[str] = Field(
        default=None, description="Links back to the originating DocumentNodeContract.node_id, when known"
    )
    source_element_id: Optional[str] = Field(
        default=None, description="Matches DocumentElementBbox.element_id -- the exact structural element this rule was extracted from, when known"
    )
    source_page_number: Optional[int] = Field(
        default=None, description="1-based source page number, when known"
    )
    source_bbox: Optional[dict[str, Any]] = Field(
        default=None, description="Bounding box on that page: {l, t, r, b, coord_origin}"
    )
    mechanism: Optional[str] = None
    ruleset_id: Optional[str] = None
    rule_category: Optional[str] = None
    category: Optional[str] = Field(default="Arch", description="Domain category: Arch")
    check_category: Optional[str] = Field(
        default=None,
        description=(
            "Name of the rule_check_categories entry (e.g. 'Fire and Smoke "
            "Protection') this rule's results are grouped under; null = uncategorized."
        ),
    )
    target_ifc_class: Optional[str] = Field(
        default=None, description="Target IFC entity type (e.g. IfcDoor, IfcWindow)"
    )
    property_set: Optional[str] = None
    property_name: Optional[str] = None
    operator: Optional[str] = None
    check_value: Optional[str] = None
    value_min: Optional[str] = None
    value_max: Optional[str] = None
    value_min_property: Optional[str] = None
    value_max_property: Optional[str] = None
    value_min_offset: Optional[str] = None
    value_max_offset: Optional[str] = None
    value_min_scale: Optional[str] = None
    value_max_scale: Optional[str] = None
    compare_property: Optional[str] = None
    name_pattern: Optional[str] = None
    uniqueness_scope: Optional[str] = None
    unit: Optional[str] = None
    severity: Optional[str] = "recommended"
    confidence: Optional[str] = None
    extraction_method: Optional[str] = None
    needs_review: Optional[int] = 0
    applies_when: Optional[dict] = Field(
        default=None,
        description=(
            "Scope predicate narrowing which elements the rule governs, e.g. "
            "{'room_type_any_of': ['bedroom']}; null when the rule has none."
        ),
    )
    rase_requirement: Optional[str] = None
    rase_applicability: Optional[dict] = None
    rase_selection: Optional[dict] = None
    rase_exception: Optional[dict] = None

    @field_validator("applies_when", mode="before")
    @classmethod
    def _decode_applies_when(cls, value: Any) -> Any:
        """Decode the JSON object string a rules row stores; an empty scope is null."""
        if isinstance(value, str):
            try:
                value = json.loads(value) if value.strip() else None
            except ValueError:
                return None
        return value or None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def reliability(self) -> Optional[RuleReliability]:
        """Reliability of this rule, or null when it names no IFC property."""
        return build_rule_reliability(self)

class RuleDraftStatus(str, Enum):
    """Review lifecycle state for a LlamaIndex-extracted rule candidate."""

    pending_review = "pending_review"
    accepted = "accepted"
    rejected = "rejected"
    edited = "edited"

class RuleExtractionDraft(BaseModel):
    """A single extracted rule candidate awaiting human review before promotion."""

    id: Optional[int] = None
    source_document_id: int
    source_node_id: Optional[str] = Field(default=None, description="Links back to DocumentNodeContract.node_id")
    source_element_id: Optional[str] = Field(
        default=None, description="Matches DocumentElementBbox.element_id -- the exact structural element this draft was extracted from, when known"
    )
    original_source_element_id: Optional[str] = Field(
        default=None,
        description=(
            "The element_id the LLM originally linked this draft to, captured only when a "
            "reviewer relinks it to a different element -- preserves what the model originally "
            "picked so localization accuracy can be scored the same way rule-content edits are, "
            "via original_proposed_rule. Null otherwise."
        ),
    )
    source_snippet: Optional[str] = Field(
        default=None, description="The originating node's text, carried forward for promotion into rules.source_text"
    )
    clause: Optional[ClauseMetadata] = None
    bbox: Optional[dict[str, Any]] = Field(
        default=None, description="Bounding box coordinates on the page: {l, t, r, b, coord_origin}"
    )
    proposed_rule: RuleCreateRequest
    original_proposed_rule: Optional[RuleCreateRequest] = Field(
        default=None,
        description=(
            "The LLM's proposed_rule as first extracted, captured only when a "
            "reviewer edits it (status=edited) -- preserves the pre-edit "
            "version so `proposed_rule` can carry the correction without "
            "losing what the model originally produced. Null otherwise."
        ),
    )
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    extraction_method: Literal["llamaindex_pydantic", "litellm_legacy"] = "litellm_legacy"
    status: RuleDraftStatus = RuleDraftStatus.pending_review
    reviewer_email: Optional[str] = None
    reviewed_at: Optional[str] = None
    review_notes: Optional[str] = None
    created_at: Optional[str] = None
    conflicts: list[RuleConflictWarning] = Field(
        default_factory=list,
        description="Cross-rule or cross-draft conflicts detected for this candidate.",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def reliability(self) -> Optional[RuleReliability]:
        """Reliability of the proposed rule; follows a reviewer's edits because it reads ``proposed_rule``."""
        return build_rule_reliability(self.proposed_rule)

class RuleExtractionDraftListResponse(BaseModel):
    """List of extraction drafts for a document."""

    drafts: list[RuleExtractionDraft]

class RuleAlignmentIssue(BaseModel):
    """One ontology-vocabulary mismatch found on a rule's target class/property.

    See app.services.rule_semantic_alignment_service.AlignmentIssue.
    """

    field: str = Field(description="'target_ifc_class' | 'property_name' | 'property_set'")
    severity: str = Field(description="'blocking' | 'warning'")
    message: str
    suggestion: Optional[str] = None

class RuleConflictWarning(BaseModel):
    """A rule or draft whose constraint is jointly unsatisfiable or in discrepancy with candidate's.

    See app.services.rule_semantic_alignment_service.ConflictWarning.
    """

    conflicting_rule_id: Optional[int] = None
    conflicting_draft_id: Optional[int] = None
    conflicting_reference: str
    conflict_type: Literal[
        "mutually_exclusive_range",
        "threshold_mismatch",
        "exact_value_mismatch",
        "scope_precedence_clash",
    ] = "mutually_exclusive_range"
    severity: Literal["critical", "warning", "caution"] = "warning"
    message: str
    resolution_suggestion: Optional[str] = None
    conflicting_details: Optional[dict[str, Any]] = None

class RuleDraftConflictDetectionRequest(BaseModel):
    """Request to analyze conflicts across a set of rule drafts or an entire document/ruleset."""

    draft_ids: Optional[list[int]] = None
    document_id: Optional[int] = None
    ruleset_id: Optional[str] = None
    include_threshold_discrepancies: bool = True

class RuleDraftConflictDetectionResponse(BaseModel):
    """Response summarizing detected cross-rule or cross-draft conflicts."""

    total_drafts_analyzed: int
    total_conflicts_found: int
    drafts_with_conflicts: list[RuleExtractionDraft]

class RulePromotionResponse(RuleResponse):
    """`RuleResponse` plus the semantic-alignment outcome of promoting it.

    Non-persisted: `alignment_issues`/`conflicts` are only ever populated on
    the promote-draft response, never read back off `public.rules`.
    """

    alignment_issues: list[RuleAlignmentIssue] = Field(default_factory=list)
    conflicts: list[RuleConflictWarning] = Field(default_factory=list)

class DraftSourceSummary(BaseModel):
    """Draft shape for the rule-source map's Drafts tab.

    Carries the full ``proposed_rule`` (not just a description) so the map
    can render it as a structured panel side by side with the rendered
    source document, without a second per-draft fetch.
    """

    id: int
    status: RuleDraftStatus
    rule_id: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    confidence: float = 0.8
    extraction_method: str = "litellm_legacy"
    source_page_number: Optional[int] = None
    source_bbox: Optional[dict[str, Any]] = None
    source_element_id: Optional[str] = None
    match_status: Literal["exact", "unmapped", "orphaned"] = "unmapped"
    proposed_rule: Optional[RuleCreateRequest] = None

class DocumentElementWithDrafts(DocumentElementBbox):
    """One document element annotated with the pending draft(s) extracted from it."""

    drafts: list[DraftSourceSummary] = Field(default_factory=list)

class DraftSourceMapResponse(BaseModel):
    """Every pending extraction draft for a document, mapped against its exact source element.

    Same three-way split as `RuleSourceMapResponse` (`unmapped_drafts`/`orphaned_drafts`),
    for drafts instead of promoted rules.
    """

    document_id: int
    elements: list[DocumentElementWithDrafts] = Field(default_factory=list)
    unmapped_drafts: list[DraftSourceSummary] = Field(default_factory=list)
    orphaned_drafts: list[DraftSourceSummary] = Field(default_factory=list)

class RuleDraftExtractionRequest(BaseModel):
    """Optional body for POST .../rules/extract-drafts.

    ``text``, when provided, scopes extraction to a caller-chosen subset of
    the document (e.g. one or more sections picked in the UI) instead of its
    full DocLang-derived text.
    """

    text: Optional[str] = None

class RuleExtractionProgressResponse(BaseModel):
    """Poll target for an in-flight or recently finished draft extraction.

    ``status`` is ``"unknown"`` when nothing has ever run for this document
    id (or the last run's entry expired) -- not an error, just "no data".
    """

    document_id: int
    total: int = 0
    completed: int = 0
    status: Literal["running", "complete", "failed", "unknown"] = "unknown"
    error: Optional[str] = None

class RuleSourceResponse(BaseModel):
    """Resolved document-viewer target for a rule's source annotation."""

    document_id: int
    filename: str
    page_number: Optional[int] = Field(
        default=None, description="Best-matching page for the rule's source_text, when the document has page-tagged text"
    )
    snippet: str = Field(default="", description="The rule's source_text, for text-layer highlighting")
    bbox: Optional[dict[str, Any]] = Field(
        default=None, description="Bounding box coordinates on the page for visual halo highlighting: {l, t, r, b, coord_origin}"
    )
    source_element_id: Optional[str] = Field(
        default=None, description="Matches DocumentElementBbox.element_id, for exact-element overlay highlighting, when known"
    )

class RuleShaclShapeResponse(BaseModel):
    """A rule's compiled W3C SHACL shape, for the Rule Inspection Studio."""

    rule_id: int
    eligible: bool = Field(
        ..., description="Whether this rule's requirement can be expressed as a SHACL shape at all"
    )
    turtle: str = Field(
        default="", description="The compiled shape, Turtle-serialized. Empty when not eligible."
    )
    reason: Optional[str] = Field(
        default=None,
        description="Why the rule is not SHACL-eligible, when eligible is False",
    )

class RuleDraftReviewRequest(BaseModel):
    """Payload for reviewing (accepting/rejecting/editing) one extraction draft."""

    status: RuleDraftStatus
    review_notes: Optional[str] = None
    reviewer_email: Optional[str] = None
    edited_rule: Optional[RuleCreateRequest] = Field(
        default=None, description="Required when status == edited"
    )

class DraftRelinkRequest(BaseModel):
    """Payload for correcting which document element an extraction draft is linked to."""

    element_id: str = Field(..., description="A DocumentElementBbox.element_id from the draft's source document")

class RuleFolderResponse(BaseModel):
    """Grouped folder / ruleset model."""

    id: Optional[int] = None
    ruleset_id: str
    display_name: str
    description: Optional[str] = ""
    mechanism_scope: Optional[str] = ""
    category: str = Field(default="Arch", description="Ruleset category: Arch")
    rules: list[RuleResponse] = Field(default_factory=list)

class RuleFolderCreateRequest(BaseModel):
    """Payload for creating a new ruleset folder."""

    ruleset_id: str = Field(..., description="Unique ruleset identifier")
    display_name: Optional[str] = Field(default=None, description="Display name")
    description: Optional[str] = Field(default="", description="Description")
    mechanism_scope: Optional[str] = Field(default="", description="Mechanism scope (e.g. CODE, IFC)")
    category: str = Field(default="Arch", description="Ruleset category: Arch")

class RuleFolderUpdateRequest(BaseModel):
    """Payload for updating an existing ruleset folder."""

    display_name: Optional[str] = None
    description: Optional[str] = None
    mechanism_scope: Optional[str] = None
    category: Optional[str] = None

class RuleBulkUpdateRequest(BaseModel):
    """Payload for updating multiple rules in bulk."""

    rule_ids: list[int] = Field(..., min_length=1, description="Rule IDs to update")
    ruleset_id: Optional[str] = Field(default=None, description="Assign to ruleset folder")
    category: Optional[str] = Field(default=None, description="Domain category: Arch")
    mechanism: Optional[str] = Field(default=None, description="Mechanism: CODE, IFC")
    severity: Optional[str] = Field(default=None, description="Severity: Critical, High, Medium, Low")
    needs_review: Optional[int] = Field(default=None, description="Needs review flag: 0 or 1")
    property_set: Optional[str] = Field(default=None, description="Property set name")
    check_category: Optional[str] = Field(
        default=None, description="Check category name to assign; '' clears it"
    )

class RuleCheckCategoryResponse(BaseModel):
    """One entry of the ordered check-category list (rule_check_categories)."""

    id: int
    name: str
    description: str = Field(default="", description="What rules in this category test")
    target_ifc_class: Optional[str] = Field(
        default=None, description="Element type the category groups (e.g. IfcWindow); null = every type"
    )
    sort_order: int = 0

class RuleBulkDeleteRequest(BaseModel):
    """Payload for deleting multiple rules in bulk."""

    rule_ids: list[int] = Field(..., min_length=1, description="Rule IDs to delete")

class RuleBulkActionResponse(BaseModel):
    """Response returned after executing a bulk rule operation."""

    success_count: int
    affected_ids: list[int] = Field(default_factory=list)

class RuleFolderBulkUpdateRequest(BaseModel):
    """Payload for updating multiple ruleset folders in bulk."""

    ruleset_ids: list[str] = Field(..., min_length=1, description="Ruleset IDs to update")
    category: Optional[str] = Field(default=None, description="Domain category: Arch")
    mechanism_scope: Optional[str] = Field(default=None, description="Mechanism scope")

class RuleFolderBulkDeleteRequest(BaseModel):
    """Payload for deleting multiple ruleset folders in bulk."""

    ruleset_ids: list[str] = Field(..., min_length=1, description="Ruleset IDs to delete")

class RuleFolderBulkActionResponse(BaseModel):
    """Response returned after executing a bulk ruleset folder operation."""

    success_count: int
    affected_ruleset_ids: list[str] = Field(default_factory=list)
    deleted_rules_count: int = 0

class RuleSnapshotCreateRequest(BaseModel):
    """Payload for freezing a ruleset's current rules into a named snapshot."""

    ruleset_id: str = Field(..., description="Ruleset/folder to snapshot")
    name: Optional[str] = Field(default=None, description="Display name; defaults to ruleset_id")
    source_mode: Optional[Literal["pdf", "ids", "manual", "mixed"]] = Field(
        default="manual", description="How the snapshotted rules originated"
    )
    notes: Optional[str] = None
    created_by: Optional[str] = None

class RuleSnapshotResponse(BaseModel):
    """A persisted, frozen rule-configuration snapshot (configuration only, no analysis results)."""

    id: int
    name: str
    source_ruleset_id: str
    source_mode: str
    category: str
    rule_count: int
    notes: Optional[str] = ""
    created_at: Optional[str] = None
    created_by: Optional[str] = ""

class IdsImportResponse(BaseModel):
    """Result of importing rules from an uploaded buildingSMART IDS file."""

    success: bool
    created_count: int
    total_parsed: int
    ruleset_id: str

class RuleExtractionResponse(BaseModel):
    """Rules extracted from an uploaded document or raw text via LLM."""

    rules: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    count: int

class RuleSeedResponse(BaseModel):
    """Outcome of (re)seeding the platform's built-in engine rulesets."""

    success: bool
    seeded_rulesets: dict[str, int] = Field(default_factory=dict)
    total_rules: int

class RuleBulkCreateResponse(BaseModel):
    """Outcome of a bulk compliance-rule insert."""

    success: bool
    created_count: int
    total_requested: int

class RuleFolderDeleteResponse(BaseModel):
    """Outcome of deleting a ruleset folder and its member rules."""

    success: bool
    ruleset_id: str
    deleted_rules: int
