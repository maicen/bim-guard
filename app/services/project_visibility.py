"""Shared project-visibility filtering.

Used by the project list endpoint, the dashboard stats orchestrator, and the
BCF reports listing so they never disagree about which projects a caller can
see -- the logic exists exactly once here rather than being reimplemented at
each call site.
"""

from __future__ import annotations

from typing import Any, Optional

from app.services.membership_service import MembershipService
from app.services.profile_service import ProfileService


def visible_project_rows(
    all_rows: list[dict[str, Any]],
    *,
    user_id: str,
    organization_id: Optional[int],
    memberships: MembershipService,
    profiles: ProfileService,
) -> list[dict[str, Any]]:
    """Filter project rows to the ones a user may see, optionally scoped to one org.

    A superadmin sees every organization's projects when no filter is applied;
    everyone else sees only projects owned by or granted to their orgs.
    """
    if profiles.is_superadmin(user_id):
        if organization_id is not None:
            shared_in = set(memberships.list_org_project_grants(organization_id))
            return [
                row for row in all_rows
                if row.get("organization_id") == organization_id or row.get("id") in shared_in
            ]
        return all_rows

    user_org_ids = memberships.org_ids_for_user(user_id)
    if organization_id is not None:
        if organization_id not in user_org_ids:
            return []
        target_orgs = {organization_id}
    else:
        target_orgs = user_org_ids

    accessible_by_org: dict[int, set[int] | None] = {
        org_id: memberships.accessible_project_ids(org_id, user_id) for org_id in target_orgs
    }
    granted_in_by_org: dict[int, set[int]] = {
        org_id: set(memberships.list_org_project_grants(org_id))
        for org_id, accessible in accessible_by_org.items()
        if accessible is None
    }

    def _visible(row: dict) -> bool:
        pid = row.get("id")
        owning_org = row.get("organization_id")
        for org_id, accessible in accessible_by_org.items():
            if accessible is None:
                if owning_org == org_id or pid in granted_in_by_org[org_id]:
                    return True
            elif pid in accessible:
                return True
        return False

    return [row for row in all_rows if _visible(row)]
