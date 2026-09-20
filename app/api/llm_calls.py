"""FastAPI router for reading the LLM call log.

Superadmin-only, matching how app/api/audit_log.py gates the audit trail --
the llm_calls table itself denies all direct client access (RLS), so this
route is the only way to read entries back.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_llm_call_log_service, get_profile_service
from app.api.organizations import _require_superadmin
from app.auth import CurrentUser, get_current_user
from app.modules.contracts import LLMCallLogEntryResponse, LLMCallLogListResponse
from app.services.llm_call_log_service import LLMCallLogService
from app.services.profile_service import ProfileService

router = APIRouter()


@router.get("", response_model=LLMCallLogListResponse, summary="List recent LLM call log entries")
def list_llm_calls(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    llm_calls: Annotated[LLMCallLogService, Depends(get_llm_call_log_service)],
    organization_id: Annotated[int | None, Query()] = None,
    project_id: Annotated[int | None, Query()] = None,
    context: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> LLMCallLogListResponse:
    """Return the most recent LLM call entries, optionally filtered."""
    _require_superadmin(current_user, profiles)
    entries = llm_calls.list_entries(
        organization_id=organization_id, project_id=project_id, context=context, limit=limit
    )
    return LLMCallLogListResponse(entries=[LLMCallLogEntryResponse(**e) for e in entries])
