"""SCIM 2.0 Users/Groups provisioning, mapped onto BIM-Guard's existing organization membership, profile, and RBAC-group model.

A SCIM "user" is a Supabase Auth account plus that account's membership row
in one organization; SCIM deprovisioning (`active: false` or DELETE) removes
the membership, not the underlying Supabase Auth identity, since the same
person may belong to other organizations this IdP doesn't manage. A SCIM
"group" is one of that organization's existing RBAC groups (see
app.services.membership_service.MembershipService's group methods) -- the
natural mapping, since a group already exists purely to grant a set of
members access to a set of projects, the same shape an IdP-pushed security
group has.
"""

from __future__ import annotations

from typing import Any

from app.services.membership_service import MembershipService
from app.services.profile_service import ProfileService

_DEFAULT_ROLE = "member"
_LIST_PAGE_SIZE = 200


class ScimUserNotFound(Exception):
    """Raised when a SCIM operation targets a user id not provisioned in this organization."""


class ScimGroupNotFound(Exception):
    """Raised when a SCIM operation targets a group id not found in this organization."""


class ScimService:
    """Domain service bridging SCIM 2.0 Users/Groups onto existing org services."""

    def __init__(
        self,
        *,
        membership_service: MembershipService,
        profile_service: ProfileService,
        db_client: Any,
    ):
        """Initialize with the org/profile services and the service-role Supabase client.

        `db_client.auth.admin` is only accessed lazily, inside the methods
        that need it (not at construction time) -- the same reason
        app.services.user_admin_service.UserAdminService stores the raw
        client rather than `.auth.admin`: PersistenceService.get_db() can
        return an in-memory fallback client with no `.auth` attribute when
        Supabase credentials aren't configured, and that fallback must stay
        usable for everything that doesn't need real user-account creation.
        """
        self._memberships = membership_service
        self._profiles = profile_service
        self._db_client = db_client

    @property
    def _auth_admin(self) -> Any:
        return self._db_client.auth.admin

    # -- Users ------------------------------------------------------------------

    def _user_row(self, organization_id: int, user_id: str) -> dict[str, Any] | None:
        role = self._memberships.role_for_user(organization_id, user_id)
        if role is None:
            return None
        profile = self._profiles.get(user_id) or {}
        return {
            "id": user_id,
            "user_name": profile.get("email") or user_id,
            "full_name": profile.get("full_name") or "",
            "role": role,
            "active": True,
        }

    def list_users(
        self,
        organization_id: int,
        *,
        user_name_filter: str | None = None,
        start_index: int = 1,
        count: int = 100,
    ) -> tuple[int, list[dict[str, Any]]]:
        """Return (total_matching, page) of users provisioned into *organization_id*."""
        rows = []
        for m in self._memberships.list_members_raw(organization_id):
            row = self._user_row(organization_id, m["user_id"])
            if row is not None:
                rows.append(row)
        if user_name_filter:
            needle = user_name_filter.strip().lower()
            rows = [r for r in rows if r["user_name"].lower() == needle]
        total = len(rows)
        start = max(start_index - 1, 0)
        page = rows[start : start + max(count, 0)]
        return total, page

    def get_user(self, organization_id: int, user_id: str) -> dict[str, Any]:
        """Return one provisioned user's row, or raise ScimUserNotFound."""
        row = self._user_row(organization_id, user_id)
        if row is None:
            raise ScimUserNotFound(user_id)
        return row

    def create_user(
        self,
        organization_id: int,
        *,
        user_name: str,
        full_name: str = "",
        active: bool = True,
    ) -> dict[str, Any]:
        """Provision *user_name* (an email) into *organization_id*.

        Creates a Supabase Auth account for them if one doesn't exist yet
        (an IdP-driven signup, using the same admin API as
        scripts/seed_dev_auth_user.py), then adds their membership.
        """
        found = self._find_auth_user_by_email(user_name)
        if found is not None:
            user_id = found["id"]
        else:
            created = self._auth_admin.create_user({"email": user_name, "email_confirm": True})
            user_id = self._extract_user_id(created)

        self._profiles.ensure_profile(user_id, full_name=full_name, email=user_name)
        if full_name:
            self._profiles.update(user_id, {"full_name": full_name})
        if active:
            self._memberships.add_member(organization_id, user_id, _DEFAULT_ROLE)
        return self._user_row(organization_id, user_id) or {
            "id": user_id,
            "user_name": user_name,
            "full_name": full_name,
            "role": _DEFAULT_ROLE,
            "active": False,
        }

    def replace_user(
        self,
        organization_id: int,
        user_id: str,
        *,
        user_name: str,
        full_name: str = "",
        active: bool = True,
    ) -> dict[str, Any]:
        """Replace a provisioned user's profile fields and org membership state."""
        if full_name:
            self._profiles.update(user_id, {"full_name": full_name})
        if active:
            role = self._memberships.role_for_user(organization_id, user_id) or _DEFAULT_ROLE
            self._memberships.add_member(organization_id, user_id, role)
        else:
            self._memberships.remove_member(organization_id, user_id)
        row = self._user_row(organization_id, user_id)
        if row is not None:
            return row
        profile = self._profiles.get(user_id) or {}
        return {
            "id": user_id,
            "user_name": profile.get("email") or user_name,
            "full_name": profile.get("full_name") or full_name,
            "role": _DEFAULT_ROLE,
            "active": False,
        }

    def patch_user_active(self, organization_id: int, user_id: str, active: bool) -> dict[str, Any]:
        """Toggle org membership -- the one PATCH operation IdPs actually send.

        Deprovisioning removes the membership (org access), not the
        underlying Supabase Auth identity -- see module docstring.
        """
        if active:
            role = self._memberships.role_for_user(organization_id, user_id) or _DEFAULT_ROLE
            self._memberships.add_member(organization_id, user_id, role)
            row = self._user_row(organization_id, user_id)
            if row is not None:
                return row
        else:
            self._memberships.remove_member(organization_id, user_id)
        profile = self._profiles.get(user_id) or {}
        return {
            "id": user_id,
            "user_name": profile.get("email") or user_id,
            "full_name": profile.get("full_name") or "",
            "role": _DEFAULT_ROLE,
            "active": active,
        }

    def delete_user(self, organization_id: int, user_id: str) -> None:
        """Deprovision *user_id* from *organization_id* (membership only)."""
        self._memberships.remove_member(organization_id, user_id)

    def _extract_user_id(self, created: Any) -> str:
        user = getattr(created, "user", None)
        if user is not None:
            return user.id
        if isinstance(created, dict):
            return created.get("user", created).get("id")
        raise ValueError("Unexpected Supabase admin create_user() response shape")

    def _find_auth_user_by_email(self, email: str) -> dict[str, Any] | None:
        normalized = email.strip().lower()
        page = 1
        while True:
            result = self._auth_admin.list_users(page=page, per_page=_LIST_PAGE_SIZE)
            users = getattr(result, "users", None)
            if users is None:
                users = result if isinstance(result, list) else result.get("users", [])
            if not users:
                return None
            for u in users:
                u_email = getattr(u, "email", None)
                if u_email is None and isinstance(u, dict):
                    u_email = u.get("email")
                if u_email and u_email.strip().lower() == normalized:
                    u_id = getattr(u, "id", None) or (u.get("id") if isinstance(u, dict) else None)
                    return {"id": u_id}
            if len(users) < _LIST_PAGE_SIZE:
                return None
            page += 1

    # -- Groups -------------------------------------------------------------------

    def _group_row(self, organization_id: int, group_id: int) -> dict[str, Any] | None:
        group = self._memberships.get_group(group_id)
        if group is None or group.get("organization_id") != organization_id:
            return None
        members = [
            m
            for m in self._memberships.list_members_raw(organization_id)
            if m.get("group_id") == group_id
        ]
        profiles = self._profiles.get_many([m["user_id"] for m in members])
        return {
            "id": group_id,
            "display_name": group["name"],
            "members": [
                {
                    "value": m["user_id"],
                    "display": profiles.get(m["user_id"], {}).get("email", m["user_id"]),
                }
                for m in members
            ],
        }

    def list_groups(self, organization_id: int) -> list[dict[str, Any]]:
        """Return every RBAC group in *organization_id*, SCIM-shaped."""
        rows = []
        for g in self._memberships.list_groups(organization_id):
            row = self._group_row(organization_id, g["id"])
            if row is not None:
                rows.append(row)
        return rows

    def get_group(self, organization_id: int, group_id: int) -> dict[str, Any]:
        """Return one group's row, or raise ScimGroupNotFound."""
        row = self._group_row(organization_id, group_id)
        if row is None:
            raise ScimGroupNotFound(group_id)
        return row

    def create_group(
        self, organization_id: int, *, display_name: str, member_ids: list[str]
    ) -> dict[str, Any]:
        """Create a new RBAC group and move *member_ids* into it."""
        group = self._memberships.create_group(organization_id, display_name)
        for user_id in member_ids:
            self._safe_set_member_group(organization_id, user_id, group["id"])
        return self._group_row(organization_id, group["id"]) or {
            "id": group["id"],
            "display_name": display_name,
            "members": [],
        }

    def replace_group(
        self, organization_id: int, group_id: int, *, display_name: str, member_ids: list[str]
    ) -> dict[str, Any]:
        """Replace a group's member list wholesale (name changes are not stored per-group today)."""
        current = self._group_row(organization_id, group_id)
        if current is None:
            raise ScimGroupNotFound(group_id)
        current_member_ids = {m["value"] for m in current["members"]}
        wanted = set(member_ids)
        for user_id in current_member_ids - wanted:
            self._safe_set_member_group(organization_id, user_id, None)
        for user_id in wanted - current_member_ids:
            self._safe_set_member_group(organization_id, user_id, group_id)
        return self._group_row(organization_id, group_id) or current

    def delete_group(self, organization_id: int, group_id: int) -> None:
        """Delete a group, raising ScimGroupNotFound if it doesn't belong to *organization_id*."""
        try:
            self._memberships.delete_group(organization_id, group_id)
        except ValueError as exc:
            raise ScimGroupNotFound(group_id) from exc

    def _safe_set_member_group(self, organization_id: int, user_id: str, group_id: int | None) -> None:
        try:
            self._memberships.set_member_group(organization_id, user_id, group_id)
        except ValueError:
            # The IdP referenced a user id that isn't a member of this
            # organization (or the group vanished mid-request) -- SCIM has no
            # clean per-member error signal here, so skip it rather than
            # failing the whole group operation.
            pass
