"""Persistent storage and metadata for generated report artifacts."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from app.logging_config import get_logger
from app.modules.reporter.bcf_generator import BCFIssue, generate_bcf
from app.services.object_storage import ObjectStorage
from app.services.persistence import PersistenceService
from app.utils import now_iso_utc

logger = get_logger(__name__)

#: Recommended fix written for a finding whose topic payload carries none.
DEFAULT_MITIGATION = "Review and resolve the compliance finding."

_REPORT_ARTIFACT_SCHEMA = {
    "id": int,
    "project_id": int,
    "ifc_file_id": int,
    "artifact_type": str,
    "filename": str,
    "storage_ref": str,
    "content_type": str,
    "byte_size": int,
    "sha256": str,
    "issue_count": int,
    "created_at": str,
    "rule_folder": str,
    "ruleset_name": str,
    "created_by": str,
    "created_by_email": str,
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

    def persist_bcf(
        self,
        project_id: int,
        topics: list[dict[str, Any]],
        *,
        ifc_file_id: int | None = None,
        rule_folder: str = "",
        ruleset_name: str = "",
        created_by: str | None = None,
        created_by_email: str | None = None,
    ) -> dict[str, Any] | None:
        """Generate and persist a BCF export, returning its metadata row.

        Args:
            project_id: Owning project.
            topics: Compliance findings to export.
            ifc_file_id: ``project_ifc_files.id`` this export was produced
                from, when the caller knows which single model it covers.
                Left ``None`` for the common case of a report federated
                across every model a project holds.
            rule_folder: The ruleset id the run was scoped to, or ``""`` for
                an unscoped ("All Rules") run.
            ruleset_name: Display name snapshot for ``rule_folder``, so the
                saved row still reads correctly if the ruleset is later
                renamed or deleted.
            created_by: Supabase auth user id of whoever triggered the run,
                or ``None`` when the caller has no authenticated user in
                scope (e.g. a background/system-triggered run).
            created_by_email: Email snapshot for ``created_by``.
        """
        if not topics:
            return None

        filename = f"compliance_project_{project_id}.bcf"
        issues = [self._topic_to_issue(topic) for topic in topics]
        content = generate_bcf(issues, filename=filename)
        return self._persist(
            project_id,
            "bcf",
            filename,
            content,
            "application/octet-stream",
            len(issues),
            rule_folder=rule_folder,
            ruleset_name=ruleset_name,
            created_by=created_by,
            created_by_email=created_by_email,
            ifc_file_id=ifc_file_id,
        )

    def persist_pdf(
        self,
        project_id: int,
        content: bytes,
        filename: str,
        *,
        issue_count: int,
        rule_folder: str = "",
        ruleset_name: str = "",
        created_by: str | None = None,
        created_by_email: str | None = None,
    ) -> dict[str, Any]:
        """Persist a rendered PDF compliance report, returning its metadata row."""
        return self._persist(
            project_id,
            "pdf",
            filename,
            content,
            "application/pdf",
            issue_count,
            rule_folder=rule_folder,
            ruleset_name=ruleset_name,
            created_by=created_by,
            created_by_email=created_by_email,
        )

    def persist_csv(
        self,
        project_id: int,
        content: bytes,
        filename: str,
        *,
        issue_count: int,
        rule_folder: str = "",
        ruleset_name: str = "",
        created_by: str | None = None,
        created_by_email: str | None = None,
    ) -> dict[str, Any]:
        """Persist a rendered full-report CSV export, returning its metadata row."""
        return self._persist(
            project_id,
            "csv",
            filename,
            content,
            "text/csv",
            issue_count,
            rule_folder=rule_folder,
            ruleset_name=ruleset_name,
            created_by=created_by,
            created_by_email=created_by_email,
        )

    def _persist(
        self,
        project_id: int,
        artifact_type: str,
        filename: str,
        content: bytes,
        content_type: str,
        issue_count: int,
        *,
        rule_folder: str = "",
        ruleset_name: str = "",
        created_by: str | None = None,
        created_by_email: str | None = None,
        ifc_file_id: int | None = None,
    ) -> dict[str, Any]:
        """Upload ``content`` to storage and insert its metadata row.

        Shared by every ``persist_*`` method so the upload/rollback and
        column shape stay in one place regardless of artifact type.
        """
        storage_ref = self._storage.save_upload(filename, content, f"reports/{artifact_type}")
        try:
            artifact = self._artifacts.insert(
                {
                    "project_id": project_id,
                    "ifc_file_id": ifc_file_id,
                    "artifact_type": artifact_type,
                    "filename": filename,
                    "storage_ref": storage_ref,
                    "content_type": content_type,
                    "byte_size": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "issue_count": issue_count,
                    "created_at": now_iso_utc(),
                    "rule_folder": rule_folder or "",
                    "ruleset_name": ruleset_name or "",
                    "created_by": created_by or "",
                    "created_by_email": created_by_email or "",
                }
            )
        except Exception:
            try:
                self._storage.delete(storage_ref)
            except Exception:
                logger.warning(
                    "Failed to clean up orphaned %s object ref=%s", artifact_type, storage_ref, exc_info=True
                )
            raise

        logger.info(
            "%s report persisted project_id=%d artifact_id=%s issues=%d bytes=%d",
            artifact_type.upper(),
            project_id,
            artifact.get("id"),
            issue_count,
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
        return self.list_by_type("bcf")

    def get_bcf(self, artifact_id: int) -> dict[str, Any] | None:
        """Return one persisted BCF export by artifact ID."""
        return self.get(artifact_id, "bcf")

    def delete_bcf(self, artifact_id: int) -> bool:
        """Delete a persisted BCF export and clean up storage."""
        return self.delete(artifact_id, "bcf")

    def list_by_type(self, artifact_type: str) -> list[dict[str, Any]]:
        """Return all persisted artifacts of ``artifact_type``, newest first."""
        rows = [row for row in self._artifacts.rows if row.get("artifact_type") == artifact_type]
        return sorted(rows, key=lambda row: int(row.get("id") or 0), reverse=True)

    def get(self, artifact_id: int, artifact_type: str) -> dict[str, Any] | None:
        """Return one persisted artifact by ID, scoped to ``artifact_type``."""
        artifact = self._artifacts.get(artifact_id)
        if artifact is None or artifact.get("artifact_type") != artifact_type:
            return None
        return artifact

    def delete(self, artifact_id: int, artifact_type: str) -> bool:
        """Delete a persisted artifact of ``artifact_type`` and clean up storage."""
        artifact = self.get(artifact_id, artifact_type)
        if not artifact:
            return False
        storage_ref = artifact.get("storage_ref")
        if storage_ref:
            try:
                self._storage.delete(storage_ref)
            except Exception:
                logger.warning("Failed to delete storage object %s", storage_ref, exc_info=True)
        self._artifacts.delete(artifact_id)
        return True

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

        labels = [rule_id, str(topic.get("type") or "Issue")]
        ruleset_id = str(topic.get("ruleset_id") or "").strip()
        if ruleset_id:
            labels.append(f"Ruleset:{ruleset_id}")

        mitigation = str(topic.get("mitigation") or "").strip() or DEFAULT_MITIGATION
        document_references = [
            {"description": description}
            for description in (
                ReportArtifactService._citation_description(citation)
                for citation in topic.get("citations") or []
            )
            if description
        ]

        # Camera/target share the element's centroid — same convention
        # the BCF exporter uses generally.
        # position_mm comes from Module 2 (world mm); the viewer's fragments
        # scene works in metres, so convert here. None (geometry unresolved
        # for this element) leaves the BCFIssue's own origin default, which
        # just means that topic's viewpoint won't fly anywhere useful —
        # selecting it still works, it just doesn't move the camera.
        pos = topic.get("position_mm")
        pos_kwargs: dict[str, float] = {}
        if pos is not None:
            x, y, z = float(pos[0]) / 1000, float(pos[1]) / 1000, float(pos[2]) / 1000
            pos_kwargs = {
                "camera_x": x, "camera_y": y, "camera_z": z,
                "target_x": x, "target_y": y, "target_z": z,
            }

        return BCFIssue(
            guid=str(topic.get("guid") or element_guid),
            title=str(topic.get("title") or "BIM Guard compliance issue"),
            description=str(topic.get("description") or ""),
            priority=priority,
            status=str(topic.get("status") or "Open").title(),
            assigned_to="BIM Coordinator",
            due_date=due_date,
            labels=labels,
            component_guid=element_guid,
            component_name=element_guid,
            service_type=rule_id,
            floor="",
            risk_band=raw_priority.upper(),
            mechanism=rule_id,
            risk_score=0.0,
            mitigation=mitigation,
            document_references=document_references,
            **pos_kwargs,
        )

    @staticmethod
    def _citation_description(citation: dict[str, Any]) -> str:
        """Render a ``{"standard", "clause", "reason"}`` citation as one line.

        The same wording the export archive uses for its "Standards References"
        block -- ``<standard> Clause <clause>: <reason>`` -- written here as a
        ``Topic/DocumentReference`` description. Any part the citation lacks is
        left out rather than filled in, and a citation with nothing to say
        yields ``""`` so the caller drops it.
        """
        standard = str(citation.get("standard") or "").strip()
        clause = str(citation.get("clause") or "").strip()
        reason = str(citation.get("reason") or "").strip()
        head = " ".join(part for part in (standard, f"Clause {clause}" if clause else "") if part)
        if head and reason:
            return f"{head}: {reason}"
        return head or reason