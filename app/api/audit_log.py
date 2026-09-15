"""FastAPI router for reading the audit trail.

Superadmin-only, matching how app/api/permissions.py gates the role-permission
matrix -- the audit_log table itself denies all direct client access (RLS),
so this route is the only way to read entries back.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_audit_log_service, get_profile_service
from app.api.organizations import _require_superadmin
from app.auth import CurrentUser, get_current_user
from app.modules.contracts import AuditLogEntryResponse, AuditLogListResponse
from app.services.audit_log_service import AuditLogService
from app.services.profile_service import ProfileService

router = APIRouter()


@router.get("", response_model=AuditLogListResponse, summary="List recent audit log entries")
def list_audit_log(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    audit_log: Annotated[AuditLogService, Depends(get_audit_log_service)],
    organization_id: Annotated[int | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> AuditLogListResponse:
    """Return the most recent audit entries, optionally scoped to an organization."""
    _require_superadmin(current_user, profiles)
    entries = audit_log.list_entries(organization_id=organization_id, limit=limit)
    return AuditLogListResponse(entries=[AuditLogEntryResponse(**e) for e in entries])
