"""Tests for the opt-in ARCH-engine side-channel wired into orchestrate_workflow.

Covers `BIMGuard_App._run_arch_engine_compliance` (app.modules.orchestrator),
which re-evaluates the already-computed egress/spatial records through the
registered `EgressAnalysisEngine`/`SpatialDaylightEngine` `RuleEvaluator`s
(previously registered but never invoked from the live pipeline -- see
tests/test_arch_engine_di.py, which only exercises them directly).
"""

from app.modules.orchestrator import BIMGuard_App
from app.services.cache import clear_cache
from app.services.db_adapters import DatabaseAdapter
from app.services.rules_service import RuleService


def _noop_log_progress(*_args, **_kwargs) -> None:
    return None


class _MockTableAdapter(DatabaseAdapter):
    """Minimal in-memory adapter, mirroring tests/test_arch_engine_di.py's."""

    def __init__(self, rows):
        self._rows = [dict(r) for r in rows]

    @property
    def columns_dict(self):
        return {"id": int, "reference": str}

    @property
    def rows(self):
        return list(self._rows)

    def get(self, pk_value):
        for r in self._rows:
            if r.get("id") == pk_value or r.get("reference") == pk_value:
                return dict(r)
        return None

    def insert(self, payload):
        row = dict(payload)
        row.setdefault("id", len(self._rows) + 1)
        self._rows.append(row)
        return row

    def update(self, *, updates, pk_values):
        for r in self._rows:
            if r.get("id") == pk_values:
                r.update(updates)

    def delete(self, pk_value):
        self._rows = [r for r in self._rows if r.get("id") != pk_value]

    def rows_where(self, where_sql="", params=None):
        return list(self._rows)


def _rule_service_with(rows):
    clear_cache()
    return RuleService(rules_repo=_MockTableAdapter(rows), folders_repo=_MockTableAdapter([]))


_EGRESS_CHECKS = {
    "exit_count": {
        "results": [
            {"code_ref": "CODE 9.9.4.1", "storey": "Ground Floor", "exit_count": 0, "required_min": 1, "passes": False},
            {"code_ref": "CODE 9.9.4.1", "storey": "Level 1", "exit_count": 2, "required_min": 1, "passes": True},
        ],
    },
    "travel_distance": [
        {
            "space_guid": "SP-002", "space_name": "Rear Bedroom", "storey_name": "Level 2",
            "travel_distance_m": 32.0, "nearest_exit": "Main Stair", "no_path": False,
        },
        {
            "space_guid": "SP-001", "space_name": "Living Room", "storey_name": "Level 1",
            "travel_distance_m": 18.5, "nearest_exit": "Front Door", "no_path": False,
        },
    ],
}

_SPATIAL_CHECKS = {
    "daylight": [
        {"space_guid": "SP-11", "space_name": "Guest Room", "floor_area_m2": 20.0, "total_window_area_m2": 1.0},
    ],
    "fire_separation": [
        {"wall_guid": "WALL-001", "wall_name": "Demising Wall A", "adjacent_spaces": [], "fire_rating_min": 60.0, "missing_rating": False},
    ],
}


def test_disabled_by_default_returns_empty():
    issues, error = BIMGuard_App._run_arch_engine_compliance(
        enable_arch_engines=False,
        ifc={"egress_checks": _EGRESS_CHECKS, "spatial_checks": _SPATIAL_CHECKS},
        project_id=1,
        log_progress=_noop_log_progress,
    )

    assert issues == []
    assert error is None


def test_enabled_flags_failing_records_only():
    from app.engines.bimguard_arch_engine import EgressAnalysisEngine, SpatialDaylightEngine

    rules_svc = _rule_service_with(
        [
            {"id": 1, "reference": "CODE 9.9.4.1", "check_value": 1},
            {"id": 2, "reference": "CODE 9.9.10.1", "check_value": 25.0},
            {"id": 3, "reference": "CODE 9.7.2.3", "check_value": 0.10, "unit": "ratio"},
            {"id": 4, "reference": "CODE 9.10.9", "check_value": 45.0, "target_ifc_class": "IfcWall"},
        ]
    )

    issues, error = BIMGuard_App._run_arch_engine_compliance(
        enable_arch_engines=True,
        ifc={"egress_checks": _EGRESS_CHECKS, "spatial_checks": _SPATIAL_CHECKS},
        project_id=1,
        log_progress=_noop_log_progress,
        egress_engine=EgressAnalysisEngine(rules_service=rules_svc),
        spatial_engine=SpatialDaylightEngine(rules_service=rules_svc),
    )

    assert error is None
    # 5 records evaluated (2 exit_count + 2 travel_distance + 1 daylight),
    # fire_separation's single record passes (60 >= 45) so contributes none;
    # failing: the zero-exit storey (exit_count records carry no guid/id, so
    # EgressAnalysisEngine.evaluate() falls back to "UNKNOWN" as element_id),
    # SP-002 (travel 32m > 25m), and SP-11 (daylight ratio below 0.10).
    element_ids = {issue["element_id"] for issue in issues}
    assert element_ids == {"UNKNOWN", "SP-002", "SP-11"}
    assert len(issues) == 3
    assert all(issue["mechanism"] in ("ARCH-EGRESS-001", "ARCH-SPATIAL-001") for issue in issues)


def test_enabled_with_no_records_is_a_noop():
    issues, error = BIMGuard_App._run_arch_engine_compliance(
        enable_arch_engines=True,
        ifc={"egress_checks": {}, "spatial_checks": {}},
        project_id=1,
        log_progress=_noop_log_progress,
    )

    assert issues == []
    assert error is None
