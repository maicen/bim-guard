"""MC-001 applies only to pipes that carry water.

WHY THIS FILE EXISTS

    MC-001's inputs -- the CIBSE TM13 temperature danger zone, the HSE HSG274
    dead-leg and flow-velocity classes, the MIT-MIC mitigations -- all describe
    microbial growth in liquid water. They were applied to every pipe element
    regardless of what it carried, so a stagnant 30 °C acid branch scored as a
    Critical Legionella finding.

    The medium is resolved from the IFC system classification the rest of the
    codebase already uses (piping_producer.classify_system -> media_for_system,
    the same derivation MM-001 scores from). Water runs MC-001; a known
    non-water medium is out of scope and raises nothing; an unknown medium is
    refused with a data_quality Issue, never assumed to be water.

NO LIVE DATABASE is needed for the gate itself; the Critical assertion reads
whichever MC-001 catalog the process holds, as every other MC-001 test does.

Run: uv run pytest tests/test_mc001_medium_scope.py -v
"""

from __future__ import annotations

import pytest

from app.engines.bimguard_mic_engine import (
    MEDIUM_APPLICABLE,
    MEDIUM_NOT_APPLICABLE,
    MEDIUM_UNRESOLVED,
    MICElement,
    MICEngine,
    assess_mic_risk,
    resolve_medium_scope,
)
from app.modules.comparator.compliance_runner import run_mic_compliance_check
from app.modules.ifc_reader.ifc_parser import ServiceElement
from app.modules.ifc_reader.piping_producer import classify_system
from app.modules.ifc_reader.piping_schema import PipingSystem
from app.modules.phase_6.phase_6c_corrosion_ui import (
    ASSUMED_NOMINAL_DIAMETER_M,
    DATA_QUALITY,
    run_corrosion_analysis,
)

#: The conditions of the false positive: no flow, 30 °C (the TM13 danger
#: zone), a 1.57 m branch -- 15.7 D on the assumed DN100, a long dead leg.
STAGNANT_WARM_BRANCH = dict(flow_velocity_ms=0.0, operating_temp_c=30.0, dead_leg_length_m=1.57)


def service_element(system: str, **overrides) -> ServiceElement:
    """One carbon-steel branch under the false-positive conditions."""
    base = dict(
        guid="GUID-MC-01",
        name="Branch-01",
        ifc_type="IfcPipeSegment",
        description="Pipework",
        material_a="carbon_steel",
        material_b=None,
        location_tag="interior_conditioned",
        floor="Level 01",
        system=system,
        joint_type="JT-001",
        anode_area_m2=0.05,
        cathode_area_m2=0.50,
        position=(0.0, 0.0, 0.0),
        length_m=1.57,
        **STAGNANT_WARM_BRANCH,
    )
    base.update(overrides)
    return ServiceElement(**base)


def run_mc001(element: ServiceElement):
    parsed = {
        "source_ref": "uploads/ifc/test.ifc",
        "source_sha256": "0" * 64,
        "schema": "IFC4",
        "schema_note": None,
        "elements": [element],
        "piping_elements": [],
        "quality": {"valid": True, "error": None},
    }
    issues = run_corrosion_analysis(parsed, engines=["MC-001"], include_low=True, run_id="MED")[
        "audit_issues"
    ]
    return [i for i in issues if (i.metadata or {}).get("mechanism_code") == "MC-001"]


def verdicts(issues):
    return [i for i in issues if i.mechanism != DATA_QUALITY]


# ---------------------------------------------------------------------------
# The regression: identical geometry, flow and temperature; only the medium
# differs.
# ---------------------------------------------------------------------------


