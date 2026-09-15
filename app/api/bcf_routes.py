"""buildingSMART BCF REST API (v2.1 / v3.0 standard).

Reference: https://github.com/buildingSMART/BCF-API
Provides live bidirectional syncing of topics, viewpoints, comments, and ISO 19650 metadata
between BIMGuard AI and authoring tools (Revit, Solibri, Archicad, BlenderBIM, etc.).
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import Response as RawResponse

from app.api.dependencies import (
    get_membership_service,
    get_profile_service,
    get_projects_service,
)
from app.auth import CurrentUser, get_current_user
from app.logging_config import get_logger
from app.modules.contracts import (
    BCFCommentCreatePayload,
    BCFCommentResponse,
    BCFCommentUpdatePayload,
    BCFCurrentUserResponse,
    BCFExtensionsResponse,
    BCFProjectResponse,
    BCFTopicCreatePayload,
    BCFTopicResponse,
    BCFTopicUpdatePayload,
    BCFVersionResponse,
    BCFViewpointCreatePayload,
    BCFViewpointResponse,
)
from app.services.bcf_importer import BCFImportError, parse_bcfzip
from app.services.bcf_sync_service import DEFAULT_BCF_SYNC_SERVICE, BCFSyncService, topic_etag
from app.services.membership_service import MembershipService
from app.services.profile_service import ProfileService
from app.services.project_visibility import visible_project_rows
from app.services.projects_service import ProjectsService

logger = get_logger(__name__)

#: Discovery router, deliberately carrying no auth dependency: BCF-API requires
#: ``GET /bcf/versions`` to be reachable before a client knows how to
#: authenticate against the rest of the API. Mounted at the same "/api/bcf"
#: prefix as ``router`` (app/main.py), so the path is "/api/bcf/versions"
#: rather than the spec's root-level "/bcf/versions" -- this API lives under
#: this app's own "/api" gateway namespace like every other router here.
public_router = APIRouter()

router = APIRouter(dependencies=[Depends(get_current_user)])


@public_router.get(
    "/versions",
    response_model=list[BCFVersionResponse],
    summary="BCF API Version Discovery",
    tags=["BCF API"],
)
def get_bcf_versions() -> list[BCFVersionResponse]:
    """Advertise the BCF API version(s) this server implements.

    Unauthenticated per the BCF-API spec, so a client can discover which
    version to speak before it has credentials.
    """
    return [BCFVersionResponse(version_id="2.1", detailed_version="2.1")]


def get_bcf_sync_service() -> BCFSyncService:
    """Dependency provider for BCF synchronization service."""
    return DEFAULT_BCF_SYNC_SERVICE


@router.get(
    "/v2.1/current-user",
    response_model=BCFCurrentUserResponse,
    summary="Get Current BCF User",
    tags=["BCF API v2.1"],
)
def get_bcf_current_user(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> BCFCurrentUserResponse:
    """Return the authenticated caller's identity.

    Spec-required regardless of auth scheme. This server authenticates with a
    Supabase JWT bearer token rather than the spec's OAuth2 flow -- a client
    that has one already used it to reach this endpoint -- so there is no
    separate ``/auth`` handshake to perform first.
    """
    return BCFCurrentUserResponse(
        id=current_user.id,
        name=(current_user.email or current_user.id),
        email=current_user.email,
    )


def _paginate(items: list, page: int, per_page: int, response: Response) -> list:
    """Slice ``items`` to one page and set ``X-Total-Count``/``Link`` headers.

    GitHub-style pagination: ``page`` is 1-based, ``Link`` carries ``rel="next"``
    and ``rel="prev"`` only when those pages exist. Total count and slicing
    both happen after every filter has already been applied, so the header
    reflects the filtered result set, not the whole table.
    """
    total = len(items)
    response.headers["X-Total-Count"] = str(total)
    start = (page - 1) * per_page
    page_items = items[start : start + per_page]

    links = []
    if start + per_page < total:
        links.append(f'<?page={page + 1}&per_page={per_page}>; rel="next"')
    if page > 1:
        links.append(f'<?page={page - 1}&per_page={per_page}>; rel="prev"')
    if links:
        response.headers["Link"] = ", ".join(links)

    return page_items


def _require_bcf_project_access(
    project_id: str,
    current_user: CurrentUser,
    projects_service: ProjectsService,
    memberships: MembershipService,
    profiles: ProfileService,
) -> None:
    """Ensure caller has access to the project if it corresponds to an existing DB project."""
    if profiles.is_superadmin(current_user.id):
        return
    try:
        pid = int(project_id)
    except ValueError:
        return

    project = projects_service.get_project(pid)
    if project:
        from app.api.projects import _can_access_project

        if not _can_access_project(project, current_user.id, memberships):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project {project_id} not found.",
            )


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
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    projects_service: Annotated[ProjectsService, Depends(get_projects_service)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> list[BCFProjectResponse]:
    """Return all projects enabled for BCF issue exchange, scoped to caller's organizations."""
    all_projects = projects_service.list_projects()
    projects = visible_project_rows(
        all_projects,
        user_id=current_user.id,
        organization_id=None,
        memberships=memberships,
        profiles=profiles,
    )
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
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    projects_service: Annotated[ProjectsService, Depends(get_projects_service)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> BCFProjectResponse:
    """Return BCF project metadata and authorization capabilities."""
    try:
        p_id = int(project_id)
        project = projects_service.get_project(p_id)
    except ValueError:
        project = None

    if project:
        if not profiles.is_superadmin(current_user.id):
            from app.api.projects import _can_access_project

            if not _can_access_project(project, current_user.id, memberships):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Project {project_id} not found.",
                )
        return BCFProjectResponse(
            project_id=str(project["id"]),
            name=project.get("name", f"Project {project['id']}"),
        )

    # Fallback for string/UUID projects
    return BCFProjectResponse(project_id=str(project_id), name=f"Project {project_id}")


