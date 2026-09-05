"""Organization membership lookups — the multi-tenancy bridge for authenticated users.

``public.memberships`` links a Supabase-authenticated user to the
organizations they belong to. ``app.api.projects`` uses ``org_ids_for_user``
to scope project access; this service also exists so a freshly authenticated
user has somewhere to belong, defaulting into the single pre-existing
"Default Organization" that owns all legacy (pre-multi-tenant) projects.
"""

from __future__ import annotations

from typing import Any

from app.services.db_adapters import DatabaseAdapter

DEFAULT_ORGANIZATION_SLUG = "default"


class MembershipService:
    """Domain service for organization membership records."""

    def __init__(self, memberships_repo: DatabaseAdapter, organizations_repo: DatabaseAdapter):
        """Initialize service with persistence repository adapters."""
        self._memberships = memberships_repo
        self._organizations = organizations_repo

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
        for a request that somehow arrives first.
        """
        memberships = self.list_for_user(user_id)
        if not memberships:
            memberships = self.ensure_default_membership(user_id)
        return {m["organization_id"] for m in memberships}

    def ensure_default_membership(self, user_id: str) -> list[dict[str, Any]]:
        """Join *user_id* into the default organization on first sign-in.

        A brand-new Supabase user has no membership row yet; without one they
        would see no organizations at all. Every pre-multi-tenant project
        already lives in the "default" organization (see
        ``supabase/migrations/20260904235344_create_organizations_and_memberships.sql``),
        so that's where a first-time sign-in lands until real organization
        creation/invite flows exist.
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
