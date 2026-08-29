"""FastAPI router for project management and IFC model operations."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.api.dependencies import get_projects_service
from app.constants import DEFAULT_ANALYSIS_TYPE, DEFAULT_COUNTRY
from app.logging_config import get_logger
from app.modules.contracts import (
    AnalysisInputItemContract,
    ProjectCreateRequest,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdateRequest,
)
from app.services.projects_service import ProjectsService

logger = get_logger(__name__)

router = APIRouter()


@router.get("", response_model=ProjectListResponse, summary="List all projects")
def list_projects(
    service: Annotated[ProjectsService, Depends(get_projects_service)],
) -> ProjectListResponse:
    """Return all projects ordered newest first."""
    rows = service.list_projects()
    projects = [ProjectResponse(**row) for row in rows]
    return ProjectListResponse(total=len(projects), projects=projects)


@router.get("/{project_id}", response_model=ProjectResponse, summary="Get project by ID")
def get_project(
    project_id: int,
    service: Annotated[ProjectsService, Depends(get_projects_service)],
) -> ProjectResponse:
    """Retrieve a single project by primary key."""
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
        )
        return ProjectResponse(**created)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


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
    ifc_file: Optional[UploadFile] = File(None),
) -> ProjectResponse:
    """Create a project and optionally attach an uploaded IFC model."""
    ifc_file_path = ""
    ifc_md5_hash = ""
    if ifc_file is not None and ifc_file.filename:
        ifc_file_path, ifc_md5_hash = await service.prepare_ifc_upload(ifc_file)

    try:
        created = service.create_project(
            name=name,
            description=description,
            status=status_field,
            ifc_file_path=ifc_file_path,
            ifc_md5_hash=ifc_md5_hash,
            country=country,
            analysis_type=analysis_type,
        )
        return ProjectResponse(**created)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


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

    updated = service.update_project(project_id, name, description, status_val)
    return ProjectResponse(**(updated or service.get_project(project_id)))


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
    token: str = ""


@router.post("/{project_id}/enhance", summary="Trigger IFC model quality improvements")
def trigger_project_enhancement(
    project_id: int,
    payload: EnhanceRequest,
    service: Annotated[ProjectsService, Depends(get_projects_service)],
) -> dict:
    """Execute model enhancement pipeline and persist a new immutable version."""
    from app.services.pipeline_services import execute_model_enhancement
    from app.services.projects_service import is_enhancement_authorized

    if not is_enhancement_authorized(payload.token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid enhancement authorization token.",
        )

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


