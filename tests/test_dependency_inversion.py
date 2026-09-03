"""Tests for Priority 2: Dependency Inversion.

Validates:
1. Typed RuleEvaluationRequest and RuleEvaluationResult models.
2. Direct RuleEvaluator implementation on GalvanicCorrosionEngine, CreviceCorrosionEngine, and MICEngine.
3. RuleEngineRegistry direct registration (without CallableRuleEvaluator).
4. Repository and storage dependency injection across all services.
5. ApplicationContainer bootstrap and composition.
"""

from __future__ import annotations

from typing import Any

from app.bootstrap import (
    ApplicationContainer,
    build_default_container,
    get_container,
    reset_container,
    set_container,
)
from app.engines.bimguard_corrosion_engine import GalvanicCorrosionEngine
from app.engines.bimguard_crevice_engine import CreviceCorrosionEngine
from app.engines.bimguard_mic_engine import MICEngine
from app.modules.contracts import RuleEvaluationRequest, RuleEvaluationResult
from app.modules.comparator.engine_registry import (
    CallableRuleEvaluator,
    RuleEngineRegistry,
    RuleEvaluator,
    register_default_engines,
)
from app.services.db_adapters import DatabaseAdapter
from app.services.documents_service import DocumentService
from app.services.model_lineage import SupabaseModelLineageRepository
from app.services.projects_service import ProjectsService
from app.services.rules_service import RuleService
from app.services.settings_service import SettingsService
from app.services.static_data_service import StaticDataService


