"""FastAPI router for project management and IFC model operations."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.api.dependencies import get_phase6_service, get_projects_service
from app.constants import (
    ANALYSIS_TYPES,
    BUILDING_CODES,
    COUNTRIES,
    DEFAULT_ANALYSIS_TYPE,
    DEFAULT_COUNTRY,
    NOTEBOOK_STANDARDS,
    PROJECT_TYPES,
)
from app.logging_config import get_logger
from app.modules.contracts import (
    AnalysisInputItemContract,
    BuildingCodeOption,
    ProjectBulkActionResponse,
    ProjectBulkDeleteRequest,
    ProjectBulkUpdateRequest,
    ProjectCreateRequest,
    ProjectIfcFileResponse,
    ProjectIfcUploadResponse,
    ProjectListResponse,
    ProjectOptionsResponse,
    ProjectResponse,
    ProjectUpdateRequest,
    StandardOption,
)
from app.services.phase6_service import Phase6Service
from app.services.projects_service import ProjectsService

logger = get_logger(__name__)

router = APIRouter()


@router.get("", response_model=ProjectListResponse, summary="List all projects")
def list_projects(
    service: Annotated[ProjectsService, Depends(get_projects_service)],
    response: Response,
) -> ProjectListResponse:
    """Return all projects ordered newest first."""
    response.headers["Cache-Control"] = "private, max-age=5, stale-while-revalidate=30"
    rows = service.list_projects()
    projects = [ProjectResponse(**row) for row in rows]
    return ProjectListResponse(total=len(projects), projects=projects)


@router.get(
    "/options",
    response_model=ProjectOptionsResponse,
    summary="Reference data for the project setup wizard",
)
def get_project_options(response: Response) -> ProjectOptionsResponse:
    """Return the choice lists the wizard renders.

    Declared above ``/{project_id}`` on purpose: FastAPI matches routes in
    declaration order, and the other way round this path would be tried as a
    project id and rejected as a 422.
    """
    response.headers["Cache-Control"] = "private, max-age=300, stale-while-revalidate=600"
    return ProjectOptionsResponse(
        countries=COUNTRIES,
        project_types=PROJECT_TYPES,
        analysis_types=ANALYSIS_TYPES,
        standards=[StandardOption(**standard) for standard in NOTEBOOK_STANDARDS],
        building_codes=[BuildingCodeOption(**code) for code in BUILDING_CODES],
    )


@router.post(
    "/bulk-delete",
    response_model=ProjectBulkActionResponse,
    summary="Delete multiple projects in bulk",
)
def bulk_delete_projects(
    payload: ProjectBulkDeleteRequest,
    service: Annotated[ProjectsService, Depends(get_projects_service)],
) -> ProjectBulkActionResponse:
    """Delete multiple projects by their primary keys."""
    deleted_ids = service.bulk_delete_projects(payload.project_ids)
    return ProjectBulkActionResponse(success_count=len(deleted_ids), affected_ids=deleted_ids)


@router.post(
    "/bulk-update",
    response_model=ProjectBulkActionResponse,
    summary="Update metadata for multiple projects in bulk",
)
def bulk_update_projects(
    payload: ProjectBulkUpdateRequest,
    service: Annotated[ProjectsService, Depends(get_projects_service)],
) -> ProjectBulkActionResponse:
    """Update metadata for multiple projects in bulk."""
    try:
        updated_ids = service.bulk_update_projects(
            payload.project_ids,
            status=payload.status,
            country=payload.country,
            analysis_type=payload.analysis_type,
        )
        return ProjectBulkActionResponse(success_count=len(updated_ids), affected_ids=updated_ids)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))



@router.get("/{project_id}", response_model=ProjectResponse, summary="Get project by ID")
def get_project(
    project_id: int,
    service: Annotated[ProjectsService, Depends(get_projects_service)],
    response: Response,
) -> ProjectResponse:
    """Retrieve a single project by primary key."""
    response.headers["Cache-Control"] = "private, max-age=10, stale-while-revalidate=30"
    row = service.get_project(project_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found.",
        )
    return ProjectResponse(**row)


@router.get("/{project_id}/inputs", response_model=list[AnalysisInputItemContract], summary="Get analysis inputs")
def get_project_inputs(
    project_id: int,
    service: Annotated[ProjectsService, Depends(get_projects_service)],
) -> list[AnalysisInputItemContract]:
    """Retrieve merged project standards and client documents."""
    project = service.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found.",
        )
    inputs = service.get_analysis_inputs(project_id)
    return [AnalysisInputItemContract(**i) for i in inputs]


def _link_project_inputs(
    service: ProjectsService,
    project_id: int,
    *,
    document_ids: list[int],
    standards_codes: list[str],
) -> None:
    """Link the wizard's chosen documents and standards to a new project.

    Deliberately non-fatal. The project row already exists by the time this
    runs, and handing the caller a 500 would leave them with a created project
    and an error page. A failure to link is logged and the project is returned.
    """
    if document_ids:
        try:
            service.link_library_documents(project_id, document_ids)
        except Exception:
            logger.exception("Could not link documents project_id=%d", project_id)

    if standards_codes:
        try:
            service.set_standards_for_project(project_id, standards_codes)
        except Exception:
            logger.exception("Could not link standards project_id=%d", project_id)


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create project (JSON)",
)
def create_project(
    payload: ProjectCreateRequest,
    service: Annotated[ProjectsService, Depends(get_projects_service)],
) -> ProjectResponse:
    """Create a new project using a JSON payload."""
    try:
        created = service.create_project(
            name=payload.name,
            description=payload.description or "",
            status=payload.status,
            country=payload.country,
            analysis_type=payload.analysis_type,
            building_code=payload.building_code,
            project_type=payload.project_type,
            project_size_sqm=payload.project_size_sqm,
            buildings_count=payload.buildings_count,
            floors_count=payload.floors_count,
            project_code=payload.project_code or "",
            originator=payload.originator or "",
            volume_system=payload.volume_system or "",
            level=payload.level or "",
            type=payload.type or "",
            role=payload.role or "",
            number=payload.number or "",
            suitability_code=payload.suitability_code or "S0",
            revision_code=payload.revision_code or "P01.01",
            cde_state=payload.cde_state.value if hasattr(payload.cde_state, "value") else (payload.cde_state or "WIP"),
            classification_standard=payload.classification_standard or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    _link_project_inputs(
        service,
        int(created["id"]),
        document_ids=payload.document_ids,
        standards_codes=payload.standards_codes,
    )
    return ProjectResponse(**created)


@router.post(
    "/upload",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create project with IFC upload (Multipart)",
)
async def create_project_with_ifc(
    name: Annotated[str, Form(..., min_length=1)],
    service: Annotated[ProjectsService, Depends(get_projects_service)],
    description: Annotated[str, Form()] = "",
    status_field: Annotated[str, Form(alias="status")] = "Draft",
    country: Annotated[str, Form()] = DEFAULT_COUNTRY,
    analysis_type: Annotated[str, Form()] = DEFAULT_ANALYSIS_TYPE,
    building_code: Annotated[Optional[str], Form()] = None,
    project_type: Annotated[Optional[str], Form()] = None,
    project_size_sqm: Annotated[Optional[float], Form()] = None,
    buildings_count: Annotated[Optional[int], Form()] = None,
    floors_count: Annotated[Optional[int], Form()] = None,
    document_ids: Annotated[list[int], Form()] = [],
    standards_codes: Annotated[list[str], Form()] = [],
    classification_standard: Annotated[Optional[str], Form()] = None,
    ifc_file: Optional[UploadFile] = File(None),
) -> ProjectResponse:
    """Create a project and optionally attach an uploaded IFC model."""
    ifc_file_path = ""
    ifc_md5_hash = ""
    project_code = ""
    originator = ""
    volume_system = ""
    level = ""
    type_code = ""
    role_code = ""
    number_code = ""
    suitability_code = "S0"
    revision_code = "P01.01"

    if ifc_file is not None and ifc_file.filename:
        ifc_file_path, ifc_md5_hash = await service.prepare_ifc_upload(ifc_file)
        from app.modules.document_parsing.iso_validator import ISO19650Validator
        val = ISO19650Validator.validate_filename(ifc_file.filename)
        if val.is_valid:
            project_code = val.fields.get("project_code", "")
            originator = val.fields.get("originator", "")
            volume_system = val.fields.get("volume_system", "")
            level = val.fields.get("level", "")
            type_code = val.fields.get("type", "")
            role_code = val.fields.get("role", "")
            number_code = val.fields.get("number", "")
            suitability_code = val.fields.get("suitability_code", "S0")
            revision_code = val.fields.get("revision_code", "P01.01")

    try:
        created = service.create_project(
            name=name,
            description=description,
            status=status_field,
            ifc_file_path=ifc_file_path,
            ifc_md5_hash=ifc_md5_hash,
            country=country,
            analysis_type=analysis_type,
            building_code=building_code,
            project_type=project_type,
            project_size_sqm=project_size_sqm,
            buildings_count=buildings_count,
            floors_count=floors_count,
            project_code=project_code,
            originator=originator,
            volume_system=volume_system,
            level=level,
            type=type_code,
            role=role_code,
            number=number_code,
            suitability_code=suitability_code,
            revision_code=revision_code,
            classification_standard=classification_standard,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    _link_project_inputs(
        service,
        int(created["id"]),
        document_ids=document_ids,
        standards_codes=standards_codes,
    )
    return ProjectResponse(**created)


@router.put("/{project_id}", response_model=ProjectResponse, summary="Update project")
def update_project(
    project_id: int,
    payload: ProjectUpdateRequest,
    service: Annotated[ProjectsService, Depends(get_projects_service)],
) -> ProjectResponse:
    """Update metadata for an existing project."""
    existing = service.get_project(project_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found.",
        )

    name = payload.name if payload.name is not None else existing.get("name", "")
    description = (
        payload.description if payload.description is not None else existing.get("description", "")
    )
    status_val = payload.status if payload.status is not None else existing.get("status", "Draft")
    country = payload.country if payload.country is not None else existing.get("country", "")
    analysis_type = (
        payload.analysis_type
        if payload.analysis_type is not None
        else existing.get("analysis_type", "")
    )

    try:
        updated = service.update_project(
            project_id,
            name,
            description,
            status_val,
            country=country,
            analysis_type=analysis_type,
            project_code=payload.project_code,
            originator=payload.originator,
            volume_system=payload.volume_system,
            level=payload.level,
            type=payload.type,
            role=payload.role,
            number=payload.number,
            suitability_code=payload.suitability_code,
            revision_code=payload.revision_code,
            cde_state=payload.cde_state.value if hasattr(payload.cde_state, "value") else payload.cde_state,
            classification_standard=payload.classification_standard,
        )
        return ProjectResponse(**(updated or service.get_project(project_id)))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete project")
def delete_project(
    project_id: int,
    service: Annotated[ProjectsService, Depends(get_projects_service)],
) -> None:
    """Delete a project and its associated metadata."""
    existing = service.get_project(project_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found.",
        )
    service.delete_project(project_id)


@router.get("/{project_id}/ifc", summary="Download project IFC model")
def download_project_ifc(
    project_id: int,
    service: Annotated[ProjectsService, Depends(get_projects_service)],
):
    """Retrieve and download the stored IFC model for a project."""
    project = service.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found.",
        )
    if not project.get("ifc_file_path"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No IFC file is attached to this project.",
        )

    file_path = service.resolve_ifc_file(project_id)
    if file_path is None or not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not retrieve the IFC file from storage.",
        )

    filename = f"{project.get('name', 'model')}.ifc"
    return FileResponse(
        str(file_path),
        media_type="application/octet-stream",
        filename=filename,
    )


@router.get("/{project_id}/enhancements", summary="Get model lineage history")
def get_project_enhancements(
    project_id: int,
    service: Annotated[ProjectsService, Depends(get_projects_service)],
) -> list[dict]:
    """Retrieve immutable model lineage versions and quality improvement records."""
    from app.services.model_lineage import SupabaseModelLineageRepository

    repo = SupabaseModelLineageRepository()
    return repo.list_for_project(project_id)


class EnhanceRequest(BaseModel):
    token: Optional[str] = ""


@router.post("/{project_id}/enhance", summary="Trigger IFC model quality improvements")
def trigger_project_enhancement(
    project_id: int,
    service: Annotated[ProjectsService, Depends(get_projects_service)],
    payload: Optional[EnhanceRequest] = None,
) -> dict:
    """Execute model enhancement pipeline and persist a new immutable version."""
    from app.services.pipeline_services import execute_model_enhancement

    project = service.get_project(project_id)
    if not project or not project.get("ifc_file_path"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has no IFC model attached.",
        )

    try:
        result = execute_model_enhancement(
            project_id=project_id,
            source_reference=project["ifc_file_path"],
        )
        return result
    except Exception as exc:
        logger.error("Enhancement failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Model quality enhancement failed: {exc}",
        )


@router.get("/{project_id}/enhancements/{lineage_id}/download", summary="Download enhanced IFC model version")
def download_project_enhancement(
    project_id: int,
    lineage_id: int,
):
    """Download quality-improved IFC model artifact for a specific lineage version."""
    from app.services.model_lineage import SupabaseModelLineageRepository
    from app.services.object_storage import ObjectStorage

    repo = SupabaseModelLineageRepository()
    lineage = repo.get(lineage_id)
    if lineage is None or int(lineage.get("project_id") or 0) != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model lineage version not found for project.",
        )

    storage = ObjectStorage()
    output_ref = str(lineage.get("output_reference") or "")
    local_path = storage.materialize_local_path(output_ref)
    if local_path is None or not local_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generated enhanced model file not found in storage.",
        )

    return FileResponse(
        str(local_path),
        media_type="application/octet-stream",
        filename=local_path.name,
    )


#: Role recorded for a model the caller gave no role for. Matches the column
#: default: a model whose discipline nobody stated is context for the ones that
#: have one, not a second primary.
DEFAULT_IFC_ROLE = "context"


def _validated_ifc_names(files: list[UploadFile]) -> list[str]:
    """Return the uploads' filenames, rejecting the set if any is not an IFC.

    Validated as a set before a single byte is stored: a caller uploading the
    four discipline models of one building wants all four attached or none, not
    three attached and a message about the fourth.

    Raises:
        HTTPException: 400 naming the offending file.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one .ifc file is required.",
        )

    names: list[str] = []
    for upload in files:
        name = (upload.filename or "").strip()
        if not name.lower().endswith(".ifc"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{name or 'A file'} is not an .ifc model; nothing was uploaded.",
            )
        names.append(name)
    return names


