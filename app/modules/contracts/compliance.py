"""Multi-stage compliance analysis, audit issues, PDF/Excel reporting, and Revit sync."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

__all__ = ['CitationContract', 'AuditIssueContract', 'IssueStatsContract', 'AnalysisRunRequest', 'AnalysisInputItemContract', 'ComplianceSummaryContract', 'ResultPageContract', 'AnalysisResultContract', 'ArchAnalysisResponse', 'ReportCoverContract', 'ReportTopFailedRuleContract', 'ReportExecutiveSummaryContract', 'ReportScopeContract', 'ReportRulesetResultContract', 'ReportPriorityFindingContract', 'ReportFindingRowContract', 'ReportUnverifiedRowContract', 'ReportRuleRegisterRowContract', 'ReportElementResultRowContract', 'ReportElementTypeSheetContract', 'ReportModel', 'StageRecordContract', 'EngineRunContract', 'WorkflowStatusContract', 'PipelineEventContract', 'RevitSyncElement', 'RevitSyncRequest', 'RevitRuleResult', 'RevitSyncResponse', 'RuleEvaluationRequest', 'RuleEvaluationResult', 'AnalysisQueuedResponse']

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
    slug: str = Field(default="architecture", description="Analysis type slug (architecture)")
    use_cache: bool = Field(default=True, description="Whether to use cached analysis results")
    enable_shacl: bool = Field(default=False, description="Enable SHACL validation side-channel")

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

class ResultPageContract(BaseModel):
    """Window description for a paginated ``audit_issues`` list.

    Present only when the caller sent at least one pagination parameter. A
    request with none returns the whole run and no ``page``, so a consumer
    written before pagination existed sees an unchanged body.

    ``total_matching`` counts the issues left after ``band``/``mechanism``/
    ``include_data_quality`` filtering and before ``offset``/``limit``, which
    is what a pager needs to size itself. It is deliberately unrelated to
    ``issue_stats``, which always describes the whole run.
    """

    limit: Optional[int] = Field(
        default=None, description="Page size requested; None when only filters were sent"
    )
    offset: int = Field(default=0, description="Issues skipped before the page")
    returned: int = Field(default=0, description="Issues in this response")
    total_matching: int = Field(
        default=0, description="Issues matching the filters, before offset/limit"
    )
    has_more: bool = Field(
        default=False, description="True when issues remain after this page"
    )

class AnalysisResultContract(BaseModel):
    """Composite analysis result returned by analysis runners."""

    pipeline: str = Field(default="audit", description="Pipeline identifier")
    project_id: int
    slug: str = "architecture"
    element_count: int = 0
    audit_issues: list[AuditIssueContract] = Field(default_factory=list)
    issue_stats: IssueStatsContract = Field(default_factory=IssueStatsContract)
    compliance_error: Optional[str] = None
    compliance_is_demo: bool = False
    cached: bool = False
    page: Optional[ResultPageContract] = Field(
        default=None,
        description=(
            "Pagination window over audit_issues. Absent unless the request "
            "carried a pagination parameter."
        ),
    )
    duration_seconds: Optional[float] = None
    elements_evaluated: Optional[int] = None
    unique_elements_evaluated: Optional[int] = None
    rules_with_elements: Optional[int] = None
    pass_rate: Optional[float] = None
    bcf_artifact_id: Optional[int] = None
    summary: Optional[dict[str, Any]] = None
    shacl_issues: list[dict[str, Any]] = Field(default_factory=list)
    shacl_error: Optional[str] = None

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
# Compliance Report (PDF / Excel) Contracts
# ---------------------------------------------------------------------------


class ReportCoverContract(BaseModel):
    """Cover-page identity and ISO 19650 metadata for a rendered report."""

    project_name: str
    project_code: str = ""
    model_file_name: str = ""
    report_id: str = Field(..., description="Deterministic id, e.g. BGR-<project_id>-<YYYYMMDDHHMMSS>")
    analysis_date: str = Field(..., description="ISO 8601 date the analysis was run")
    discipline: str = "Architecture"
    ifc_schema: str = ""
    suitability_code: str = ""
    revision_code: str = ""
    cde_state: str = ""
    document_id: str = Field("", description="ISO 19650 container/document identifier string")

class ReportTopFailedRuleContract(BaseModel):
    """One row of the executive summary's worst-offending-rules list."""

    rule_reference: str
    rule_description: str = ""
    fail_count: int = 0