class MockTableAdapter(DatabaseAdapter):
    """In-memory mock adapter for repository dependency injection testing."""

    def __init__(self, initial_rows: list[dict[str, Any]] | None = None) -> None:
        self._rows: list[dict[str, Any]] = [dict(r) for r in (initial_rows or [])]

    @property
    def columns_dict(self) -> dict[str, Any]:
        return {"id": int, "name": str}

    @property
    def rows(self):
        return list(self._rows)

    def get(self, pk_value: Any) -> dict[str, Any] | None:
        for r in self._rows:
            if r.get("id") == pk_value or r.get("key") == pk_value:
                return dict(r)
        return None

    def insert(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = dict(payload)
        if "id" not in row:
            row["id"] = len(self._rows) + 1
        self._rows.append(row)
        return row

    def update(self, *, updates: dict[str, Any], pk_values: Any) -> None:
        for r in self._rows:
            if r.get("id") == pk_values or r.get("key") == pk_values:
                r.update(updates)

    def delete(self, pk_value: Any) -> None:
        self._rows = [r for r in self._rows if r.get("id") != pk_value and r.get("key") != pk_value]

    def rows_where(self, where_sql: str = "", params: list[Any] | None = None) -> list[dict[str, Any]]:
        return list(self._rows)


class MockStorage:
    """Mock storage adapter for dependency injection testing."""

    def __init__(self) -> None:
        self.saved: dict[str, bytes] = {}

    def save_upload(self, filename: str, content: bytes, subdir: str) -> str:
        key = f"{subdir}/{filename}"
        self.saved[key] = content
        return f"mock://{key}"

    def materialize_local_path(self, reference: str):
        return None


def test_rule_evaluation_contracts_typed_and_dict_compatible():
    """Verify RuleEvaluationResult supports typed attributes and dict compatibility."""
    result = RuleEvaluationResult(
        rule_type="GC-001",
        band="Medium",
        score=0.55,
        details={"voltage_gap_V": 0.45},
        status="PASS",
        element_id="E-123",
    )

    # Typed attribute access
    assert result.rule_type == "GC-001"
    assert result.band == "Medium"
    assert result.score == 0.55
    assert result.details["voltage_gap_V"] == 0.45
    assert result.element_id == "E-123"

    # Dict-like access for backwards compatibility
    assert result["band"] == "Medium"
    assert result["score"] == 0.55
    assert result.get("band") == "Medium"
    assert result.get("unknown", "default") == "default"
    assert "band" in result
    assert "score" in result

    # Dict equality
    assert result == {"band": "Medium", "score": 0.55}

    # Serialization
    d = result.to_dict()
    assert d["rule_type"] == "GC-001"
    assert d["band"] == "Medium"

    # Typed request
    req = RuleEvaluationRequest(
        rule_type="GC-001",
        element={"material": "carbon_steel"},
        metadata={"run_id": "test"},
    )
    assert req.rule_type == "GC-001"
    assert req.element["material"] == "carbon_steel"


def test_physics_engines_implement_rule_evaluator_directly():
    """Verify each physics engine satisfies RuleEvaluator protocol directly."""
    galvanic = GalvanicCorrosionEngine()
    crevice = CreviceCorrosionEngine()
    mic = MICEngine()

    assert isinstance(galvanic, RuleEvaluator)
    assert isinstance(crevice, RuleEvaluator)
    assert isinstance(mic, RuleEvaluator)

    assert galvanic.rule_type == "GC-001"
    assert crevice.rule_type == "CC-001"
    assert mic.rule_type == "MC-001"

    # Test galvanic evaluate directly returns RuleEvaluationResult
    g_res = galvanic.evaluate({"material": "copper", "paired_material": "carbon_steel", "guid": "P-1"})
    assert isinstance(g_res, RuleEvaluationResult)
    assert g_res.rule_type == "GC-001"
    assert g_res.band in ("Low", "Medium", "High", "Critical")
    assert "voltage_gap_V" in g_res.details

    # Test crevice evaluate directly returns RuleEvaluationResult
    c_res = crevice.evaluate({"material": "stainless_steel", "joint_description": "flanged", "guid": "P-2"})
    assert isinstance(c_res, RuleEvaluationResult)
    assert c_res.rule_type == "CC-001"
    assert "crevice_geometry" in c_res.details

    # Test mic evaluate directly returns RuleEvaluationResult
    m_res = mic.evaluate({"material": "carbon_steel", "guid": "P-3", "nominal_diameter_m": 0.1})
    assert isinstance(m_res, RuleEvaluationResult)
    assert m_res.rule_type == "MC-001"
    assert "flow_class" in m_res.details


def test_registry_registers_engines_without_callable_adapters():
    """Verify registered default engines are direct instances, not CallableRuleEvaluator adapters."""
    registry = RuleEngineRegistry()
    register_default_engines(registry)

    for rule_code in ["GC-001", "CC-001", "MC-001"]:
        evaluator = registry.get(rule_code)
        assert not isinstance(evaluator, CallableRuleEvaluator)
        assert hasattr(evaluator, "evaluate")
        assert evaluator.rule_type == rule_code


def test_projects_service_repository_injection():
    """Verify ProjectsService accepts injected repositories without instantiating Supabase."""
    mock_projects = MockTableAdapter([{"id": 1, "name": "Injected Project", "status": "Draft"}])
    mock_standards = MockTableAdapter()
    mock_client_docs = MockTableAdapter()
    mock_storage = MockStorage()

    svc = ProjectsService(
        projects_repo=mock_projects,
        standards_repo=mock_standards,
        client_documents_repo=mock_client_docs,
        storage=mock_storage,
    )

    projects = svc.list_projects()
    assert len(projects) == 1
    assert projects[0]["name"] == "Injected Project"

    # Create project through injected repository
    new_proj = svc.create_project(
        name="Project 2",
        description="Test",
        country="US",
        analysis_type="Architecture",
    )
    assert new_proj["id"] == 2
    assert len(svc.list_projects()) == 2


def test_documents_service_repository_injection():
    """Verify DocumentService accepts injected repositories without instantiating Supabase."""
    mock_docs = MockTableAdapter([{"id": 10, "filename": "spec.pdf", "extracted_text": "text"}])
    mock_storage = MockStorage()

    svc = DocumentService(
        documents_repo=mock_docs,
        storage=mock_storage,
    )

    docs = svc.list_documents()
    assert len(docs) == 1
    assert docs[0]["filename"] == "spec.pdf"


def test_rules_service_repository_injection():
    """Verify RuleService accepts injected rules and folders repositories."""
    mock_rules = MockTableAdapter([
        {"id": 1, "reference": "R-1", "rule_type": "FIRE", "ruleset_id": "DEFAULT"}
    ])
    mock_folders = MockTableAdapter([
        {"id": 1, "ruleset_id": "DEFAULT", "display_name": "Default Rules"}
    ])

    svc = RuleService(
        rules_repo=mock_rules,
        folders_repo=mock_folders,
    )

    rules = svc.list_rules()
    assert len(rules) == 1
    assert rules[0]["reference"] == "R-1"


def test_lineage_repository_injection():
    """Verify SupabaseModelLineageRepository accepts injected lineage repository."""
    mock_lineage = MockTableAdapter()
    repo = SupabaseModelLineageRepository(lineage_repo=mock_lineage)

    res = repo.record(
        project_id=1,
        source_reference="sb://test/orig.ifc",
        source_sha256="abc123hash",
        source_version=1,
        output_reference="sb://test/out_v2.ifc",
        version=2,
        summary={"changes": 3},
    )
    assert res["project_id"] == 1
    assert res["version"] == 2
    assert len(mock_lineage.rows) == 1


def test_settings_service_injection():
    """Verify SettingsService accepts injected StaticDataService."""
    mock_assets = MockTableAdapter()
    mock_settings = MockTableAdapter([
        {"key": "BIM_GUARD_LOG_LEVEL", "value": "DEBUG", "scope": "runtime", "is_secret": 0}
    ])
    static_svc = StaticDataService(assets_repo=mock_assets, settings_repo=mock_settings)
    settings_svc = SettingsService(static_data_service=static_svc)

    val = settings_svc.get("BIM_GUARD_LOG_LEVEL")
    assert val == "DEBUG"


def test_application_container_bootstrap():
    """Verify ApplicationContainer wires all dependencies and engines."""
    reset_container()
    container = get_container()
    assert isinstance(container, ApplicationContainer)
    assert container.projects_service is not None
    assert container.rules_service is not None
    assert container.documents_service is not None
    assert container.settings_service is not None
    assert container.analysis_service is not None
    assert container.phase6_service is not None

    # Engines are registered in the container registry
    assert container.engine_registry.supports("GC-001")
    assert container.engine_registry.supports("CC-001")
    assert container.engine_registry.supports("MC-001")

    # FastAPI dependencies resolve from the container
    from app.api.dependencies import (
        get_analysis_service,
        get_documents_service,
        get_phase6_service,
        get_projects_service,
        get_rules_service,
        get_settings_service,
    )

    assert get_projects_service() is container.projects_service
    assert get_rules_service() is container.rules_service
    assert get_documents_service() is container.documents_service
    assert get_settings_service() is container.settings_service
    assert get_analysis_service() is container.analysis_service
    assert get_phase6_service() is container.phase6_service

    # Verify build_default_container creates a fresh container
    fresh = build_default_container()
    assert isinstance(fresh, ApplicationContainer)

    # Verify set_container overrides the active container
    set_container(fresh)
    assert get_container() is fresh
    reset_container()
