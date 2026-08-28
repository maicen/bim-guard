"""Strict Pydantic data contracts for inter-module data exchange."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ElementDataContract(BaseModel):
    """Normalized IFC element data contract passed between parsing and rules engines."""

    global_id: str = Field(..., description="Unique IFC GlobalId")
    ifc_class: str = Field(..., description="IFC entity type name (e.g. IfcPipeSegment)")
    name: Optional[str] = Field(None, description="Element instance name")
    properties: dict[str, Any] = Field(default_factory=dict, description="Property set attributes")
    geometry_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Bounding box or position coordinates"
    )


class RuleContract(BaseModel):
    """Structured compliance rule specification."""

    rule_id: str = Field(..., description="Unique rule identifier")
    rule_desc: str = Field(..., description="Human-readable rule description")
    target: str = Field(..., description="Target IFC class or element group")
    property_name: str = Field(..., description="Property key evaluated")
    expected_value: Any = Field(None, description="Expected target value or regex pattern")
    severity: str = Field("recommended", description="Rule severity (mandatory, recommended)")


class ComplianceFailureContract(BaseModel):
    """Detailed record of a single element compliance failure."""

    guid: str = Field(..., description="GlobalId of failing element")
    reason: str = Field(..., description="Reason for validation failure")
    position_mm: Optional[tuple[float, float, float]] = Field(
        None, description="3D coordinates in mm"
    )


class RuleValidationContract(BaseModel):
    """Result payload from evaluating a rule against elements."""

    rule_ref: str = Field(..., description="Rule ID evaluated")
    rule_desc: str = Field(..., description="Description of rule")
    target: str = Field(..., description="Target IFC class")
    property_name: str = Field(..., description="Property evaluated")
    status: str = Field(..., description="PASS, FAIL, or N/A")
    failures: list[ComplianceFailureContract] = Field(
        default_factory=list, description="List of failing element records"
    )
    severity: str = Field("recommended", description="Severity level")


class ReportPayloadContract(BaseModel):
    """Serialized container payload emitted for BCF and CSV reporting."""

    project_id: int = Field(..., description="Project database ID")
    run_id: str = Field("BGR-RUN", description="Audit or analysis run ID")
    element_count: int = Field(0, description="Total elements evaluated")
    results: list[RuleValidationContract] = Field(
        default_factory=list, description="Rule evaluation results"
    )
    issues: list[dict[str, Any]] = Field(default_factory=list, description="Audit issues list")
    bcf_topics: list[dict[str, Any]] = Field(
        default_factory=list, description="BCF topic structures"
    )

