"""FastAPI service dependency injection providers."""

from __future__ import annotations

from app.services.phase6_service import Phase6Service
from app.services.pipeline_services import AnalysisService
from app.services.projects_service import ProjectsService
from app.services.rules_service import RuleService

_projects_service = ProjectsService()
_rules_service = RuleService()
_phase6_service = Phase6Service()
_analysis_service = AnalysisService()


def get_projects_service() -> ProjectsService:
    """Return the singleton ProjectsService instance."""
    return _projects_service


def get_rules_service() -> RuleService:
    """Return the singleton RuleService instance."""
    return _rules_service


def get_phase6_service() -> Phase6Service:
    """Return the singleton Phase6Service instance."""
    return _phase6_service


def get_analysis_service() -> AnalysisService:
    """Return the singleton AnalysisService instance."""
    return _analysis_service

