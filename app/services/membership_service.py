"""Organization membership lookups — the multi-tenancy bridge for authenticated users.

``public.memberships`` links a Supabase-authenticated user to the
organizations they belong to. ``app.api.projects`` uses ``org_ids_for_user``
to scope project access; this service also exists so a freshly authenticated
user has somewhere to belong on first sign-in — either by consuming a pending
``public.organization_invites`` row addressed to their email, or, absent one,
defaulting into the single pre-existing "Default Organization" that owns all
legacy (pre-multi-tenant) projects.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.db_adapters import DatabaseAdapter

DEFAULT_ORGANIZATION_SLUG = "default"


class MembershipService:
    """Domain service for organization membership records."""

    def __init__(
        self,
        memberships_repo: DatabaseAdapter,
        organizations_repo: DatabaseAdapter,
        invites_repo: DatabaseAdapter,
        groups_repo: DatabaseAdapter,
        group_project_grants_repo: DatabaseAdapter,
        organization_project_grants_repo: DatabaseAdapter,
    ):
        """Initialize service with persistence repository adapters."""
        self._memberships = memberships_repo
        self._organizations = organizations_repo
        self._invites = invites_repo
        self._groups = groups_repo
        self._group_project_grants = group_project_grants_repo
        self._org_project_grants = organization_project_grants_repo

    def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        """Return the organizations *user_id* belongs to, with their role in each."""
        memberships = self._memberships.rows_where("user_id = ?", [user_id])
        results: list[dict[str, Any]] = []
        for membership in memberships:
            org = self._organizations.get(membership["organization_id"])
            if org is None:
                continue
            results.append(
                {
                    "organization_id": org["id"],
                    "name": org["name"],
                    "slug": org["slug"],
                    "role": membership["role"],
                }
            )
        return results

    def org_ids_for_user(self, user_id: str) -> set[int]:
        """Return the ids of every organization *user_id* belongs to.

        Falls back to :meth:`ensure_default_membership` when the caller has
        no membership row yet — normally this has already happened by login
        time (``GET /api/auth/me`` calls it), so this is just a safety net
        for a request that somehow arrives first. This path has no email to
        consume invites with, so it can only ever land someone in the default
        organization; :meth:`ensure_membership` is what handles invites.
        """
        memberships = self.list_for_user(user_id)
        if not memberships:
            memberships = self.ensure_default_membership(user_id)
        return {m["organization_id"] for m in memberships}

    def ensure_membership(self, user_id: str, email: str) -> list[dict[str, Any]]:
        """Give a first-time signer somewhere to belong.

        Order of precedence: an existing membership wins outright; failing
        that, any pending invite addressed to *email* is consumed (turned
        into real memberships, one per invited organization); failing that,
        the caller joins the default organization — see
        :meth:`ensure_default_membership`.
        """
        existing = self.list_for_user(user_id)
        if existing:
            return existing

        invited = self._consume_invites(user_id, email)
        if invited:
            return invited

        return self.ensure_default_membership(user_id)

    def _consume_invites(self, user_id: str, email: str) -> list[dict[str, Any]]:
        """Turn every pending invite addressed to *email* into a real membership."""
        normalized = (email or "").strip().lower()
        if not normalized:
            return []

        pending = [
            invite
            for invite in self._invites.rows_where("email = ?", [normalized])
            if not invite.get("accepted_at")
        ]
        if not pending:
            return []

        now = datetime.now(timezone.utc).isoformat()
        for invite in pending:
            self._memberships.insert(
                {
                    "organization_id": invite["organization_id"],
                    "user_id": user_id,
                    "role": invite.get("role") or "member",
                }
            )
            self._invites.update(updates={"accepted_at": now}, pk_values=invite["id"])

        return self.list_for_user(user_id)

    def get_organization(self, organization_id: int) -> dict[str, Any] | None:
        """Return the organization row for *organization_id*, or None."""
        return self._organizations.get(organization_id)

    def list_all_organizations(self) -> list[dict[str, Any]]:
        """Return every organization on the platform, newest first.

        Used only for the superadmin's org<->ruleset grant screen; nothing
        else needs to enumerate organizations outside the caller's own.
        """
        return sorted(self._organizations.rows, key=lambda o: o["id"], reverse=True)

    def role_for_user(self, organization_id: int, user_id: str) -> str | None:
        """Return *user_id*'s role in *organization_id*, or None if not a member."""
        rows = self._memberships.rows_where(
            "organization_id = ?", [organization_id]
        )
        return next((r["role"] for r in rows if r["user_id"] == user_id), None)

    def list_members_raw(self, organization_id: int) -> list[dict[str, Any]]:
        """Return the raw membership rows (user_id, role) for *organization_id*."""
        return self._memberships.rows_where("organization_id = ?", [organization_id])

    def update_role(self, organization_id: int, user_id: str, role: str) -> None:
        """Change a member's role within an organization.

        Raises:
            ValueError: if *user_id* has no membership row in *organization_id*.
        """
        rows = self._memberships.rows_where("organization_id = ?", [organization_id])
        membership = next((r for r in rows if r["user_id"] == user_id), None)
        if membership is None:
            raise ValueError(f"User {user_id} is not a member of organization {organization_id}.")
        self._memberships.update(updates={"role": role}, pk_values=membership["id"])

    def remove_member(self, organization_id: int, user_id: str) -> None:
        """Remove *user_id*'s membership in *organization_id*, if any."""
        rows = self._memberships.rows_where("organization_id = ?", [organization_id])
        membership = next((r for r in rows if r["user_id"] == user_id), None)
        if membership is not None:
            self._memberships.delete(membership["id"])

    def list_invites(self, organization_id: int) -> list[dict[str, Any]]:
        """Return every invite (pending and accepted) for *organization_id*, newest first."""
        rows = self._invites.rows_where("organization_id = ?", [organization_id])
        return sorted(rows, key=lambda r: r.get("id", 0), reverse=True)

    def create_invite(self, organization_id: int, email: str, role: str) -> dict[str, Any]:
        """Create a pending invite addressed to *email* for *organization_id*."""
        normalized = (email or "").strip().lower()
        if not normalized:
            raise ValueError("An email address is required to invite someone.")
        return self._invites.insert(
            {
                "organization_id": organization_id,
                "email": normalized,
                "role": role,
            }
        )

    def revoke_invite(self, organization_id: int, invite_id: int) -> None:
        """Delete a pending invite, scoped to *organization_id* so one admin can't revoke another org's invite by guessing its id.

        Raises:
            ValueError: if no such invite exists in this organization.
        """
        invite = self._invites.get(invite_id)
        if invite is None or invite.get("organization_id") != organization_id:
            raise ValueError(f"Invite {invite_id} not found in organization {organization_id}.")
        self._invites.delete(invite_id)

    def ensure_default_membership(self, user_id: str) -> list[dict[str, Any]]:
        """Join *user_id* into the default organization on first sign-in.

        A brand-new Supabase user has no membership row yet; without one they
        would see no organizations at all. Every pre-multi-tenant project
        already lives in the "default" organization (see
        ``supabase/migrations/20260904235344_create_organizations_and_memberships.sql``),
        so that's where a first-time sign-in lands absent a pending invite.
        """
        existing = self.list_for_user(user_id)
        if existing:
            return existing

        default_org = next(
            iter(self._organizations.rows_where("slug = ?", [DEFAULT_ORGANIZATION_SLUG], limit=1)),
            None,
        )
        if default_org is None:
            return []

        self._memberships.insert(
            {
                "organization_id": default_org["id"],
                "user_id": user_id,
                "role": "member",
            }
        )
        return self.list_for_user(user_id)

    # -- Groups ---------------------------------------------------------------

    def list_groups(self, organization_id: int) -> list[dict[str, Any]]:
        """Return every group in *organization_id*, newest first, with member counts."""
        groups = self._groups.rows_where("organization_id = ?", [organization_id])
        members = self._memberships.rows_where("organization_id = ?", [organization_id])
        counts: dict[int, int] = {}
        for m in members:
            gid = m.get("group_id")
            if gid is not None:
                counts[gid] = counts.get(gid, 0) + 1
        results = [
            {
                "id": g["id"],
                "organization_id": g["organization_id"],
                "name": g["name"],
                "member_count": counts.get(g["id"], 0),
            }
            for g in groups
        ]
        return sorted(results, key=lambda g: g["id"], reverse=True)

    def create_group(self, organization_id: int, name: str) -> dict[str, Any]:
        """Create a new group within *organization_id*.

        Raises:
            ValueError: if *name* is blank or already used in this organization.
        """
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValueError("A group name is required.")
        existing = self._groups.rows_where("organization_id = ?", [organization_id])
        if any(g["name"].lower() == clean_name.lower() for g in existing):
            raise ValueError(f"A group named {clean_name!r} already exists in this organization.")
        return self._groups.insert({"organization_id": organization_id, "name": clean_name})

    def get_group(self, group_id: int) -> dict[str, Any] | None:
        """Return the group row for *group_id*, or None."""
        return self._groups.get(group_id)

    def delete_group(self, organization_id: int, group_id: int) -> None:
        """Delete a group, un-grouping any members who were in it.

        Raises:
            ValueError: if no such group exists in this organization.
        """
        group = self._groups.get(group_id)
        if group is None or group.get("organization_id") != organization_id:
            raise ValueError(f"Group {group_id} not found in organization {organization_id}.")
        for m in self._memberships.rows_where("organization_id = ?", [organization_id]):
            if m.get("group_id") == group_id:
                self._memberships.update(updates={"group_id": None}, pk_values=m["id"])
        self._groups.delete(group_id)

    def set_member_group(self, organization_id: int, user_id: str, group_id: int | None) -> None:
        """Move a member into *group_id* (or ungroup them, if None).

        Raises:
            ValueError: if the member or the target group doesn't belong to
                *organization_id*.
        """
        membership = self._membership_row(organization_id, user_id)
        if membership is None:
            raise ValueError(f"User {user_id} is not a member of organization {organization_id}.")
        if group_id is not None:
            group = self._groups.get(group_id)
            if group is None or group.get("organization_id") != organization_id:
                raise ValueError(f"Group {group_id} not found in organization {organization_id}.")
        self._memberships.update(updates={"group_id": group_id}, pk_values=membership["id"])

    def _membership_row(self, organization_id: int, user_id: str) -> dict[str, Any] | None:
        rows = self._memberships.rows_where("organization_id = ?", [organization_id])
        return next((r for r in rows if r["user_id"] == user_id), None)

    # -- Group -> project grants ------------------------------------------------

    def list_group_project_ids(self, group_id: int) -> list[int]:
        """Return the ids of every project *group_id* is granted access to."""
        rows = self._group_project_grants.rows_where("group_id = ?", [group_id])
        return [r["project_id"] for r in rows]

    def set_group_project_grants(self, group_id: int, project_ids: list[int]) -> None:
        """Replace *group_id*'s entire set of granted projects."""
        existing = {r["project_id"]: r for r in self._group_project_grants.rows_where("group_id = ?", [group_id])}
        wanted = set(project_ids)
        for project_id, row in existing.items():
            if project_id not in wanted:
                self._group_project_grants.delete(row["id"])
        for project_id in wanted - set(existing.keys()):
            self._group_project_grants.insert({"group_id": group_id, "project_id": project_id})

    def member_can_access_project(self, organization_id: int, user_id: str, project_id: int) -> bool:
        """Whether a confirmed member of *organization_id* may access *project_id*.

        An owner or admin sees every project in their own organization. A
        plain member sees only what their group is granted — nothing, if
        they aren't in a group. This is the RBAC layer beneath organization
        membership: belonging to the org is necessary but not sufficient.
        """
        membership = self._membership_row(organization_id, user_id)
        if membership is None:
            return False
        if membership["role"] in ("owner", "admin"):
            return True
        group_id = membership.get("group_id")
        if group_id is None:
            return False
        grants = self._group_project_grants.rows_where("group_id = ?", [group_id])
        return any(g["project_id"] == project_id for g in grants)

    def accessible_project_ids(self, organization_id: int, user_id: str) -> set[int] | None:
        """Return the project ids a confirmed member of *organization_id* may access.

        None means "every project in the organization" (owner/admin); a set
        (possibly empty) is the member's group grant.
        """
        membership = self._membership_row(organization_id, user_id)
        if membership is None:
            return set()
        if membership["role"] in ("owner", "admin"):
            return None
        group_id = membership.get("group_id")
        if group_id is None:
            return set()
        return set(self.list_group_project_ids(group_id))

    # -- Organization -> project grants (cross-org sharing, superadmin) --------

    def list_org_project_grants(self, organization_id: int) -> list[int]:
        """Return the ids of every project shared into *organization_id*.

        Projects it doesn't own but has been granted access to.
        """
        rows = self._org_project_grants.rows_where("organization_id = ?", [organization_id])
        return [r["project_id"] for r in rows]

    def set_org_project_grants(self, organization_id: int, project_ids: list[int]) -> None:
        """Replace *organization_id*'s entire set of granted (non-owned) projects."""
        existing = {
            r["project_id"]: r for r in self._org_project_grants.rows_where("organization_id = ?", [organization_id])
        }
        wanted = set(project_ids)
        for project_id, row in existing.items():
            if project_id not in wanted:
                self._org_project_grants.delete(row["id"])
        for project_id in wanted - set(existing.keys()):
            self._org_project_grants.insert({"organization_id": organization_id, "project_id": project_id})

    def granting_organizations_for_project(self, project_id: int) -> list[int]:
        """Organizations (other than the owner) granted access to *project_id*."""
        rows = self._org_project_grants.rows_where("project_id = ?", [project_id])
        return [r["organization_id"] for r in rows]

    def organizations_with_project_access(self, project_id: int, owning_organization_id: int) -> set[int]:
        """Every organization that may access *project_id*: its owner plus any cross-org grants.

        ``member_can_access_project`` doesn't care whether an organization
        owns a project or was merely granted it -- both checks are the same
        role/group test -- so this is the only place ownership and grants
        need to be combined.
        """
        return {owning_organization_id, *self.granting_organizations_for_project(project_id)}
