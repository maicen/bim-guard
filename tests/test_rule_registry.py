from types import SimpleNamespace

from app.modules.comparator.compliance_runner import run_compliance_checks
from app.modules.comparator.engine_registry import (
    RuleEngineRegistry,
    register_default_engines,
)


def test_rule_registry_contains_expected_evaluators():
    registry = RuleEngineRegistry()
    register_default_engines(registry)
    registered = set(registry.registered_rule_types())
    assert {"GC-001", "CC-001", "MC-001"}.issubset(registered)


def test_compliance_runner_dispatches_through_registry():
    element = SimpleNamespace(
        GlobalId="GUID-001",
        Name="Carbon Steel Pipe",
        material="carbon_steel",
        element_type="IfcPipeSegment",
        environment="normal",
        system_type="Cooling Water",
        floor="Level 1",
        zone="Zone A",
        joint_description="tight",
        operating_temp_c=30.0,
        nominal_diameter_m=0.2,
        flow_velocity_ms=1.0,
        dead_leg_length_m=0.5,
        insulation_condition="poor",
    )
    element.get_info = lambda: {
        "material": "carbon_steel",
        "environment": "normal",
        "system_type": "Cooling Water",
        "floor": "Level 1",
        "zone": "Zone A",
        "joint_description": "tight",
        "operating_temp_c": 30.0,
        "nominal_diameter_m": 0.2,
        "flow_velocity_ms": 1.0,
        "dead_leg_length_m": 0.5,
        "insulation_condition": "poor",
    }

    rows = run_compliance_checks([element])

    assert len(rows) == 1
    row = rows[0]
    assert row["guid"] == "GUID-001"
    assert row["name"] == "Carbon Steel Pipe"
    assert {"galvanic_band", "crevice_band", "mic_band", "dominant_mechanism"}.issubset(row)
