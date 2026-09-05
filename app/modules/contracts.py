"""Strict Pydantic data contracts for inter-module data exchange."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


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


class StandardOption(BaseModel):
    """One selectable normative reference offered by the wizard."""

    id: str
    name: str
    domain: str
    description: str = ""
    applicable_to: list[str] = Field(default_factory=list)


class BuildingCodeOption(BaseModel):
    """One building code the wizard offers under a jurisdiction."""

    id: str
    name: str
    description: str = ""
    jurisdictions: list[str] = Field(
        default_factory=list,
        description="Countries the code governs; empty means it applies everywhere",
    )
    ruleset_id: str = Field(
        default="", description="Seeded ruleset executed for this code, if one is bundled"
    )


class ProjectOptionsResponse(BaseModel):
    """Reference data the project setup wizard renders its choices from.

    Served from :mod:`app.constants` so the lists live in one place rather than
    being duplicated into the Svelte client, where they would drift.
    """

    countries: list[str]
    project_types: list[str]
    analysis_types: list[str]
    standards: list[StandardOption]
    # The whole catalog, not the codes for one country: the wizard re-filters it
    # by jurisdiction as the user changes step 1, with no second round trip.
    building_codes: list[BuildingCodeOption] = Field(default_factory=list)


class CDEState(str, Enum):
    """ISO 19650 Common Data Environment (CDE) Workflow States."""

    WIP = "WIP"
    SHARED = "SHARED"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class ProjectCreateRequest(BaseModel):
    """Payload for creating a project."""

    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(default="", description="Optional description")
    status: str = Field(default="Draft", description="Workflow status")
    country: str = Field(..., description="Jurisdiction governing code applicability")
    analysis_type: str = Field(..., description="Analysis domain: Arch, Piping, or seismic")
    organization_id: Optional[int] = Field(default=None, description="Owning organization ID")

    # Wizard step 3: optional building code ID
    building_code: Optional[str] = Field(default=None, description="Building code ID")

    # Wizard step 1 building details
    project_type: Optional[str] = Field(
        default=None, description="Building type from PROJECT_TYPES"
    )
    project_size_sqm: Optional[float] = Field(
        default=None, ge=0.0, description="Gross floor area in square metres"
    )
    buildings_count: Optional[int] = Field(
        default=None, ge=0, description="Number of buildings in the project"
    )
    floors_count: Optional[int] = Field(
        default=None, ge=0, description="Number of floors in the project"
    )

    # ISO 19650 Container Naming & CDE Metadata
    project_code: Optional[str] = Field(default="", description="ISO 19650 Project Code")
    originator: Optional[str] = Field(default="", description="ISO 19650 Originator Code")
    volume_system: Optional[str] = Field(default="", description="ISO 19650 Volume/System Breakdown")
    level: Optional[str] = Field(default="", description="ISO 19650 Level/Location Breakdown")
    type: Optional[str] = Field(default="", description="ISO 19650 Type Code")
    role: Optional[str] = Field(default="", description="ISO 19650 Role/Discipline Code")
    number: Optional[str] = Field(default="", description="ISO 19650 Sequential Number")
    suitability_code: Optional[str] = Field(default="S0", description="ISO 19650 Suitability Code (S0-S4, A1-A4)")
    revision_code: Optional[str] = Field(default="P01.01", description="ISO 19650 Revision Code (P01.01, C01)")
    cde_state: CDEState = Field(default=CDEState.WIP, description="CDE State (WIP, SHARED, PUBLISHED, ARCHIVED)")

    # bSDD-backed project classification standard (e.g. uniclass_2015, omniclass_2020)
    classification_standard: Optional[str] = Field(
        default="", description="bSDD dictionary code used for this project's element/property classification"
    )

    # Wizard steps 4 and 5. Linked after the project row exists, so a failure
    # to link does not cost the caller the project.
    document_ids: list[int] = Field(
        default_factory=list, description="IDs of library documents to link"
    )
    standards_codes: list[str] = Field(
        default_factory=list, description="Notebook standard IDs to link"
    )


class ProjectUpdateRequest(BaseModel):
    """Payload for updating an existing project."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = None
    country: Optional[str] = None
    analysis_type: Optional[str] = None

    # ISO 19650 Container Naming & CDE Metadata
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
    classification_standard: Optional[str] = None


class ProjectBulkDeleteRequest(BaseModel):
    """Payload for deleting multiple projects in bulk."""

    project_ids: list[int] = Field(..., min_length=1, description="IDs of projects to delete")


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


class ProjectBulkUpdateRequest(BaseModel):
    """Payload for updating metadata on multiple projects in bulk."""

    project_ids: list[int] = Field(..., min_length=1, description="IDs of projects to update")
    status: Optional[str] = Field(None, description="Optional new status (Active, Draft, Archived)")
    country: Optional[str] = Field(None, description="Optional new country/jurisdiction")
    analysis_type: Optional[str] = Field(None, description="Optional new analysis domain")


class ProjectBulkActionResponse(BaseModel):
    """Response returned after executing a bulk project operation."""

    success_count: int = Field(..., description="Number of projects affected")
    affected_ids: list[int] = Field(default_factory=list, description="IDs of affected projects")


