"""GitHub repository integration, tree inspection, and model attachment contracts."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.modules.contracts.base import TimestampFields

__all__ = ['GitHubRepoCreateRequest', 'GitHubRepoUpdateRequest', 'GitHubRepoResponse', 'GitHubRepoItem', 'GitHubRepoStructureResponse', 'AttachRepoModelsRequest']

# ---------------------------------------------------------------------------
# GitHub Repository Contracts
# ---------------------------------------------------------------------------


class GitHubRepoCreateRequest(BaseModel):
    """Payload for creating or adding a GitHub repository project storage source."""

    url: str = Field(..., min_length=5, description="Full GitHub repository URL (e.g. https://github.com/owner/repo)")
    name: Optional[str] = Field(None, description="Display name for repository")
    branch: Optional[str] = Field("main", description="Git branch to inspect")
    description: Optional[str] = Field("", description="Optional repository description")

class GitHubRepoUpdateRequest(BaseModel):
    """Payload for updating GitHub repository storage configuration."""

    name: Optional[str] = Field(None, description="Updated display name")
    branch: Optional[str] = Field(None, description="Updated default git branch")
    description: Optional[str] = Field(None, description="Updated description")
    is_active: Optional[bool] = Field(None, description="Toggle active state")

class GitHubRepoResponse(TimestampFields):
    """Response contract for a registered GitHub repository."""

    id: int
    name: str
    owner: str
    url: str
    branch: str = "main"
    description: str = ""
    is_active: bool = True
    organization_id: int

class GitHubRepoItem(BaseModel):
    """File item inside a GitHub repository tree."""

    path: str
    name: str
    type: str = "file"  # file or folder
    size: int = 0
    extension: str = ""
    category: str = "general"
    download_url: str = ""

class GitHubRepoStructureResponse(BaseModel):
    """Complete structure response listing models in a GitHub repository."""

    repo_id: int
    owner: str
    name: str
    url: str
    branch: str = "main"
    total_files: int = 0
    models_count: int = 0
    categories: list[str] = []
    items: list[GitHubRepoItem] = []

class AttachRepoModelsRequest(BaseModel):
    """Payload for attaching one or more IFC models from a GitHub repository to an existing project."""

    repo_id: int = Field(..., description="Registered GitHub repository the files live in")
    file_paths: list[str] = Field(
        ..., min_length=1, description="Relative file paths in the repository (e.g. models/hospital/Clinic_Architectural.ifc)"
    )
    primary_index: int = Field(
        0, ge=0, description="Index into file_paths naming the model to attach as primary"
    )
