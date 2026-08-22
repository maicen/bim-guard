"""Persistence repository for immutable IFC model enhancement lineage."""

from __future__ import annotations

from typing import Any

from app.services.persistence import PersistenceService
from app.utils import now_iso_utc


class SupabaseModelLineageRepository:
    """Append enhancement lineage records through the shared Supabase adapter."""

    def __init__(self) -> None:
        """Initialize the model enhancement lineage table adapter."""
        self._lineage = PersistenceService.get_table(
            "model_enhancement_lineage",
            {
                "id": int,
                "project_id": int,
                "source_reference": str,
                "output_reference": str,
                "version": int,
                "summary": dict,
                "created_at": str,
            },
        )

    def record(
        self,
        *,
        project_id: int,
        source_reference: str,
        output_reference: str,
        version: int,
        summary: dict[str, Any],
    ) -> dict[str, Any]:
        """Append one source-to-output model lineage record."""
        return self._lineage.insert(
            {
                "project_id": project_id,
                "source_reference": source_reference,
                "output_reference": output_reference,
                "version": version,
                "summary": summary,
                "created_at": now_iso_utc(),
            }
        )