class ProjectResponse(BaseModel):
    """Detailed response model for a project."""

    id: int
    name: str
    organization_id: Optional[int] = None
    description: Optional[str] = ""
    status: Optional[str] = "Draft"
    country: Optional[str] = "US"
    analysis_type: Optional[str] = "Arch"
    building_code: Optional[str] = None
    project_type: Optional[str] = None
    project_size_sqm: Optional[float] = None
    buildings_count: Optional[int] = None
    floors_count: Optional[int] = None
    ifc_file_path: Optional[str] = None
    ifc_md5_hash: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    # ISO 19650 & CDE fields
    project_code: Optional[str] = ""
    originator: Optional[str] = ""
    volume_system: Optional[str] = ""
    level: Optional[str] = ""
    type: Optional[str] = ""
    role: Optional[str] = ""
    number: Optional[str] = ""
    suitability_code: Optional[str] = "S0"
    revision_code: Optional[str] = "P01.01"
    cde_state: CDEState = CDEState.WIP
    cde_approved_by: Optional[str] = ""
    cde_approved_at: Optional[str] = None
    classification_standard: Optional[str] = ""


class ProjectIfcFileResponse(BaseModel):
    """One IFC model attached to a project."""

    id: Optional[int] = Field(
        default=None,
        description=(
            "project_ifc_files.id; None for a model attached before that table "
            "existed, which is reported from projects.ifc_file_path"
        ),
    )
    project_id: int
    file_path: str = Field(..., description="ObjectStorage reference for the stored model")
    file_name: str = ""
    is_primary: bool = False
    role: str = Field(
        default="context",
        description="Discipline the model carries, e.g. structural; an open vocabulary",
    )
    uploaded_at: Optional[str] = None

    # ISO 19650 & CDE fields
    project_code: Optional[str] = ""
    originator: Optional[str] = ""
    volume_system: Optional[str] = ""
    level: Optional[str] = ""
    type: Optional[str] = ""
    number: Optional[str] = ""
    suitability_code: Optional[str] = "S0"
    revision_code: Optional[str] = "P01.01"
    cde_state: CDEState = CDEState.WIP
    cde_approved_by: Optional[str] = ""
    cde_approved_at: Optional[str] = None


class ProjectIfcUploadResponse(BaseModel):
    """Outcome of attaching one or more IFC models to a project."""

    success: bool = True
    files: list[ProjectIfcFileResponse] = Field(default_factory=list)
    primary_id: Optional[int] = Field(
        default=None, description="id of the model the analysis runs start from"
    )