@router.get(
    "/v2.1/projects/{project_id}/extensions",
    response_model=BCFExtensionsResponse,
    summary="Get BCF Project Extensions",
    tags=["BCF API v2.1"],
)
def get_bcf_extensions(
    project_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    projects_service: Annotated[ProjectsService, Depends(get_projects_service)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> BCFExtensionsResponse:
    """Return the enumerations and actions this API accepts for the project.

    Fixed vocabulary rather than DB-driven: every value returned here is what
    ``BCFTopicCreatePayload``/``BCFTopicUpdatePayload`` actually validate, so a
    client populating a dropdown from this response cannot submit a value the
    create/update endpoints would reject.
    """
    _require_bcf_project_access(project_id, current_user, projects_service, memberships, profiles)
    return BCFExtensionsResponse()


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
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    projects_service: Annotated[ProjectsService, Depends(get_projects_service)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[BCFSyncService, Depends(get_bcf_sync_service)],
    response: Response,
    topic_status: Optional[str] = Query(None, alias="topic_status", description="Filter by topic status"),
    topic_type: Optional[str] = Query(None, alias="topic_type", description="Filter by topic type"),
    priority: Optional[str] = Query(None, alias="priority", description="Filter by priority"),
    assigned_to: Optional[str] = Query(None, alias="assigned_to", description="Filter by assignee"),
    cde_state: Optional[str] = Query(None, alias="cde_state", description="Filter by ISO 19650 CDE state"),
    page: int = Query(1, ge=1, description="1-based page number"),
    per_page: int = Query(100, ge=1, le=500, description="Topics per page"),
) -> list[BCFTopicResponse]:
    """Retrieve BCF topics for a given project, filtered and paginated."""
    _require_bcf_project_access(project_id, current_user, projects_service, memberships, profiles)
    topics = service.get_topics(
        project_id=project_id,
        topic_status=topic_status,
        topic_type=topic_type,
        priority=priority,
        assigned_to=assigned_to,
        cde_state=cde_state,
    )
    return _paginate(topics, page, per_page, response)


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
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    projects_service: Annotated[ProjectsService, Depends(get_projects_service)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[BCFSyncService, Depends(get_bcf_sync_service)],
) -> BCFTopicResponse:
    """Create a new BCF topic with ISO 19650 metadata container linking."""
    _require_bcf_project_access(project_id, current_user, projects_service, memberships, profiles)
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


@router.post(
    "/v2.1/projects/{project_id}/import",
    response_model=list[BCFTopicResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Import a BCF-XML (.bcfzip) Archive",
    tags=["BCF API v2.1"],
)
async def import_bcf_archive(
    project_id: str,
    file: UploadFile,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    projects_service: Annotated[ProjectsService, Depends(get_projects_service)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[BCFSyncService, Depends(get_bcf_sync_service)],
) -> list[BCFTopicResponse]:
    """Import topics, comments and viewpoints from an uploaded ``.bcfzip`` archive.

    Not part of BCF-API itself (the spec only defines the file format, not a
    REST upload path for it) -- added so a coordinator can bring a `.bcfzip`
    exported from Revit, Solibri or BlenderBIM into this project rather than
    this API being export-only. Re-importing the same archive updates its
    topics in place (see ``BCFSyncService.import_topic``).
    """
    _require_bcf_project_access(project_id, current_user, projects_service, memberships, profiles)
    data = await file.read()
    try:
        parsed_topics = parse_bcfzip(data)
    except BCFImportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return [service.import_topic(project_id, topic) for topic in parsed_topics]


@router.get(
    "/v2.1/projects/{project_id}/topics/{topic_guid}",
    response_model=BCFTopicResponse,
    summary="Get BCF Topic by GUID",
    tags=["BCF API v2.1"],
)
def get_topic(
    project_id: str,
    topic_guid: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    projects_service: Annotated[ProjectsService, Depends(get_projects_service)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[BCFSyncService, Depends(get_bcf_sync_service)],
    response: Response,
) -> BCFTopicResponse:
    """Fetch details of a single BCF topic.

    Sets ``ETag`` so a client can round-trip it as ``If-Match`` on the
    following ``PUT`` to detect a concurrent edit.
    """
    _require_bcf_project_access(project_id, current_user, projects_service, memberships, profiles)
    topic = service.get_topic(project_id, topic_guid)
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BCF Topic {topic_guid} not found in project {project_id}",
        )
    response.headers["ETag"] = topic_etag(topic)
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
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    projects_service: Annotated[ProjectsService, Depends(get_projects_service)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[BCFSyncService, Depends(get_bcf_sync_service)],
    response: Response,
    if_match: Annotated[Optional[str], Header(alias="If-Match")] = None,
) -> BCFTopicResponse:
    """Update status, priority, description, or ISO 19650 metadata of a topic.

    Honors optimistic concurrency via ``If-Match``: when the caller sends the
    ``ETag`` it last read, a topic modified by someone else in between fails
    with 412 instead of silently overwriting their change.
    """
    _require_bcf_project_access(project_id, current_user, projects_service, memberships, profiles)
    current = service.get_topic(project_id, topic_guid)
    if not current:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BCF Topic {topic_guid} not found in project {project_id}",
        )
    if if_match and if_match != topic_etag(current):
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="Topic was modified since it was last read; refetch and retry.",
        )

    updated = service.update_topic(project_id, topic_guid, payload)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BCF Topic {topic_guid} not found in project {project_id}",
        )
    response.headers["ETag"] = topic_etag(updated)
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
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    projects_service: Annotated[ProjectsService, Depends(get_projects_service)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[BCFSyncService, Depends(get_bcf_sync_service)],
) -> None:
    """Delete a BCF topic and all associated viewpoints/comments."""
    _require_bcf_project_access(project_id, current_user, projects_service, memberships, profiles)
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
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    projects_service: Annotated[ProjectsService, Depends(get_projects_service)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[BCFSyncService, Depends(get_bcf_sync_service)],
    response: Response,
    page: int = Query(1, ge=1, description="1-based page number"),
    per_page: int = Query(100, ge=1, le=500, description="Comments per page"),
) -> list[BCFCommentResponse]:
    """List comments attached to a topic, paginated."""
    _require_bcf_project_access(project_id, current_user, projects_service, memberships, profiles)
    comments = service.get_comments(topic_guid)
    return _paginate(comments, page, per_page, response)


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
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    projects_service: Annotated[ProjectsService, Depends(get_projects_service)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[BCFSyncService, Depends(get_bcf_sync_service)],
) -> BCFCommentResponse:
    """Add a new comment to a BCF topic."""
    _require_bcf_project_access(project_id, current_user, projects_service, memberships, profiles)
    return service.create_comment(topic_guid=topic_guid, payload=payload)


@router.put(
    "/v2.1/projects/{project_id}/topics/{topic_guid}/comments/{comment_guid}",
    response_model=BCFCommentResponse,
    summary="Update Topic Comment",
    tags=["BCF API v2.1"],
)
def update_comment(
    project_id: str,
    topic_guid: str,
    comment_guid: str,
    payload: BCFCommentUpdatePayload,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    projects_service: Annotated[ProjectsService, Depends(get_projects_service)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[BCFSyncService, Depends(get_bcf_sync_service)],
) -> BCFCommentResponse:
    """Edit an existing comment's text."""
    _require_bcf_project_access(project_id, current_user, projects_service, memberships, profiles)
    updated = service.update_comment(topic_guid, comment_guid, payload)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comment {comment_guid} not found on topic {topic_guid}",
        )
    return updated


@router.delete(
    "/v2.1/projects/{project_id}/topics/{topic_guid}/comments/{comment_guid}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Topic Comment",
    tags=["BCF API v2.1"],
)
def delete_comment(
    project_id: str,
    topic_guid: str,
    comment_guid: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    projects_service: Annotated[ProjectsService, Depends(get_projects_service)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[BCFSyncService, Depends(get_bcf_sync_service)],
) -> None:
    """Delete a comment from a topic."""
    _require_bcf_project_access(project_id, current_user, projects_service, memberships, profiles)
    deleted = service.delete_comment(topic_guid, comment_guid)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comment {comment_guid} not found on topic {topic_guid}",
        )


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
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    projects_service: Annotated[ProjectsService, Depends(get_projects_service)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[BCFSyncService, Depends(get_bcf_sync_service)],
) -> list[BCFViewpointResponse]:
    """Retrieve 3D camera viewpoints associated with a topic."""
    _require_bcf_project_access(project_id, current_user, projects_service, memberships, profiles)
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
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    projects_service: Annotated[ProjectsService, Depends(get_projects_service)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[BCFSyncService, Depends(get_bcf_sync_service)],
) -> BCFViewpointResponse:
    """Create a new camera viewpoint with component highlighting."""
    _require_bcf_project_access(project_id, current_user, projects_service, memberships, profiles)
    return service.create_viewpoint(topic_guid=topic_guid, payload=payload)


@router.delete(
    "/v2.1/projects/{project_id}/topics/{topic_guid}/viewpoints/{viewpoint_guid}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Topic Viewpoint",
    tags=["BCF API v2.1"],
)
def delete_viewpoint(
    project_id: str,
    topic_guid: str,
    viewpoint_guid: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    projects_service: Annotated[ProjectsService, Depends(get_projects_service)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[BCFSyncService, Depends(get_bcf_sync_service)],
) -> None:
    """Delete a viewpoint from a topic."""
    _require_bcf_project_access(project_id, current_user, projects_service, memberships, profiles)
    deleted = service.delete_viewpoint(topic_guid, viewpoint_guid)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Viewpoint {viewpoint_guid} not found on topic {topic_guid}",
        )


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
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    projects_service: Annotated[ProjectsService, Depends(get_projects_service)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[BCFSyncService, Depends(get_bcf_sync_service)],
) -> BCFViewpointResponse:
    """Fetch camera viewpoint definition."""
    _require_bcf_project_access(project_id, current_user, projects_service, memberships, profiles)
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
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    projects_service: Annotated[ProjectsService, Depends(get_projects_service)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    service: Annotated[BCFSyncService, Depends(get_bcf_sync_service)],
) -> RawResponse:
    """Return raw snapshot PNG image binary for viewpoint."""
    _require_bcf_project_access(project_id, current_user, projects_service, memberships, profiles)
    img_bytes = service.get_snapshot(viewpoint_guid)
    if not img_bytes:
        # Generate 1x1 transparent PNG fallback
        img_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    return RawResponse(content=img_bytes, media_type="image/png")
