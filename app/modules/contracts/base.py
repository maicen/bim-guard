"""Core ISO 19650 governance, timestamp fields, enums, and legacy element contracts."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

__all__ = ['ElementDataContract', 'RuleContract', 'ComplianceFailureContract', 'RuleValidationContract', 'ReportPayloadContract', 'CDEState', 'ExchangeDisposition', 'PROJECT_CODE_MIN_LENGTH', 'PROJECT_CODE_MAX_LENGTH', 'PROJECT_CODE_PATTERN', 'SHORT_NAME_MIN_LENGTH', 'SHORT_NAME_MAX_LENGTH', 'IsoGovernanceFieldsRequired', 'IsoGovernanceFieldsOptional', 'TimestampFields', 'ISO19650Metadata', 'HealthCheckResponse', 'ErrorResponse']

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

class CDEState(str, Enum):
    """ISO 19650 Common Data Environment (CDE) Workflow States."""

    WIP = "WIP"
    SHARED = "SHARED"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"

class ExchangeDisposition(str, Enum):
    """ISO 19650-4 formal information exchange disposition.

    Combines the four-tier verification/validation pipeline (Tier 1
    syntactic, Tier 2 IDS/schema, Tier 3 semantic/bSDD, Tier 4 engineering
    compliance) into one authoritative verdict:
    - REJECTED: a Tier 1 parsing failure or a critical Tier 2 IDS failure.
    - ACCEPTED_WITH_COMMENTS: Tier 1/2 pass, but Tier 3 or Tier 4 raised
      non-critical warnings that must be tracked before the next milestone.
    - ACCEPTED: every tier passed without exception.
    """

    REJECTED = "REJECTED"
    ACCEPTED_WITH_COMMENTS = "ACCEPTED_WITH_COMMENTS"
    ACCEPTED = "ACCEPTED"

#: ISO 19650 container naming keeps the project code segment short --
#: 2-6 uppercase/lowercase alphanumeric characters, no separators (the
#: hyphen is the field delimiter itself; see iso_validator.py).
PROJECT_CODE_MIN_LENGTH = 2

PROJECT_CODE_MAX_LENGTH = 6

PROJECT_CODE_PATTERN = r"^[A-Za-z0-9]+$"

#: The short name is a human-readable nickname (not an ISO 19650 field), kept
#: short enough to fit in the header and breadcrumbs that now display it
#: instead of the full project name.
SHORT_NAME_MIN_LENGTH = 2

SHORT_NAME_MAX_LENGTH = 24

class IsoGovernanceFieldsRequired(BaseModel):
    """ISO 19650/CDE metadata block shared by response-style models.

    `project_code` is excluded -- its required-ness and validation constraints
    vary by call site.
    """

    originator: Optional[str] = Field(default="", description="ISO 19650 Originator Code")
    volume_system: Optional[str] = Field(default="", description="ISO 19650 Volume/System Breakdown")
    level: Optional[str] = Field(default="", description="ISO 19650 Level/Location Breakdown")
    type: Optional[str] = Field(default="", description="ISO 19650 Type Code")
    role: Optional[str] = Field(default="", description="ISO 19650 Role/Discipline Code")
    number: Optional[str] = Field(default="", description="ISO 19650 Sequential Number")
    suitability_code: Optional[str] = Field(default="S0", description="ISO 19650 Suitability Code (S0-S4, A1-A4)")
    revision_code: Optional[str] = Field(default="P01.01", description="ISO 19650 Revision Code (P01.01, C01)")
    cde_state: CDEState = Field(default=CDEState.WIP, description="CDE State (WIP, SHARED, PUBLISHED, ARCHIVED)")

class IsoGovernanceFieldsOptional(BaseModel):
    """Same ISO 19650/CDE fields as `IsoGovernanceFieldsRequired`, all-None for partial-update payloads."""

    project_code: Optional[str] = None
    originator: Optional[str] = None
    volume_system: Optional[str] = None
    level: Optional[str] = None
    type: Optional[str] = None
    role: Optional[str] = None
    number: Optional[str] = None
    suitability_code: Optional[str] = None
    revision_code: Optional[str] = None
    cde_state: Optional[CDEState] = None

class TimestampFields(BaseModel):
    """Shared `created_at`/`updated_at` pair for response models."""

    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class ISO19650Metadata(BaseModel):
    """ISO 19650 UK National Annex container naming & suitability fields."""

    project_code: str = Field(default="", description="Project code string (e.g. PRJ)")
    originator: str = Field(default="", description="Authoring organization code (e.g. BIMG)")
    volume_system: str = Field(default="", description="Volume or spatial breakdown code (e.g. ZZ, 01)")
    level: str = Field(default="", description="Level / location breakdown (e.g. ZZ, 00)")
    type: str = Field(default="", description="Document / Model type code (e.g. M3, DR)")
    role: str = Field(default="", description="Discipline role code (e.g. A, S, M)")
    number: str = Field(default="", description="Sequential document number (e.g. 0001)")
    suitability_code: str = Field(default="S0", description="ISO 19650 suitability code (S0-S4, A1-A4, B1-B4)")
    revision_code: str = Field(default="P01.01", description="ISO 19650 revision code (e.g. P01.01, C01)")
    cde_state: CDEState = Field(default=CDEState.WIP, description="CDE state (WIP, SHARED, PUBLISHED, ARCHIVED)")
    cde_approved_by: Optional[str] = Field(default="", description="Lead appointed party approver")
    cde_approved_at: Optional[str] = Field(default=None, description="ISO timestamp of CDE approval")

class HealthCheckResponse(BaseModel):
    """API gateway liveness/readiness probe result."""

    status: str
    service: str
    version: str
    graph_backend: str = Field(
        "none",
        description=(
            "Which GraphDatabaseProvider is actually backing graph_service: "
            "'neo4j', 'kuzu', or 'none' if neither initialized. Informational "
            "only -- a broken graph backend does not fail this health check, "
            "since compliance/rules/documents work independently of it."
        ),
    )

class ErrorResponse(BaseModel):
    """Standard shape for every error response raised via HTTPException."""

    detail: str = Field(..., description="Human-readable error message")
    code: int = Field(..., description="HTTP status code")
