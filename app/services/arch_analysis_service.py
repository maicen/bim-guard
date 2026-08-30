"""Service encapsulating architectural compliance analysis workflows.

Adheres to Dependency Inversion: receives projects, rules, documents, and reporting
services via constructor injection instead of creating them internally.
"""

from __future__ import annotations

from app.logging_config import get_logger
from app.modules.contracts import ArchAnalysisResponse
from app.modules.module4_comparator.engine_registry import (
    DEFAULT_ENGINE_REGISTRY,
    RuleEngineRegistry,
)
from app.services.documents_service import DocumentService
from app.services.projects_service import ProjectsService
from app.services.report_artifacts import ReportArtifactService
from app.services.rules_service import RuleService

logger = get_logger(__name__)


class ArchAnalysisService:
    """Encapsulates architectural compliance execution with dependency-injected services."""

    def __init__(
        self,
        *,
        projects_service: ProjectsService | None = None,
        rules_service: RuleService | None = None,
        documents_service: DocumentService | None = None,
        report_service: ReportArtifactService | None = None,
        engine_registry: RuleEngineRegistry | None = None,
    ) -> None:
        """Initialize architectural analysis service with explicit dependencies."""
        self._projects = projects_service if projects_service is not None else ProjectsService()
        self._rules = rules_service if rules_service is not None else RuleService()
        self._documents = documents_service if documents_service is not None else DocumentService()
        self._report_svc = report_service if report_service is not None else ReportArtifactService()
        self._registry = engine_registry if engine_registry is not None else DEFAULT_ENGINE_REGISTRY

    def run_analysis(
        self,
        project_id: int,
        rule_folder: str = "",
    ) -> ArchAnalysisResponse:
        """Execute architectural compliance checks for a project and return response model."""
        from app.services.pipeline_services import PipelineOrchestratorService

        result = PipelineOrchestratorService.orchestrate_workflow(
            project_id=project_id,
            analysis_theme="Architecture",
            rule_folder=rule_folder,
        )

        if "error" in result:
            raise ValueError(result["error"])

        categories = result.get("categories", {})
        # The workflow payload names its findings "audit_issues"; there is no
        # "issues" key, so the old read reported zero findings on every project.
        issues = result.get("audit_issues", [])
        project = result.get("project", {})
        rule_compliance_summary = result.get("rule_compliance_summary", {})
        bcf_topics = result.get("bcf_topics", [])

        bcf_artifact_id = None
        if bcf_topics:
            try:
                persisted = self._report_svc.persist_bcf(project_id, bcf_topics)
                if persisted:
                    bcf_artifact_id = persisted.get("id")
            except Exception:
                logger.exception("BCF persistence failed project_id=%d", project_id)

        if not bcf_artifact_id:
            latest = self._report_svc.latest_bcf(project_id)
            if latest:
                bcf_artifact_id = latest.get("id")

        return ArchAnalysisResponse(
            project_id=project_id,
            project_name=project.get("name", f"Project {project_id}"),
            categories=categories,
            total_issues=len(issues),
            issues=issues,
            summary=result.get("summary", {}),
            rule_compliance_summary=rule_compliance_summary,
            bcf_artifact_id=bcf_artifact_id,
            building_summary=result.get("building_summary", {}),
            spatial_checks=result.get("spatial_checks", {}),
            egress_checks=result.get("egress_checks", {}) or {},
            rule_compliance=result.get("rule_compliance", []),
            rule_folder=result.get("rule_folder", ""),
            ifc_element_count=result.get("ifc_element_count", 0),
        )
