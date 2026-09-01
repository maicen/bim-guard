"""BCF Synchronization Service.

Synchronizes BCF 2.1 topics, comments, and viewpoints bidirectionally
with BIMGuard Issue entities and ISO 19650 metadata.

Reference: buildingSMART BCF-API REST Specification
https://github.com/buildingSMART/BCF-API
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

logger = get_logger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class BCFSyncService:
    """In-memory & persistent store bridging BCF REST API and BIMGuard compliance findings."""

    def __init__(self) -> None:
        # In-memory stores keyed by project_id -> list of entities
        self._topics_by_project: dict[str, dict[str, dict[str, Any]]] = {}
        self._comments_by_topic: dict[str, list[dict[str, Any]]] = {}
        self._viewpoints_by_topic: dict[str, list[dict[str, Any]]] = {}
        self._snapshots_by_viewpoint: dict[str, bytes] = {}

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
        project_store = self._topics_by_project.get(str(project_id), {})
        topics = list(project_store.values())

        if topic_status:
            topics = [t for t in topics if t.get("topic_status", "").lower() == topic_status.lower()]
        if topic_type:
            topics = [t for t in topics if t.get("topic_type", "").lower() == topic_type.lower()]
        if priority:
            topics = [t for t in topics if t.get("priority", "").lower() == priority.lower()]
        if assigned_to:
            topics = [t for t in topics if assigned_to.lower() in (t.get("assigned_to") or "").lower()]
        if cde_state:
            topics = [t for t in topics if t.get("cde_state", "") == cde_state]

        results = []
        for t in topics:
            guid = t["guid"]
            comments_count = len(self._comments_by_topic.get(guid, []))
            viewpoints_count = len(self._viewpoints_by_topic.get(guid, []))
            results.append(
                BCFTopicResponse(
                    guid=guid,
                    topic_type=t.get("topic_type", "Issue"),
                    topic_status=t.get("topic_status", "Open"),
                    title=t.get("title", "Untitled Topic"),
                    priority=t.get("priority", "Normal"),
                    index=t.get("index", 1),
                    creation_date=t.get("creation_date", _utc_now_iso()),
                    creation_author=t.get("creation_author", "BIMGUARD-AI"),
                    modified_date=t.get("modified_date"),
                    modified_author=t.get("modified_author"),
                    assigned_to=t.get("assigned_to"),
                    description=t.get("description"),
                    due_date=t.get("due_date"),
                    labels=t.get("labels", []),
                    stage=t.get("stage"),
                    component_guids=t.get("component_guids", []),
                    project_code=t.get("project_code"),
                    originator=t.get("originator"),
                    suitability_code=t.get("suitability_code"),
                    revision_code=t.get("revision_code"),
                    cde_state=t.get("cde_state"),
                    comments_count=comments_count,
                    viewpoints_count=viewpoints_count,
                )
            )
        return results

    def get_topic(self, project_id: str, topic_guid: str) -> Optional[BCFTopicResponse]:
        """Fetch single topic by GUID."""
        project_store = self._topics_by_project.get(str(project_id), {})
        t = project_store.get(str(topic_guid).upper()) or project_store.get(str(topic_guid))
        if not t:
            return None

        guid = t["guid"]
        comments_count = len(self._comments_by_topic.get(guid, []))
        viewpoints_count = len(self._viewpoints_by_topic.get(guid, []))
        return BCFTopicResponse(
            guid=guid,
            topic_type=t.get("topic_type", "Issue"),
            topic_status=t.get("topic_status", "Open"),
            title=t.get("title", "Untitled Topic"),
            priority=t.get("priority", "Normal"),
            index=t.get("index", 1),
            creation_date=t.get("creation_date", _utc_now_iso()),
            creation_author=t.get("creation_author", "BIMGUARD-AI"),
            modified_date=t.get("modified_date"),
            modified_author=t.get("modified_author"),
            assigned_to=t.get("assigned_to"),
            description=t.get("description"),
            due_date=t.get("due_date"),
            labels=t.get("labels", []),
            stage=t.get("stage"),
            component_guids=t.get("component_guids", []),
            project_code=t.get("project_code"),
            originator=t.get("originator"),
            suitability_code=t.get("suitability_code"),
            revision_code=t.get("revision_code"),
            cde_state=t.get("cde_state"),
            comments_count=comments_count,
            viewpoints_count=viewpoints_count,
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
        proj_key = str(project_id)
        if proj_key not in self._topics_by_project:
            self._topics_by_project[proj_key] = {}

        guid = str(uuid.uuid4()).upper()
        now = _utc_now_iso()
        index = len(self._topics_by_project[proj_key]) + 1

        topic_data = {
            "guid": guid,
            "topic_type": payload.topic_type,
            "topic_status": payload.topic_status,
            "title": payload.title,
            "priority": payload.priority,
            "index": index,
            "creation_date": now,
            "creation_author": author,
            "modified_date": now,
            "modified_author": author,
            "assigned_to": payload.assigned_to,
            "description": payload.description,
            "due_date": payload.due_date,
            "labels": payload.labels,
            "component_guids": payload.component_guids,
            "project_code": project_code,
            "originator": originator,
            "suitability_code": payload.suitability_code or "S0",
            "revision_code": payload.revision_code or "P01.01",
            "cde_state": payload.cde_state or CDEState.WIP,
        }

        self._topics_by_project[proj_key][guid] = topic_data
        self._comments_by_topic[guid] = []
        self._viewpoints_by_topic[guid] = []

        # If description is present, also add initial comment
        if payload.description:
            self.create_comment(
                topic_guid=guid,
                payload=BCFCommentCreatePayload(comment=payload.description),
                author=author,
            )

        return self.get_topic(project_id, guid)  # type: ignore

    def update_topic(
        self,
        project_id: str,
        topic_guid: str,
        payload: BCFTopicUpdatePayload,
        author: str = "BIMGUARD-AI",
    ) -> Optional[BCFTopicResponse]:
        """Update fields of an existing topic."""
        proj_key = str(project_id)
        project_store = self._topics_by_project.get(proj_key, {})
        guid = str(topic_guid).upper()
        if guid not in project_store and str(topic_guid) in project_store:
            guid = str(topic_guid)

        if guid not in project_store:
            return None

        t = project_store[guid]
        now = _utc_now_iso()
        t["modified_date"] = now
        t["modified_author"] = author

        if payload.title is not None:
            t["title"] = payload.title
        if payload.topic_type is not None:
            t["topic_type"] = payload.topic_type
        if payload.topic_status is not None:
            t["topic_status"] = payload.topic_status
        if payload.priority is not None:
            t["priority"] = payload.priority
        if payload.description is not None:
            t["description"] = payload.description
        if payload.assigned_to is not None:
            t["assigned_to"] = payload.assigned_to
        if payload.due_date is not None:
            t["due_date"] = payload.due_date
        if payload.labels is not None:
            t["labels"] = payload.labels
        if payload.component_guids is not None:
            t["component_guids"] = payload.component_guids
        if payload.suitability_code is not None:
            t["suitability_code"] = payload.suitability_code
        if payload.revision_code is not None:
            t["revision_code"] = payload.revision_code
        if payload.cde_state is not None:
            t["cde_state"] = payload.cde_state

        return self.get_topic(project_id, guid)

    def get_comments(self, topic_guid: str) -> list[BCFCommentResponse]:
        """List comments for a topic."""
        guid = str(topic_guid).upper()
        items = self._comments_by_topic.get(guid, [])
        return [BCFCommentResponse(**i) for i in items]

    def create_comment(
        self,
        topic_guid: str,
        payload: BCFCommentCreatePayload,
        author: str = "BIMGUARD-AI",
    ) -> BCFCommentResponse:
        """Add a comment to a topic."""
        guid = str(topic_guid).upper()
        if guid not in self._comments_by_topic:
            self._comments_by_topic[guid] = []

        comment_guid = str(uuid.uuid4()).upper()
        now = _utc_now_iso()
        item = {
            "guid": comment_guid,
            "date": now,
            "author": author,
            "comment": payload.comment,
            "topic_guid": guid,
            "viewpoint_guid": payload.viewpoint_guid,
        }
        self._comments_by_topic[guid].append(item)
        return BCFCommentResponse(**item)

    def get_viewpoints(self, topic_guid: str) -> list[BCFViewpointResponse]:
        """List viewpoints for a topic."""
        guid = str(topic_guid).upper()
        items = self._viewpoints_by_topic.get(guid, [])
        return [BCFViewpointResponse(**i) for i in items]

    def create_viewpoint(
        self,
        topic_guid: str,
        payload: BCFViewpointCreatePayload,
    ) -> BCFViewpointResponse:
        """Create a 3D camera viewpoint with optional snapshot for a topic."""
        guid = str(topic_guid).upper()
        if guid not in self._viewpoints_by_topic:
            self._viewpoints_by_topic[guid] = []

        vp_guid = str(uuid.uuid4()).upper()
        idx = len(self._viewpoints_by_topic[guid]) + 1

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

        snapshot_url = None
        if payload.snapshot_base64:
            try:
                raw_bytes = base64.b64decode(payload.snapshot_base64)
                self._snapshots_by_viewpoint[vp_guid] = raw_bytes
                snapshot_url = f"/api/bcf/v2.1/projects/0/topics/{guid}/viewpoints/{vp_guid}/snapshot"
            except Exception as exc:
                logger.debug("Failed decoding base64 snapshot: %s", exc)

        item = {
            "guid": vp_guid,
            "topic_guid": guid,
            "index": idx,
            "perspective_camera": perspective_cam,
            "orthogonal_camera": payload.orthogonal_camera,
            "components": components_data,
            "snapshot_url": snapshot_url,
        }
        self._viewpoints_by_topic[guid].append(item)
        return BCFViewpointResponse(**item)

    def get_snapshot(self, viewpoint_guid: str) -> Optional[bytes]:
        """Fetch snapshot PNG bytes for a viewpoint."""
        return self._snapshots_by_viewpoint.get(str(viewpoint_guid).upper())


# Global Singleton BCF Sync Service
DEFAULT_BCF_SYNC_SERVICE = BCFSyncService()