class ReportExecutiveSummaryContract(BaseModel):
    """Headline counts, narrative and chart SVGs for the executive summary page."""

    elements_evaluated: int = 0
    unique_elements_evaluated: int = 0
    rules_executed: int = 0
    rules_with_elements: int = 0
    checks_run: int = 0
    passed: int = 0
    failed: int = 0
    unable_to_verify: int = 0
    pass_rate: float = 0.0
    mandatory_failed: int = 0
    narrative: str = ""
    ruleset_chart_svg: str = ""
    storey_chart_svg: str = ""
    top_failed_rules: list[ReportTopFailedRuleContract] = Field(default_factory=list)

class ReportScopeContract(BaseModel):
    """Model/analysis scope and document-control table for the report."""

    model_file_name: str = ""
    ifc_schema: str = ""
    element_count: int = 0
    storey_count: Optional[int] = None
    ruleset_names: list[str] = Field(default_factory=list)
    # Not recorded per analysis run today -- left unset rather than fabricated;
    # the template renders these as "Pending" instead of a made-up value.
    model_hash: Optional[str] = None
    rule_database_version: Optional[str] = None
    engine_version: Optional[str] = None
    generated_at: str = ""
    generated_by: str = ""

class ReportRulesetResultContract(BaseModel):
    """One row of the results-by-ruleset table."""

    ruleset_id: str
    ruleset_name: str
    source_citation: str = ""
    rule_count: int = 0
    passed: int = 0
    failed: int = 0
    unable_to_verify: int = 0
    pass_rate: float = 0.0

class ReportPriorityFindingContract(BaseModel):
    """One detailed finding card in the priority-findings section.

    Also reused, unlimited and ruleset-tagged, as ``ReportModel.all_findings``
    -- the Excel export's Findings Register needs every field the PDF's
    priority-finding cards already carry, plus which ruleset the rule belongs
    to for filtering, so this shape is shared rather than duplicated.
    """

    rule_reference: str
    rule_description: str = ""
    ruleset_id: str = ""
    ruleset_name: str = ""
    element_name: str = ""
    element_guid: str = ""
    storey: str = ""
    measured: str = ""
    required: str = ""
    difference: str = ""
    citation: str = ""
    ifc_property: str = ""
    reliability: str = "low"
    reliability_reason: str = ""
    action_required: str = ""
    assignee_role: str = "BIM coordinator"
    severity: str = "mandatory"

class ReportFindingRowContract(BaseModel):
    """One flat row of the findings register table."""

    element_name: str = ""
    element_guid: str = ""
    storey: str = ""
    rule_reference: str = ""
    measured: str = ""
    required: str = ""
    difference: str = ""
    severity: str = "mandatory"

class ReportUnverifiedRowContract(BaseModel):
    """One rule that could not be verified against the model (not a failure)."""

    rule_reference: str
    rule_description: str = ""
    reason: str = ""
    affected_count: int = 0

class ReportRuleRegisterRowContract(BaseModel):
    """One row of the full rule register, for finding -> rule -> clause traceability."""

    rule_reference: str
    rule_description: str = ""
    ruleset_id: str = ""
    ruleset_name: str = ""
    citation: str = ""
    ifc_property: str = ""
    reliability: str = "low"
    status: str = ""
    fail_count: int = 0
    total_count: int = 0

