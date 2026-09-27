"""Building Collaboration Format (BCF-API 3.0) REST contracts."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from app.modules.contracts.base import CDEState

__all__ = ['BCFVersionResponse', 'BCFExtensionsResponse', 'BCFProjectResponse', 'BCFCommentResponse', 'BCFCommentCreatePayload', 'BCFCommentUpdatePayload', 'BCFCurrentUserResponse', 'BCFViewpointResponse', 'BCFViewpointCreatePayload', 'BCFTopicResponse', 'BCFTopicCreatePayload', 'BCFTopicUpdatePayload']

# ------------------------------------------------------------------------------
# 5. BCF REST API (v2.1 / v3.0) Contracts
# ------------------------------------------------------------------------------


class BCFVersionResponse(BaseModel):
    """One entry of the ``GET /bcf/versions`` discovery response."""

    version_id: str
    detailed_version: str

class BCFExtensionsResponse(BaseModel):
    """Per-project enumerations a BCF client uses to populate its UI.

    Mirrors the ``GET /bcf/2.1/projects/{project_id}/extensions`` contract:
    the fixed vocabularies this API actually accepts on topic create/update,
    plus the actions a caller may take at project/topic/comment level.
    """

    topic_type: list[str] = Field(default_factory=lambda: ["Issue", "Request", "Clashes", "Remark"])
    topic_status: list[str] = Field(default_factory=lambda: ["Open", "InProgress", "Resolved", "Closed"])
    topic_label: list[str] = Field(default_factory=list)
    priority: list[str] = Field(default_factory=lambda: ["Critical", "Major", "Normal", "Minor"])
    user_id_type: list[str] = Field(default_factory=list)
    stage: list[str] = Field(default_factory=list)
    snippet_type: list[str] = Field(default_factory=list)
    project_actions: list[str] = Field(default_factory=lambda: ["update"])
    topic_actions: list[str] = Field(default_factory=lambda: ["createTopic", "updateTopic", "deleteTopic"])
    comment_actions: list[str] = Field(default_factory=lambda: ["createComment", "updateComment", "deleteComment"])

class BCFProjectResponse(BaseModel):
    """BCF Project information contract."""

    project_id: str
    name: str
    authorization: dict[str, list[str]] = Field(
        default_factory=lambda: {"project_actions": ["update"], "topic_actions": ["create", "update", "delete"]}
    )

class BCFCommentResponse(BaseModel):
    """BCF Topic comment contract."""

    guid: str
    date: str
    author: str
    comment: str
    topic_guid: str
    modified_date: Optional[str] = None
    modified_author: Optional[str] = None
    viewpoint_guid: Optional[str] = None

class BCFCommentCreatePayload(BaseModel):
    """Payload for adding a new comment to a BCF topic."""

    comment: str = Field(..., min_length=1, description="Comment text content")
    viewpoint_guid: Optional[str] = Field(None, description="Optional associated viewpoint GUID")

class BCFCommentUpdatePayload(BaseModel):
    """Payload for updating an existing comment's text."""

    comment: str = Field(..., min_length=1, description="Replacement comment text content")

class BCFCurrentUserResponse(BaseModel):
    """``GET /bcf/2.1/current-user`` contract.

    Present regardless of which authentication scheme fronts the API — this
    server authenticates callers via a Supabase JWT bearer token rather than
    the spec's OAuth2 authorization-code flow, but a BCF client still needs a
    way to ask "who am I" once authenticated.
    """

    id: str
    name: str
    email: Optional[str] = None

class BCFViewpointResponse(BaseModel):
    """BCF Topic viewpoint contract."""

    guid: str
    topic_guid: str
    index: int = 0
    perspective_camera: Optional[dict[str, Any]] = None
    orthogonal_camera: Optional[dict[str, Any]] = None
    lines: list[dict[str, Any]] = Field(default_factory=list)
    clipping_planes: list[dict[str, Any]] = Field(default_factory=list)
    components: dict[str, Any] = Field(default_factory=dict)
    snapshot_url: Optional[str] = None

class BCFViewpointCreatePayload(BaseModel):
    """Payload for creating a viewpoint on a BCF topic."""

    perspective_camera: Optional[dict[str, Any]] = None
    orthogonal_camera: Optional[dict[str, Any]] = None
    components: Optional[dict[str, Any]] = None
    snapshot_base64: Optional[str] = None

class BCFTopicResponse(BaseModel):
    """BCF Topic entity contract."""

    guid: str
    topic_type: str = "Issue"
    topic_status: str = "Open"
    title: str
    priority: str = "Normal"
    index: int = 1
    creation_date: str
    creation_author: str
    modified_date: Optional[str] = None
    modified_author: Optional[str] = None
    assigned_to: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[str] = None
    labels: list[str] = Field(default_factory=list)
    stage: Optional[str] = None
    # Component references
    component_guids: list[str] = Field(default_factory=list)
    # ISO 19650 governance metadata
    project_code: Optional[str] = None
    originator: Optional[str] = None
    suitability_code: Optional[str] = None
    revision_code: Optional[str] = None
    cde_state: Optional[CDEState] = None
    comments_count: int = 0
    viewpoints_count: int = 0

class BCFTopicCreatePayload(BaseModel):
    """Payload for creating a BCF topic via REST API."""

    title: str = Field(..., min_length=1, description="Topic title")
    topic_type: str = Field("Issue", description="Type (Issue, Request, Clashes, Remark)")
    topic_status: str = Field("Open", description="Status (Open, InProgress, Closed, Resolved)")
    priority: str = Field("Normal", description="Priority (Critical, Major, Normal, Minor)")
    description: Optional[str] = None
    assigned_to: Optional[str] = None
    due_date: Optional[str] = None
    labels: list[str] = Field(default_factory=list)
    component_guids: list[str] = Field(default_factory=list)
    # ISO 19650 metadata
    suitability_code: Optional[str] = "S0"
    revision_code: Optional[str] = "P01.01"
    cde_state: Optional[CDEState] = CDEState.WIP

class BCFTopicUpdatePayload(BaseModel):
    """Payload for updating an existing BCF topic."""

    title: Optional[str] = None
    topic_type: Optional[str] = None
    topic_status: Optional[str] = None
    priority: Optional[str] = None
    description: Optional[str] = None
    assigned_to: Optional[str] = None
    due_date: Optional[str] = None
    labels: Optional[list[str]] = None
    component_guids: Optional[list[str]] = None
    suitability_code: Optional[str] = None
    revision_code: Optional[str] = None
    cde_state: Optional[CDEState] = None
