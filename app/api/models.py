"""FastAPI router for IFC model attachment and lifecycle.

Split out of ``app.api.projects``: a project can hold many models, and each
one has a lifecycle of its own (attach, become primary, get replaced, get
deleted) independent of the project's. Mounted at ``/api`` (not
``/api/models``) so it can expose both the model-collection shape
(``/api/models``, ``/api/models/{model_id}``) and the project-scoped attach
routes (``/api/projects/{project_id}/models``) from one router.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.api.dependencies import (
    get_github_repo_service,
    get_models_service,
    get_naming_config_service,
    get_phase6_service,
)
from app.api.projects import get_authorized_project
from app.logging_config import get_logger
from app.modules.contracts import (
    AttachRepoModelsRequest,
    ModelListResponse,
    ModelResponse,
    ModelUpdateRequest,
    ModelUploadResponse,
)
from app.services.github_repo_service import GitHubRepoService
from app.services.iso_validator import ISO19650ValidationError, validate_and_parse_filename
from app.services.models_service import ModelsService
from app.services.naming_config_service import NamingConfigService
from app.services.phase6_service import Phase6Service

logger = get_logger(__name__)

router = APIRouter()


#: Role recorded for a model the caller gave no role for. Matches the column
#: default: a model whose discipline nobody stated is context for the ones that
#: have one, not a second primary.
DEFAULT_MODEL_ROLE = "context"


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
        return [(role or "").strip() or DEFAULT_MODEL_ROLE for role in roles]
    return [
        ModelsService.PRIMARY_ROLE if index == primary_index else DEFAULT_MODEL_ROLE
        for index in range(count)
    ]


def _not_found(project_id: int, model_id: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Project {project_id} has no attached model with ID {model_id}.",
    )


@router.get(
    "/models",
    response_model=ModelListResponse,
    summary="List the IFC models attached to a project",
)
def list_models(
    project_id: int,
    project: Annotated[dict, Depends(get_authorized_project)],
    service: Annotated[ModelsService, Depends(get_models_service)],
) -> ModelListResponse:
    """Return a project's attached models, primary first.

    A project whose model predates ``project_ifc_files`` reports that model as a
    single primary entry with no ``id``, so a client renders one shape either
    side of the migration.

    Raises:
        HTTPException: 404 if the project does not exist. An existing project
            with no model is an empty list, not a 404 -- having no model yet is
            a state, not a missing resource.
    """
    models = [
        ModelResponse(**{"project_id": project_id, **row})
        for row in service.list_models(project_id)
    ]
    return ModelListResponse(project_id=project_id, models=models)


@router.get(
    "/models/{model_id}",
    response_model=ModelResponse,
    summary="Get one of a project's attached IFC models",
)
def get_model(
    model_id: int,
    project_id: int,
    project: Annotated[dict, Depends(get_authorized_project)],
    service: Annotated[ModelsService, Depends(get_models_service)],
) -> ModelResponse:
    """Return one attached model, by ``project_ifc_files.id``.

    Raises:
        HTTPException: 404 if the project does not exist or holds no such model.
    """
    for row in service.list_models(project_id):
        if row.get("id") == model_id:
            return ModelResponse(**{"project_id": project_id, **row})
    raise _not_found(project_id, model_id)


@router.post(
    "/projects/{project_id}/models",
    response_model=ModelUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Attach one or more IFC models to a project (Multipart)",
)
async def upload_models(
    project_id: int,
    project: Annotated[dict, Depends(get_authorized_project)],
    service: Annotated[ModelsService, Depends(get_models_service)],
    phase6_service: Annotated[Phase6Service, Depends(get_phase6_service)],
    naming_service: Annotated[NamingConfigService, Depends(get_naming_config_service)],
    files: Annotated[list[UploadFile], File(description="IFC models to attach")],
    primary_index: Annotated[int, Form()] = 0,
    roles: Annotated[list[str], Form()] = [],
) -> ModelUploadResponse:
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
    
    naming_config = naming_service.get_for_project(project_id)
    convention = naming_service.resolve_convention(naming_config)
    separator = str(naming_config.get("separator") or convention.get("separator") or "-")
    expected_project_code = project.get("project_code")

    parsed_files = []
    for name in names:
        try:
            parsed = validate_and_parse_filename(name, separator=separator, expected_project_code=expected_project_code)
            parsed_files.append(parsed)
        except ISO19650ValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            )

    attached: list[ModelResponse] = []
    for index, (upload, name, parsed) in enumerate(zip(files, names, parsed_files)):
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

        row = service.attach_model(
            project_id,
            file_path=stored.ref.storage_ref,
            file_name=stored.ref.filename,
            role=file_roles[index],
            is_primary=index == primary_index,
            project_code=parsed.get("project_code"),
            originator=parsed.get("originator"),
            volume_system=parsed.get("volume_system"),
            level=parsed.get("level"),
            type_code=parsed.get("type"),
            role_iso=parsed.get("role"),
            number=parsed.get("number"),
            cde_state="WIP",
        )
        attached.append(ModelResponse(**{"project_id": project_id, **row}))

    primary = service.get_primary(project_id)
    logger.info(
        "Project IFC models attached project_id=%d count=%d primary=%s",
        project_id,
        len(attached),
        (primary or {}).get("file_path"),
    )
    return ModelUploadResponse(
        success=True,
        files=attached,
        primary_id=(primary or {}).get("id"),
    )


@router.post(
    "/projects/{project_id}/models/from-repo",
    response_model=ModelUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Attach one or more IFC models from a GitHub repository to a project",
)
def attach_repo_models(
    project_id: int,
    payload: AttachRepoModelsRequest,
    project: Annotated[dict, Depends(get_authorized_project)],
    repo_service: Annotated[GitHubRepoService, Depends(get_github_repo_service)],
    service: Annotated[ModelsService, Depends(get_models_service)],
) -> ModelUploadResponse:
    """Attach model file(s) from a registered GitHub repository, by path.

    Unlike ``/models``, no bytes pass through this request: each model is
    recorded pointing at the repository's raw-content URL, which
    ``ObjectStorage`` already knows how to fetch and cache on demand.

    Raises:
        HTTPException: 404 if the project or repository does not exist; 400 if
            ``primary_index`` is out of range.
    """
    try:
        rows = repo_service.attach_models_to_project(
            project_id,
            repo_id=payload.repo_id,
            file_paths=payload.file_paths,
            primary_index=payload.primary_index,
        )
    except ValueError as exc:
        detail = str(exc)
        code = status.HTTP_404_NOT_FOUND if "Repository" in detail else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=detail)

    attached = [ModelResponse(**{"project_id": project_id, **row}) for row in rows]
    primary = service.get_primary(project_id)
    logger.info(
        "Project IFC models attached from repo project_id=%d repo_id=%d count=%d",
        project_id,
        payload.repo_id,
        len(attached),
    )
    return ModelUploadResponse(
        success=True,
        files=attached,
        primary_id=(primary or {}).get("id"),
    )


@router.post(
    "/models/{model_id}/primary",
    response_model=ModelResponse,
    summary="Set one of a project's attached IFC models as primary",
)
def set_primary_model(
    model_id: int,
    project_id: int,
    project: Annotated[dict, Depends(get_authorized_project)],
    service: Annotated[ModelsService, Depends(get_models_service)],
) -> ModelResponse:
    """Promote one of a project's models to primary, by ``project_ifc_files.id``.

    Raises:
        HTTPException: 404 if the project does not exist or holds no such model.
    """
    row = service.set_primary(project_id, model_id)
    if row is None:
        raise _not_found(project_id, model_id)
    return ModelResponse(**{"project_id": project_id, **row})


@router.post(
    "/models/{model_id}/refresh-metadata",
    response_model=ModelResponse,
    summary="Re-read schema/authoring-app/storey/element/discipline metadata for an attached model",
)
def refresh_model_metadata(
    model_id: int,
    project_id: int,
    project: Annotated[dict, Depends(get_authorized_project)],
    service: Annotated[ModelsService, Depends(get_models_service)],
) -> ModelResponse:
    """Re-extract a model's summary metadata without re-uploading it.

    For a row attached before this feature existed, or one whose extraction
    ran into a transient storage error the first time. Does not touch the
    stored model bytes.

    Raises:
        HTTPException: 404 if the project does not exist or holds no such model.
    """
    row = service.refresh_metadata(project_id, model_id)
    if row is None:
        raise _not_found(project_id, model_id)
    return ModelResponse(**{"project_id": project_id, **row})


@router.patch(
    "/models/{model_id}",
    response_model=ModelResponse,
    summary="Edit an attached model's display name, role, or ISO 19650 fields",
)
def update_model(
    model_id: int,
    project_id: int,
    payload: ModelUpdateRequest,
    project: Annotated[dict, Depends(get_authorized_project)],
    service: Annotated[ModelsService, Depends(get_models_service)],
) -> ModelResponse:
    """Update naming/ISO 19650 fields on an attached model.

    Every field in the payload is optional; only the ones actually sent are
    changed. Does not touch the stored model bytes -- see the ``/replace``
    endpoint for swapping the IFC file itself.

    Raises:
        HTTPException: 404 if the project does not exist or holds no such model.
    """
    row = service.update_model(project_id, model_id, **payload.model_dump(exclude_unset=True))
    if row is None:
        raise _not_found(project_id, model_id)
    return ModelResponse(**{"project_id": project_id, **row})


@router.post(
    "/models/{model_id}/replace",
    response_model=ModelResponse,
    summary="Replace the stored IFC file of an attached model with a new upload",
)
async def replace_model(
    model_id: int,
    project_id: int,
    project: Annotated[dict, Depends(get_authorized_project)],
    service: Annotated[ModelsService, Depends(get_models_service)],
    file: Annotated[UploadFile, File(description="Replacement IFC model")],
) -> ModelResponse:
    """Swap an attached model's bytes for a new upload, in place.

    The row's ``id``, role, and ISO 19650 fields are kept; only the file
    itself and its derived summary metadata (schema, storey/element counts,
    discipline breakdown) change. If the replaced model was primary,
    ``projects.ifc_file_path`` is repointed at the new object.

    Raises:
        HTTPException: 400 if the upload is not an ``.ifc`` file; 404 if the
            project does not exist or holds no such model.
    """
    [name] = _validated_ifc_names([file])
    content = await file.read()
    row = service.replace_model(project_id, model_id, content=content, file_name=name)
    if row is None:
        raise _not_found(project_id, model_id)
    return ModelResponse(**{"project_id": project_id, **row})


@router.delete(
    "/models/{model_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Detach and delete one of a project's attached IFC models",
)
def delete_model(
    model_id: int,
    project_id: int,
    project: Annotated[dict, Depends(get_authorized_project)],
    service: Annotated[ModelsService, Depends(get_models_service)],
) -> None:
    """Remove one of a project's models, by ``project_ifc_files.id``.

    Deleting the primary model promotes the next remaining one; deleting a
    project's last model leaves it with none, which is a valid state.

    Raises:
        HTTPException: 404 if the project does not exist or holds no such model.
    """
    deleted = service.delete_model(project_id, model_id)
    if deleted is None:
        raise _not_found(project_id, model_id)


@router.get(
    "/models/{model_id}/download",
    summary="Download one of a project's attached IFC models",
)
def download_model(
    model_id: int,
    project_id: int,
    project: Annotated[dict, Depends(get_authorized_project)],
    service: Annotated[ModelsService, Depends(get_models_service)],
):
    """Retrieve the bytes of one attached model, by ``project_ifc_files.id``.

    ``GET /api/projects/{project_id}/ifc`` resolves through
    ``projects.ifc_file_path`` and so always serves the primary. A viewer
    offering the project's models as a list needs to fetch the one the user
    picked, which is what this addresses.

    Args:
        model_id: ``project_ifc_files.id`` of the model to download.
        project_id: Project owning the model.

    Raises:
        HTTPException: 404 if the project does not exist or holds no such model;
            502 if the row names bytes that storage cannot produce.
    """
    resolved, missing = service.resolve_all_paths(project_id)
    for row, local_path in resolved:
        if row.get("id") == model_id and local_path.exists():
            return FileResponse(
                str(local_path),
                media_type="application/octet-stream",
                filename=row.get("file_name") or f"model-{model_id}.ifc",
            )

    # Separated so "storage is down" does not read to the caller as "you asked
    # for a model this project never had".
    if any(row.get("id") == model_id for row in missing):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not retrieve the IFC file from storage.",
        )
    raise _not_found(project_id, model_id)