class ReportElementResultRowContract(BaseModel):
    """One (rule, element) result on an element-type sheet: pass, fail, unable to verify, or waived.

    Unlike ``ReportFindingRowContract`` (failures only, for the PDF), this
    carries every evaluated outcome -- the Excel export's element-type sheets
    are a full audit table per IFC class, not just a list of what failed.
    """

    element_name: str = ""
    element_guid: str = ""
    storey: str = ""
    rule_reference: str
    rule_description: str = ""
    ruleset_id: str = ""
    ruleset_name: str = ""
    ifc_property: str = ""
    measured: str = ""
    required: str = ""
    difference: str = ""
    result: str = Field("unable_to_verify", description="pass | fail | unable_to_verify | waived")
    severity: str = "mandatory"
    reliability: str = "low"
    citation: str = ""
    action_required: str = ""
    assignee_role: str = "BIM coordinator"

class ReportElementTypeSheetContract(BaseModel):
    """Every rule's result (pass/fail/unable-to-verify) for one IFC element type.

    ``type_label`` is a friendly category name (e.g. "Doors") derived from
    ``ifc_class`` (e.g. "IfcDoor") -- see ``ReportService._element_type_label``.
    """

    type_label: str
    ifc_class: str = ""
    rows: list[ReportElementResultRowContract] = Field(default_factory=list)
    passed: int = 0
    failed: int = 0
    unable_to_verify: int = 0
    waived: int = 0

class ReportModel(BaseModel):
    """Deterministic, fully-computed data for one rendered compliance report.

    Built once by ``ReportService`` from a project's analysis run and handed
    unchanged to both the Jinja2 HTML/PDF template and the Excel export --
    neither formatter recomputes anything, they only lay out what is here.
    """

    cover: ReportCoverContract
    executive_summary: ReportExecutiveSummaryContract
    scope: ReportScopeContract
    results_by_ruleset: list[ReportRulesetResultContract] = Field(default_factory=list)
    priority_findings: list[ReportPriorityFindingContract] = Field(default_factory=list)
    findings_register: list[ReportFindingRowContract] = Field(default_factory=list)
    findings_register_total: int = 0
    findings_register_truncated: bool = False
    unable_to_verify: list[ReportUnverifiedRowContract] = Field(default_factory=list)
    rule_register: list[ReportRuleRegisterRowContract] = Field(default_factory=list)
    #: One entry per IFC element type (Doors, Windows, Stairs, ...), each
    #: carrying every rule's full pass/fail/unable-to-verify result for that
    #: type. This is what the Excel export's per-element-type sheets are built
    #: from; the PDF does not use it.
    element_type_sheets: list[ReportElementTypeSheetContract] = Field(default_factory=list)

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
    status: str = Field(
        default="pending",
        description=(
            "Overall run state: 'idle' (nothing tracked), 'running', or -- once "
            "every engine of the active run has finished -- 'complete' / 'failed'."
        ),
    )
    run_key: str = Field(
        default="default",
        description=(
            "Which concurrent run reported most recently -- 'default' for "
            "architecture, 'graph' for the graph engine, "
            "'inspector' for the Digital Inspector agent. "
            "A client scopes a progress average to this rather than averaging "
            "one theme's engines against another theme's."
        ),
    )
    engines: dict[str, Any] = Field(default_factory=dict)
    timestamp: Optional[str] = None

class PipelineEventContract(BaseModel):
    """Real-time event emitted during pipeline execution for SSE streaming."""

    event_type: str = Field(..., description="stage_transition, metric_increment, completed, failed")
    source_module: str = Field(..., description="Engine or driver identifier")
    project_id: int
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: str

class RevitSyncElement(BaseModel):
    """Element descriptor pushed by pyRevit."""

    ifc_class: str = Field(..., description="IFC entity type (e.g. IfcStairFlight, IfcDoor)")
    name: str = Field("", description="Element name or mark")
    guid: str = Field("", description="Unique identifier (UniqueId / GUID)")
    storey: str = Field("", description="Level or storey name")
    properties: dict[str, Any] = Field(default_factory=dict, description="Extracted parameters")

