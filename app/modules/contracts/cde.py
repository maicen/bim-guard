"""Common Data Environment (openCDE), IFC validation, and IDS compliance contracts."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from app.modules.contracts.base import CDEState, ExchangeDisposition

__all__ = ['CDEVersionItem', 'CDEVersionsResponse', 'CDEUserResponse', 'CDEDocumentItem', 'CDESyncRequest', 'CDESyncResponse', 'CDEWebhookPayload', 'IFCValidationIssue', 'IFCValidationStageResult', 'IFCValidationReport', 'IDSRequirementFacet', 'IDSFacetViolation', 'IDSValidationReport', 'IDSExportRequest', 'CDEAuthConfigResponse', 'CDETokenResponse', 'CDEPromoteRequest', 'CDEPromoteResponse']

# ------------------------------------------------------------------------------
# 2. openCDE APIs Contracts
# ------------------------------------------------------------------------------


class CDEVersionItem(BaseModel):
    """OpenCDE API version descriptor entry."""

    version: str = Field(..., description="API version (e.g. 1.0, 2.1)")
    api_type: str = Field(..., description="API family: foundation, documents, or bcf")
    detailed_version: Optional[str] = Field(None, description="Detailed semantic version")

class CDEVersionsResponse(BaseModel):
    """Response returned by GET /api/cde/versions per OpenCDE Foundation API."""

    versions: list[CDEVersionItem] = Field(default_factory=list)

class CDEUserResponse(BaseModel):
    """OpenCDE user profile representation."""

    id: str = Field(..., description="User unique identifier")
    name: str = Field(..., description="Full user or service name")
    email: Optional[str] = Field(None, description="User email address")
    role: Optional[str] = Field("Engineer", description="User role in CDE")

class CDEDocumentItem(BaseModel):
    """OpenCDE Documents API standard document item."""

    id: str = Field(..., description="Document identifier in CDE")
    name: str = Field(..., description="Document filename or title")
    document_type: str = Field("IFC", description="Type: IFC, Specification, Drawing, Report")
    size_bytes: int = Field(0, description="File size in bytes")
    etag: str = Field(..., description="HTTP ETag hash for caching")
    url: Optional[str] = Field(None, description="Direct download URL or storage URI")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last modification timestamp")
    # ISO 19650 metadata attributes
    project_code: str = Field("", description="ISO 19650 Project Code")
    originator: str = Field("", description="ISO 19650 Originator")
    volume_system: str = Field("", description="ISO 19650 Volume/System")
    level: str = Field("", description="ISO 19650 Level")
    type: str = Field("", description="ISO 19650 Type")
    role: str = Field("", description="ISO 19650 Role")
    number: str = Field("", description="ISO 19650 Number")
    suitability_code: str = Field("S0", description="ISO 19650 Suitability Code")
    revision_code: str = Field("P01.01", description="ISO 19650 Revision Code")
    cde_state: CDEState = Field(CDEState.WIP, description="ISO 19650 CDE Workflow State")

class CDESyncRequest(BaseModel):
    """Payload for synchronizing models/documents from an external CDE."""

    cde_server_url: str = Field(..., description="Base URL of external CDE")
    project_id: int = Field(..., description="Target BIMGuard project ID")
    external_project_id: str = Field(..., description="Project ID in external CDE")
    document_ids: list[str] = Field(default_factory=list, description="Specific external document IDs to pull")
    auto_analyze: bool = Field(False, description="Automatically trigger compliance analysis upon sync")
    access_token: str | None = Field(
        None,
        description="Bearer token for the external CDE. Defaults to the caller's own "
        "BIM-Guard access token when omitted -- works when the external CDE validates "
        "the same identity provider (e.g. a self-hosted openCDE test server configured "
        "against this same Supabase project).",
    )

class CDESyncResponse(BaseModel):
    """Outcome of an external CDE synchronization request."""

    success: bool
    synced_documents_count: int = 0
    synced_files: list[str] = []
    errors: list[str] = []
    message: str = ""

class CDEWebhookPayload(BaseModel):
    """Incoming OpenCDE webhook event payload."""

    event_type: str = Field(..., description="Event type: document.created, document.updated, model.published")
    external_project_id: str = Field(..., description="External CDE project ID")
    document_id: str = Field(..., description="External document identifier")
    document_name: str = Field(..., description="Document file name")
    download_url: Optional[str] = Field(None, description="Direct pre-authenticated download URL")
    etag: Optional[str] = Field(None, description="File ETag digest")
    timestamp: Optional[str] = Field(None, description="Event timestamp")

# ------------------------------------------------------------------------------
# 3. IFC Validation Service Pre-Flight Checks Contracts
# ------------------------------------------------------------------------------


class IFCValidationIssue(BaseModel):
    """Single diagnostic issue identified during IFC pre-flight validation."""

    rule_code: str = Field(..., description="Validation rule code (e.g. IFC-SYN-001, IFC-VAL-002)")
    stage: str = Field(..., description="Validation stage: syntax, schema, or gherkin_rules")
    severity: str = Field("error", description="Severity: fatal, error, warning, info")
    message: str = Field(..., description="Diagnostic description")
    line_number: Optional[int] = Field(None, description="Line number in IFC STEP physical file if applicable")
    entity_id: Optional[str] = Field(None, description="IFC Step entity ID (#123) or GlobalId")

class IFCValidationStageResult(BaseModel):
    """Result for one specific validation stage."""

    stage_name: str
    passed: bool
    issues_count: int = 0
    details: list[IFCValidationIssue] = []

class IFCValidationReport(BaseModel):
    """Comprehensive diagnostic report from the IFC Pre-Flight Validation Service."""

    valid: bool = Field(..., description="True if model is safe for heavy compute pipelines")
    schema_version: Optional[str] = Field(None, description="Detected IFC schema (e.g. IFC4, IFC2X3)")
    file_size_bytes: int = Field(0, description="Size of validated file")
    syntax_stage: IFCValidationStageResult
    schema_stage: IFCValidationStageResult
    rules_stage: IFCValidationStageResult
    total_issues: int = 0
    fatal_errors: int = 0
    warnings: int = 0
    summary_message: str = ""

# ------------------------------------------------------------------------------
# 4. IDS (Information Delivery Specification) Contracts
# ------------------------------------------------------------------------------


class IDSRequirementFacet(BaseModel):
    """Specification of a single requirement facet in an IDS specification."""

    facet_type: str = Field("property", description="Facet type: entity, property, classification, material, partOf")
    property_set: Optional[str] = Field(None, description="Property set name (for property facet)")
    name: Optional[str] = Field(None, description="Property name, entity name, or classification system")
    data_type: Optional[str] = Field("IFCLABEL", description="IFC data type")
    expected_value: Optional[Any] = Field(None, description="Target value or pattern")
    operator: str = Field("=", description="Comparison operator: =, !=, >, <, >=, <=, between, exists")
    min_value: Optional[float] = Field(None, description="Lower range bound")
    max_value: Optional[float] = Field(None, description="Upper range bound")
    tolerance: Optional[float] = Field(None, description="Numerical tolerance threshold")
    cardinality: str = Field("required", description="Cardinality: required, optional, prohibited")
    uri: Optional[str] = Field(None, description="Standard URI or bSDD reference")

class IDSFacetViolation(BaseModel):
    """Violation of an individual IDS specification facet."""

    element_guid: str
    element_type: str
    spec_name: str
    facet_type: str
    details: str
    expected: str
    actual: Optional[str] = None

class IDSValidationReport(BaseModel):
    """Report detailing evaluation of IFC elements against IDS requirements."""

    passed: bool
    specifications_count: int = 0
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    compliance_percent: float = 100.0
    violations: list[IDSFacetViolation] = []

class IDSExportRequest(BaseModel):
    """Payload for requesting an IDS XML export for a ruleset."""

    ruleset_id: str
    ifc_version: str = "IFC4"
    include_tolerances: bool = True

class CDEAuthConfigResponse(BaseModel):
    """OpenCDE OAuth2 discovery configuration metadata."""

    oauth2_auth_url: str
    oauth2_token_url: str
    supported_scopes: list[str]
    token_type: str

class CDETokenResponse(BaseModel):
    """OpenCDE OAuth2 Bearer token exchange/refresh result."""

    access_token: str
    token_type: str
    expires_in: int
    scope: str
    grant_type: str

class CDEPromoteRequest(BaseModel):
    """Request payload for CDE gate transition."""

    project_id: int
    actor: Optional[str] = "Lead Appointed Party"
    ruleset_id: Optional[str] = Field(
        None,
        description="Ruleset to run Tier 2 (buildingSMART IDS 1.0) verification against before promotion. "
        "When omitted, Tier 2 is treated as not applicable rather than failed.",
    )

class CDEPromoteResponse(BaseModel):
    """Response payload after CDE gate transition."""

    success: bool
    cde_state: str
    message: str
    disposition: Optional[ExchangeDisposition] = Field(
        None, description="ISO 19650-4 combined exchange disposition evaluated for this promotion"
    )
