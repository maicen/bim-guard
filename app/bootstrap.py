"""Application bootstrap module for centralized engine and repository composition.

Adheres to the Dependency Inversion Principle (DIP):
Constructs and wires all persistence adapters, object storage, and physics engines
into high-level domain services, replacing ad-hoc internal instantiation across
the codebase.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.logging_config import get_logger
from app.modules.module1_doc_parser.engines.docling_driver import (
    DoclingHostedDriver,
    DoclingLocalDriver,
)
from app.modules.module1_doc_parser.engines.unstructured_driver import (
    UnstructuredHostedDriver,
    UnstructuredLocalDriver,
)
from app.modules.module4_comparator.engine_registry import (
    RuleEngineRegistry,
    register_default_engines,
)
from app.services.arch_analysis_service import ArchAnalysisService
from app.services.db_adapters import DatabaseAdapter
from app.services.digital_inspector_service import DigitalInspectorService
from app.services.documents_service import DocumentService
from app.services.github_repo_service import GitHubRepoService
from app.services.model_lineage import SupabaseModelLineageRepository
from app.services.naming_config_service import (
    _SCHEMA as _NAMING_CONFIG_SCHEMA,
)
from app.services.naming_config_service import (
    NamingConfigService,
)
from app.services.object_storage import ObjectStorage
from app.services.parsing_engine_instances_service import ParsingEngineInstancesService
from app.services.persistence import PersistenceService
from app.services.phase6_service import Phase6Service
from app.services.pipeline_services import AnalysisService
from app.services.projects_service import ProjectsService
from app.services.rules_service import (
    _FOLDER_COLUMNS,
    _META_COLUMNS,
    _RICH_COLUMNS,
    RuleService,
)
from app.services.settings_service import SettingsService
from app.services.static_data_service import (
    _SETTINGS_SCHEMA,
    _STATIC_ASSET_SCHEMA,
    StaticDataService,
)

logger = get_logger(__name__)


@dataclass
class ApplicationContainer:
    """Central dependency container holding wired services and repositories."""

    storage: ObjectStorage
    projects_repo: DatabaseAdapter
    standards_repo: DatabaseAdapter
    client_documents_repo: DatabaseAdapter
    documents_repo: DatabaseAdapter
    rules_repo: DatabaseAdapter
    folders_repo: DatabaseAdapter
    lineage_repo: DatabaseAdapter
    assets_repo: DatabaseAdapter
    settings_repo: DatabaseAdapter
    github_repos_repo: DatabaseAdapter
    naming_config_repo: DatabaseAdapter
    parsing_engine_instances_repo: DatabaseAdapter
    lineage: SupabaseModelLineageRepository
    static_data_service: StaticDataService
    projects_service: ProjectsService
    rules_service: RuleService
    documents_service: DocumentService
    settings_service: SettingsService
    github_repo_service: GitHubRepoService
    naming_config_service: NamingConfigService
    parsing_engine_instances_service: ParsingEngineInstancesService
    analysis_service: AnalysisService
    phase6_service: Phase6Service
    arch_analysis_service: ArchAnalysisService
    digital_inspector_service: DigitalInspectorService
    engine_registry: RuleEngineRegistry = field(default_factory=RuleEngineRegistry)


_container: ApplicationContainer | None = None


def build_default_container() -> ApplicationContainer:
    """Compose default infrastructure repositories, engines, and domain services."""
    logger.info("Initializing ApplicationContainer with default repositories and engines")

    # 1. Object storage
    storage = ObjectStorage()

    # 2. Persistence repositories
    projects_repo = PersistenceService.get_table(
        "projects",
        {
            "id": int,
            "name": str,
            "description": str,
            "status": str,
            "country": str,
            "analysis_type": str,
            "ifc_file_path": str,
            "ifc_md5_hash": str,
            "created_at": str,
            "updated_at": str,
        },
        required_columns={"ifc_file_path": str, "ifc_md5_hash": str},
    )

    standards_repo = PersistenceService.get_table(
        "standards_by_project",
        {
            "id": int,
            "project_id": int,
            "standard_id": str,
            "source": str,
            "file_path": str,
            "created_at": str,
            "updated_at": str,
        },
    )

    client_documents_repo = PersistenceService.get_table(
        "client_documents",
        {
            "id": int,
            "project_id": int,
            "filename": str,
            "file_path": str,
            "file_type": str,
            "category": str,
            "description": str,
            "tags": str,
            "upload_date": str,
            "updated_at": str,
        },
    )

    documents_repo = PersistenceService.get_table(
        "documents",
        {
            "id": int,
            "md5_hash": str,
            "filename": str,
            "file_path": str,
            "extracted_text": str,
            "upload_date": str,
        },
    )

    all_rule_columns = {**_RICH_COLUMNS, **_META_COLUMNS}
    rules_repo = PersistenceService.get_table(
        "rules",
        {
            "id": int,
            "reference": str,
            "rule_type": str,
            "description": str,
            "target_ifc_class": str,
            "parameters": str,
            "created_at": str,
            "updated_at": str,
        },
        required_columns=all_rule_columns,
    )

    folders_repo = PersistenceService.get_table(
        "rule_folders",
        _FOLDER_COLUMNS,
    )

    lineage_repo = PersistenceService.get_table(
        "model_enhancement_lineage",
        {
            "id": int,
            "project_id": int,
            "source_reference": str,
            "source_sha256": str,
            "source_version": int,
            "output_reference": str,
            "version": int,
            "summary": dict,
            "created_at": str,
        },
    )

    assets_repo = PersistenceService.get_table(
        "static_data_assets",
        _STATIC_ASSET_SCHEMA,
    )

    settings_repo = PersistenceService.get_table(
        "app_settings",
        _SETTINGS_SCHEMA,
        pk="key",
    )

    github_repos_repo = PersistenceService.get_table(
        "github_repositories",
        {
            "id": int,
            "name": str,
            "owner": str,
            "url": str,
            "branch": str,
            "description": str,
            "is_active": bool,
            "created_at": str,
            "updated_at": str,
        },
    )

    naming_config_repo = PersistenceService.get_table(
        "project_naming_config",
        _NAMING_CONFIG_SCHEMA,
    )

    parsing_engine_instances_repo = PersistenceService.get_table(
        "parsing_engine_instances",
        {
            "id": int,
            "name": str,
            "kind": str,
            "api_url": str,
            "api_key": str,
            "strategy": str,
            "is_default": bool,
            "is_enabled": bool,
            "notes": str,
            "created_at": str,
            "updated_at": str,
        },
    )

    # 3. Model Lineage & Static Data
    lineage = SupabaseModelLineageRepository(lineage_repo=lineage_repo)
    static_data_service = StaticDataService(
        assets_repo=assets_repo,
        settings_repo=settings_repo,
    )

    # 4. Domain Services
    projects_service = ProjectsService(
        projects_repo=projects_repo,
        standards_repo=standards_repo,
        client_documents_repo=client_documents_repo,
        storage=storage,
        lineage=lineage,
    )

    rules_service = RuleService(
        rules_repo=rules_repo,
        folders_repo=folders_repo,
    )

    documents_service = DocumentService(
        documents_repo=documents_repo,
        storage=storage,
    )

    settings_service = SettingsService(
        static_data_service=static_data_service,
    )

    github_repo_service = GitHubRepoService(
        github_repos_repo=github_repos_repo,
        projects_service=projects_service,
    )

    # Seed default repo if database is empty
    try:
        if not github_repo_service.list_repos():
            github_repo_service.create_repo(
                url="https://github.com/maicen/bimguard-test-models",
                name="bimguard-test-models",
                branch="main",
                description="Official BIM-Guard test models repository containing architectural, structural, HVAC, electrical, and plumbing IFC models.",
            )
    except Exception:
        logger.warning("Could not seed default GitHub repository; continuing startup", exc_info=True)

    naming_config_service = NamingConfigService(
        naming_repo=naming_config_repo,
    )

    parsing_engine_instances_service = ParsingEngineInstancesService(
        instances_repo=parsing_engine_instances_repo,
    )

    # Seed the registry from legacy env vars on first boot, so existing
    # UNSTRUCTURED_API_KEY / UNSTRUCTURED_LOCAL_URL / DOCLING_* deployments
    # keep working without manual setup. Each named instance is seeded
    # independently (checked by name, not "table is empty") so a later env
    # var — e.g. DOCLING_API_KEY added after the Unstructured instances were
    # already seeded on a prior boot — still gets picked up. Once seeded, an
    # instance's fields are the database's to own; these env vars are only
    # ever consulted to create a missing row, never to update an existing one.
    try:
        from app.modules.config import (
            DOCLING_API_KEY,
            DOCLING_LOCAL_URL,
            DOCLING_SERVICE_URL,
            UNSTRUCTURED_API_KEY,
            UNSTRUCTURED_API_URL,
            UNSTRUCTURED_LOCAL_URL,
            UNSTRUCTURED_STRATEGY,
        )

        has_default = any(
            row.get("is_default") for row in parsing_engine_instances_service.list_instances()
        )

        def _seed_if_missing(name: str, **kwargs) -> None:
            nonlocal has_default
            if parsing_engine_instances_service.get_by_name(name):
                return
            parsing_engine_instances_service.create_instance(
                name=name, is_default=not has_default, **kwargs
            )
            has_default = True

        if UNSTRUCTURED_LOCAL_URL:
            _seed_if_missing(
                "local",
                kind=UnstructuredLocalDriver.kind,
                api_url=UNSTRUCTURED_LOCAL_URL,
                strategy=UNSTRUCTURED_STRATEGY,
                notes="Self-hosted Unstructured Docker container (seeded from UNSTRUCTURED_LOCAL_URL).",
            )
        if UNSTRUCTURED_API_KEY:
            _seed_if_missing(
                "hosted-default",
                kind=UnstructuredHostedDriver.kind,
                api_url=UNSTRUCTURED_API_URL or "https://api.unstructuredapp.io",
                api_key=UNSTRUCTURED_API_KEY,
                strategy=UNSTRUCTURED_STRATEGY,
                notes="Unstructured Platform API (seeded from UNSTRUCTURED_API_KEY).",
            )
        if DOCLING_SERVICE_URL and DOCLING_API_KEY:
            _seed_if_missing(
                "docling-hosted",
                kind=DoclingHostedDriver.kind,
                api_url=DOCLING_SERVICE_URL,
                api_key=DOCLING_API_KEY,
                notes="Hosted Docling Serve instance (seeded from DOCLING_SERVICE_URL/DOCLING_API_KEY).",
            )
        if DOCLING_LOCAL_URL:
            _seed_if_missing(
                "docling-local",
                kind=DoclingLocalDriver.kind,
                api_url=DOCLING_LOCAL_URL,
                notes="Self-hosted docling-serve Docker container (seeded from DOCLING_LOCAL_URL).",
            )
    except Exception:
        logger.warning(
            "Could not seed default parsing engine instances; continuing startup", exc_info=True
        )

    analysis_service = AnalysisService()
    phase6_service = Phase6Service()

    # 5. Physics & Architectural Engines & Registry
    registry = RuleEngineRegistry()
    register_default_engines(registry)

    arch_analysis_service = ArchAnalysisService(
        projects_service=projects_service,
        rules_service=rules_service,
        documents_service=documents_service,
        engine_registry=registry,
    )

    digital_inspector_service = DigitalInspectorService()

    return ApplicationContainer(
        storage=storage,
        projects_repo=projects_repo,
        standards_repo=standards_repo,
        client_documents_repo=client_documents_repo,
        documents_repo=documents_repo,
        rules_repo=rules_repo,
        folders_repo=folders_repo,
        lineage_repo=lineage_repo,
        assets_repo=assets_repo,
        settings_repo=settings_repo,
        github_repos_repo=github_repos_repo,
        naming_config_repo=naming_config_repo,
        parsing_engine_instances_repo=parsing_engine_instances_repo,
        lineage=lineage,
        static_data_service=static_data_service,
        projects_service=projects_service,
        rules_service=rules_service,
        documents_service=documents_service,
        settings_service=settings_service,
        github_repo_service=github_repo_service,
        naming_config_service=naming_config_service,
        parsing_engine_instances_service=parsing_engine_instances_service,
        analysis_service=analysis_service,
        phase6_service=phase6_service,
        arch_analysis_service=arch_analysis_service,
        digital_inspector_service=digital_inspector_service,
        engine_registry=registry,
    )



def get_container() -> ApplicationContainer:
    """Return the global singleton ApplicationContainer, initializing if necessary."""
    global _container
    if _container is None:
        _container = build_default_container()
    return _container


def set_container(container: ApplicationContainer) -> None:
    """Explicitly override the global application container (e.g. for testing)."""
    global _container
    _container = container


def reset_container() -> None:
    """Reset the global container singleton so the next call rebuilds defaults."""
    global _container
    _container = None