class RevitSyncRequest(BaseModel):
    """Payload pushed by pyRevit or direct integration."""

    project_name: str = Field("Revit Model", description="Project label")
    theme: str = Field("Architecture", description="Analysis theme")
    elements: list[RevitSyncElement] = Field(default_factory=list, description="Extracted elements")

class RevitRuleResult(BaseModel):
    """Validation result for one rule against Revit elements."""

    rule_ref: Optional[str] = None
    rule_desc: Optional[str] = None
    target: Optional[str] = None
    property_name: Optional[str] = None
    status: Optional[str] = None
    pass_count: Optional[int] = 0
    fail_count: Optional[int] = 0
    missing_count: Optional[int] = 0
    failures: list[dict[str, Any]] = Field(default_factory=list)

class RevitSyncResponse(BaseModel):
    """Compliance verification result returned to pyRevit / UI."""

    element_count: int
    theme: str
    summary: dict[str, Any] = Field(default_factory=dict)
    results: list[RevitRuleResult] = Field(default_factory=list)

# ---------------------------------------------------------------------------
# Evaluator Domain Contracts (Dependency Inversion)
# ---------------------------------------------------------------------------


class RuleEvaluationRequest(BaseModel):
    """Typed request payload for evaluating an element against a physics/compliance engine."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    rule_type: str = Field(..., description="Target rule code (e.g. ARCH-EGRESS-001, ARCH-SPATIAL-001)")
    element: Any = Field(..., description="Target IFC element, element pair, or dictionary data")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Contextual evaluation metadata")

class RuleEvaluationResult(BaseModel):
    """Typed result payload produced by an engine implementing RuleEvaluator."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    rule_type: str = Field(..., description="Evaluated rule identifier")
    band: Optional[str] = Field(None, description="Assessed risk band (Low, Medium, High, Critical)")
    score: float = Field(0.0, description="Calculated composite risk score [0.0, 1.0]")
    details: dict[str, Any] = Field(default_factory=dict, description="Mechanism-specific engineering metrics")
    status: str = Field(
        "PASS",
        description="Compliance status: PASS, FAIL, NOT_ASSESSED, or NOT_APPLICABLE (outside rule scope)",
    )
    element_id: Optional[str] = Field(None, description="GlobalId or identifier of the evaluated element")
    mitigation: Optional[str] = Field(None, description="Remediation guidance")
    action: Optional[str] = Field(None, description="Operational compliance action")
    raw_result: Optional[Any] = Field(None, description="Underlying physics engine result dataclass instance")

    def __getitem__(self, item: str) -> Any:
        """Allow dictionary-style subscripting for backward compatibility."""
        if hasattr(self, item):
            return getattr(self, item)
        if item in self.__dict__:
            return self.__dict__[item]
        raise KeyError(item)

    def get(self, item: str, default: Any = None) -> Any:
        """Allow dictionary-style .get() access for backward compatibility."""
        if hasattr(self, item):
            return getattr(self, item)
        return self.__dict__.get(item, default)

    def __contains__(self, item: object) -> bool:
        """Support 'in' operator for backward compatibility."""
        return isinstance(item, str) and (hasattr(self, item) or item in self.__dict__)

    def keys(self):
        """Return dictionary keys for dictionary-style unpacking and inspection."""
        base_keys = {
            "rule_type",
            "band",
            "score",
            "details",
            "status",
            "element_id",
            "mitigation",
            "action",
            "raw_result",
        }
        return base_keys.union(self.__dict__.keys())

    def __eq__(self, other: object) -> bool:
        """Support equality check against dictionaries for backward compatibility."""
        if isinstance(other, dict):
            return all(self.get(k) == v for k, v in other.items())
        return super().__eq__(other)

    def to_dict(self) -> dict[str, Any]:
        """Serialize result to a standard dictionary."""
        return self.model_dump()

class AnalysisQueuedResponse(BaseModel):
    """Acknowledgement that a background analysis run was queued, not completed inline."""

    status: Literal["queued"]
    project_id: int
    slug: str
    message: str
