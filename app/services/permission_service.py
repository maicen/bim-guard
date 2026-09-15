"""Service layer for the superadmin-configurable role-permission matrix.

Every action in app.modules.permissions.Action requires a minimum org role
(owner/admin/member) to perform — this service is the single place that
decides, and is the drop-in replacement for the hardcoded
`role not in ("owner", "admin")` checks that used to live in
app/api/organizations.py, app/api/llm_provider_instances.py, and
app/api/projects.py. `can`/`require` resolve an org override row over the
platform-default (organization_id IS NULL) row for the action, mirroring
the same two-tier fallback ParsingEngineInstancesService uses for parsing
engines. A platform superadmin (ProfileService.is_superadmin) always
bypasses this matrix entirely, exactly as the hardcoded checks did before.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from app.auth import CurrentUser
from app.modules.permissions import ROLE_RANK, Action
from app.services.db_adapters import DatabaseAdapter
from app.services.membership_service import MembershipService
from app.services.profile_service import ProfileService

_DEFAULT_MIN_ROLE = "admin"


class PermissionService:
    """Domain service for evaluating and editing the role-permission matrix."""

    def __init__(
        self,
        role_permissions_repo: DatabaseAdapter,
        membership_service: MembershipService,
        profile_service: ProfileService,
    ):
        self._repo = role_permissions_repo
        self._memberships = membership_service
        self._profiles = profile_service

    def can(self, organization_id: int, user_id: str, action: Action) -> bool:
        """Check whether *user_id*'s role in *organization_id* meets *action*'s minimum role."""
        if self._profiles.is_superadmin(user_id):
            return True
        role = self._memberships.role_for_user(organization_id, user_id)
        if role is None:
            return False
        min_role = self._min_role_for(organization_id, action)
        return ROLE_RANK.get(role, -1) >= ROLE_RANK.get(min_role, 99)

    def require(self, organization_id: int, current_user: CurrentUser, action: Action) -> None:
        """Raise 404 if not a member of *organization_id*, else 403 if under-privileged."""
        if self._profiles.is_superadmin(current_user.id):
            return
        role = self._memberships.role_for_user(organization_id, current_user.id)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Organization {organization_id} not found.",
            )
        min_role = self._min_role_for(organization_id, action)
        if ROLE_RANK.get(role, -1) < ROLE_RANK.get(min_role, 99):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires the '{min_role}' role or higher in this organization.",
            )

    def get_effective_matrix(self, organization_id: int | None) -> dict[Action, str]:
        """Every action's effective minimum role for *organization_id* (org override merged over platform default)."""
        platform_rows = {r["action"]: r["min_role"] for r in self._rows_for(None)}
        matrix = {action: platform_rows.get(action.value, _DEFAULT_MIN_ROLE) for action in Action}
        if organization_id is not None:
            org_rows = {r["action"]: r["min_role"] for r in self._rows_for(organization_id)}
            for action in Action:
                if action.value in org_rows:
                    matrix[action] = org_rows[action.value]
        return matrix

    def set_min_role(self, organization_id: int | None, action: Action, min_role: str) -> None:
        """Set (creating or updating) the min_role for *action* in the given scope."""
        if min_role not in ROLE_RANK:
            raise ValueError(f"min_role must be one of {sorted(ROLE_RANK)}.")
        existing = self._row_for(organization_id, action)
        now = datetime.now(timezone.utc).isoformat()
        if existing:
            self._repo.update(updates={"min_role": min_role, "updated_at": now}, pk_values=existing["id"])
        else:
            self._repo.insert(
                {
                    "organization_id": organization_id,
                    "action": action.value,
                    "min_role": min_role,
                    "updated_at": now,
                }
            )

    def reset_to_default(self, organization_id: int, action: Action) -> None:
        """Delete an org's override row for *action*, so it falls back to the platform default."""
        existing = self._row_for(organization_id, action)
        if existing:
            self._repo.delete(existing["id"])

    def _min_role_for(self, organization_id: int, action: Action) -> str:
        org_row = self._row_for(organization_id, action)
        if org_row:
            return org_row["min_role"]
        platform_row = self._row_for(None, action)
        return platform_row["min_role"] if platform_row else _DEFAULT_MIN_ROLE

    def _row_for(self, organization_id: int | None, action: Action) -> dict[str, Any] | None:
        for row in self._rows_for(organization_id):
            if row.get("action") == action.value:
                return row
        return None

    def _rows_for(self, organization_id: int | None) -> list[dict[str, Any]]:
        return [r for r in self._repo.rows if r.get("organization_id") == organization_id]
