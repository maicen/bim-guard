"""BCF Synchronization Service.

Synchronizes BCF 2.1 topics, comments, and viewpoints bidirectionally
with BIMGuard Issue entities and ISO 19650 metadata.

Reference: buildingSMART BCF-API REST Specification
https://github.com/buildingSMART/BCF-API

Persisted to Supabase (``public.bcf_topics`` / ``bcf_comments`` /
``bcf_viewpoints``, migration ``20260915173941_create_bcf_tables``) rather than
kept in a process-local dict: a REST API is expected to survive a restart and
be shared across the multi-worker production uvicorn processes this repo's own
``run_production_server`` scripts start, and an in-memory singleton could do
neither.
"""

from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.logging_config import get_logger
from app.modules.contracts import (
    BCFCommentCreatePayload,
    BCFCommentResponse,
    BCFTopicCreatePayload,
    BCFTopicResponse,
    BCFTopicUpdatePayload,
    BCFViewpointCreatePayload,
    BCFViewpointResponse,
    CDEState,
)
from app.services.persistence import PersistenceService

logger = get_logger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class BCFSyncService:
    """Supabase-backed store bridging the BCF REST API and BIMGuard compliance findings."""

    def __init__(self, *, topics_repo=None, comments_repo=None, viewpoints_repo=None) -> None:
        """Wire the three BCF tables, defaulting to the shared Supabase connection."""
        self._topics = (
            topics_repo
            if topics_repo is not None
            else PersistenceService.get_table(
                "bcf_topics",
                {
                    "guid": str,
                    "project_id": str,
                    "topic_type": str,
                    "topic_status": str,
                    "title": str,
                    "priority": str,
                    "topic_index": int,
                    "creation_date": str,
                    "creation_author": str,
                    "modified_date": str,
                    "modified_author": str,
                    "assigned_to": str,
                    "description": str,
                    "due_date": str,
                    "labels": str,
                    "stage": str,
                    "component_guids": str,
                    "project_code": str,
                    "originator": str,
                    "suitability_code": str,
                    "revision_code": str,
                    "cde_state": str,
                },
                pk="guid",
            )
        )
        self._comments = (
            comments_repo
            if comments_repo is not None
            else PersistenceService.get_table(
                "bcf_comments",
                {
                    "guid": str,
                    "topic_guid": str,
                    "comment_date": str,
                    "author": str,
                    "comment": str,
                    "modified_date": str,
                    "modified_author": str,
                    "viewpoint_guid": str,
                },
                pk="guid",
            )
        )
        self._viewpoints = (
            viewpoints_repo
            if viewpoints_repo is not None
            else PersistenceService.get_table(
                "bcf_viewpoints",
                {
                    "guid": str,
                    "topic_guid": str,
                    "viewpoint_index": int,
                    "perspective_camera": str,
                    "orthogonal_camera": str,
                    "lines": str,
                    "clipping_planes": str,
                    "components": str,
                    "snapshot_base64": str,
                },
                pk="guid",
            )
        )

    # ------------------------------------------------------------------
    # Row <-> contract mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _topic_from_row(row: dict[str, Any], comments_count: int, viewpoints_count: int) -> BCFTopicResponse:
        cde_state = row.get("cde_state") or None
        return BCFTopicResponse(
            guid=row["guid"],
            topic_type=row.get("topic_type") or "Issue",
            topic_status=row.get("topic_status") or "Open",
            title=row.get("title") or "Untitled Topic",
            priority=row.get("priority") or "Normal",
            index=row.get("topic_index") or 1,
            creation_date=row.get("creation_date") or _utc_now_iso(),
            creation_author=row.get("creation_author") or "BIMGUARD-AI",
            modified_date=row.get("modified_date") or None,
            modified_author=row.get("modified_author") or None,
            assigned_to=row.get("assigned_to") or None,
            description=row.get("description") or None,
            due_date=row.get("due_date") or None,
            labels=row.get("labels") or [],
            stage=row.get("stage") or None,
            component_guids=row.get("component_guids") or [],
            project_code=row.get("project_code") or None,
            originator=row.get("originator") or None,
            suitability_code=row.get("suitability_code") or None,
            revision_code=row.get("revision_code") or None,
            cde_state=CDEState(cde_state) if cde_state else None,
            comments_count=comments_count,
            viewpoints_count=viewpoints_count,
        )

    @staticmethod
    def _comment_from_row(row: dict[str, Any]) -> BCFCommentResponse:
        return BCFCommentResponse(
            guid=row["guid"],
            date=row.get("comment_date") or _utc_now_iso(),
            author=row.get("author") or "",
            comment=row.get("comment") or "",
            topic_guid=row["topic_guid"],
            modified_date=row.get("modified_date") or None,
            modified_author=row.get("modified_author") or None,
            viewpoint_guid=row.get("viewpoint_guid") or None,
        )

    @staticmethod
    def _viewpoint_from_row(row: dict[str, Any]) -> BCFViewpointResponse:
        return BCFViewpointResponse(
            guid=row["guid"],
            topic_guid=row["topic_guid"],
            index=row.get("viewpoint_index") or 0,
            perspective_camera=row.get("perspective_camera") or None,
            orthogonal_camera=row.get("orthogonal_camera") or None,
            lines=row.get("lines") or [],
            clipping_planes=row.get("clipping_planes") or [],
            components=row.get("components") or {},
            snapshot_url=(
                f"/api/bcf/v2.1/projects/0/topics/{row['topic_guid']}/viewpoints/{row['guid']}/snapshot"
                if row.get("snapshot_base64")
                else None
            ),
        )

    # ------------------------------------------------------------------
    # Topics
    # ------------------------------------------------------------------

    def get_topics(
        self,
        project_id: str,
        topic_status: str | None = None,
        topic_type: str | None = None,
        priority: str | None = None,
        assigned_to: str | None = None,
        cde_state: str | None = None,
    ) -> list[BCFTopicResponse]:
        """List topics for a project with optional filters."""
        rows = self._topics.rows_where("project_id = ?", [str(project_id)])

        if topic_status:
            rows = [r for r in rows if (r.get("topic_status") or "").lower() == topic_status.lower()]
        if topic_type:
            rows = [r for r in rows if (r.get("topic_type") or "").lower() == topic_type.lower()]
        if priority:
            rows = [r for r in rows if (r.get("priority") or "").lower() == priority.lower()]
        if assigned_to:
            rows = [r for r in rows if assigned_to.lower() in (r.get("assigned_to") or "").lower()]
        if cde_state:
            rows = [r for r in rows if (r.get("cde_state") or "") == cde_state]

        return [
            self._topic_from_row(
                row,
                comments_count=len(self._comments.rows_where("topic_guid = ?", [row["guid"]])),
                viewpoints_count=len(self._viewpoints.rows_where("topic_guid = ?", [row["guid"]])),
            )
            for row in rows
        ]

    def get_topic(self, project_id: str, topic_guid: str) -> Optional[BCFTopicResponse]:
        """Fetch single topic by GUID, scoped to its project."""
        row = self._topics.get(str(topic_guid).upper()) or self._topics.get(str(topic_guid))
        if not row or str(row.get("project_id")) != str(project_id):
            return None
        return self._topic_from_row(
            row,
            comments_count=len(self._comments.rows_where("topic_guid = ?", [row["guid"]])),
            viewpoints_count=len(self._viewpoints.rows_where("topic_guid = ?", [row["guid"]])),
        )

    def create_topic(
        self,
        project_id: str,
        payload: BCFTopicCreatePayload,
        author: str = "BIMGUARD-AI",
        project_code: str = "",
        originator: str = "",
    ) -> BCFTopicResponse:
        """Create new BCF Topic under a project."""
        guid = str(uuid.uuid4()).upper()
        now = _utc_now_iso()
        existing = self._topics.rows_where("project_id = ?", [str(project_id)])

        row = {
            "guid": guid,
            "project_id": str(project_id),
            "topic_type": payload.topic_type,
            "topic_status": payload.topic_status,
            "title": payload.title,
            "priority": payload.priority,
            "topic_index": len(existing) + 1,
            "creation_date": now,
            "creation_author": author,
            "modified_date": now,
            "modified_author": author,
            "assigned_to": payload.assigned_to,
            "description": payload.description,
            "due_date": payload.due_date,
            "labels": payload.labels or [],
            "component_guids": payload.component_guids or [],
            "project_code": project_code,
            "originator": originator,
            "suitability_code": payload.suitability_code or "S0",
            "revision_code": payload.revision_code or "P01.01",
            "cde_state": (payload.cde_state or CDEState.WIP).value,
        }
        self._topics.insert(row)

        if payload.description:
            self.create_comment(
                topic_guid=guid,
                payload=BCFCommentCreatePayload(comment=payload.description),
                author=author,
            )

        return self.get_topic(project_id, guid)  # type: ignore[return-value]

    def update_topic(
        self,
        project_id: str,
        topic_guid: str,
        payload: BCFTopicUpdatePayload,
        author: str = "BIMGUARD-AI",
    ) -> Optional[BCFTopicResponse]:
        """Update fields of an existing topic."""
        row = self._topics.get(str(topic_guid).upper()) or self._topics.get(str(topic_guid))
        if not row or str(row.get("project_id")) != str(project_id):
            return None
        guid = row["guid"]

        updates: dict[str, Any] = {
            "modified_date": _utc_now_iso(),
            "modified_author": author,
        }
        if payload.title is not None:
            updates["title"] = payload.title
        if payload.topic_type is not None:
            updates["topic_type"] = payload.topic_type
        if payload.topic_status is not None:
            updates["topic_status"] = payload.topic_status
        if payload.priority is not None:
            updates["priority"] = payload.priority
        if payload.description is not None:
            updates["description"] = payload.description
        if payload.assigned_to is not None:
            updates["assigned_to"] = payload.assigned_to
        if payload.due_date is not None:
            updates["due_date"] = payload.due_date
        if payload.labels is not None:
            updates["labels"] = payload.labels
        if payload.component_guids is not None:
            updates["component_guids"] = payload.component_guids
        if payload.suitability_code is not None:
            updates["suitability_code"] = payload.suitability_code
        if payload.revision_code is not None:
            updates["revision_code"] = payload.revision_code
        if payload.cde_state is not None:
            updates["cde_state"] = payload.cde_state.value

        self._topics.update(updates=updates, pk_values=guid)
        return self.get_topic(project_id, guid)

    def delete_topic(self, project_id: str, topic_guid: str) -> bool:
        """Delete a BCF topic and its associated comments and viewpoints."""
        row = self._topics.get(str(topic_guid).upper()) or self._topics.get(str(topic_guid))
        if not row or str(row.get("project_id")) != str(project_id):
            return False
        guid = row["guid"]

        for comment in self._comments.rows_where("topic_guid = ?", [guid]):
            self._comments.delete(comment["guid"])
        for vp in self._viewpoints.rows_where("topic_guid = ?", [guid]):
            self._viewpoints.delete(vp["guid"])
        self._topics.delete(guid)
        return True

    def bulk_delete_topics(self, project_id: str, topic_guids: list[str]) -> int:
        """Bulk delete multiple BCF topics."""
        deleted_count = 0
        for guid in topic_guids:
            if self.delete_topic(project_id, guid):
                deleted_count += 1
        return deleted_count

    # ------------------------------------------------------------------
    # Comments
    # ------------------------------------------------------------------

    def get_comments(self, topic_guid: str) -> list[BCFCommentResponse]:
        """List comments for a topic."""
        guid = str(topic_guid).upper()
        rows = self._comments.rows_where("topic_guid = ?", [guid])
        return [self._comment_from_row(r) for r in rows]

    def create_comment(
        self,
        topic_guid: str,
        payload: BCFCommentCreatePayload,
        author: str = "BIMGUARD-AI",
    ) -> BCFCommentResponse:
        """Add a comment to a topic."""
        guid = str(topic_guid).upper()
        comment_guid = str(uuid.uuid4()).upper()
        row = {
            "guid": comment_guid,
            "topic_guid": guid,
            "comment_date": _utc_now_iso(),
            "author": author,
            "comment": payload.comment,
            "viewpoint_guid": payload.viewpoint_guid,
        }
        self._comments.insert(row)
        return self._comment_from_row(row)

    # ------------------------------------------------------------------
    # Viewpoints
    # ------------------------------------------------------------------

    def get_viewpoints(self, topic_guid: str) -> list[BCFViewpointResponse]:
        """List viewpoints for a topic."""
        guid = str(topic_guid).upper()
        rows = self._viewpoints.rows_where("topic_guid = ?", [guid])
        return [self._viewpoint_from_row(r) for r in rows]

    def create_viewpoint(
        self,
        topic_guid: str,
        payload: BCFViewpointCreatePayload,
    ) -> BCFViewpointResponse:
        """Create a 3D camera viewpoint with optional snapshot for a topic."""
        guid = str(topic_guid).upper()
        vp_guid = str(uuid.uuid4()).upper()
        existing = self._viewpoints.rows_where("topic_guid = ?", [guid])

        perspective_cam = payload.perspective_camera or {
            "camera_view_point": {"x": 5.0, "y": 5.0, "z": 5.0},
            "camera_direction": {"x": -0.577, "y": -0.577, "z": -0.577},
            "camera_up_vector": {"x": 0.0, "y": 0.0, "z": 1.0},
            "field_of_view": 60.0,
        }
        components_data = payload.components or {
            "selection": [],
            "coloring": [],
            "visibility": {"default_visibility": True, "exceptions": []},
        }

        snapshot_base64 = None
        if payload.snapshot_base64:
            try:
                base64.b64decode(payload.snapshot_base64)
                snapshot_base64 = payload.snapshot_base64
            except Exception as exc:
                logger.debug("Failed decoding base64 snapshot: %s", exc)

        row = {
            "guid": vp_guid,
            "topic_guid": guid,
            "viewpoint_index": len(existing) + 1,
            "perspective_camera": perspective_cam,
            "orthogonal_camera": payload.orthogonal_camera,
            "components": components_data,
            "snapshot_base64": snapshot_base64,
        }
        self._viewpoints.insert(row)
        return self._viewpoint_from_row(row)

    def get_snapshot(self, viewpoint_guid: str) -> Optional[bytes]:
        """Fetch snapshot PNG bytes for a viewpoint."""
        row = self._viewpoints.get(str(viewpoint_guid).upper())
        if not row or not row.get("snapshot_base64"):
            return None
        return base64.b64decode(row["snapshot_base64"])


# Global Singleton BCF Sync Service
DEFAULT_BCF_SYNC_SERVICE = BCFSyncService()
