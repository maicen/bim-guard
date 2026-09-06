"""buildingSMART BCF REST API (v2.1 / v3.0 standard).

Reference: https://github.com/buildingSMART/BCF-API
Provides live bidirectional syncing of topics, viewpoints, comments, and ISO 19650 metadata
between BIMGuard AI and authoring tools (Revit, Solibri, Archicad, BlenderBIM, etc.).
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response as RawResponse

from app.api.dependencies import get_projects_service
from app.auth import get_current_user
from app.logging_config import get_logger
from app.modules.contracts import (
    BCFCommentCreatePayload,
    BCFCommentResponse,
    BCFProjectResponse,
    BCFTopicCreatePayload,
    BCFTopicResponse,
    BCFTopicUpdatePayload,
    BCFViewpointCreatePayload,
    BCFViewpointResponse,
)
from app.services.bcf_sync_service import DEFAULT_BCF_SYNC_SERVICE, BCFSyncService
from app.services.projects_service import ProjectsService

logger = get_logger(__name__)

# ``project_id`` here is the BCF spec's opaque string id, not necessarily one
# of our own numeric project ids (see get_bcf_project's fallback), so this
# can't reuse projects.py's per-project ownership dependency the way
# analyze.py and naming_config.py do. Requiring sign-in at the router level
# closes the "anyone, unauthenticated" gap this API previously had; scoping
# it further to "signed-in users may only touch their own project's BCF
# topics" is a follow-up, not attempted here.
router = APIRouter(dependencies=[Depends(get_current_user)])


def get_bcf_sync_service() -> BCFSyncService:
    """Dependency provider for BCF synchronization service."""
    return DEFAULT_BCF_SYNC_SERVICE


# ------------------------------------------------------------------------------
# 1. Projects Endpoints
# ------------------------------------------------------------------------------


@router.get(
    "/v2.1/projects",
    response_model=list[BCFProjectResponse],
    summary="List BCF Projects",
    tags=["BCF API v2.1"],
)
def list_bcf_projects(
    projects_service: Annotated[ProjectsService, Depends(get_projects_service)],
) -> list[BCFProjectResponse]:
    """Return all projects enabled for BCF issue exchange."""
    projects = projects_service.list_projects()
    return [
        BCFProjectResponse(
            project_id=str(p["id"]),
            name=p.get("name", f"Project {p['id']}"),
        )
        for p in projects
    ]


@router.get(
    "/v2.1/projects/{project_id}",
    response_model=BCFProjectResponse,
    summary="Get BCF Project Details",
    tags=["BCF API v2.1"],
)
def get_bcf_project(
    project_id: str,
    projects_service: Annotated[ProjectsService, Depends(get_projects_service)],
) -> BCFProjectResponse:
    """Return BCF project metadata and authorization capabilities."""
    try:
        p_id = int(project_id)
        project = projects_service.get_project(p_id)
    except ValueError:
        project = None

    if not project:
        # Fallback for string/UUID projects
        return BCFProjectResponse(project_id=str(project_id), name=f"Project {project_id}")

    return BCFProjectResponse(
        project_id=str(project["id"]),
        name=project.get("name", f"Project {project['id']}"),
    )


# ------------------------------------------------------------------------------
# 2. Topics Endpoints
# ------------------------------------------------------------------------------


@router.get(
    "/v2.1/projects/{project_id}/topics",
    response_model=list[BCFTopicResponse],
    summary="List BCF Topics",
    tags=["BCF API v2.1"],
)
def list_topics(
    project_id: str,
    service: Annotated[BCFSyncService, Depends(get_bcf_sync_service)],
    topic_status: Optional[str] = Query(None, alias="topic_status", description="Filter by topic status"),
    topic_type: Optional[str] = Query(None, alias="topic_type", description="Filter by topic type"),
    priority: Optional[str] = Query(None, alias="priority", description="Filter by priority"),
    assigned_to: Optional[str] = Query(None, alias="assigned_to", description="Filter by assignee"),
    cde_state: Optional[str] = Query(None, alias="cde_state", description="Filter by ISO 19650 CDE state"),
) -> list[BCFTopicResponse]:
    """Retrieve all BCF topics for a given project with filtering support."""
    return service.get_topics(
        project_id=project_id,
        topic_status=topic_status,
        topic_type=topic_type,
        priority=priority,
        assigned_to=assigned_to,
        cde_state=cde_state,
    )


@router.post(
    "/v2.1/projects/{project_id}/topics",
    response_model=BCFTopicResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create BCF Topic",
    tags=["BCF API v2.1"],
)
def create_topic(
    project_id: str,
    payload: BCFTopicCreatePayload,
    service: Annotated[BCFSyncService, Depends(get_bcf_sync_service)],
    projects_service: Annotated[ProjectsService, Depends(get_projects_service)],
) -> BCFTopicResponse:
    """Create a new BCF topic with ISO 19650 metadata container linking."""
    project_code = ""
    originator = ""
    try:
        p_id = int(project_id)
        proj = projects_service.get_project(p_id)
        if proj:
            project_code = proj.get("project_code", "")
            originator = proj.get("originator", "")
    except ValueError:
        pass

    return service.create_topic(
        project_id=project_id,
        payload=payload,
        project_code=project_code,
        originator=originator,
    )


@router.get(
    "/v2.1/projects/{project_id}/topics/{topic_guid}",
    response_model=BCFTopicResponse,
    summary="Get BCF Topic by GUID",
    tags=["BCF API v2.1"],
)
def get_topic(
    project_id: str,
    topic_guid: str,
    service: Annotated[BCFSyncService, Depends(get_bcf_sync_service)],
) -> BCFTopicResponse:
    """Fetch details of a single BCF topic."""
    topic = service.get_topic(project_id, topic_guid)
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BCF Topic {topic_guid} not found in project {project_id}",
        )
    return topic


@router.put(
    "/v2.1/projects/{project_id}/topics/{topic_guid}",
    response_model=BCFTopicResponse,
    summary="Update BCF Topic",
    tags=["BCF API v2.1"],
)
def update_topic(
    project_id: str,
    topic_guid: str,
    payload: BCFTopicUpdatePayload,
    service: Annotated[BCFSyncService, Depends(get_bcf_sync_service)],
) -> BCFTopicResponse:
    """Update status, priority, description, or ISO 19650 metadata of a topic."""
    updated = service.update_topic(project_id, topic_guid, payload)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BCF Topic {topic_guid} not found in project {project_id}",
        )
    return updated


@router.delete(
    "/v2.1/projects/{project_id}/topics/{topic_guid}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete BCF Topic",
    tags=["BCF API v2.1"],
)
def delete_topic(
    project_id: str,
    topic_guid: str,
    service: Annotated[BCFSyncService, Depends(get_bcf_sync_service)],
) -> None:
    """Delete a BCF topic and all associated viewpoints/comments."""
    deleted = service.delete_topic(project_id, topic_guid)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BCF Topic {topic_guid} not found in project {project_id}",
        )



# ------------------------------------------------------------------------------
# 3. Comments Endpoints
# ------------------------------------------------------------------------------


@router.get(
    "/v2.1/projects/{project_id}/topics/{topic_guid}/comments",
    response_model=list[BCFCommentResponse],
    summary="List Topic Comments",
    tags=["BCF API v2.1"],
)
def list_comments(
    project_id: str,
    topic_guid: str,
    service: Annotated[BCFSyncService, Depends(get_bcf_sync_service)],
) -> list[BCFCommentResponse]:
    """List all comments attached to a topic."""
    return service.get_comments(topic_guid)


@router.post(
    "/v2.1/projects/{project_id}/topics/{topic_guid}/comments",
    response_model=BCFCommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Topic Comment",
    tags=["BCF API v2.1"],
)
def create_comment(
    project_id: str,
    topic_guid: str,
    payload: BCFCommentCreatePayload,
    service: Annotated[BCFSyncService, Depends(get_bcf_sync_service)],
) -> BCFCommentResponse:
    """Add a new comment to a BCF topic."""
    return service.create_comment(topic_guid=topic_guid, payload=payload)


# ------------------------------------------------------------------------------
# 4. Viewpoints Endpoints
# ------------------------------------------------------------------------------


@router.get(
    "/v2.1/projects/{project_id}/topics/{topic_guid}/viewpoints",
    response_model=list[BCFViewpointResponse],
    summary="List Topic Viewpoints",
    tags=["BCF API v2.1"],
)
def list_viewpoints(
    project_id: str,
    topic_guid: str,
    service: Annotated[BCFSyncService, Depends(get_bcf_sync_service)],
) -> list[BCFViewpointResponse]:
    """Retrieve 3D camera viewpoints associated with a topic."""
    return service.get_viewpoints(topic_guid)


@router.post(
    "/v2.1/projects/{project_id}/topics/{topic_guid}/viewpoints",
    response_model=BCFViewpointResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Topic Viewpoint",
    tags=["BCF API v2.1"],
)
def create_viewpoint(
    project_id: str,
    topic_guid: str,
    payload: BCFViewpointCreatePayload,
    service: Annotated[BCFSyncService, Depends(get_bcf_sync_service)],
) -> BCFViewpointResponse:
    """Create a new camera viewpoint with component highlighting."""
    return service.create_viewpoint(topic_guid=topic_guid, payload=payload)


@router.get(
    "/v2.1/projects/{project_id}/topics/{topic_guid}/viewpoints/{viewpoint_guid}",
    response_model=BCFViewpointResponse,
    summary="Get Viewpoint by GUID",
    tags=["BCF API v2.1"],
)
def get_viewpoint(
    project_id: str,
    topic_guid: str,
    viewpoint_guid: str,
    service: Annotated[BCFSyncService, Depends(get_bcf_sync_service)],
) -> BCFViewpointResponse:
    """Fetch camera viewpoint definition."""
    vps = service.get_viewpoints(topic_guid)
    target = next((v for v in vps if v.guid.upper() == viewpoint_guid.upper()), None)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Viewpoint {viewpoint_guid} not found")
    return target


@router.get(
    "/v2.1/projects/{project_id}/topics/{topic_guid}/viewpoints/{viewpoint_guid}/snapshot",
    summary="Get Viewpoint Snapshot Image",
    tags=["BCF API v2.1"],
)
@router.get(
    "/v2.1/projects/{project_id}/topics/{topic_guid}/viewpoints/{viewpoint_guid}/bitmap",
    summary="Get Viewpoint Bitmap Image Alias",
    tags=["BCF API v2.1"],
)
def get_viewpoint_snapshot(
    project_id: str,
    topic_guid: str,
    viewpoint_guid: str,
    service: Annotated[BCFSyncService, Depends(get_bcf_sync_service)],
) -> RawResponse:
    """Return raw snapshot PNG image binary for viewpoint."""
    img_bytes = service.get_snapshot(viewpoint_guid)
    if not img_bytes:
        # Generate 1x1 transparent PNG fallback
        img_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    return RawResponse(content=img_bytes, media_type="image/png")
