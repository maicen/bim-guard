from types import SimpleNamespace

from app.modules.pipeline_services import (
    AnalysisService,
    EnhancementService,
    enhance_model,
    run_compliance_analysis,
)


def test_analysis_and_enhancement_services_are_separated():
    element = SimpleNamespace(
        GlobalId="GUID-001",
        Name="Carbon Steel Pipe",
        material="carbon_steel",
        environment="normal",
        system_type="Cooling Water",
        zone="Zone A",
        floor="Level 1",
        nominal_diameter_m=0.2,
        flow_velocity_ms=1.0,
        operating_temp_c=30.0,
        dead_leg_length_m=0.5,
        insulation_condition="poor",
    )

    analysis = AnalysisService().run([element])
    assert analysis["pipeline"] == "analysis"
    assert analysis["element_count"] == 1
    assert "results" in analysis
    assert isinstance(analysis["results"], list)

    enhancement = EnhancementService().plan(
        [element],
        changes={"material": "stainless_steel", "insulation_condition": "improved"},
    )
    assert enhancement["pipeline"] == "enhancement"
    assert enhancement["version"] == 1
    assert enhancement["items"][0]["element_id"] == "GUID-001"
    assert enhancement["items"][0]["changes"]["material"] == "stainless_steel"


def test_phase_1_analysis_and_enhancement_entry_points_are_explicit():
    element = SimpleNamespace(
        GlobalId="GUID-002",
        Name="Carbon Steel Valve",
        material="carbon_steel",
        environment="normal",
        system_type="Cooling Water",
        zone="Zone B",
        floor="Level 2",
        nominal_diameter_m=0.15,
        flow_velocity_ms=0.8,
        operating_temp_c=35.0,
        dead_leg_length_m=0.3,
        insulation_condition="poor",
    )

    analysis = run_compliance_analysis([element])
    assert analysis["pipeline"] == "analysis"
    assert analysis["element_count"] == 1
    assert analysis["results"][0]["guid"] == "GUID-002"

    enhancement = enhance_model(
        [element],
        changes={"material": "duplex_steel", "insulation_condition": "improved"},
        version=2,
    )
    assert enhancement["pipeline"] == "enhancement"
    assert enhancement["version"] == 2
    assert enhancement["items"][0]["changes"]["material"] == "duplex_steel"
