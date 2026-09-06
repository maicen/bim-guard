"""Document access control.

Which organizations, and which of their projects, may use which documents
from the global Rule Documents library (``public.documents`` — no owning
organization, the same situation rulesets were in before
``RulesetAccessService``). Mirrors that service's two-level grant exactly:

1. ``organization_document_grants`` — which documents an organization may
   use at all. Superadmin-controlled.
2. ``project_document_bindings`` — which of the org's granted documents are
   actually bound to one project. Owner/admin-controlled, and always a
   subset of (1). A freshly created project has none.
"""

from __future__ import annotations

from app.services.db_adapters import DatabaseAdapter


class DocumentAccessService:
    """Domain service for organization/project document grants."""

    def __init__(
        self,
        organization_document_grants_repo: DatabaseAdapter,
        project_document_bindings_repo: DatabaseAdapter,
    ):
        """Initialize service with persistence repository adapters."""
        self._org_grants = organization_document_grants_repo
        self._project_bindings = project_document_bindings_repo

    # -- Organization grants (superadmin) --------------------------------------

    def list_org_grants(self, organization_id: int) -> list[int]:
        """Return the document ids *organization_id* is allowed to use at all."""
        rows = self._org_grants.rows_where("organization_id = ?", [organization_id])
        return [r["document_id"] for r in rows]

    def set_org_grants(self, organization_id: int, document_ids: list[int]) -> None:
        """Replace *organization_id*'s entire set of granted documents.

        Narrowing an org's grants does not retroactively unbind any project
        that already had one of the removed documents bound -- a project's
        own bindings are the source of truth for what it lists as relevant.
        """
        existing = {
            r["document_id"]: r
            for r in self._org_grants.rows_where("organization_id = ?", [organization_id])
        }
        wanted = set(document_ids)

        # Batch deletes
        to_delete = [row["id"] for doc_id, row in existing.items() if doc_id not in wanted]
        if to_delete:
            self._org_grants.delete_many(to_delete)

        # Batch inserts
        to_insert = [
            {"organization_id": organization_id, "document_id": doc_id}
            for doc_id in wanted - set(existing.keys())
        ]
        if to_insert:
            self._org_grants.insert_many(to_insert)

    # -- Project bindings (owner/admin) ----------------------------------------

    def list_project_bindings(self, project_id: int) -> list[int]:
        """Return the document ids bound to *project_id*."""
        rows = self._project_bindings.rows_where("project_id = ?", [project_id])
        return [r["document_id"] for r in rows]

    def set_project_bindings(
        self,
        project_id: int,
        document_ids: list[int],
        *,
        organization_id: int,
    ) -> None:
        """Replace *project_id*'s entire set of bound documents.

        Raises:
            ValueError: if any requested document isn't granted to
                *organization_id* -- a project can only bind what its own
                organization has been granted, never more.
        """
        allowed = set(self.list_org_grants(organization_id))
        requested = set(document_ids)
        not_allowed = requested - allowed
        if not_allowed:
            raise ValueError(
                f"Document(s) {sorted(not_allowed)!r} are not granted to this organization; "
                "ask a superadmin to grant them first."
            )

        existing = {
            r["document_id"]: r
            for r in self._project_bindings.rows_where("project_id = ?", [project_id])
        }

        # Batch deletes
        to_delete = [row["id"] for doc_id, row in existing.items() if doc_id not in requested]
        if to_delete:
            self._project_bindings.delete_many(to_delete)

        # Batch inserts
        to_insert = [
            {"project_id": project_id, "document_id": doc_id}
            for doc_id in requested - set(existing.keys())
        ]
        if to_insert:
            self._project_bindings.insert_many(to_insert)

    def project_can_use_document(self, project_id: int, document_id: int) -> bool:
        """Whether *project_id* has *document_id* bound."""
        return document_id in self.list_project_bindings(project_id)
