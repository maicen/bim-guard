"""Tests for Architectural Analysis Engine: Dependency Inversion, RuleEvaluator Contracts, and DB-Driven Rules."""

from __future__ import annotations

from typing import Any

import pytest

from app.bootstrap import get_container, reset_container
from app.engines.bimguard_arch_engine import EgressAnalysisEngine, SpatialDaylightEngine
from app.modules.contracts import RuleEvaluationResult
from app.modules.module2_ifc_read.ifc_egress import (
    check_egress_travel_distance,
    check_exit_count,
)
from app.modules.module2_ifc_read.ifc_spatial import (
    check_daylight_ratios,
    check_fire_separation,
)
from app.modules.module4_comparator.engine_registry import (
    RuleEngineRegistry,
    RuleEvaluator,
    register_default_engines,
)

pytestmark = pytest.mark.slow
from app.services.arch_analysis_service import ArchAnalysisService
from app.services.db_adapters import DatabaseAdapter
from app.services.rules_service import RuleService
from app.services.ruleset_seeder import seed_architectural_code_rules


class MockTableAdapter(DatabaseAdapter):
    """In-memory table adapter for test isolation."""

    def __init__(self, initial_rows: list[dict[str, Any]] | None = None) -> None:
        self._rows: list[dict[str, Any]] = [dict(r) for r in (initial_rows or [])]

    @property
    def columns_dict(self) -> dict[str, Any]:
        return {"id": int, "reference": str}

    @property
    def rows(self):
        return list(self._rows)

    def get(self, pk_value: Any) -> dict[str, Any] | None:
        for r in self._rows:
            if r.get("id") == pk_value or r.get("reference") == pk_value:
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
            if r.get("id") == pk_values:
                r.update(updates)

    def delete(self, pk_value: Any) -> None:
        self._rows = [r for r in self._rows if r.get("id") != pk_value]

    def rows_where(self, where_sql: str = "", params: list[Any] | None = None) -> list[dict[str, Any]]:
        return list(self._rows)


def test_seed_architectural_code_rules():
    """Verify that hardcoded architectural rules are seeded into the database table."""
    mock_rules = MockTableAdapter()
    mock_folders = MockTableAdapter()
    rules_svc = RuleService(rules_repo=mock_rules, folders_repo=mock_folders)

    count = seed_architectural_code_rules(rules_svc)
    assert count == 14

    refs = {r["reference"] for r in rules_svc.list_rules()}
    assert "CODE 9.9.10.1" in refs
    assert "CODE 9.9.4.1" in refs
    assert "CODE 9.7.2.3" in refs
    assert "CODE 9.10.9.14.PW" in refs
    assert "BIMGUARD-WIN.FireRating" in refs
    assert "BIMGUARD-WIN.AcousticRating" in refs
    assert "BIMGUARD-WIN.SecurityRating" in refs
    assert "BIMGUARD-WIN.ThermalTransmittance" in refs
    assert "BIMGUARD-WIN.Infiltration" in refs
    assert "BIMGUARD-WIN.IsExternal" in refs
    assert "BIMGUARD-WIN.HandicapAccessible" in refs
    assert "BIMGUARD-WIN.FireExit" in refs
    assert "BIMGUARD-WIN.SelfClosing" in refs
    assert "BIMGUARD-WIN.SmokeStop" in refs

    # Verify idempotency
    count_second_run = seed_architectural_code_rules(rules_svc)
    assert count_second_run == 0


def test_egress_analysis_engine_implements_rule_evaluator():
    """Verify EgressAnalysisEngine conforms to RuleEvaluator protocol and handles records."""
    engine = EgressAnalysisEngine()
    assert isinstance(engine, RuleEvaluator)
    assert engine.rule_type == "ARCH-EGRESS-001"

    # Compliant travel distance
    res_pass = engine.evaluate({
        "space_guid": "SP-001",
        "space_name": "Living Room",
        "storey_name": "Level 1",
        "travel_distance_m": 18.5,
        "nearest_exit": "Front Door",
        "no_path": False,
    })
    assert isinstance(res_pass, RuleEvaluationResult)
    assert res_pass.status == "PASS"
    assert res_pass.band == "Low"
    assert res_pass.details["travel_distance_m"] == 18.5
    assert res_pass.element_id == "SP-001"

    # Non-compliant travel distance
    res_fail = engine.evaluate({
        "space_guid": "SP-002",
        "space_name": "Rear Bedroom",
        "storey_name": "Level 2",
        "travel_distance_m": 32.0,
        "nearest_exit": "Main Stair",
        "no_path": False,
    })
    assert res_fail.status == "FAIL"
    assert res_fail.band == "High"
    assert res_fail.details["travel_distance_m"] == 32.0

    # No path to exit
    res_no_path = engine.evaluate({
        "space_guid": "SP-003",
        "space_name": "Isolated Storage",
        "storey_name": "Basement",
        "travel_distance_m": None,
        "no_path": True,
    })
    assert res_no_path.status == "FAIL"
    assert res_no_path.band == "Critical"

    # Exit count check
    res_exit_pass = engine.evaluate({
        "guid": "STOREY-1",
        "storey_name": "Ground Floor",
        "exit_count": 2,
    })
    assert res_exit_pass.status == "PASS"
    assert res_exit_pass.band == "Low"

    res_exit_fail = engine.evaluate({
        "guid": "STOREY-2",
        "storey_name": "Second Floor",
        "exit_count": 0,
    })
    assert res_exit_fail.status == "FAIL"
    assert res_exit_fail.band == "High"


