"""FastAPI router for GitHub repository project storage sources and tree structure reading."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.dependencies import get_github_repo_service
from app.logging_config import get_logger
from app.modules.contracts import (
    GitHubRepoCreateRequest,
    GitHubRepoResponse,
    GitHubRepoStructureResponse,
    GitHubRepoUpdateRequest,
)
from app.services.github_repo_service import GitHubRepoService

logger = get_logger(__name__)

router = APIRouter()


@router.get("", response_model=list[GitHubRepoResponse], summary="List registered GitHub repositories")
def list_repositories(
    service: Annotated[GitHubRepoService, Depends(get_github_repo_service)],
    response: Response,
) -> list[GitHubRepoResponse]:
    """Return all registered GitHub repository project storage sources."""
    response.headers["Cache-Control"] = "private, max-age=10, stale-while-revalidate=30"
    rows = service.list_repos()
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
) -> GitHubRepoResponse:
    """Parse GitHub URL and register a new repository project storage source."""
    try:
        created = service.create_repo(
            url=payload.url,
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
    return GitHubRepoResponse(**repo)


@router.put("/{repo_id}", response_model=GitHubRepoResponse, summary="Update repository metadata")
def update_repository(
    repo_id: int,
    payload: GitHubRepoUpdateRequest,
    service: Annotated[GitHubRepoService, Depends(get_github_repo_service)],
) -> GitHubRepoResponse:
    """Update metadata for an existing registered GitHub repository."""
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
) -> None:
    """Remove a registered GitHub repository source."""
    existing = service.get_repo(repo_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"GitHub Repository with ID {repo_id} not found.",
        )
    service.delete_repo(repo_id)


@router.get("/{repo_id}/structure", response_model=GitHubRepoStructureResponse, summary="Read repository tree structure")
def get_repository_structure(
    repo_id: int,
    service: Annotated[GitHubRepoService, Depends(get_github_repo_service)],
    response: Response,
) -> GitHubRepoStructureResponse:
    """Fetch and parse repository git tree structure to discover IFC models and categories."""
    response.headers["Cache-Control"] = "private, max-age=30, stale-while-revalidate=120"
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