def _roles_for(roles: list[str], count: int, primary_index: int) -> list[str]:
    """Align the roles list with the files list.

    ``roles`` is parallel to ``files`` when given. Omitting it entirely is the
    common case -- a caller who has not classified the models yet -- and is not
    an error; a partial list is, because there is no way to tell which files the
    roles it does hold were meant for.

    Raises:
        HTTPException: 400 if a non-empty ``roles`` does not match ``files``.
    """
    if roles and len(roles) != count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"roles has {len(roles)} entries for {count} files; pass one role "
                "per file, or none at all."
            ),
        )
    if roles:
        return [(role or "").strip() or DEFAULT_IFC_ROLE for role in roles]
    return [
        ProjectsService.PRIMARY_ROLE if index == primary_index else DEFAULT_IFC_ROLE
        for index in range(count)
    ]


@router.post(
    "/{project_id}/upload",
    response_model=ProjectIfcUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Attach one or more IFC models to a project (Multipart)",
)
async def upload_project_ifc_files(
    project_id: int,
    service: Annotated[ProjectsService, Depends(get_projects_service)],
    phase6_service: Annotated[Phase6Service, Depends(get_phase6_service)],
    files: Annotated[list[UploadFile], File(description="IFC models to attach")],
    primary_index: Annotated[int, Form()] = 0,
    roles: Annotated[list[str], Form()] = [],
) -> ProjectIfcUploadResponse:
    """Store every uploaded model and record it against the project.

    The model at ``primary_index`` becomes the project's primary: the one a
    corrosion run analyses, and the one ``projects.ifc_file_path`` keeps
    pointing at so every reader that predates ``project_ifc_files`` still
    resolves a model. The rest are attached alongside it, which is what lets a
    seismic run see the whole building rather than one discipline of it.

    Args:
        project_id: Project to attach the models to.
        files: The uploads. Every one must be an ``.ifc``.
        primary_index: Index into ``files`` of the primary model.
        roles: Optional discipline per file, parallel to ``files``.

    Raises:
        HTTPException: 404 if the project does not exist; 400 if the uploads are
            not all IFC models, if ``primary_index`` is out of range, or if
            ``roles`` is given with a different length than ``files``; 500 if
            storage rejects a model, naming it and how many were stored first.
    """
    if service.get_project(project_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found.",
        )

    names = _validated_ifc_names(files)
    if not 0 <= primary_index < len(names):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"primary_index {primary_index} is outside the {len(names)} "
                "uploaded files; nothing was uploaded."
            ),
        )
    file_roles = _roles_for(roles, len(names), primary_index)

    attached: list[ProjectIfcFileResponse] = []
    for index, (upload, name) in enumerate(zip(files, names)):
        content = await upload.read()
        stored = phase6_service.upload_service.upload(
            name, content, project_id=project_id, kind="ifc"
        )
        if not stored.success or stored.ref is None:
            # The models stored before this one keep their rows. Rolling them
            # back would delete bytes that are safely stored and correctly
            # recorded to undo nothing; the caller is told how far the upload
            # got so the retry can be the remainder.
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    f"{name} could not be stored: {stored.error or 'unknown error'}. "
                    f"{len(attached)} of {len(names)} models were attached."
                ),
            )

        row = service.add_ifc_file(
            project_id,
            file_path=stored.ref.storage_ref,
            file_name=stored.ref.filename,
            role=file_roles[index],
            is_primary=index == primary_index,
        )
        attached.append(ProjectIfcFileResponse(**{"project_id": project_id, **row}))

    primary = service.get_primary_ifc_file(project_id)
    logger.info(
        "Project IFC models attached project_id=%d count=%d primary=%s",
        project_id,
        len(attached),
        (primary or {}).get("file_path"),
    )
    return ProjectIfcUploadResponse(
        success=True,
        files=attached,
        primary_id=(primary or {}).get("id"),
    )


