"""Persistent storage and metadata for generated report artifacts."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from app.logging_config import get_logger
from app.modules.module5_reporter.bcf_generator import BCFIssue, generate_bcf
from app.services.object_storage import ObjectStorage
from app.services.persistence import PersistenceService
from app.utils import now_iso_utc

logger = get_logger(__name__)

_REPORT_ARTIFACT_SCHEMA = {
    "id": int,
    "project_id": int,
    "artifact_type": str,
    "filename": str,
    "storage_ref": str,
    "content_type": str,
    "byte_size": int,
    "sha256": str,
    "issue_count": int,
    "created_at": str,
}


class ReportArtifactService:
    """Generate and persist downloadable project report artifacts."""

    def __init__(self, *, storage=None, table=None) -> None:
        """Initialize report metadata and object-storage dependencies."""
        self._storage = storage or ObjectStorage()
        self._artifacts = table or PersistenceService.get_table(
            "report_artifacts",
            _REPORT_ARTIFACT_SCHEMA,
        )

    def persist_bcf(self, project_id: int, topics: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Generate and persist a BCF export, returning its metadata row."""
        if not topics:
            return None

        filename = f"compliance_project_{project_id}.bcf"
        issues = [self._topic_to_issue(topic) for topic in topics]
        content = generate_bcf(issues, filename=filename)
        storage_ref = self._storage.save_upload(filename, content, "reports/bcf")
        try:
            artifact = self._artifacts.insert(
                {
                    "project_id": project_id,
                    "artifact_type": "bcf",
                    "filename": filename,
                    "storage_ref": storage_ref,
                    "content_type": "application/octet-stream",
                    "byte_size": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "issue_count": len(issues),
                    "created_at": now_iso_utc(),
                }
            )
        except Exception:
            try:
                self._storage.delete(storage_ref)
            except Exception:
                logger.warning("Failed to clean up orphaned BCF object ref=%s", storage_ref, exc_info=True)
            raise

        logger.info(
            "BCF report persisted project_id=%d artifact_id=%s issues=%d bytes=%d",
            project_id,
            artifact.get("id"),
            len(issues),
            len(content),
        )
        return artifact

    def latest_bcf(self, project_id: int) -> dict[str, Any] | None:
        """Return metadata for the latest persisted BCF export of a project."""
        rows = self._artifacts.rows_where("project_id = ?", [project_id])
        matches = [row for row in rows if row.get("artifact_type") == "bcf"]
        return max(matches, key=lambda row: int(row.get("id") or 0), default=None)

    def list_bcf(self) -> list[dict[str, Any]]:
        """Return all persisted BCF exports ordered from newest to oldest."""
        rows = [row for row in self._artifacts.rows if row.get("artifact_type") == "bcf"]
        return sorted(rows, key=lambda row: int(row.get("id") or 0), reverse=True)

    def get_bcf(self, artifact_id: int) -> dict[str, Any] | None:
        """Return one persisted BCF export by artifact ID."""
        artifact = self._artifacts.get(artifact_id)
        if artifact is None or artifact.get("artifact_type") != "bcf":
            return None
        return artifact

    def materialize(self, artifact: dict[str, Any]):
        """Return a local cache path for a persisted report artifact."""
        return self._storage.materialize_local_path(str(artifact.get("storage_ref") or ""))

    @staticmethod
    def _topic_to_issue(topic: dict[str, Any]) -> BCFIssue:
        """Adapt the pipeline's compact topic payload to the BCF generator contract."""
        raw_priority = str(topic.get("priority") or "medium").lower()
        priority = {
            "critical": "Critical",
            "high": "Major",
            "mandatory": "Major",
            "medium": "Normal",
            "recommended": "Normal",
            "low": "Minor",
        }.get(raw_priority, "Normal")
        element_guid = str(topic.get("element_guid") or "")
        rule_id = str(topic.get("rule_id") or "BIM-GUARD")
        due_date = datetime.now(UTC).date().isoformat()
        return BCFIssue(
            guid=str(topic.get("guid") or element_guid),
            title=str(topic.get("title") or "BIM Guard compliance issue"),
            description=str(topic.get("description") or ""),
            priority=priority,
            status=str(topic.get("status") or "Open").title(),
            assigned_to="BIM Coordinator",
            due_date=due_date,
            labels=[rule_id, str(topic.get("type") or "Issue")],
            component_guid=element_guid,
            component_name=element_guid,
            service_type=rule_id,
            floor="",
            risk_band=raw_priority.upper(),
            mechanism=rule_id,
            risk_score=0.0,
            mitigation="Review and resolve the compliance finding.",
        )