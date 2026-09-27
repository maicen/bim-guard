"""Project, model, options, and project lifecycle contracts."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.modules.contracts.base import (
    PROJECT_CODE_MAX_LENGTH,
    PROJECT_CODE_MIN_LENGTH,
    PROJECT_CODE_PATTERN,
    SHORT_NAME_MAX_LENGTH,
    SHORT_NAME_MIN_LENGTH,
    CDEState,
    IsoGovernanceFieldsOptional,
    IsoGovernanceFieldsRequired,
    TimestampFields,
)

__all__ = ['StandardOption', 'BuildingCodeOption', 'ProjectOptionsResponse', 'ProjectCreateRequest', 'ProjectClientNamesResponse', 'ProjectUpdateRequest', 'ProjectBulkDeleteRequest', 'ProjectBulkUpdateRequest', 'ProjectBulkActionResponse', 'ProjectResponse', 'ModelResponse', 'ModelUpdateRequest', 'ModelUploadResponse', 'ModelAttachStatusResponse', 'ModelListResponse', 'ModelLineageResponse', 'ProjectListResponse', 'IfcUploadAttachResponse', 'ModelEnhancementResponse', 'IsoNamingValidationResponse']

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

class ProjectCreateRequest(BaseModel):
    """Payload for creating a project.

    Carries no workflow status: every project created through this contract
    starts ``Active`` (set by the route), so the wizard no longer asks.
    """

    client_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        # At least one non-space character: a blank client is not a client.
        pattern=r"\S",
        description="Client (appointing party) the project is delivered for",
    )
    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    short_name: str = Field(
        ...,
        min_length=SHORT_NAME_MIN_LENGTH,
        max_length=SHORT_NAME_MAX_LENGTH,
        description="Short display nickname shown in the header and breadcrumbs",
    )
    description: Optional[str] = Field(default="", description="Optional description")
    country: str = Field(..., description="Jurisdiction governing code applicability")
    analysis_type: str = Field(..., description="Analysis domain: Arch")
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
    project_code: str = Field(
        ...,
        min_length=PROJECT_CODE_MIN_LENGTH,
        max_length=PROJECT_CODE_MAX_LENGTH,
        pattern=PROJECT_CODE_PATTERN,
        description="ISO 19650 Project Code (2-6 alphanumeric characters)",
    )
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

class ProjectClientNamesResponse(BaseModel):
    """Distinct client names already used on the caller's visible projects."""

    client_names: list[str] = Field(
        default_factory=list,
        description="Case-insensitively distinct client names, sorted alphabetically",
    )

