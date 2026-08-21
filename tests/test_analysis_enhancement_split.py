from types import SimpleNamespace

from app.modules.pipeline_services import AnalysisService, EnhancementService


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
