"""FastAPI router for ISO 19650 information-container naming configuration.

Serves the static catalog -- the conventions, token vocabulary, master code
library and CDE status table -- and reads, writes and previews the naming setup
of one project.
"""

from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_naming_config_service
from app.api.projects import get_authorized_project
from app.logging_config import get_logger
from app.modules.contracts import (
    NamingCatalogResponseContract as NamingCatalogResponse,
)
from app.modules.contracts import (
    NamingConfigContract as NamingConfig,
)
from app.modules.contracts import (
    NamingConfigUpdateContract as NamingConfigUpdate,
)
from app.modules.contracts import (
    NamingPreviewRequestContract as NamingPreviewRequest,
)
from app.modules.contracts import (
    NamingPreviewResponseContract as NamingPreviewResponse,
)
from app.services.naming_config_service import (
    CDE_STATUS_CODES,
    DATE_FORMATS,
    DEFAULT_CONVENTION,
    DEFAULTS,
    NAMING_TOKENS,
    SEPARATORS,
    NamingConfigService,
)

logger = get_logger(__name__)

router = APIRouter()

_TOKEN_RE = re.compile(r"\{(\w+)\}")


@router.get(
    "/catalog",
    response_model=NamingCatalogResponse,
    summary="Get the ISO 19650 naming catalog",
)
def get_catalog(
    service: Annotated[NamingConfigService, Depends(get_naming_config_service)],
) -> NamingCatalogResponse:
    """Return the conventions, tokens, code library and CDE statuses.

    None of this is per-project, so a client fetches it once and reuses it
    across every project it configures.
    """
    return NamingCatalogResponse(
        conventions=service.conventions(),
        tokens=NAMING_TOKENS,
        codes=service.master_codes(),
        cde_statuses=CDE_STATUS_CODES,
        date_formats=list(DATE_FORMATS),
        separators=SEPARATORS,
        default_convention=DEFAULT_CONVENTION,
    )


@router.get(
    "/presets",
    response_model=NamingCatalogResponse,
    summary="Get the ISO 19650 naming catalog (alias of /catalog)",
)
def get_presets(
    service: Annotated[NamingConfigService, Depends(get_naming_config_service)],
) -> NamingCatalogResponse:
    """Return the same payload as ``/catalog``.

    Kept because ``/presets`` is the path the feature was specified against; the
    catalog is one document and splitting the conventions out of it would make a
    client fetch twice to render one form.
    """
    return get_catalog(service)


@router.get(
    "/projects/{project_id}",
    response_model=NamingConfig,
    summary="Get a project's naming configuration",
)
def get_project_naming_config(
    project_id: int,
    service: Annotated[NamingConfigService, Depends(get_naming_config_service)],
    project: Annotated[dict, Depends(get_authorized_project)],
) -> NamingConfig:
    """Return one project's naming setup, or the defaults if it has none.

    Raises:
        HTTPException: 404 if the project does not exist or is not the
            caller's to access.
    """
    return NamingConfig(**service.get_for_project(project_id))


@router.put(
    "/projects/{project_id}",
    response_model=NamingConfig,
    summary="Save a project's naming configuration",
)
def save_project_naming_config(
    project_id: int,
    payload: NamingConfigUpdate,
    service: Annotated[NamingConfigService, Depends(get_naming_config_service)],
    project: Annotated[dict, Depends(get_authorized_project)],
) -> NamingConfig:
    """Create or update one project's naming setup and return it.

    Only the fields present in the payload are written, so a save from one tab
    of the form leaves the rest as they were.

    Raises:
        HTTPException: 404 if the project does not exist or is not the
            caller's to access.
    """
    saved = service.save_for_project(project_id, payload.model_dump(exclude_unset=True))
    return NamingConfig(**saved)


@router.delete(
    "/projects/{project_id}",
    response_model=NamingConfig,
    summary="Reset a project's naming configuration to the defaults",
)
def reset_project_naming_config(
    project_id: int,
    service: Annotated[NamingConfigService, Depends(get_naming_config_service)],
    project: Annotated[dict, Depends(get_authorized_project)],
) -> NamingConfig:
    """Drop a project's saved configuration and return the defaults it falls back to.

    Deleting a configuration a project never had is not an error: the outcome
    the caller asked for -- this project is unconfigured -- already holds.

    Raises:
        HTTPException: 404 if the project does not exist or is not the
            caller's to access.
    """
    service.delete_for_project(project_id)
    return NamingConfig(**service.get_for_project(project_id))


@router.post(
    "/preview",
    response_model=NamingPreviewResponse,
    summary="Render a sample name from an unsaved configuration",
)
def preview_name(
    payload: NamingPreviewRequest,
    service: Annotated[NamingConfigService, Depends(get_naming_config_service)],
) -> NamingPreviewResponse:
    """Render one container name from a configuration without saving it.

    Rendering lives here rather than in the client so the name a form previews
    and the name an export writes are produced by the same code.
    """
    config = {**DEFAULTS, **payload.config.model_dump(exclude_unset=True)}
    config = {
        key: ([item.model_dump() for item in value] if _is_model_list(value) else value)
        for key, value in config.items()
    }
    convention = service.resolve_convention(config)
    separator = str(config.get("separator") or convention.get("separator") or "_")
    name = service.render_name(config, overrides=payload.overrides)
    return NamingPreviewResponse(
        name=name,
        convention_id=str(convention.get("id") or DEFAULT_CONVENTION),
        applied_format=service.applied_format(convention, separator),
        unresolved_tokens=_TOKEN_RE.findall(name),
    )


def _is_model_list(value: object) -> bool:
    """Return True for a list of Pydantic models, which has to be dumped to dicts."""
    return isinstance(value, list) and bool(value) and hasattr(value[0], "model_dump")
