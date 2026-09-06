"""FastAPI router for application runtime settings and log level."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_profile_service, get_settings_service
from app.api.organizations import _require_superadmin
from app.auth import CurrentUser, get_current_user
from app.logging_config import current_level_name, get_logger, set_log_level
from app.modules.contracts import (
    SettingItemContract as SettingItem,
)
from app.modules.contracts import (
    SettingsResponseContract as SettingsResponse,
)
from app.modules.contracts import (
    SettingsUpdateRequestContract as SettingsUpdateRequest,
)
from app.services.persistence import PersistenceService
from app.services.profile_service import ProfileService
from app.services.settings_service import SettingsService

logger = get_logger(__name__)

# These are instance-wide settings (e.g. the process log level), not scoped
# to any organization or project, so "signed in" isn't a fine enough check --
# every route here is superadmin-only, the same bar app/api/organizations.py
# holds its platform-wide actions to.
router = APIRouter()


@router.get("", response_model=SettingsResponse, summary="Get application settings")
def get_settings(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[SettingsService, Depends(get_settings_service)],
) -> SettingsResponse:
    """Retrieve runtime settings stored in database and current log level."""
    _require_superadmin(current_user, profiles)
    raw_settings = service.list_settings()
    items = [
        SettingItem(
            key=str(s.get("key", "")),
            value=str(s.get("value", "")),
            description=str(s.get("description", "")),
        )
        for s in raw_settings
        if s.get("key")
    ]
    return SettingsResponse(
        settings=items,
        active_log_level=current_level_name(),
        db_backend=PersistenceService.DB_BACKEND.upper(),
    )


@router.post("", response_model=SettingsResponse, summary="Update application settings")
def update_settings(
    payload: SettingsUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[SettingsService, Depends(get_settings_service)],
) -> SettingsResponse:
    """Update runtime key-value settings in persistence."""
    _require_superadmin(current_user, profiles)
    for key, value in payload.settings.items():
        if not key:
            continue
        service.set(key, value)
        if key == "BIM_GUARD_LOG_LEVEL" and value:
            try:
                set_log_level(value)
            except Exception as exc:
                logger.warning("Could not set log level to %s: %s", value, exc)

    return get_settings(current_user, profiles, service)

