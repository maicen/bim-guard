"""Persistence repository for immutable IFC model enhancement lineage."""

from __future__ import annotations

from typing import Any

from app.services.persistence import PersistenceService
from app.utils import now_iso_utc


class SupabaseModelLineageRepository:
    """Append enhancement lineage records through the shared Supabase adapter."""

    def __init__(self, *, lineage_repo=None) -> None:
        """Initialize the model enhancement lineage table adapter with dependency injection."""
        self._lineage = (
            lineage_repo
            if lineage_repo is not None
            else PersistenceService.get_table(
                "model_enhancement_lineage",
                {
                    "id": int,
                    "project_id": int,
                    "source_reference": str,
                    "source_sha256": str,
                    "source_version": int,
                    "output_reference": str,
                    "version": int,
                    "summary": dict,
                    "created_at": str,
                },
            )
        )

    def record(
        self,
        *,
        project_id: int,
        source_reference: str,
        source_sha256: str,
        source_version: int,
        output_reference: str,
        version: int,
        summary: dict[str, Any],
    ) -> dict[str, Any]:
        """Append one source-to-output model lineage record."""
        return self._lineage.insert(
            {
                "project_id": project_id,
                "source_reference": source_reference,
                "source_sha256": source_sha256,
                "source_version": source_version,
                "output_reference": output_reference,
                "version": version,
                "summary": summary,
                "created_at": now_iso_utc(),
            }
        )

    def find_by_source_sha256(
        self, project_id: int, source_sha256: str
    ) -> dict[str, Any] | None:
        """Return an existing enhancement for the same project and source bytes."""
        rows = self._lineage.rows_where("project_id = ?", [project_id])
        return next(
            (row for row in rows if row.get("source_sha256") == source_sha256),
            None,
        )

    def allocate_next_version(self, project_id: int) -> int:
        """Atomically reserve the next model version through the database allocator."""
        response = PersistenceService.get_db().rpc(
            "allocate_model_enhancement_version",
            {"target_project_id": project_id},
        ).execute()
        version = response.data
        if isinstance(version, list):
            version = version[0] if version else None
        if not isinstance(version, int) or version < 1:
            raise RuntimeError("Supabase did not return a valid enhancement version")
        return version

    def list_for_project(self, project_id: int) -> list[dict[str, Any]]:
        """Return enhancement lineage for one project, newest version first."""
        rows = self._lineage.rows_where("project_id = ?", [project_id])
        return sorted(rows, key=lambda row: int(row.get("version") or 0), reverse=True)

    def get(self, lineage_id: int) -> dict[str, Any] | None:
        """Return one lineage record by primary key."""
        return self._lineage.get(lineage_id)