class ProjectListResponse(BaseModel):
    """Paginated or listed collection of projects."""

    total: int = Field(..., description="Total number of projects")
    projects: list[ProjectResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Document Contracts
# ---------------------------------------------------------------------------


class DocumentUpdateRequest(BaseModel):
    """Payload for updating document metadata or extracted text."""

    filename: Optional[str] = Field(None, min_length=1, description="Updated document filename")
    doc_type: Optional[str] = Field(None, description="Updated document type classification")
    extracted_text: Optional[str] = Field(None, description="Updated extracted text content")

    # ISO 19650 Container Naming & CDE Metadata
    project_code: Optional[str] = Field(None, description="ISO 19650 Project Code")
    originator: Optional[str] = Field(None, description="ISO 19650 Originator Code")
    suitability_code: Optional[str] = Field(None, description="ISO 19650 Suitability Code")
    revision_code: Optional[str] = Field(None, description="ISO 19650 Revision Code")
    cde_state: Optional[CDEState] = Field(None, description="CDE State")


class DocumentResponse(BaseModel):
    """Summary document item returned in lists."""

    id: int
    filename: str
    doc_type: str = Field(default="Specification", description="Document classification type")
    file_path: Optional[str] = None
    upload_date: Optional[str] = None
    extracted_text_preview: Optional[str] = None
    char_count: int = 0

    # ISO 19650 & CDE fields
    project_code: Optional[str] = ""
    originator: Optional[str] = ""
    volume_system: Optional[str] = ""
    level: Optional[str] = ""
    type: Optional[str] = ""
    role: Optional[str] = ""
    number: Optional[str] = ""
    suitability_code: Optional[str] = "S0"
    revision_code: Optional[str] = "P01.01"
    cde_state: CDEState = CDEState.WIP


class DocumentDetailResponse(BaseModel):
    """Complete document record including full extracted text."""

    id: int
    filename: str
    doc_type: str = Field(default="Specification", description="Document classification type")
    file_path: Optional[str] = None
    upload_date: Optional[str] = None
    extracted_text: str = ""
    char_count: int = 0

    # ISO 19650 & CDE fields
    project_code: Optional[str] = ""
    originator: Optional[str] = ""
    volume_system: Optional[str] = ""
    level: Optional[str] = ""
    type: Optional[str] = ""
    role: Optional[str] = ""
    number: Optional[str] = ""
    suitability_code: Optional[str] = "S0"
    revision_code: Optional[str] = "P01.01"
    cde_state: CDEState = CDEState.WIP


class GoogleDriveImportRequest(BaseModel):
    """Payload for importing one or more documents from Google Drive share links."""

    urls: list[str] = Field(..., min_length=1, description="Google Drive file URLs or bare file IDs")
    doc_type: Optional[str] = Field(default="Specification", description="Document type applied to every import")
    project_code: Optional[str] = Field(default="", description="ISO 19650 Project Code")
    originator: Optional[str] = Field(default="", description="ISO 19650 Originator Code")
    suitability_code: Optional[str] = Field(default="S0", description="ISO 19650 Suitability Code")
    revision_code: Optional[str] = Field(default="P01.01", description="ISO 19650 Revision Code")
    parser: Optional[str] = Field(default="auto", description="Extraction parser: auto | unstructured | light")
    engine_instance: Optional[str] = Field(default="", description="Named parsing engine instance to use")


class GoogleDriveImportResult(BaseModel):
    """Per-URL outcome of a Google Drive import batch."""

    url: str
    ok: bool
    document: Optional[DocumentDetailResponse] = None
    error: Optional[str] = None


class GoogleDriveImportResponse(BaseModel):
    """Result of importing a batch of Google Drive share links."""

    results: list[GoogleDriveImportResult] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# LlamaIndex Document Ingestion Contracts
# ---------------------------------------------------------------------------


class ClauseMetadata(BaseModel):
    """Provenance for a single extracted document node (clause/table/section)."""

    clause_id: Optional[str] = Field(default=None, description="Clause/article reference, e.g. '9.8.2.1.(1)'")
    page_number: Optional[int] = Field(default=None, description="1-based source page number, when known")
    parent_section: Optional[str] = Field(default=None, description="Nearest enclosing section heading")
    section_path: list[str] = Field(default_factory=list, description="Breadcrumb of headings, e.g. ['5', '5.3', '5.3.2']")
    node_type: Literal["paragraph", "table", "list", "heading"] = "paragraph"
    source_document_id: int = Field(..., description="FK to documents.id")


class DeonticStatement(BaseModel):
    """A single 'shall/must/should/may' obligation extracted from a clause."""

    text: str = Field(..., description="The extracted obligation sentence")
    modality: Literal["shall", "must", "should", "may"]
    subject: Optional[str] = Field(default=None, description="IFC entity/discipline the obligation refers to")
    clause: ClauseMetadata


class DocumentNodeContract(BaseModel):
    """A LlamaIndex node persisted for BCF/rule traceability."""

    node_id: str
    text: str
    metadata: ClauseMetadata
    deontic_statements: list[DeonticStatement] = Field(default_factory=list)


class DocumentIngestResponse(BaseModel):
    """Result of running LlamaIndex ingestion over one document."""

    document_id: int
    nodes: list[DocumentNodeContract]
    deontic_statement_count: int = 0


class DocumentSection(BaseModel):
    """One heading-delimited section/paragraph, offered as an extraction-scope choice."""

    section_number: Optional[str] = Field(default=None, description="Detected clause/section number, e.g. '9.8.2'")
    section_name: Optional[str] = Field(default=None, description="Heading text for the section")
    text: str = Field(..., description="Full text of the section, for scoped rule extraction")
    char_count: int = 0


class DocumentSectionsResponse(BaseModel):
    """Sections detected in a document, for choosing an extraction scope."""

    document_id: int
    sections: list[DocumentSection] = Field(default_factory=list)


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
    category: Optional[str] = Field(default=None, description="Domain category: Arch, Piping, or seismic")
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
    compare_property: Optional[str] = None
    name_pattern: Optional[str] = None
    uniqueness_scope: Optional[str] = None
    unit: Optional[str] = None
    severity: Optional[str] = None
    needs_review: Optional[int] = None
    category: Optional[str] = None


class RuleResponse(BaseModel):
    """Detailed response model for a rule."""

    id: int
    rule_id: Optional[str] = None
    description: Optional[str] = None
    source_text: Optional[str] = None
    source_document_id: Optional[int] = Field(
        default=None, description="FK to documents.id — the document this rule was extracted from, when known"
    )
    mechanism: Optional[str] = None
    ruleset_id: Optional[str] = None
    rule_category: Optional[str] = None
    category: Optional[str] = Field(default="Arch", description="Domain category: Arch, Piping, or seismic")
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
    source_snippet: Optional[str] = Field(
        default=None, description="The originating node's text, carried forward for promotion into rules.source_text"
    )
    clause: Optional[ClauseMetadata] = None
    proposed_rule: RuleCreateRequest
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    extraction_method: Literal["llamaindex_pydantic", "litellm_legacy"] = "litellm_legacy"
    status: RuleDraftStatus = RuleDraftStatus.pending_review
    reviewer_email: Optional[str] = None
    reviewed_at: Optional[str] = None
    review_notes: Optional[str] = None
    created_at: Optional[str] = None


class RuleExtractionDraftListResponse(BaseModel):
    """List of extraction drafts for a document."""

    drafts: list[RuleExtractionDraft]


class RuleSourceResponse(BaseModel):
    """Resolved document-viewer target for a rule's source annotation."""

    document_id: int
    filename: str
    page_number: Optional[int] = Field(
        default=None, description="Best-matching page for the rule's source_text, when the document has page-tagged text"
    )
    snippet: str = Field(default="", description="The rule's source_text, for text-layer highlighting")


class RuleDraftReviewRequest(BaseModel):
    """Payload for reviewing (accepting/rejecting/editing) one extraction draft."""

    status: RuleDraftStatus
    review_notes: Optional[str] = None
    reviewer_email: Optional[str] = None
    edited_rule: Optional[RuleCreateRequest] = Field(
        default=None, description="Required when status == edited"
    )


class RuleFolderResponse(BaseModel):
    """Grouped folder / ruleset model."""

    id: Optional[int] = None
    ruleset_id: str
    display_name: str
    description: Optional[str] = ""
    mechanism_scope: Optional[str] = ""
    category: str = Field(default="Arch", description="Ruleset category: Arch, Piping, or seismic")
    rules: list[RuleResponse] = Field(default_factory=list)


class RuleFolderCreateRequest(BaseModel):
    """Payload for creating a new ruleset folder."""

    ruleset_id: str = Field(..., description="Unique ruleset identifier")
    display_name: Optional[str] = Field(default=None, description="Display name")
    description: Optional[str] = Field(default="", description="Description")
    mechanism_scope: Optional[str] = Field(default="", description="Mechanism scope (e.g. CODE, GC-001, SEISMIC)")
    category: str = Field(default="Arch", description="Ruleset category: Arch, Piping, or seismic")


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
    category: Optional[str] = Field(default=None, description="Domain category: Arch, Piping, or seismic")
    mechanism: Optional[str] = Field(default=None, description="Mechanism: CODE, GC-001, CC-001, MC-001, SEISMIC")
    severity: Optional[str] = Field(default=None, description="Severity: Critical, High, Medium, Low")
    needs_review: Optional[int] = Field(default=None, description="Needs review flag: 0 or 1")
    property_set: Optional[str] = Field(default=None, description="Property set name")


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
    category: Optional[str] = Field(default=None, description="Domain category: Arch, Piping, or seismic")
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
    engines: Optional[list[str]] = Field(
        default=None,
        description=(
            "Engine codes to execute, e.g. ['GC-001', 'CC-001']. Prefixes ('GC') and "
            "rule ids ('GC-001.01') are accepted. None runs every engine; an empty "
            "list runs none. Unselected engines are skipped, not filtered afterwards."
        ),
    )
    include_low: bool = Field(
        default=True,
        description=(
            "Emit Low-band verdicts. True by default: a Low verdict is an "
            "assessed finding, and suppressing it made whole engines look "
            "empty. Set false for the Medium-and-above view."
        ),
    )
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
    slug: str = "corrosion"
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
    iso_checks: dict[str, Any] = Field(default_factory=dict)
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

    rule_type: str = Field(..., description="Target rule code (e.g. GC-001, CC-001, MC-001)")
    element: Any = Field(..., description="Target IFC element, element pair, or dictionary data")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Contextual evaluation metadata")


class RuleEvaluationResult(BaseModel):
    """Typed result payload produced by an engine implementing RuleEvaluator."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    rule_type: str = Field(..., description="Evaluated rule identifier")
    band: Optional[str] = Field(None, description="Assessed risk band (Low, Medium, High, Critical)")
    score: float = Field(0.0, description="Calculated composite risk score [0.0, 1.0]")
    details: dict[str, Any] = Field(default_factory=dict, description="Mechanism-specific engineering metrics")
    status: str = Field("PASS", description="Compliance status: PASS, FAIL, or NOT_ASSESSED")
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


# ---------------------------------------------------------------------------
# GitHub Repository Contracts
# ---------------------------------------------------------------------------


class GitHubRepoCreateRequest(BaseModel):
    """Payload for creating or adding a GitHub repository project storage source."""

    url: str = Field(..., min_length=5, description="Full GitHub repository URL (e.g. https://github.com/owner/repo)")
    name: Optional[str] = Field(None, description="Display name for repository")
    branch: Optional[str] = Field("main", description="Git branch to inspect")
    description: Optional[str] = Field("", description="Optional repository description")


class GitHubRepoUpdateRequest(BaseModel):
    """Payload for updating GitHub repository storage configuration."""

    name: Optional[str] = Field(None, description="Updated display name")
    branch: Optional[str] = Field(None, description="Updated default git branch")
    description: Optional[str] = Field(None, description="Updated description")
    is_active: Optional[bool] = Field(None, description="Toggle active state")


class GitHubRepoResponse(BaseModel):
    """Response contract for a registered GitHub repository."""

    id: int
    name: str
    owner: str
    url: str
    branch: str = "main"
    description: str = ""
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class GitHubRepoItem(BaseModel):
    """File item inside a GitHub repository tree."""

    path: str
    name: str
    type: str = "file"  # file or folder
    size: int = 0
    extension: str = ""
    category: str = "general"
    download_url: str = ""


class GitHubRepoStructureResponse(BaseModel):
    """Complete structure response listing models in a GitHub repository."""

    repo_id: int
    owner: str
    name: str
    url: str
    branch: str = "main"
    total_files: int = 0
    models_count: int = 0
    categories: list[str] = []
    items: list[GitHubRepoItem] = []


class AttachRepoModelsRequest(BaseModel):
    """Payload for attaching one or more IFC models from a GitHub repository to an existing project."""

    repo_id: int = Field(..., description="Registered GitHub repository the files live in")
    file_paths: list[str] = Field(
        ..., min_length=1, description="Relative file paths in the repository (e.g. models/hospital/Clinic_Architectural.ifc)"
    )
    primary_index: int = Field(
        0, ge=0, description="Index into file_paths naming the model to attach as primary"
    )


# ==============================================================================
# Parsing Engine Instance Contracts
# ==============================================================================
#
# `kind` is deliberately a plain `str`, not a Literal enumerating known
# values: the set of valid kinds is owned by ParsingEngineRegistry
# (app/modules/document_parsing/engines), which can grow without touching
# this contract. ParsingEngineInstancesService validates a submitted kind
# against the registry at request time; GET /api/parsing-engines/kinds
# (ParsingEngineKindResponse) is the discoverable source of truth for what's
# currently valid, and is what the Settings UI renders its kind selector from.


class ParsingEngineInstanceCreateRequest(BaseModel):
    """Payload for registering a new document-parsing engine instance."""

    name: str = Field(..., min_length=1, description="Unique display name, e.g. 'local', 'hosted-1', 'docling'")
    kind: str = Field(
        ..., min_length=1, description="A registered engine kind — see GET /api/parsing-engines/kinds"
    )
    api_url: str = Field(..., min_length=1, description="Base URL of the parsing engine server")
    api_key: Optional[str] = Field(
        None, description="API key — required for kinds where GET /api/parsing-engines/kinds reports requires_api_key"
    )
    strategy: Optional[str] = Field(
        "auto",
        description="Partition strategy (only meaningful for kinds where supports_strategy is true, e.g. auto, fast, hi_res, ocr_only)",
    )
    is_default: Optional[bool] = Field(False, description="Use this instance when none is explicitly selected")
    is_enabled: Optional[bool] = Field(True, description="Whether this instance is selectable")
    notes: Optional[str] = Field("", description="Optional free-text notes")


class ParsingEngineInstanceUpdateRequest(BaseModel):
    """Payload for updating an existing parsing-engine instance.

    `kind` cannot be changed after creation — register a new instance instead.
    """

    name: Optional[str] = Field(None, description="Updated display name")
    api_url: Optional[str] = Field(None, description="Updated server URL")
    api_key: Optional[str] = Field(None, description="Updated API key (omit to leave unchanged)")
    strategy: Optional[str] = Field(None, description="Updated partition strategy")
    is_default: Optional[bool] = Field(None, description="Make (or unmake) this the default instance")
    is_enabled: Optional[bool] = Field(None, description="Toggle whether this instance is selectable")
    notes: Optional[str] = Field(None, description="Updated notes")


class ParsingEngineInstanceResponse(BaseModel):
    """Response contract for a registered parsing-engine instance.

    The stored api_key is never echoed back — only whether one is set.
    """

    id: int
    name: str
    kind: str
    api_url: str
    has_api_key: bool = False
    strategy: str = "auto"
    is_default: bool = False
    is_enabled: bool = True
    notes: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ParsingEngineInstanceTestResponse(BaseModel):
    """Result of a connectivity check against a configured instance."""

    ok: bool
    detail: str = ""


class ParsingEngineKindResponse(BaseModel):
    """Metadata for one registered parsing-engine kind (a ParsingEngineDriver).

    Drives the Settings UI's kind selector — a new backend driver shows up
    there automatically, with no frontend changes.
    """

    kind: str
    family: str
    display_name: str
    description: str = ""
    requires_api_key: bool = False
    supports_strategy: bool = False
    url_placeholder: str = ""


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


class BSDDDictionaryItem(BaseModel):
    """bSDD dictionary catalog contract."""

    uri: str = Field(..., description="Unique URI identifying the dictionary")
    code: str = Field(..., description="Short dictionary identifier (e.g. uniclass_2015, omniclass_23)")
    name: str = Field(..., description="Full dictionary name")
    version: str = Field("1.0", description="Dictionary version")
    organization_code_owner: str = Field("buildingSMART", description="Owner organization code")
    language_iso_code: str = Field("en-GB", description="Language code")
    classes_count: int = Field(0, description="Number of classes in dictionary")


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


class CDESyncResponse(BaseModel):
    """Outcome of an external CDE synchronization request."""

    success: bool
    synced_documents_count: int = 0
    synced_files: list[str] = []
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


# ------------------------------------------------------------------------------
# 5. BCF REST API (v2.1 / v3.0) Contracts
# ------------------------------------------------------------------------------


class BCFProjectResponse(BaseModel):
    """BCF Project information contract."""

    project_id: str
    name: str
    authorization: dict[str, list[str]] = Field(
        default_factory=lambda: {"project_actions": ["update"], "topic_actions": ["create", "update", "delete"]}
    )


class BCFCommentResponse(BaseModel):
    """BCF Topic comment contract."""

    guid: str
    date: str
    author: str
    comment: str
    topic_guid: str
    modified_date: Optional[str] = None
    modified_author: Optional[str] = None
    viewpoint_guid: Optional[str] = None


class BCFCommentCreatePayload(BaseModel):
    """Payload for adding a new comment to a BCF topic."""

    comment: str = Field(..., min_length=1, description="Comment text content")
    viewpoint_guid: Optional[str] = Field(None, description="Optional associated viewpoint GUID")


class BCFViewpointResponse(BaseModel):
    """BCF Topic viewpoint contract."""

    guid: str
    topic_guid: str
    index: int = 0
    perspective_camera: Optional[dict[str, Any]] = None
    orthogonal_camera: Optional[dict[str, Any]] = None
    lines: list[dict[str, Any]] = Field(default_factory=list)
    clipping_planes: list[dict[str, Any]] = Field(default_factory=list)
    components: dict[str, Any] = Field(default_factory=dict)
    snapshot_url: Optional[str] = None


class BCFViewpointCreatePayload(BaseModel):
    """Payload for creating a viewpoint on a BCF topic."""

    perspective_camera: Optional[dict[str, Any]] = None
    orthogonal_camera: Optional[dict[str, Any]] = None
    components: Optional[dict[str, Any]] = None
    snapshot_base64: Optional[str] = None


class BCFTopicResponse(BaseModel):
    """BCF Topic entity contract."""

    guid: str
    topic_type: str = "Issue"
    topic_status: str = "Open"
    title: str
    priority: str = "Normal"
    index: int = 1
    creation_date: str
    creation_author: str
    modified_date: Optional[str] = None
    modified_author: Optional[str] = None
    assigned_to: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[str] = None
    labels: list[str] = Field(default_factory=list)
    stage: Optional[str] = None
    # Component references
    component_guids: list[str] = Field(default_factory=list)
    # ISO 19650 governance metadata
    project_code: Optional[str] = None
    originator: Optional[str] = None
    suitability_code: Optional[str] = None
    revision_code: Optional[str] = None
    cde_state: Optional[CDEState] = None
    comments_count: int = 0
    viewpoints_count: int = 0


class BCFTopicCreatePayload(BaseModel):
    """Payload for creating a BCF topic via REST API."""

    title: str = Field(..., min_length=1, description="Topic title")
    topic_type: str = Field("Issue", description="Type (Issue, Request, Clashes, Remark)")
    topic_status: str = Field("Open", description="Status (Open, InProgress, Closed, Resolved)")
    priority: str = Field("Normal", description="Priority (Critical, Major, Normal, Minor)")
    description: Optional[str] = None
    assigned_to: Optional[str] = None
    due_date: Optional[str] = None
    labels: list[str] = Field(default_factory=list)
    component_guids: list[str] = Field(default_factory=list)
    # ISO 19650 metadata
    suitability_code: Optional[str] = "S0"
    revision_code: Optional[str] = "P01.01"
    cde_state: Optional[CDEState] = CDEState.WIP


class BCFTopicUpdatePayload(BaseModel):
    """Payload for updating an existing BCF topic."""

    title: Optional[str] = None
    topic_type: Optional[str] = None
    topic_status: Optional[str] = None
    priority: Optional[str] = None
    description: Optional[str] = None
    assigned_to: Optional[str] = None
    due_date: Optional[str] = None
    labels: Optional[list[str]] = None
    component_guids: Optional[list[str]] = None
    suitability_code: Optional[str] = None
    revision_code: Optional[str] = None
    cde_state: Optional[CDEState] = None






# ── ISO 19650 naming configuration ───────────────────────────────────────────


class NamingCodeContract(BaseModel):
    """One entry of the ISO 19650 code library: a code and what it stands for."""

    code: str = Field(..., description="The code as it appears in a container name, e.g. G00")
    label: str = Field(..., description="What the code stands for, e.g. Ground")


class NamingConventionContract(BaseModel):
    """One naming convention: a format string over the token vocabulary."""

    id: str = Field(..., description="Stable identifier, e.g. iso19650_date")
    name: str = Field(..., description="Display name")
    format: str = Field(..., description="Format string, e.g. {project}_{originator}_...")
    separator: str = Field("_", description="Field separator this format is written with")
    description: str = Field("", description="When to use this convention")
    preset: bool = Field(False, description="True for the five built-ins, which cannot be edited")
    iso_compliant: bool = Field(
        True, description="False for conventions offered for clash-test names, not for a CDE"
    )


class NamingTokenContract(BaseModel):
    """One token a convention format may contain."""

    token: str = Field(..., description="Token name without braces, e.g. originator")
    label: str = Field(..., description="What the token names")
    source: str = Field(
        ..., description="Where its value comes from: config, library or runtime"
    )


class CdeStatusContract(BaseModel):
    """One row of the CDE status table (ISO 19650-2 Table 1)."""

    code: str = Field(..., description="Status code, e.g. S1")
    label: str = Field(..., description="What the status means")
    colour: str = Field(..., description="Hex colour the status is drawn in")
    selectable: bool = Field(
        True, description="False for the rows shown for reference but not offered as a suitability"
    )


class NamingCatalogResponseContract(BaseModel):
    """The static half of the naming feature: everything not specific to a project."""

    conventions: list[NamingConventionContract] = Field(default_factory=list)
    tokens: list[NamingTokenContract] = Field(default_factory=list)
    codes: dict[str, list[NamingCodeContract]] = Field(
        default_factory=dict, description="Master library keyed by disciplines/volumes/levels/types"
    )
    cde_statuses: list[CdeStatusContract] = Field(default_factory=list)
    date_formats: list[str] = Field(default_factory=list)
    separators: list[str] = Field(default_factory=list)
    default_convention: str = Field("iso19650_date")


class NamingConfigContract(BaseModel):
    """A project's ISO 19650 naming configuration."""

    project_id: int
    is_configured: bool = Field(
        False, description="False when nothing has been saved and these are the defaults"
    )
    project_code: str = ""
    originator_code: str = ""
    type_code: str = "CO"
    suitability: str = "S1"
    revision: str = "01"
    separator: str = "_"
    date_format: str = "YYMMDD"
    class_a: str = ""
    class_b: str = ""
    active_convention: str = "iso19650_date"
    level_codes: list[NamingCodeContract] = Field(default_factory=list)
    type_codes: list[NamingCodeContract] = Field(default_factory=list)
    discipline_codes: list[NamingCodeContract] = Field(default_factory=list)
    volume_codes: list[NamingCodeContract] = Field(default_factory=list)
    custom_conventions: list[NamingConventionContract] = Field(default_factory=list)
    updated_at: Optional[str] = None


class NamingConfigUpdateContract(BaseModel):
    """Fields to write to a project's naming configuration.

    Every field is optional and only the ones supplied are written, so saving
    one tab of the form cannot blank the others.
    """

    project_code: Optional[str] = None
    originator_code: Optional[str] = None
    type_code: Optional[str] = None
    suitability: Optional[str] = None
    revision: Optional[str] = None
    separator: Optional[str] = None
    date_format: Optional[str] = None
    class_a: Optional[str] = None
    class_b: Optional[str] = None
    active_convention: Optional[str] = None
    level_codes: Optional[list[NamingCodeContract]] = None
    type_codes: Optional[list[NamingCodeContract]] = None
    discipline_codes: Optional[list[NamingCodeContract]] = None
    volume_codes: Optional[list[NamingCodeContract]] = None
    custom_conventions: Optional[list[NamingConventionContract]] = None


class NamingPreviewRequestContract(BaseModel):
    """A configuration to render a sample name from, without saving it."""

    config: NamingConfigUpdateContract = Field(
        default_factory=NamingConfigUpdateContract,
        description="The configuration being edited; unset fields fall back to the defaults",
    )
    overrides: dict[str, str] = Field(
        default_factory=dict,
        description="Values for the runtime tokens, e.g. {'sequence': '0042'}",
    )


class NamingPreviewResponseContract(BaseModel):
    """A rendered name and the convention that produced it."""

    name: str = Field(..., description="The rendered information container name")
    convention_id: str = Field(..., description="id of the convention actually applied")
    applied_format: str = Field(
        "",
        description=(
            "The format string as rendered, with the project's separator substituted "
            "for the one the convention was authored with"
        ),
    )
    unresolved_tokens: list[str] = Field(
        default_factory=list,
        description="Tokens left literal because nothing supplied a value for them",
    )


# ---------------------------------------------------------------------------
# Digital Inspector (LangGraph agent) Contracts
# ---------------------------------------------------------------------------


class InspectorQueryRequest(BaseModel):
    """A natural-language query for the Digital Inspector agent."""

    query: str = Field(..., min_length=1, description="Free-text question about the project")


class InspectorToolCallContract(BaseModel):
    """One tool invocation recorded during an inspector run."""

    tool_name: str
    input: dict[str, Any] = Field(default_factory=dict)
    output: Optional[dict[str, Any]] = None
    status: Literal["running", "success", "error"] = "running"


class InspectorResponse(BaseModel):
    """Final answer and tool-call trace from a Digital Inspector run."""

    project_id: int
    answer: str
    tool_calls: list[InspectorToolCallContract] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Auth / Multi-Tenancy Contracts
# ---------------------------------------------------------------------------


class OrganizationMembership(BaseModel):
    """One organization the authenticated caller belongs to, and their role in it."""

    organization_id: int
    name: str
    slug: str
    role: Literal["owner", "admin", "member"]


class UserProfile(BaseModel):
    """Editable identity and preferences layered on top of auth.users."""

    full_name: str = ""
    avatar_url: str = ""
    title: str = Field(default="", description="Job title / discipline, shown alongside the name")
    default_organization_id: Optional[int] = None
    preferences: dict[str, Any] = Field(default_factory=dict)
    is_superadmin: bool = Field(
        default=False,
        description="Platform-wide bypass of organization-membership checks. Not settable via PATCH.",
    )


class ProfileUpdateRequest(BaseModel):
    """Fields to write to the caller's profile. Every field is optional."""

    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    title: Optional[str] = None
    default_organization_id: Optional[int] = None
    preferences: Optional[dict[str, Any]] = None


class CurrentUserResponse(BaseModel):
    """The authenticated caller's identity, profile, and organization memberships."""

    id: str = Field(..., description="Supabase auth.users.id (uuid)")
    email: Optional[str] = None
    profile: UserProfile = Field(default_factory=UserProfile)
    organizations: list[OrganizationMembership] = Field(default_factory=list)


class OrganizationMemberResponse(BaseModel):
    """A member of an organization, as shown on the Org Settings screen."""

    user_id: str
    email: str = ""
    full_name: str = ""
    avatar_url: str = ""
    role: Literal["owner", "admin", "member"]
    group_id: Optional[int] = None
    group_name: Optional[str] = None


class OrganizationMemberListResponse(BaseModel):
    """Every member of one organization."""

    organization_id: int
    members: list[OrganizationMemberResponse] = Field(default_factory=list)


class MemberRoleUpdateRequest(BaseModel):
    """New role to assign a member."""

    role: Literal["owner", "admin", "member"]


class OrganizationInviteResponse(BaseModel):
    """A pending or accepted invite into an organization."""

    id: int
    organization_id: int
    email: str
    role: Literal["owner", "admin", "member"]
    accepted_at: Optional[str] = None


class OrganizationInviteListResponse(BaseModel):
    """Every invite (pending and accepted) for one organization."""

    organization_id: int
    invites: list[OrganizationInviteResponse] = Field(default_factory=list)


class OrganizationInviteCreateRequest(BaseModel):
    """A new invite to send for an organization."""

    email: str = Field(..., min_length=3, description="Address the invite is addressed to")
    role: Literal["owner", "admin", "member"] = "member"


class OrganizationSummary(BaseModel):
    """One organization, as listed for the platform superadmin."""

    id: int
    name: str
    slug: str


class OrganizationListResponse(BaseModel):
    """Every organization on the platform. Superadmin only."""

    organizations: list[OrganizationSummary] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# RBAC: Groups and Resource Grants
# ---------------------------------------------------------------------------


class GroupResponse(BaseModel):
    """One user group within an organization."""

    id: int
    organization_id: int
    name: str
    member_count: int = 0


class GroupListResponse(BaseModel):
    """Every group in one organization."""

    organization_id: int
    groups: list[GroupResponse] = Field(default_factory=list)


class GroupCreateRequest(BaseModel):
    """A new group to create within an organization."""

    name: str = Field(..., min_length=1, max_length=100)


class MemberGroupUpdateRequest(BaseModel):
    """Which group to place a member in, or null to leave them ungrouped."""

    group_id: Optional[int] = None


class GroupProjectGrantsResponse(BaseModel):
    """The set of projects one group can access."""

    group_id: int
    project_ids: list[int] = Field(default_factory=list)


class GroupProjectGrantsUpdateRequest(BaseModel):
    """Replace a group's entire set of granted projects."""

    project_ids: list[int] = Field(default_factory=list)


class OrganizationRulesetGrantsResponse(BaseModel):
    """The set of rulesets one organization may use at all (superadmin-controlled)."""

    organization_id: int
    ruleset_ids: list[str] = Field(default_factory=list)


class OrganizationRulesetGrantsUpdateRequest(BaseModel):
    """Replace an organization's entire set of granted rulesets."""

    ruleset_ids: list[str] = Field(default_factory=list)


class ProjectRulesetBindingsResponse(BaseModel):
    """The rulesets bound to one project.

    Also carries which of the org's grants remain available to bind
    (owner-controlled, subset of ``OrganizationRulesetGrantsResponse``).
    """

    project_id: int
    ruleset_ids: list[str] = Field(default_factory=list)
    available_ruleset_ids: list[str] = Field(default_factory=list)


class ProjectRulesetBindingsUpdateRequest(BaseModel):
    """Replace a project's entire set of bound rulesets."""

    ruleset_ids: list[str] = Field(default_factory=list)


class OrganizationProjectGrantsResponse(BaseModel):
    """Projects shared into one organization from elsewhere.

    Cross-org sharing, superadmin-controlled. Does not include projects the
    organization owns outright -- those need no grant.
    """

    organization_id: int
    project_ids: list[int] = Field(default_factory=list)


class OrganizationProjectGrantsUpdateRequest(BaseModel):
    """Replace an organization's entire set of shared-in (non-owned) projects."""

    project_ids: list[int] = Field(default_factory=list)


class OrganizationDocumentGrantsResponse(BaseModel):
    """The set of documents one organization may use at all (superadmin-controlled)."""

    organization_id: int
    document_ids: list[int] = Field(default_factory=list)


class OrganizationDocumentGrantsUpdateRequest(BaseModel):
    """Replace an organization's entire set of granted documents."""

    document_ids: list[int] = Field(default_factory=list)


class ProjectDocumentBindingsResponse(BaseModel):
    """The documents bound to one project.

    Also carries which of the org's grants remain available to bind
    (owner-controlled, subset of ``OrganizationDocumentGrantsResponse``).
    """

    project_id: int
    document_ids: list[int] = Field(default_factory=list)
    available_document_ids: list[int] = Field(default_factory=list)


class ProjectDocumentBindingsUpdateRequest(BaseModel):
    """Replace a project's entire set of bound documents."""

    document_ids: list[int] = Field(default_factory=list)