def test_spatial_daylight_engine_implements_rule_evaluator():
    """Verify SpatialDaylightEngine conforms to RuleEvaluator protocol and handles records."""
    engine = SpatialDaylightEngine()
    assert isinstance(engine, RuleEvaluator)
    assert engine.rule_type == "ARCH-SPATIAL-001"

    # Compliant daylight (ratio 0.15 >= 0.10)
    res_daylight_pass = engine.evaluate({
        "space_guid": "SP-10",
        "space_name": "Master Bedroom",
        "floor_area_m2": 20.0,
        "total_window_area_m2": 3.0,
    })
    assert isinstance(res_daylight_pass, RuleEvaluationResult)
    assert res_daylight_pass.status == "PASS"
    assert res_daylight_pass.band == "Low"
    assert res_daylight_pass.details["daylight_ratio"] == 0.15

    # Non-compliant daylight (ratio 0.05 < 0.10)
    res_daylight_fail = engine.evaluate({
        "space_guid": "SP-11",
        "space_name": "Guest Room",
        "floor_area_m2": 20.0,
        "total_window_area_m2": 1.0,
    })
    assert res_daylight_fail.status == "FAIL"
    assert res_daylight_fail.band == "Medium"

    # Party wall fire rating check: Pass
    res_fire_pass = engine.evaluate({
        "wall_guid": "WALL-001",
        "wall_name": "Demising Wall A",
        "adjacent_spaces": ["Unit 1", "Unit 2"],
        "fire_rating_min": 60.0,
        "missing_rating": False,
    })
    assert res_fire_pass.status == "PASS"
    assert res_fire_pass.band == "Low"

    # Party wall fire rating check: Fail
    res_fire_fail = engine.evaluate({
        "wall_guid": "WALL-002",
        "wall_name": "Demising Wall B",
        "adjacent_spaces": ["Unit 1", "Corridor"],
        "fire_rating_min": 30.0,
        "missing_rating": False,
    })
    assert res_fire_fail.status == "FAIL"
    assert res_fire_fail.band == "High"

    # Party wall fire rating check: Missing
    res_fire_missing = engine.evaluate({
        "wall_guid": "WALL-003",
        "wall_name": "Demising Wall C",
        "adjacent_spaces": ["Unit 2", "Corridor"],
        "fire_rating_min": None,
        "missing_rating": True,
    })
    assert res_fire_missing.status == "FAIL"
    assert res_fire_missing.band == "High"


def test_registry_registers_architectural_engines():
    """Verify architectural engines are registered in default RuleEngineRegistry."""
    registry = RuleEngineRegistry()
    register_default_engines(registry)

    assert registry.supports("ARCH-EGRESS-001")
    assert registry.supports("ARCH-SPATIAL-001")
    assert isinstance(registry.get("ARCH-EGRESS-001"), EgressAnalysisEngine)
    assert isinstance(registry.get("ARCH-SPATIAL-001"), SpatialDaylightEngine)


def test_dynamic_threshold_override_in_functions():
    """Verify functions accept and use overridden dynamic thresholds."""
    # check_exit_count with custom required_min
    result_exits = check_exit_count(None, min_exits=2)
    assert result_exits["total_exterior_doors"] == 0

    class DummyGraph:
        graph = None

    # check_egress_travel_distance with custom max_distance_m
    result_travel = check_egress_travel_distance(DummyGraph(), max_distance_m=30.0)
    assert result_travel == []

    class DummyAdjacency:
        has_boundaries = False

    # check_daylight_ratios with custom min_ratio
    result_daylight = check_daylight_ratios(DummyAdjacency(), min_ratio=0.12)
    assert result_daylight == []

    # check_fire_separation with custom min_rating_min
    result_fire = check_fire_separation(DummyAdjacency(), min_rating_min=60.0)
    assert result_fire == []


def test_arch_analysis_service_dependency_injection():
    """Verify ArchAnalysisService accepts injected dependencies and can be resolved."""
    mock_rules = MockTableAdapter()
    mock_folders = MockTableAdapter()
    rules_svc = RuleService(rules_repo=mock_rules, folders_repo=mock_folders)

    service = ArchAnalysisService(rules_service=rules_svc)
    assert service._rules is rules_svc

    # Verify ApplicationContainer exposes arch_analysis_service
    reset_container()
    container = get_container()
    assert hasattr(container, "arch_analysis_service")
    assert isinstance(container.arch_analysis_service, ArchAnalysisService)

    # Verify FastAPI dependency resolution
    from app.api.dependencies import get_arch_analysis_service

    assert get_arch_analysis_service() is container.arch_analysis_service