@router.get(
    "/{project_id}/files",
    response_model=list[ProjectIfcFileResponse],
    summary="List the IFC models attached to a project",
)
def list_project_ifc_files(
    project_id: int,
    service: Annotated[ProjectsService, Depends(get_projects_service)],
) -> list[ProjectIfcFileResponse]:
    """Return a project's attached models, primary first.

    A project whose model predates ``project_ifc_files`` reports that model as a
    single primary entry with no ``id``, so a client renders one shape either
    side of the migration.

    Raises:
        HTTPException: 404 if the project does not exist. An existing project
            with no model is an empty list, not a 404 -- having no model yet is
            a state, not a missing resource.
    """
    if service.get_project(project_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found.",
        )
    return [
        ProjectIfcFileResponse(**{"project_id": project_id, **row})
        for row in service.get_ifc_files_by_project(project_id)
    ]


@router.get(
    "/{project_id}/files/{file_id}/ifc",
    summary="Download one of a project's attached IFC models",
)
def download_project_ifc_file(
    project_id: int,
    file_id: int,
    service: Annotated[ProjectsService, Depends(get_projects_service)],
):
    """Retrieve the bytes of one attached model, by ``project_ifc_files.id``.

    ``GET /{project_id}/ifc`` resolves through ``projects.ifc_file_path`` and so
    always serves the primary. A viewer offering the project's models as a list
    needs to fetch the one the user picked, which is what this addresses.

    Args:
        project_id: Project owning the model.
        file_id: ``project_ifc_files.id`` of the model to download.

    Raises:
        HTTPException: 404 if the project does not exist or holds no such model;
            502 if the row names bytes that storage cannot produce.
    """
    if service.get_project(project_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {project_id} not found.",
        )

    resolved, missing = service.resolve_ifc_file_paths(project_id)
    for row, local_path in resolved:
        if row.get("id") == file_id and local_path.exists():
            return FileResponse(
                str(local_path),
                media_type="application/octet-stream",
                filename=row.get("file_name") or f"model-{file_id}.ifc",
            )

    # Separated so "storage is down" does not read to the caller as "you asked
    # for a model this project never had".
    if any(row.get("id") == file_id for row in missing):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not retrieve the IFC file from storage.",
        )
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Project {project_id} has no attached model with ID {file_id}.",
    )