class TestWaterStillFlagged:
    """The fix must not suppress the finding where it is real."""

    def test_domestic_cold_water_branch_is_critical(self):
        found = verdicts(run_mc001(service_element("Domestic Cold Water")))
        assert len(found) == 1
        assert found[0].band.value == "critical"

    def test_engine_result_is_the_legionella_danger_zone(self):
        result = assess_mic_risk(
            MICElement(
                global_id="W",
                element_type="IfcPipeSegment",
                system_type="DOMESTICCOLDWATER",
                material="carbon_steel",
                nominal_diameter_m=ASSUMED_NOMINAL_DIAMETER_M,
                **STAGNANT_WARM_BRANCH,
            )
        )
        assert result.risk_band == "Critical"
        assert result.flow_velocity_class == "FV0_STAGNANT"
        assert result.dead_leg_class == "DL3_LONG"
        assert "MIT-MIC-001" in result.mitigations


class TestAcidNotFlagged:
    """The defect: an acid line scored as a Legionella risk."""

    @pytest.mark.parametrize("system", ["Acid Waste", "Chemical Transfer", "CHEMICAL", "Diesel Fuel"])
    def test_no_mc001_issue_of_any_kind(self, system):
        """Out of scope: no verdict, and no data_quality note claiming missing data."""
        assert run_mc001(service_element(system)) == []

    def test_acid_waste_is_not_read_as_foul_water(self):
        """The "waste" rule must not match first and make the acid line water."""
        assert classify_system("Acid Waste") is PipingSystem.CHEMICAL

    def test_registry_engine_reports_not_applicable(self):
        result = MICEngine().evaluate(
            {"guid": "A", "system_type": "Acid Waste", "material": "carbon_steel", **STAGNANT_WARM_BRANCH}
        )
        assert result.status == "NOT_APPLICABLE"
        assert result.band is None
        assert result.details["medium"] == "chemical"

    def test_compliance_runner_emits_no_band(self):
        payload = run_mic_compliance_check(
            {"system_type": "Acid Waste", "material": "carbon_steel", **STAGNANT_WARM_BRANCH}
        )
        assert payload["band"] is None


# ---------------------------------------------------------------------------
# Medium resolution
# ---------------------------------------------------------------------------


class TestMediumScope:
    @pytest.mark.parametrize(
        "hint",
        ["Domestic Hot Water", "DOMESTICCOLDWATER", "Chilled Water", "Fire Main", "Condenser Water"],
    )
    def test_water_systems_apply(self, hint):
        assert resolve_medium_scope(hint).status == MEDIUM_APPLICABLE

    @pytest.mark.parametrize(
        "hint", ["Acid Waste", "Natural Gas", "Compressed Air", "Steam HP", "OIL", "Pool chemical dosing"]
    )
    def test_non_water_media_do_not_apply(self, hint):
        assert resolve_medium_scope(hint).status == MEDIUM_NOT_APPLICABLE

    @pytest.mark.parametrize("hint", ["Unassigned", "Mech System 7", ""])
    def test_unclassifiable_is_unresolved_not_water(self, hint):
        assert resolve_medium_scope(hint).status == MEDIUM_UNRESOLVED

    def test_later_hint_resolves_a_bare_system_tag(self):
        """Real Revit export: system Name "OX 50", ObjectType "PIPING - OXYGEN"."""
        assert resolve_medium_scope("OX 50", "PIPING - OXYGEN").status == MEDIUM_NOT_APPLICABLE

    def test_parser_hints_reach_the_gate(self):
        element = service_element("OX 50", system_hints=("PIPING - OXYGEN",))
        assert run_mc001(element) == []


class TestUnknownMediumRefused:
    """No medium, no assumption: refused with a data_quality Issue."""

    def test_unknown_medium_yields_no_verdict(self):
        found = run_mc001(service_element("Unassigned", name="Pipe Types:Standard"))
        assert verdicts(found) == []

    def test_unknown_medium_yields_a_data_quality_issue(self):
        found = run_mc001(service_element("Unassigned", name="Pipe Types:Standard"))
        gated = [i for i in found if (i.metadata or {}).get("check") == "medium_unresolved"]
        assert len(gated) == 1
        assert gated[0].metadata["medium"] == "unknown"

    def test_registry_engine_reports_not_assessed(self):
        result = MICEngine().evaluate({"guid": "U", "material": "carbon_steel", **STAGNANT_WARM_BRANCH})
        assert result.status == "NOT_ASSESSED"
        assert result.band is None
