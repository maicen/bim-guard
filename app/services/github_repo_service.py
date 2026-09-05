"""Service layer for managing GitHub repository project sources and structure parsing."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from re import match
from typing import Any, Optional

import httpx

from app.logging_config import get_logger
from app.modules.contracts import (
    GitHubRepoItem,
    GitHubRepoStructureResponse,
)
from app.services.db_adapters import DatabaseAdapter
from app.services.projects_service import ProjectsService

logger = get_logger(__name__)


def parse_github_url(url: str) -> tuple[str, str]:
    """Parse a GitHub URL into (owner, repo_name).

    Supports formats:
      - https://github.com/owner/repo
      - https://github.com/owner/repo.git
      - github.com/owner/repo
      - owner/repo
    """
    clean_url = url.strip().rstrip("/")
    if clean_url.endswith(".git"):
        clean_url = clean_url[:-4]

    # Regex matching owner and repo
    m = match(r"^(?:https?://)?(?:www\.)?github\.com/([^/]+)/([^/]+)$", clean_url)
    if m:
        return m.group(1), m.group(2)

    parts = [p for p in clean_url.split("/") if p]
    if len(parts) == 2:
        return parts[0], parts[1]

    raise ValueError(f"Invalid GitHub repository URL format: '{url}'. Expected format 'https://github.com/owner/repo'.")


class GitHubRepoService:
    """Domain service for GitHub repositories management, git tree structure parsing, and model importing."""

    def __init__(
        self,
        github_repos_repo: DatabaseAdapter,
        projects_service: Optional[ProjectsService] = None,
    ):
        """Initialize service with persistence repository adapter."""
        self._repos = github_repos_repo
        self._projects_service = projects_service
        self._tree_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

    def list_repos(self) -> list[dict[str, Any]]:
        """Retrieve all registered GitHub repositories ordered newest first."""
        rows = list(self._repos.rows)
        return sorted(rows, key=lambda r: int(r.get("id") or 0), reverse=True)

    def get_repo(self, repo_id: int) -> dict[str, Any] | None:
        """Retrieve a registered GitHub repository by primary key."""
        return self._repos.get(repo_id)

    def get_repo_by_url(self, url: str) -> dict[str, Any] | None:
        """Retrieve a registered GitHub repository by URL."""
        clean = url.strip().rstrip("/")
        for repo in self.list_repos():
            if repo.get("url", "").strip().rstrip("/") == clean:
                return repo
        return None

    def create_repo(
        self,
        url: str,
        name: Optional[str] = None,
        branch: str = "main",
        description: str = "",
    ) -> dict[str, Any]:
        """Parse URL, validate repository details, and persist new GitHub repo source."""
        owner, repo_name = parse_github_url(url)
        clean_url = f"https://github.com/{owner}/{repo_name}"

        existing = self.get_repo_by_url(clean_url)
        if existing:
            return existing

        display_name = name.strip() if name and name.strip() else repo_name
        now = datetime.now(timezone.utc).isoformat()

        payload = {
            "name": display_name,
            "owner": owner,
            "url": clean_url,
            "branch": branch.strip() or "main",
            "description": description.strip(),
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

        return self._repos.insert(payload)

    def update_repo(
        self,
        repo_id: int,
        name: Optional[str] = None,
        branch: Optional[str] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> dict[str, Any] | None:
        """Update metadata for an existing registered GitHub repository."""
        existing = self.get_repo(repo_id)
        if not existing:
            return None

        updates: dict[str, Any] = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if name is not None:
            updates["name"] = name.strip()
        if branch is not None:
            updates["branch"] = branch.strip()
        if description is not None:
            updates["description"] = description.strip()
        if is_active is not None:
            updates["is_active"] = bool(is_active)

        self._repos.update(updates=updates, pk_values=repo_id)
        return self.get_repo(repo_id)

    def delete_repo(self, repo_id: int) -> None:
        """Delete a registered GitHub repository by primary key."""
        self._repos.delete(repo_id)

    def get_repo_structure(self, repo_id: int) -> GitHubRepoStructureResponse:
        """Fetch and parse repository file tree structure to list IFC models and categories."""
        repo = self.get_repo(repo_id)
        if not repo:
            raise ValueError(f"GitHub Repository with ID {repo_id} not found.")

        owner = repo["owner"]
        name = repo["name"]
        branch = repo.get("branch") or "main"
        repo_url = repo.get("url") or f"https://github.com/{owner}/{name}"

        raw_tree_items = self._fetch_git_tree(owner, name, branch)

        items: list[GitHubRepoItem] = []
        categories_set: set[str] = set()

        for raw_item in raw_tree_items:
            path_str = raw_item.get("path", "")
            item_type = raw_item.get("type", "blob")
            size = raw_item.get("size", 0)

            # Filter for model files or zip files containing models
            ext = Path(path_str).suffix.lower()
            if ext in {".ifc", ".zip"}:
                parts = path_str.split("/")
                category = parts[1] if len(parts) > 2 and parts[0] == "models" else (parts[0] if len(parts) > 1 else "general")
                categories_set.add(category)

                filename = Path(path_str).name
                download_url = f"https://raw.githubusercontent.com/{owner}/{name}/{branch}/{path_str}"

                items.append(
                    GitHubRepoItem(
                        path=path_str,
                        name=filename,
                        type="file" if item_type == "blob" else "folder",
                        size=size,
                        extension=ext,
                        category=category,
                        download_url=download_url,
                    )
                )

        categories = sorted(list(categories_set))
        if not categories:
            categories = ["models"]

        return GitHubRepoStructureResponse(
            repo_id=repo_id,
            owner=owner,
            name=name,
            url=repo_url,
            branch=branch,
            total_files=len(raw_tree_items),
            models_count=len(items),
            categories=categories,
            items=items,
        )

    def _fetch_git_tree(self, owner: str, name: str, branch: str) -> list[dict[str, Any]]:
        """Fetch tree from GitHub API with in-memory TTL caching and fallback handling."""
        cache_key = f"{owner.lower()}/{name.lower()}:{branch}"
        now_ts = datetime.now(timezone.utc).timestamp()

        # Cache hit check (10 minutes TTL = 600s)
        if cache_key in self._tree_cache:
            cached_time, cached_tree = self._tree_cache[cache_key]
            if now_ts - cached_time < 600:
                logger.debug("Returning in-memory cached git tree for %s", cache_key)
                return cached_tree

        tree_url = f"https://api.github.com/repos/{owner}/{name}/git/trees/{branch}?recursive=1"
        headers = {
            "User-Agent": "BIM-Guard-App/1.0",
            "Accept": "application/vnd.github.v3+json",
        }
        token = os.getenv("GITHUB_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"token {token}"

        try:
            with httpx.Client(timeout=3.0, follow_redirects=True) as client:
                resp = client.get(tree_url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    tree = data.get("tree", [])
                    if tree:
                        self._tree_cache[cache_key] = (now_ts, tree)
                        return tree
                logger.warning("GitHub API tree request returned status %d for %s/%s", resp.status_code, owner, name)
        except Exception as exc:
            logger.warning("Could not fetch GitHub tree for %s/%s: %s", owner, name, exc)

        # Fallback tree for default bimguard-test-models if API rate limited or offline
        fallback_tree = []
        if owner.lower() == "maicen" and name.lower() == "bimguard-test-models":
            fallback_tree = self._fallback_bimguard_test_models_tree()

        if fallback_tree:
            self._tree_cache[cache_key] = (now_ts, fallback_tree)

        return fallback_tree

    def _fallback_bimguard_test_models_tree(self) -> list[dict[str, Any]]:
        """Provide a complete static tree fallback for maicen/bimguard-test-models."""
        return [
            {"path": "models/hospital/Clinic_Architectural.ifc", "type": "blob", "size": 13003205},
            {"path": "models/hospital/Clinic_Electrical.ifc", "type": "blob", "size": 6800204},
            {"path": "models/hospital/Clinic_HVAC.ifc", "type": "blob", "size": 26914597},
            {"path": "models/hospital/Clinic_Plumbing.ifc", "type": "blob", "size": 55834520},
            {"path": "models/hospital/Clinic_Structural.ifc", "type": "blob", "size": 19058175},
            {"path": "models/hospital/GVA_Sanitario.ifc", "type": "blob", "size": 6961187},
            {"path": "models/hospital/west_riverside_hospital_arc_ifc4.ifc", "type": "blob", "size": 80937122},
            {"path": "models/hospital/west_riverside_hospital_elec_ifc4.ifc", "type": "blob", "size": 4435308},
            {"path": "models/hospital/west_riverside_hospital_fire_ifc4.ifc", "type": "blob", "size": 905021},
            {"path": "models/hospital/west_riverside_hospital_mech_ifc4.ifc", "type": "blob", "size": 73047260},
            {"path": "models/hospital/west_riverside_hospital_plumb_ifc4.ifc", "type": "blob", "size": 23762808},
            {"path": "models/hospital/west_riverside_hospital_sprinkle_ifc4.ifc", "type": "blob", "size": 33990094},
            {"path": "models/hospital/west_riverside_hospital_str_ifc4.ifc", "type": "blob", "size": 6484576},
            {"path": "models/industrial/aisc_sculpture_brep.ifc", "type": "blob", "size": 554146},
            {"path": "models/industrial/aisc_sculpture_param.ifc", "type": "blob", "size": 316004},
            {"path": "models/industrial/craslabbim.ifc", "type": "blob", "size": 67553572},
            {"path": "models/office/AC20-FZK-Haus.ifc", "type": "blob", "size": 2570803},
            {"path": "models/office/AC20-Institute-Var-2.ifc", "type": "blob", "size": 10934237},
            {"path": "models/office/DigitalHub_FM-ARC_v2.ifc", "type": "blob", "size": 9022255},
            {"path": "models/office/DigitalHub_FM-HZG_v2.ifc", "type": "blob", "size": 20890415},
            {"path": "models/office/DigitalHub_FM-LFT_v2.ifc", "type": "blob", "size": 12737833},
            {"path": "models/office/DigitalHub_FM-SAN_v2.ifc", "type": "blob", "size": 25178864},
            {"path": "models/office/Duplex_A_20110907.ifc", "type": "blob", "size": 2380763},
            {"path": "models/office/Duplex_Electrical_20121207.ifc", "type": "blob", "size": 1602758},
            {"path": "models/office/Duplex_MEP_20110907.ifc", "type": "blob", "size": 17871432},
            {"path": "models/office/Duplex_Plumbing_20121113.ifc", "type": "blob", "size": 31556138},
            {"path": "models/office/GVA_Administrativo.ifc", "type": "blob", "size": 7213289},
            {"path": "models/office/IFC_Schependomlaan.ifc", "type": "blob", "size": 49286967},
            {"path": "models/office/Molio_with_URIs.ifc", "type": "blob", "size": 73945142},
            {"path": "models/office/wbdg_office_arc.ifc", "type": "blob", "size": 4099293},
            {"path": "models/office/wbdg_office_mep.ifc", "type": "blob", "size": 41894594},
            {"path": "models/office/wbdg_office_str.ifc", "type": "blob", "size": 11067475},
            {"path": "models/schemas/west_riverside_hospital_mech_ifc2x3.ifc", "type": "blob", "size": 78764170},
            {"path": "models/schemas/west_riverside_hospital_plumb_ifc2x3.ifc", "type": "blob", "size": 24998920},
        ]

    def attach_models_to_project(
        self,
        project_id: int,
        repo_id: int,
        file_paths: list[str],
        primary_index: int = 0,
    ) -> list[dict[str, Any]]:
        """Attach one or more IFC models from a GitHub repository to an existing project.

        Each file is attached by pointing a ``project_ifc_files`` row directly
        at the repository's raw-content URL -- ``ObjectStorage.materialize_local_path``
        already downloads and caches ``http(s)://`` references, so there is no
        need to fetch the bytes here and re-upload them into BIM-Guard's own
        storage first.

        Args:
            project_id: Project the models attach to. The caller is
                responsible for having authorized access to it.
            repo_id: Registered GitHub repository the files live in.
            file_paths: Relative paths within the repository, e.g.
                ``"models/hospital/Clinic_Architectural.ifc"``.
            primary_index: Index into ``file_paths`` naming the model to
                attach as primary; the rest attach as context models.

        Returns:
            The attached ``project_ifc_files`` rows, in ``file_paths`` order.

        Raises:
            RuntimeError: if this service was built without a ``ProjectsService``.
            ValueError: if the repository does not exist, or if
                ``primary_index`` falls outside ``file_paths``.
        """
        if not self._projects_service:
            raise RuntimeError("ProjectsService is not attached to GitHubRepoService.")

        repo = self.get_repo(repo_id)
        if not repo:
            raise ValueError(f"GitHub Repository with ID {repo_id} not found.")
        if not 0 <= primary_index < len(file_paths):
            raise ValueError(
                f"primary_index {primary_index} is outside the {len(file_paths)} file(s) given."
            )

        owner = repo["owner"]
        repo_name = repo["name"]
        branch = repo.get("branch") or "main"

        attached: list[dict[str, Any]] = []
        for index, file_path in enumerate(file_paths):
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo_name}/{branch}/{file_path}"
            row = self._projects_service.add_ifc_file(
                project_id,
                file_path=raw_url,
                file_name=Path(file_path).name,
                role="primary" if index == primary_index else "context",
                is_primary=index == primary_index,
            )
            attached.append(row)

        return attached
