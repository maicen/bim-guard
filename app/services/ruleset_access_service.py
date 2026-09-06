"""Ruleset access control.

Which organizations, and which of their projects, may use which rulesets
(``rule_folders.ruleset_id``).

Rules are the one platform resource that is genuinely global and shared
today (see ``app.api.rules``), so unlike projects/models/docs — which are
already scoped by ``organization_id`` on the row itself — access to a
ruleset needs its own two-level grant:

1. ``organization_ruleset_grants`` — which rulesets an organization may use
   at all. Superadmin-controlled.
2. ``project_ruleset_bindings`` — which of the org's granted rulesets are
   actually bound to one project. Owner/admin-controlled, and always a
   subset of (1). A freshly created project has none: "zero bindings unless
   assigned" is this table being empty, not a flag.
"""

from __future__ import annotations

from app.services.db_adapters import DatabaseAdapter


class RulesetAccessService:
    """Domain service for organization/project ruleset grants."""

    def __init__(
        self,
        organization_ruleset_grants_repo: DatabaseAdapter,
        project_ruleset_bindings_repo: DatabaseAdapter,
    ):
        """Initialize service with persistence repository adapters."""
        self._org_grants = organization_ruleset_grants_repo
        self._project_bindings = project_ruleset_bindings_repo

    # -- Organization grants (superadmin) --------------------------------------

    def list_org_grants(self, organization_id: int) -> list[str]:
        """Return the ruleset ids *organization_id* is allowed to use at all."""
        rows = self._org_grants.rows_where("organization_id = ?", [organization_id])
        return [r["ruleset_id"] for r in rows]

    def set_org_grants(self, organization_id: int, ruleset_ids: list[str]) -> None:
        """Replace *organization_id*'s entire set of granted rulesets.

        Narrowing an org's grants does not retroactively unbind any project
        that already had one of the removed rulesets bound — a project's own
        bindings are the source of truth for what an analysis run may select
        from; see :meth:`project_available_ruleset_ids`, which is where the
        two are intersected back together.
        """
        existing = {r["ruleset_id"]: r for r in self._org_grants.rows_where("organization_id = ?", [organization_id])}
        wanted = set(ruleset_ids)
        to_delete = [row["id"] for ruleset_id, row in existing.items() if ruleset_id not in wanted]
        if to_delete:
            if hasattr(self._org_grants, "delete_many"):
                self._org_grants.delete_many(to_delete)
            else:
                for pk in to_delete:
                    self._org_grants.delete(pk)
        to_insert = [
            {"organization_id": organization_id, "ruleset_id": ruleset_id}
            for ruleset_id in wanted - set(existing.keys())
        ]
        if to_insert:
            if hasattr(self._org_grants, "insert_many"):
                self._org_grants.insert_many(to_insert)
            else:
                for row in to_insert:
                    self._org_grants.insert(row)

    # -- Project bindings (owner/admin) ----------------------------------------

    def list_project_bindings(self, project_id: int) -> list[str]:
        """Return the ruleset ids bound to *project_id*."""
        rows = self._project_bindings.rows_where("project_id = ?", [project_id])
        return [r["ruleset_id"] for r in rows]

    def set_project_bindings(
        self,
        project_id: int,
        ruleset_ids: list[str],
        *,
        organization_id: int,
    ) -> None:
        """Replace *project_id*'s entire set of bound rulesets.

        Raises:
            ValueError: if any requested ruleset isn't granted to
                *organization_id* — a project can only bind what its own
                organization has been granted, never more.
        """
        allowed = set(self.list_org_grants(organization_id))
        requested = set(ruleset_ids)
        not_allowed = requested - allowed
        if not_allowed:
            raise ValueError(
                f"Ruleset(s) {sorted(not_allowed)!r} are not granted to this organization; "
                "ask a superadmin to grant them first."
            )

        existing = {r["ruleset_id"]: r for r in self._project_bindings.rows_where("project_id = ?", [project_id])}
        to_delete = [row["id"] for ruleset_id, row in existing.items() if ruleset_id not in requested]
        if to_delete:
            if hasattr(self._project_bindings, "delete_many"):
                self._project_bindings.delete_many(to_delete)
            else:
                for pk in to_delete:
                    self._project_bindings.delete(pk)
        to_insert = [
            {"project_id": project_id, "ruleset_id": ruleset_id}
            for ruleset_id in requested - set(existing.keys())
        ]
        if to_insert:
            if hasattr(self._project_bindings, "insert_many"):
                self._project_bindings.insert_many(to_insert)
            else:
                for row in to_insert:
                    self._project_bindings.insert(row)

    def project_can_use_ruleset(self, project_id: int, ruleset_id: str) -> bool:
        """Whether *project_id* has *ruleset_id* bound."""
        return ruleset_id in self.list_project_bindings(project_id)
