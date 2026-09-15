"""FastAPI router for GitHub repository project storage sources and tree structure reading."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status

from app.api.dependencies import (
    get_github_repo_service,
    get_membership_service,
    get_profile_service,
)
from app.auth import CurrentUser, get_current_user
from app.logging_config import get_logger
from app.modules.contracts import (
    GitHubRepoCreateRequest,
    GitHubRepoResponse,
    GitHubRepoStructureResponse,
    GitHubRepoUpdateRequest,
)
from app.services.github_repo_service import GitHubRepoService
from app.services.membership_service import MembershipService
from app.services.profile_service import ProfileService

logger = get_logger(__name__)

# Repositories are scoped to the organization that registered them
# (organization_id, backfilled to a default org for pre-multi-tenant rows --
# see 20260915010000_add_organization_id_to_github_repositories.sql). Every
# route below still requires only a signed-in caller at the router level;
# per-repo read/write access is enforced by _require_repo_org_access, the
# same superadmin-bypass / org-membership pattern used for documents
# (app/api/documents.py) and rulesets (app/api/rules.py).
router = APIRouter(dependencies=[Depends(get_current_user)])


def _require_repo_org_access(
    repo: dict,
    current_user: CurrentUser,
    memberships: MembershipService,
    profiles: ProfileService,
) -> None:
    """Raise 404 unless *current_user* belongs to the organization that owns *repo*.

    404 rather than 403 so an unauthorized caller can't distinguish "not
    yours" from "doesn't exist", matching the document/ruleset access checks.
    """
    if profiles.is_superadmin(current_user.id):
        return
    org_id = repo.get("organization_id")
    if org_id is not None and org_id in memberships.org_ids_for_user(current_user.id):
        return
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"GitHub Repository with ID {repo.get('id')} not found.",
    )


def _resolve_target_org_id(
    organization_id: Optional[int],
    x_org_id: Optional[str],
    current_user: CurrentUser,
    memberships: MembershipService,
    profiles: ProfileService,
) -> int:
    """Resolve and authorize the organization a new repository should be registered under."""
    target_org_id = organization_id
    if target_org_id is None and x_org_id and x_org_id.strip().isdigit():
        target_org_id = int(x_org_id.strip())

    user_orgs = memberships.org_ids_for_user(current_user.id)
    if target_org_id is not None:
        if not profiles.is_superadmin(current_user.id) and target_org_id not in user_orgs:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You do not belong to organization {target_org_id}.",
            )
        return target_org_id

    if user_orgs:
        return next(iter(user_orgs))

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="No organization_id provided and the caller belongs to no organization.",
    )


@router.get("", response_model=list[GitHubRepoResponse], summary="List registered GitHub repositories")
def list_repositories(
    service: Annotated[GitHubRepoService, Depends(get_github_repo_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    response: Response,
) -> list[GitHubRepoResponse]:
    """Return GitHub repository project storage sources visible to the caller's organizations."""
    response.headers["Cache-Control"] = "private, max-age=10, stale-while-revalidate=30"
    org_ids = None if profiles.is_superadmin(current_user.id) else set(memberships.org_ids_for_user(current_user.id))
    rows = service.list_repos(organization_ids=org_ids)
    return [GitHubRepoResponse(**row) for row in rows]


@router.post(
    "",
    response_model=GitHubRepoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a GitHub repository source",
)
def create_repository(
    payload: GitHubRepoCreateRequest,
    service: Annotated[GitHubRepoService, Depends(get_github_repo_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    organization_id: Optional[int] = Query(None, description="Organization to register the repository under"),
    x_org_id: Optional[str] = Header(None, alias="X-Organization-Id"),
) -> GitHubRepoResponse:
    """Parse GitHub URL and register a new repository project storage source."""
    target_org_id = _resolve_target_org_id(organization_id, x_org_id, current_user, memberships, profiles)
    try:
        created = service.create_repo(
            url=payload.url,
            organization_id=target_org_id,
            name=payload.name,
            branch=payload.branch or "main",
            description=payload.description or "",
        )
        return GitHubRepoResponse(**created)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{repo_id}", response_model=GitHubRepoResponse, summary="Get registered repository by ID")
def get_repository(
    repo_id: int,
    service: Annotated[GitHubRepoService, Depends(get_github_repo_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    response: Response,
) -> GitHubRepoResponse:
    """Retrieve details for a single registered GitHub repository."""
    response.headers["Cache-Control"] = "private, max-age=10, stale-while-revalidate=30"
    repo = service.get_repo(repo_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"GitHub Repository with ID {repo_id} not found.",
        )
    _require_repo_org_access(repo, current_user, memberships, profiles)
    return GitHubRepoResponse(**repo)


@router.put("/{repo_id}", response_model=GitHubRepoResponse, summary="Update repository metadata")
def update_repository(
    repo_id: int,
    payload: GitHubRepoUpdateRequest,
    service: Annotated[GitHubRepoService, Depends(get_github_repo_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> GitHubRepoResponse:
    """Update metadata for an existing registered GitHub repository."""
    existing = service.get_repo(repo_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"GitHub Repository with ID {repo_id} not found.",
        )
    _require_repo_org_access(existing, current_user, memberships, profiles)
    updated = service.update_repo(
        repo_id,
        name=payload.name,
        branch=payload.branch,
        description=payload.description,
        is_active=payload.is_active,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"GitHub Repository with ID {repo_id} not found.",
        )
    return GitHubRepoResponse(**updated)


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete registered repository")
def delete_repository(
    repo_id: int,
    service: Annotated[GitHubRepoService, Depends(get_github_repo_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> None:
    """Remove a registered GitHub repository source."""
    existing = service.get_repo(repo_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"GitHub Repository with ID {repo_id} not found.",
        )
    _require_repo_org_access(existing, current_user, memberships, profiles)
    service.delete_repo(repo_id)


@router.get("/{repo_id}/structure", response_model=GitHubRepoStructureResponse, summary="Read repository tree structure")
def get_repository_structure(
    repo_id: int,
    service: Annotated[GitHubRepoService, Depends(get_github_repo_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    response: Response,
) -> GitHubRepoStructureResponse:
    """Fetch and parse repository git tree structure to discover IFC models and categories."""
    response.headers["Cache-Control"] = "private, max-age=30, stale-while-revalidate=120"
    existing = service.get_repo(repo_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"GitHub Repository with ID {repo_id} not found.",
        )
    _require_repo_org_access(existing, current_user, memberships, profiles)
    try:
        return service.get_repo_structure(repo_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Failed to fetch GitHub repository structure repo_id=%d: %s", repo_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not read GitHub repository structure: {exc}",
        )