class ProjectUpdateRequest(IsoGovernanceFieldsOptional):
    """Payload for updating an existing project."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    short_name: Optional[str] = Field(
        None, min_length=SHORT_NAME_MIN_LENGTH, max_length=SHORT_NAME_MAX_LENGTH
    )
    description: Optional[str] = None
    status: Optional[str] = None
    country: Optional[str] = None
    analysis_type: Optional[str] = None

    # ISO 19650 Container Naming & CDE Metadata
    project_code: Optional[str] = Field(
        None,
        min_length=PROJECT_CODE_MIN_LENGTH,
        max_length=PROJECT_CODE_MAX_LENGTH,
        pattern=PROJECT_CODE_PATTERN,
    )
    classification_standard: Optional[str] = None
    project_type: Optional[str] = Field(
        None, description="Optional building type from PROJECT_TYPES"
    )

class ProjectBulkDeleteRequest(BaseModel):
    """Payload for deleting multiple projects in bulk."""

    project_ids: list[int] = Field(..., min_length=1, description="IDs of projects to delete")

class ProjectBulkUpdateRequest(BaseModel):
    """Payload for updating metadata on multiple projects in bulk."""

    project_ids: list[int] = Field(..., min_length=1, description="IDs of projects to update")
    status: Optional[str] = Field(None, description="Optional new status (Active, Draft, Archived)")
    country: Optional[str] = Field(None, description="Optional new country/jurisdiction")
    analysis_type: Optional[str] = Field(None, description="Optional new analysis domain")
    project_type: Optional[str] = Field(None, description="Optional new project type from PROJECT_TYPES")

class ProjectBulkActionResponse(BaseModel):
    """Response returned after executing a bulk project operation."""

    success_count: int = Field(..., description="Number of projects affected")
    affected_ids: list[int] = Field(default_factory=list, description="IDs of affected projects")

class ProjectResponse(IsoGovernanceFieldsRequired, TimestampFields):
    """Detailed response model for a project."""

    id: int
    name: str
    short_name: Optional[str] = ""
    client_name: Optional[str] = ""
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

    # ISO 19650 & CDE fields
    project_code: Optional[str] = ""
    cde_approved_by: Optional[str] = ""
    cde_approved_at: Optional[str] = None
    classification_standard: Optional[str] = ""

class ModelResponse(IsoGovernanceFieldsRequired):
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

    # IFC-derived summary metadata (cheap header/type-count reads taken at attach time)
    ifc_schema: Optional[str] = Field(
        default="", description="IFC schema version from the model header, e.g. IFC4, IFC2X3"
    )
    authoring_application: Optional[str] = Field(
        default="", description="Authoring application + version that produced this model"
    )
    storey_count: Optional[int] = Field(
        default=None, description="Count of IfcBuildingStorey entities"
    )
    element_count: Optional[int] = Field(
        default=None, description="Count of IfcElement occurrences"
    )
    discipline_summary: dict[str, int] = Field(
        default_factory=dict,
        description="Heuristic element-count breakdown by discipline (architectural/structural/mep/other)",
    )

    # ISO 19650 & CDE fields
    project_code: Optional[str] = ""
    cde_approved_by: Optional[str] = ""
    cde_approved_at: Optional[str] = None

class ModelUpdateRequest(BaseModel):
    """Payload for editing an attached model's naming/ISO 19650 fields.

    Every field is optional and independently applied: a caller sends only
    what the user actually changed. Does not touch the stored model bytes or
    the derived IFC summary columns.
    """

    file_name: Optional[str] = Field(default=None, description="Display name for the model")
    role: Optional[str] = Field(default=None, description="Discipline the model carries")
    project_code: Optional[str] = Field(default=None, description="ISO 19650 Project Code")
    originator: Optional[str] = Field(default=None, description="ISO 19650 Originator Code")
    volume_system: Optional[str] = Field(default=None, description="ISO 19650 Volume/System Breakdown")
    level: Optional[str] = Field(default=None, description="ISO 19650 Level/Location Breakdown")
    type: Optional[str] = Field(default=None, description="ISO 19650 Type Code")
    number: Optional[str] = Field(default=None, description="ISO 19650 Sequential Number")
    suitability_code: Optional[str] = Field(default=None, description="ISO 19650 Suitability Code (S0-S4, A1-A4)")
    revision_code: Optional[str] = Field(default=None, description="ISO 19650 Revision Code (P01.01, C01)")

class ModelUploadResponse(BaseModel):
    """Outcome of attaching one or more IFC models to a project."""

    success: bool = True
    files: list[ModelResponse] = Field(default_factory=list)
    primary_id: Optional[int] = Field(
        default=None, description="id of the model the analysis runs start from"
    )
    processing: bool = Field(
        default=False,
        description=(
            "True when storing and attaching the models is still running in the "
            "background -- poll GET /projects/{id}/models/attach-status for "
            "completion instead of expecting `files`/`primary_id` here yet."
        ),
    )
    warnings: list[str] = Field(
        default_factory=list,
        description=(
            "Non-blocking notes on the upload, e.g. a filename that does not "
            "follow ISO 19650 container naming and so carries no naming metadata."
        ),
    )

class ModelAttachStatusResponse(BaseModel):
    """Progress of a background model-attach job started by a model upload."""

    processing: bool
    total: int
    attached: int
    error: Optional[str] = None

class ModelListResponse(BaseModel):
    """A project's attached IFC models."""

    project_id: int
    models: list[ModelResponse] = Field(default_factory=list)

class ModelLineageResponse(BaseModel):
    """One immutable model-enhancement lineage record."""

    id: int
    project_id: int
    ifc_file_id: Optional[int] = Field(
        default=None, description="project_ifc_files.id this version was produced from, when known"
    )
    source_reference: str = ""
    output_reference: str = ""
    version: int
    source_version: Optional[int] = 0
    source_sha256: Optional[str] = ""
    summary: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None

class ProjectListResponse(BaseModel):
    """Paginated or listed collection of projects."""

    total: int = Field(..., description="Total number of projects")
    projects: list[ProjectResponse] = Field(default_factory=list)

# ---------------------------------------------------------------------------
# API Standards: Strict Contracts For Previously Untyped Endpoints
# ---------------------------------------------------------------------------


class IfcUploadAttachResponse(BaseModel):
    """Result of attaching one uploaded IFC model to a project."""

    success: bool
    filename: str
    size_bytes: int
    sha256: str

class ModelEnhancementResponse(BaseModel):
    """Outcome of running the IFC model-quality enhancement pipeline."""

    model_config = ConfigDict(extra="allow")

    success: bool = True
    ifc_file_id: Optional[int] = Field(
        default=None, description="project_ifc_files.id the enhancement was produced from, when known"
    )

class IsoNamingValidationResponse(BaseModel):
    """Result of validating a filename against the ISO 19650 National Annex format."""

    is_valid: bool
    fields: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