# ---------------------------------------------------------------------------
# ISO 19650 CDE State Machine Endpoints
# ---------------------------------------------------------------------------


class CDETransitionRequest(BaseModel):
    target_state: str = Field(..., description="Target CDE state (WIP, SHARED, PUBLISHED, ARCHIVED)")
    actor: str = Field(default="Lead Appointed Party", description="Entity initiating state transition")
    approved_by: str = Field(default="", description="Approver identifier for SHARED -> PUBLISHED transition")


class CDEApprovalRequest(BaseModel):
    approved_by: str = Field(..., description="Lead Appointed Party approver name / title")


@router.post("/{project_id}/cde/transition", response_model=ProjectResponse, summary="Execute ISO 19650 CDE state transition")
def transition_project_cde_state(
    project_id: int,
    payload: CDETransitionRequest,
    service: Annotated[ProjectsService, Depends(get_projects_service)],
):
    """Execute ISO 19650 CDE state transition with gateway verification."""
    from app.services.cde_state_machine import CDEStateMachine

    sm = CDEStateMachine(projects_service=service)
    try:
        updated = sm.transition_project(
            project_id=project_id,
            target_state=payload.target_state,
            actor=payload.actor,
            approved_by=payload.approved_by,
        )
        return ProjectResponse(**updated)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{project_id}/cde/approve", response_model=ProjectResponse, summary="Approve project for PUBLISHED CDE state")
def approve_project_cde_state(
    project_id: int,
    payload: CDEApprovalRequest,
    service: Annotated[ProjectsService, Depends(get_projects_service)],
):
    """Grant Lead Appointed Party approval for PUBLISHED state transition."""
    from app.services.cde_state_machine import CDEStateMachine

    sm = CDEStateMachine(projects_service=service)
    try:
        updated = sm.transition_project(
            project_id=project_id,
            target_state="PUBLISHED",
            approved_by=payload.approved_by,
        )
        return ProjectResponse(**updated)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{project_id}/cde/validate-naming", summary="Validate project IFC container ISO 19650 naming")
def validate_project_iso_naming(
    project_id: int,
    service: Annotated[ProjectsService, Depends(get_projects_service)],
) -> dict:
    """Validate project attached primary model filename against ISO 19650 National Annex."""
    from app.modules.document_parsing.iso_validator import ISO19650Validator

    project = service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    filename = project.get("ifc_file_path", "")
    val = ISO19650Validator.validate_filename(filename)
    return val.to_dict()

