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

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
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
    ModelAttachStatusResponse,
    ModelListResponse,
    ModelResponse,
    ModelUpdateRequest,
    ModelUploadResponse,
)
from app.services import model_attach_tracker
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


def _iso_fields_for(
    name: str,
    *,
    separator: str,
    guess_separator: bool,
    expected_project_code: str,
    allow_project_code_mismatch: bool,
) -> tuple[dict[str, str], str | None]:
    """Read ISO 19650 container-naming fields from a filename, without requiring them.

    The parsed fields are stored as metadata only -- nothing selects an
    engine, discipline or analysis path from them -- so a filename that does
    not follow the 7-field convention is attached with a warning rather than
    rejected, and its fields are left to default from the owning project.

    The one field that is checked is the project code: a filename that parses
    cleanly and names a different project is most likely being uploaded to
    the wrong one, and the upload UI does not surface warnings, so that case
    is still refused unless the caller explicitly opts in.

    Returns:
        ``(fields, warning)`` -- ``fields`` is empty when the name did not
        parse; ``warning`` is ``None`` when there is nothing to report.

    Raises:
        HTTPException: 422 when a cleanly parsed project code does not match
            the project's and ``allow_project_code_mismatch`` is not set.
    """
    file_sep = separator
    if guess_separator:
        if name.count("-") >= 6 and name.count("_") < 6:
            file_sep = "-"
        elif name.count("_") >= 6 and name.count("-") < 6:
            file_sep = "_"
    try:
        fields = validate_and_parse_filename(name, separator=file_sep)
    except ISO19650ValidationError as exc:
        return {}, f"{name} does not follow ISO 19650 container naming ({exc}); attached without naming metadata."

    parsed_code = fields["project_code"]
    if expected_project_code and parsed_code.casefold() != expected_project_code.strip().casefold():
        mismatch = (
            f"{name} names project code '{parsed_code}', but this project's code is "
            f"'{expected_project_code}'."
        )
        if not allow_project_code_mismatch:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"{mismatch} It may belong to a different project; nothing was uploaded. "
                    "Rename the file, or resend with allow_project_code_mismatch=true to attach it anyway."
                ),
            )
        return fields, f"{mismatch} Attached anyway, as requested."
    return fields, None


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
    background_tasks: BackgroundTasks,
    files: Annotated[list[UploadFile], File(description="IFC models to attach")],
    primary_index: Annotated[int, Form()] = 0,
    roles: Annotated[list[str], Form()] = [],
    allow_project_code_mismatch: Annotated[bool, Form()] = False,
) -> ModelUploadResponse:
    """Validate the upload, then store and attach every model in the background.

    The model at ``primary_index`` becomes the project's primary: the one a
    corrosion run analyses, and the one ``projects.ifc_file_path`` keeps
    pointing at so every reader that predates ``project_ifc_files`` still
    resolves a model. The rest are attached alongside it, which is what lets a
    seismic run see the whole building rather than one discipline of it.

    Everything that can be checked from the request alone (file extensions,
    ``primary_index``, ``roles``, the ISO 19650 project code) still happens
    here and still fails the request synchronously. A filename that does not
    follow ISO 19650 container naming is not a failure: the model attaches
    and the response carries a warning (see :func:`_iso_fields_for`). The slow part -- an IFC preflight
    parse plus a network upload to Supabase Storage, per file -- runs after
    the response, because doing it inline routinely exceeded the Cloudflare
    Tunnel's ~100s idle timeout (HTTP 524) for large or multi-file attaches,
    even though the origin kept working and finished anyway. Poll
    ``GET /projects/{id}/models/attach-status`` for completion.

    Args:
        project_id: Project to attach the models to.
        files: The uploads. Every one must be an ``.ifc``.
        primary_index: Index into ``files`` of the primary model.
        roles: Optional discipline per file, parallel to ``files``.
        allow_project_code_mismatch: Attach a file whose ISO 19650 name
            carries another project's code instead of refusing it.

    Raises:
        HTTPException: 404 if the project does not exist; 400 if the uploads are
            not all IFC models, if ``primary_index`` is out of range, or if
            ``roles`` is given with a different length than ``files``; 422 if a
            filename parses as ISO 19650 but names a different project code
            and ``allow_project_code_mismatch`` is not set.
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
    is_configured = bool(naming_config and naming_config.get("is_configured"))
    convention = naming_service.resolve_convention(naming_config) if is_configured else {}
    separator = str(naming_config.get("separator") or convention.get("separator") or "-") if is_configured else "-"
    expected_project_code = str(project.get("project_code") or "")

    parsed_files = []
    warnings: list[str] = []
    for name in names:
        parsed, warning = _iso_fields_for(
            name,
            separator=separator,
            guess_separator=not is_configured,
            expected_project_code=expected_project_code,
            allow_project_code_mismatch=allow_project_code_mismatch,
        )
        parsed_files.append(parsed)
        if warning:
            warnings.append(warning)
            logger.warning("Model naming warning project_id=%d: %s", project_id, warning)

    # Bytes must be read from the request while it's still open; storing them
    # is the slow part deferred below.
    contents = [await upload.read() for upload in files]

    model_attach_tracker.start(project_id, total=len(names))
    background_tasks.add_task(
        _attach_files_in_background,
        project_id=project_id,
        names=names,
        contents=contents,
        parsed_files=parsed_files,
        file_roles=file_roles,
        primary_index=primary_index,
        service=service,
        phase6_service=phase6_service,
    )

    return ModelUploadResponse(
        success=True, files=[], primary_id=None, processing=True, warnings=warnings
    )


def _attach_files_in_background(
    *,
    project_id: int,
    names: list[str],
    contents: list[bytes],
    parsed_files: list[dict],
    file_roles: list[str],
    primary_index: int,
    service: ModelsService,
    phase6_service: Phase6Service,
) -> None:
    """Store and attach every file, off the request/response cycle.

    Runs in a worker thread after the response is sent (see ``BackgroundTasks``
    in :func:`upload_models`). Reports progress through
    :mod:`app.services.model_attach_tracker` since there is no request left to
    answer.
    """
    attached_count = 0
    try:
        for index, (name, content, parsed) in enumerate(zip(names, contents, parsed_files)):
            stored = phase6_service.upload_service.upload(
                name, content, project_id=project_id, kind="ifc"
            )
            if not stored.success or stored.ref is None:
                # The models stored before this one keep their rows. Rolling
                # them back would delete bytes that are safely stored and
                # correctly recorded to undo nothing.
                model_attach_tracker.finish(
                    project_id,
                    error=(
                        f"{name} could not be stored: {stored.error or 'unknown error'}. "
                        f"{attached_count} of {len(names)} models were attached."
                    ),
                )
                return

            service.attach_model(
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
            attached_count += 1
            model_attach_tracker.progress(project_id, attached=attached_count)

        primary = service.get_primary(project_id)
        logger.info(
            "Project IFC models attached project_id=%d count=%d primary=%s",
            project_id,
            attached_count,
            (primary or {}).get("file_path"),
        )
        model_attach_tracker.finish(project_id)
    except Exception as exc:
        logger.exception("Background model attach failed project_id=%d", project_id)
        model_attach_tracker.finish(project_id, error=str(exc))


@router.get(
    "/projects/{project_id}/models/attach-status",
    response_model=ModelAttachStatusResponse,
    summary="Poll the status of a background model-attach job",
)
def get_attach_status(
    project_id: int,
    project: Annotated[dict, Depends(get_authorized_project)],
) -> ModelAttachStatusResponse:
    """Report progress of the attach job started by the last model upload.

    ``processing`` is ``False`` both before any attach has run and once the
    last one has finished -- the caller distinguishes those by ``attached``
    and ``error``, or simply by having just received ``processing: True`` from
    the upload call that started this job.
    """
    job = model_attach_tracker.get(project_id)
    if job is None:
        return ModelAttachStatusResponse(processing=False, total=0, attached=0, error=None)
    return ModelAttachStatusResponse(
        processing=not job.done,
        total=job.total,
        attached=job.attached,
        error=job.error,
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
