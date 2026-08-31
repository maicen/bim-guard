"""FastAPI service dependency injection providers."""

from __future__ import annotations

from app.bootstrap import get_container
from app.services.arch_analysis_service import ArchAnalysisService
from app.services.documents_service import DocumentService
from app.services.github_repo_service import GitHubRepoService
from app.services.phase6_service import Phase6Service
from app.services.pipeline_services import AnalysisService
from app.services.projects_service import ProjectsService
from app.services.rules_service import RuleService
from app.services.settings_service import SettingsService


def get_projects_service() -> ProjectsService:
    """Return the configured ProjectsService instance."""
    return get_container().projects_service


def get_rules_service() -> RuleService:
    """Return the configured RuleService instance."""
    return get_container().rules_service


def get_phase6_service() -> Phase6Service:
    """Return the configured Phase6Service instance."""
    return get_container().phase6_service


def get_analysis_service() -> AnalysisService:
    """Return the configured AnalysisService instance."""
    return get_container().analysis_service


def get_documents_service() -> DocumentService:
    """Return the configured DocumentService instance."""
    return get_container().documents_service


def get_settings_service() -> SettingsService:
    """Return the configured SettingsService instance."""
    return get_container().settings_service


def get_arch_analysis_service() -> ArchAnalysisService:
    """Return the configured ArchAnalysisService instance."""
    return get_container().arch_analysis_service


def get_github_repo_service() -> GitHubRepoService:
    """Return the configured GitHubRepoService instance."""
    return get_container().github_repo_service



