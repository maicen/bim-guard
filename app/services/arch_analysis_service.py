"""Service encapsulating architectural compliance analysis workflows.

Adheres to Dependency Inversion: receives projects, rules, documents, and reporting
services via constructor injection instead of creating them internally.
"""

from __future__ import annotations

from app.logging_config import get_logger
from app.modules.comparator.engine_registry import (
    DEFAULT_ENGINE_REGISTRY,
    RuleEngineRegistry,
)
from app.modules.contracts import ArchAnalysisResponse
from app.services.documents_service import DocumentService
from app.services.projects_service import ProjectsService
from app.services.report_artifacts import ReportArtifactService
from app.services.rules_service import RuleService
from app.services.ruleset_access_service import RulesetAccessService

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
        ruleset_access_service: RulesetAccessService | None = None,
    ) -> None:
        """Initialize architectural analysis service with explicit dependencies."""
        self._projects = projects_service if projects_service is not None else ProjectsService()
        self._rules = rules_service if rules_service is not None else RuleService()
        self._documents = documents_service if documents_service is not None else DocumentService()
        self._report_svc = report_service if report_service is not None else ReportArtifactService()
        self._registry = engine_registry if engine_registry is not None else DEFAULT_ENGINE_REGISTRY
        self._ruleset_access = ruleset_access_service

    def _run_orchestrator(self, project_id: int, rule_folder: str) -> dict:
        """Validate ruleset access and run the orchestrator, returning its raw payload.

        Raises:
            ValueError: if *rule_folder* is given but isn't granted to this
                project's organization (see ``RulesetAccessService`` /
                ``organization_ruleset_grants``). Any ruleset the org has
                been granted may be used to test any of its projects --
                per-project "Rule Assignments" (``project_ruleset_bindings``)
                is a curation aid for owners/admins, not a run-time gate, so
                a model can be checked against any granted ruleset without
                first being bound to it. Built-in code rules (an empty
                ``rule_folder``) are unaffected.
        """
        from app.services.pipeline_services import PipelineOrchestratorService

        if rule_folder and self._ruleset_access is not None:
            project = self._projects.get_project(project_id)
            organization_id = (project or {}).get("organization_id")
            granted = self._ruleset_access.list_org_grants(organization_id) if organization_id is not None else []
            if rule_folder not in granted:
                raise ValueError(
                    f"Ruleset {rule_folder!r} is not granted to this project's organization. "
                    "Ask a superadmin to grant it first."
                )

        return PipelineOrchestratorService.orchestrate_workflow(
            project_id=project_id,
            analysis_theme="Architecture",
            rule_folder=rule_folder,
        )

    def resolve_ruleset_name(self, rule_folder: str) -> str:
        """Display-name snapshot for ``rule_folder``, or ``""`` when unscoped."""
        if not rule_folder:
            return ""
        folder = self._rules.get_folder(rule_folder)
        return str((folder or {}).get("display_name") or "")

    def compute_rule_compliance(
        self, project_id: int, rule_folder: str = ""
    ) -> tuple[list[dict], dict]:
        """Return ``(rule_compliance, rule_compliance_summary)`` for a ruleset-scoped run.

        Side-effect free (no BCF persistence) -- unlike :meth:`run_analysis`,
        which unconditionally persists a BCF artifact whenever the run
        produces ``bcf_topics``. Used to build a ruleset-scoped PDF/CSV
        report without ever creating a stray duplicate BCF row as a side
        effect of that unrelated save action.
        """
        raw = self._run_orchestrator(project_id, rule_folder)
        if "error" in raw:
            raise ValueError(raw["error"])
        return raw.get("rule_compliance", []), raw.get("rule_compliance_summary", {})

    def run_analysis(
        self,
        project_id: int,
        rule_folder: str = "",
        *,
        created_by: str | None = None,
        created_by_email: str | None = None,
    ) -> ArchAnalysisResponse:
        """Execute architectural compliance checks for a project and return response model.

        Raises:
            ValueError: if *rule_folder* is given but isn't granted to this
                project's organization -- see :meth:`_run_orchestrator`.
        """
        result = self._run_orchestrator(project_id, rule_folder)

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
                persisted = self._report_svc.persist_bcf(
                    project_id,
                    bcf_topics,
                    rule_folder=rule_folder,
                    ruleset_name=self.resolve_ruleset_name(rule_folder),
                    created_by=created_by,
                    created_by_email=created_by_email,
                )
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
