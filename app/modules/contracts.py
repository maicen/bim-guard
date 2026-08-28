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


# ---------------------------------------------------------------------------
# Project Contracts
# ---------------------------------------------------------------------------


class ProjectCreateRequest(BaseModel):
    """Payload for creating a new project via the API."""

    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(default="", description="Project description")
    status: str = Field(default="Draft", description="Workflow status (e.g. Draft, Active)")
    country: str = Field(default="US", description="Regulatory jurisdiction or country code")
    analysis_type: str = Field(default="Architecture", description="Target analysis domain")


class ProjectUpdateRequest(BaseModel):
    """Payload for updating an existing project."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = None
    country: Optional[str] = None
    analysis_type: Optional[str] = None


class ProjectResponse(BaseModel):
    """Detailed response model for a project."""

    id: int
    name: str
    description: Optional[str] = ""
    status: Optional[str] = "Draft"
    country: Optional[str] = "US"
    analysis_type: Optional[str] = "Architecture"
    ifc_file_path: Optional[str] = None
    ifc_md5_hash: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ProjectListResponse(BaseModel):
    """Paginated or listed collection of projects."""

    total: int = Field(..., description="Total number of projects")
    projects: list[ProjectResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Rule & Ruleset Contracts
# ---------------------------------------------------------------------------


class RuleCreateRequest(BaseModel):
    """Payload for creating or registering a rule."""

    rule_id: str = Field(..., description="Unique rule identifier (e.g. GC-001.01)")
    description: Optional[str] = Field(default="", description="Rule human description")
    mechanism: Optional[str] = Field(default="CODE", description="Domain or mechanism (e.g. GC-001, CODE)")
    ruleset_id: Optional[str] = Field(default=None, description="Group or folder ruleset identifier")
    rule_category: Optional[str] = Field(default="property_check", description="Rule classification")
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
    compare_property: Optional[str] = None
    name_pattern: Optional[str] = None
    uniqueness_scope: Optional[str] = None
    unit: Optional[str] = None
    severity: str = Field(default="recommended", description="Severity (mandatory, recommended)")
    confidence: Optional[str] = None
    extraction_method: Optional[str] = "manual"
    needs_review: int = Field(default=0, description="1 if flag for review")


class RuleUpdateRequest(BaseModel):
    """Payload for updating an existing rule."""

    description: Optional[str] = None
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
    compare_property: Optional[str] = None
    name_pattern: Optional[str] = None
    uniqueness_scope: Optional[str] = None
    unit: Optional[str] = None
    severity: Optional[str] = None
    needs_review: Optional[int] = None


class RuleResponse(BaseModel):
    """Detailed response model for a rule."""

    id: int
    rule_id: Optional[str] = None
    description: Optional[str] = None
    source_text: Optional[str] = None
    mechanism: Optional[str] = None
    ruleset_id: Optional[str] = None
    rule_category: Optional[str] = None
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
    compare_property: Optional[str] = None
    name_pattern: Optional[str] = None
    uniqueness_scope: Optional[str] = None
    unit: Optional[str] = None
    severity: Optional[str] = "recommended"
    confidence: Optional[str] = None
    extraction_method: Optional[str] = None
    needs_review: Optional[int] = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class RuleFolderResponse(BaseModel):
    """Grouped folder / ruleset model."""

    id: Optional[int] = None
    ruleset_id: str
    display_name: str
    description: Optional[str] = ""
    mechanism_scope: Optional[str] = ""
    rules: list[RuleResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Analysis & Finding Contracts
# ---------------------------------------------------------------------------


class CitationContract(BaseModel):
    """Regulatory standard citation and clause rationale."""

    standard: str = Field("", description="Standard reference, e.g. NASA-STD-6012 or EN 1998-1")
    clause: str = Field("", description="Specific clause or table, e.g. Table 2 or Clause 4.3")
    reason: str = Field("", description="Regulatory requirement or threshold rationale")


class AuditIssueContract(BaseModel):
    """Individual compliance violation or issue finding."""

    id: str = Field(..., description="Finding identifier (e.g. BGR-0001)")
    element_id: str = Field(..., description="Target IFC element GlobalId")
    rule_id: str = Field(..., description="Evaluated rule ID")
    title: str = Field(..., description="Short finding summary")
    band: str = Field(default="low", description="Risk band: critical, high, medium, low")
    score: float = Field(default=0.0, description="Risk score 0.0 to 1.0")
    mechanism: str = Field(default="", description="Evaluated mechanism label")
    description: str = Field(default="", description="Detailed issue description")
    mitigation: str = Field(default="", description="Remediation guidance")
    assignee_role: str = Field(default="BIM coordinator", description="Assigned role for resolution")
    citations: list[CitationContract] = Field(default_factory=list, description="White Box audit citations")
    details: dict[str, Any] = Field(default_factory=dict, description="Metadata and position info")


class IssueStatsContract(BaseModel):
    """Statistical summary of issue findings by severity band."""

    total: int = 0
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    data_quality: int = 0


class AnalysisRunRequest(BaseModel):
    """Request to trigger compliance analysis."""

    project_id: int = Field(..., description="Target project ID")
    slug: str = Field(default="corrosion", description="Analysis type slug (corrosion, seismic)")
    rule_ids: Optional[list[str]] = Field(default=None, description="Optional rule subset to evaluate")
    use_cache: bool = Field(default=True, description="Whether to use cached analysis results")


class AnalysisInputItemContract(BaseModel):
    """Project standard or client document analysis input."""

    kind: str = Field(..., description="standard or document")
    id: str = Field(..., description="Prefixed identifier")
    label: str = Field(..., description="Name or filename")
    detail: str = Field("", description="Domain or document category")
    file_path: str = Field("", description="Storage reference")


class ComplianceSummaryContract(BaseModel):
    """Evidence metrics and check-time summary from compliance reporting."""

    total_rules: int = 0
    passed: int = 0
    failed: int = 0
    missing_data: int = 0
    no_elements: int = 0
    mandatory_failed: int = 0
    pass_rate: float = 0.0
    duration_seconds: Optional[float] = None
    elements_evaluated: int = 0
    unique_elements_evaluated: int = 0
    rules_with_elements: int = 0
    by_target: dict[str, Any] = Field(default_factory=dict)


class AnalysisResultContract(BaseModel):
    """Composite analysis result returned by analysis runners."""

    pipeline: str = Field(default="audit", description="Pipeline identifier")
    project_id: int
    slug: str = "corrosion"
    element_count: int = 0
    audit_issues: list[AuditIssueContract] = Field(default_factory=list)
    issue_stats: IssueStatsContract = Field(default_factory=IssueStatsContract)
    compliance_error: Optional[str] = None
    compliance_is_demo: bool = False
    cached: bool = False
    duration_seconds: Optional[float] = None
    elements_evaluated: Optional[int] = None
    unique_elements_evaluated: Optional[int] = None
    rules_with_elements: Optional[int] = None
    pass_rate: Optional[float] = None
    bcf_artifact_id: Optional[int] = None
    summary: Optional[dict[str, Any]] = None


class ArchAnalysisResponse(BaseModel):
    """Architectural compliance analysis response model."""

    project_id: int
    project_name: str
    categories: dict[str, Any] = Field(default_factory=dict)
    total_issues: int = 0
    issues: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    rule_compliance_summary: dict[str, Any] = Field(default_factory=dict)
    bcf_artifact_id: Optional[int] = None
    building_summary: dict[str, Any] = Field(default_factory=dict)
    spatial_checks: dict[str, Any] = Field(default_factory=dict)
    egress_checks: dict[str, Any] = Field(default_factory=dict)
    rule_compliance: list[dict[str, Any]] = Field(default_factory=list)
    rule_folder: Optional[str] = None
    ifc_element_count: Optional[int] = 0


# ---------------------------------------------------------------------------
# Workflow Status & Live Pipeline Contracts
# ---------------------------------------------------------------------------


class StageRecordContract(BaseModel):
    """Record of a single pipeline execution stage."""

    stage: int
    name: str
    duration_seconds: Optional[float] = None


class EngineRunContract(BaseModel):
    """Live progress and status of an individual compliance engine."""

    code: str = ""
    label: str = ""
    status: str = Field(..., description="pending, running, complete, failed, not_implemented")
    engine_name: Optional[str] = None
    current_stage: Optional[int] = None
    stage_name: Optional[str] = None
    progress_percent: int = 0
    total_stages: int = 6
    metrics: dict[str, Any] = Field(default_factory=dict)
    stages: list[StageRecordContract] = Field(default_factory=list)
    error: Optional[str] = None



class WorkflowStatusContract(BaseModel):
    """Overall workflow snapshot for a project."""

    project_id: int
    status: str = Field(default="pending", description="Overall project analysis state")
    engines: dict[str, Any] = Field(default_factory=dict)
    timestamp: Optional[str] = None


class PipelineEventContract(BaseModel):
    """Real-time event emitted during pipeline execution for SSE streaming."""

    event_type: str = Field(..., description="stage_transition, metric_increment, completed, failed")
    source_module: str = Field(..., description="Engine or driver identifier")
    project_id: int
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: str


class DashboardStatsResponse(BaseModel):
    """System-level dashboard metrics and database health."""

    total_projects: int = Field(0, description="Total registered projects")
    total_documents: int = Field(0, description="Total processed documents")
    total_rules: int = Field(0, description="Total active compliance rules")
    issues_found: int = Field(34, description="Count of identified non-compliances")
    db_ok: bool = Field(True, description="Database connection health status")
    db_backend: str = Field("SUPABASE", description="Primary database backend (SUPABASE)")


class SettingItemContract(BaseModel):
    """Single application runtime configuration setting."""

    key: str = Field(..., description="Configuration key")
    value: str = Field(..., description="Configuration value")
    description: str = Field("", description="Setting purpose or documentation")


class SettingsResponseContract(BaseModel):
    """Response container for runtime settings and active database backend."""

    settings: list[SettingItemContract] = Field(default_factory=list)
    active_log_level: str = Field("INFO", description="Current logging level")
    db_backend: str = Field("SUPABASE", description="Active database backend")


class SettingsUpdateRequestContract(BaseModel):
    """Payload for batch updating application settings."""

    settings: dict[str, str] = Field(..., description="Map of setting key to new value")



