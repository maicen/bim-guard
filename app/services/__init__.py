"""Service-layer modules for persistence, extraction, and compliance logic.

This is the stable, documented programmatic (Python-import) surface for
BIM-Guard's business logic -- ``from app.services import ProjectsService``
(etc.) is the supported import path for a script or an external project
(e.g. the ``bim-guard-evaluation`` companion project referenced in
CLAUDE.md) that wants project/rule/document/analysis operations without
going through the REST API. Every ``app/api/*.py`` route handler for the
same capability delegates to the identical class listed here, so the two
access modes never diverge in behavior -- see the "Programmatic API"
section of docs/architecture.md.

Submodules not re-exported here are internal implementation detail; import
them directly if needed, but they carry no compatibility guarantee.
"""

from app.services.analysis_runner import RUNNABLE_SLUGS, run_analysis
from app.services.arch_analysis_service import ArchAnalysisService
from app.services.bsdd_client import BSDDClient
from app.services.digital_inspector_service import DigitalInspectorService
from app.services.documents_service import DocumentService
from app.services.github_repo_service import GitHubRepoService
from app.services.membership_service import MembershipService
from app.services.naming_config_service import NamingConfigService
from app.services.parsing_engine_instances_service import ParsingEngineInstancesService
from app.services.profile_service import ProfileService
from app.services.projects_service import ProjectsService
from app.services.report_artifacts import ReportArtifactService
from app.services.rule_extraction_service import RuleExtractionService
from app.services.rules_service import RuleService

__all__ = [
    "run_analysis",
    "RUNNABLE_SLUGS",
    "ArchAnalysisService",
    "BSDDClient",
    "DigitalInspectorService",
    "DocumentService",
    "GitHubRepoService",
    "MembershipService",
    "NamingConfigService",
    "ParsingEngineInstancesService",
    "ProfileService",
    "ProjectsService",
    "ReportArtifactService",
    "RuleExtractionService",
    "RuleService",
]
