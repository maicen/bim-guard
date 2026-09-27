"""buildingSMART Data Dictionary (bSDD) properties, classes, and semantic matching contracts."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

__all__ = ['BSDDPropertyItem', 'BSDDClassItem', 'SemanticMatchRequest', 'SemanticMatchResponse', 'BSDDDictionaryItem', 'BSDDValidationViolation', 'BSDDValidationResult', 'BSDDClassSearchResponse', 'BSDDPropertySearchResponse']

# ==============================================================================
# buildingSMART Ecosystem Contracts
# ==============================================================================


# ------------------------------------------------------------------------------
# 1. bSDD (buildingSMART Data Dictionary) Contracts
# ------------------------------------------------------------------------------


class BSDDPropertyItem(BaseModel):
    """bSDD property definition contract."""

    uri: str = Field(..., description="Unique bSDD URI for the property")
    name: str = Field(..., description="Property name (e.g. FireRating, Material)")
    code: Optional[str] = Field(
        None,
        description=(
            "The dictionary's own machine identifier for this property, when distinct from `name` "
            "-- e.g. clean camelCase 'FireRating' for an IFC 4.3 entry whose `name` is the "
            "human-readable 'Fire Rating'. Some dictionaries (e.g. ACCORD) instead store a raw "
            "GUID here and keep the clean identifier in `name` -- callers that need a real IFC "
            "attribute key to look up on a parsed model should check both, never assume either is "
            "always the safe one."
        ),
    )
    property_set: Optional[str] = Field(None, description="Standard property set name (e.g. Pset_PipeSegmentCommon)")
    data_type: Optional[str] = Field(None, description="IFC or XSD data type (e.g. IfcLabel, IfcReal, IfcBoolean)")
    units: Optional[str] = Field(None, description="Physical units (e.g. mm, m/s, degC)")
    allowed_values: list[str] = Field(default_factory=list, description="List of allowed enumeration values if restricted")
    definition: Optional[str] = Field(
        None, description="What the property actually means (bSDD's `definition` field -- most bSDD properties carry this, not `description`)"
    )
    description: Optional[str] = Field(
        None, description="Supplementary note from bSDD, when distinct from `definition` -- often an implementation/technical remark rather than the meaning itself"
    )

class BSDDClassItem(BaseModel):
    """bSDD class / classification definition contract."""

    uri: str = Field(..., description="Unique bSDD URI for the class")
    code: str = Field(..., description="Class code (e.g. Pr_65_52_63 or IfcPipeSegment)")
    name: str = Field(..., description="Human-readable class name")
    dictionary_uri: str = Field(..., description="URI of the parent dictionary")
    class_type: str = Field(
        "Class", description="bSDD classType (e.g. Class, GroupOfProperties for a Pset_/Qto_ property or quantity set)"
    )
    parent_class_code: Optional[str] = Field(None, description="Parent class code if hierarchical")
    child_class_codes: list[str] = Field(default_factory=list, description="Codes of direct subtypes of this class")
    related_ifc_entities: list[str] = Field(default_factory=list, description="Associated IFC entity types")
    properties: list[BSDDPropertyItem] = Field(default_factory=list, description="Properties defined on this class")
    definition: Optional[str] = Field(
        None, description="What the class actually means (bSDD classes carry `definition`, essentially never `description`)"
    )
    description: Optional[str] = Field(None, description="Supplementary note from bSDD, when distinct from `definition`")

class SemanticMatchRequest(BaseModel):
    """A non-standard local name to resolve against the bSDD ontology via LLM disambiguation."""

    query: str = Field(..., min_length=1, description="The non-standard local class or property name")
    kind: Literal["class", "property"]
    target_ifc_class: Optional[str] = Field(
        default=None, description="For kind='property': the element class this property belongs to, for context only"
    )
    model: Optional[str] = Field(default=None, description="LLM model override; falls back to the configured default")
    organization_id: Optional[int] = Field(
        default=None, description="Resolves the LLM API key from this org's configured provider first"
    )

class SemanticMatchResponse(BaseModel):
    """The best bSDD match for a `SemanticMatchRequest`, or none found."""

    matched: bool
    matched_uri: Optional[str] = None
    matched_code: Optional[str] = None
    confidence: float = 0.0
    reasoning: Optional[str] = None

class BSDDDictionaryItem(BaseModel):
    """bSDD dictionary catalog contract."""

    uri: str = Field(..., description="Unique URI identifying the dictionary")
    code: str = Field(..., description="Short dictionary identifier (e.g. uniclass_2015, omniclass_23)")
    name: str = Field(..., description="Full dictionary name")
    version: str = Field("1.0", description="Dictionary version")
    organization_code_owner: str = Field("buildingSMART", description="Owner organization code")
    language_iso_code: str = Field("en-GB", description="Language code")
    classes_count: int = Field(0, description="Number of classes in dictionary")
    is_curated: bool = Field(False, description="Whether this dictionary is a vetted BIM-Guard curated ontology standard")
    domain: Optional[str] = Field(None, description="Engineering or regulatory domain classification")

class BSDDValidationViolation(BaseModel):
    """Single semantic validation violation detected by bSDD checks."""

    element_guid: str = Field(..., description="IFC GUID of failing element")
    element_type: str = Field(..., description="IFC entity type")
    field_checked: str = Field(..., description="Property, classification, or material checked")
    expected_constraint: str = Field(..., description="Constraint specified by bSDD")
    actual_value: Optional[Any] = Field(None, description="Value extracted from element")
    severity: str = Field("warning", description="Severity (error, warning, info)")
    message: str = Field(..., description="Human-readable violation message")
    dictionary_uri: Optional[str] = Field(None, description="bSDD dictionary reference URI")

class BSDDValidationResult(BaseModel):
    """Aggregated outcome of bSDD semantic validation on model elements."""

    passed: bool = Field(..., description="True if no blocking semantic errors occurred")
    dictionary_uri: str = Field(..., description="bSDD dictionary URI used for verification")
    total_elements_checked: int = Field(0, description="Total elements inspected")
    total_properties_checked: int = Field(0, description="Total property assertions checked")
    passed_count: int = Field(0, description="Count of compliant assertions")
    violations_count: int = Field(0, description="Count of violations found")
    compliance_score_pct: float = Field(100.0, description="Semantic compliance percentage")
    violations: list[BSDDValidationViolation] = Field(default_factory=list, description="List of semantic violations")

class BSDDClassSearchResponse(BaseModel):
    """Response payload for bSDD class text searches."""

    query: str
    total: int = 0
    classes: list[BSDDClassItem] = []

class BSDDPropertySearchResponse(BaseModel):
    """Response payload for bSDD property text searches."""

    query: str
    total: int = 0
    properties: list[BSDDPropertyItem] = []
