"""The pre-flight gate: an engine is never handed an invented input.

WHY THIS FILE EXISTS

    GC-001, CC-001 and MC-001 each substitute a real, scoreable value when an
    input is missing, so a model carrying no material data produced a full set
    of confident verdicts computed entirely from substitutions — 6,587 Medium
    crevice verdicts and 6,587 Critical MIC verdicts on Clinic_Plumbing, one per
    element, uniformly, with not a single data_quality Issue among them.

    The arithmetic was never wrong. The inputs were invented. So the gate does
    not correct a score; it declines to ask for one, and says so.

    These tests are about *whether the engine is entered*, not about bands. A
    test that asserted a band here would fail whenever a rule pack was retuned
    and would not check the gate at all.

NO LIVE DATABASE. Elements are hand-built, so the gated input is explicit.

Run: uv run pytest tests/test_corrosion_preflight_gate.py -v
"""

from __future__ import annotations

import pytest

from app.modules.ifc_reader.ifc_parser import (
    MATERIAL_SOURCE_IFC,
    MATERIAL_SOURCE_UNMAPPED,
    ServiceElement,
)
from app.modules.phase_6.phase_6c_corrosion_ui import (
    DATA_QUALITY,
    run_corrosion_analysis,
)


def service_element(**overrides) -> ServiceElement:
    """Build one element by hand, so the gated input is explicit."""
    base = dict(
        guid="GUID-01",
        name="CHW-Supply-01",
        ifc_type="IfcPipeSegment",
        description="Pipework",
        material_a="stainless_316",
        material_b="galvanised_steel",
        location_tag="interior_conditioned",
        floor="Level 02",
        system="Chilled water",
        joint_type="JT-001",
        anode_area_m2=0.05,
        cathode_area_m2=0.50,
        position=(1.0, 2.0, 3.0),
        length_m=2.5,
    )
    base.update(overrides)
    return ServiceElement(**base)


def parsed(elements: list[ServiceElement]) -> dict:
    """A minimal ParsedIFC with no piping view, so only GC/CC/MC run."""
    return {
        "source_ref": "uploads/ifc/test.ifc",
        "source_sha256": "0" * 64,
        "schema": "IFC4",
        "schema_note": None,
        "elements": elements,
        "piping_elements": [],
        "quality": {"valid": True, "error": None},
    }


def run(element: ServiceElement, engines: list[str]):
    """Run selected engines over one element and return its Issues."""
    return run_corrosion_analysis(
        parsed([element]), engines=engines, include_low=True, run_id="GATE"
    )["audit_issues"]


def issues_for(issues, code: str):
    return [i for i in issues if (i.metadata or {}).get("mechanism_code") == code]


def verdicts(issues, code: str):
    return [i for i in issues_for(issues, code) if i.mechanism != DATA_QUALITY]


def gated(issues, code: str, check: str):
    return [
        i
        for i in issues_for(issues, code)
        if i.mechanism == DATA_QUALITY and (i.metadata or {}).get("check") == check
    ]


# ---------------------------------------------------------------------------
# GC-001 and CC-001: material
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("code", ["GC-001", "CC-001"])
class TestUnknownMaterialIsRefused:
    """The defect: "Unknown" was coerced into a scoreable material."""

    def test_unknown_material_yields_no_verdict(self, code):
        found = run(service_element(material_a="Unknown", material_b=None), [code])
        assert verdicts(found, code) == []

    def test_unknown_material_yields_a_data_quality_issue(self, code):
        found = run(service_element(material_a="Unknown", material_b=None), [code])
        assert len(gated(found, code, "material_unresolved")) == 1

    def test_the_element_does_not_vanish(self, code):
        """Step 2 of the four-step rule still applies to a gated element."""
        found = run(service_element(material_a="Unknown", material_b=None), [code])
        assert [i for i in issues_for(found, code)]

    def test_an_empty_material_is_refused_too(self, code):
        found = run(service_element(material_a="", material_b=None), [code])
        assert verdicts(found, code) == []
        assert len(gated(found, code, "material_unresolved")) == 1

    def test_unknown_is_matched_regardless_of_case(self, code):
        found = run(service_element(material_a="UNKNOWN", material_b=None), [code])
        assert len(gated(found, code, "material_unresolved")) == 1

    def test_free_text_read_from_the_ifc_is_refused(self, code):
        """Read from the model, but resolvable by nothing — coerced just the same."""
        element = service_element(
            material_a="Unobtainium_Grade_7",
            material_b=None,
            material_source=MATERIAL_SOURCE_UNMAPPED,
        )
        found = run(element, [code])
        assert verdicts(found, code) == []
        assert len(gated(found, code, "material_unresolved")) == 1


@pytest.mark.parametrize("code", ["GC-001", "CC-001"])
class TestKnownMaterialStillRuns:
    """The gate must not cost a verdict that was legitimately earned."""

    def test_a_known_material_reaches_the_engine(self, code):
        found = run(service_element(), [code])
        assert verdicts(found, code), f"{code} produced no verdict for a real material"

    def test_a_known_material_is_not_gated(self, code):
        found = run(service_element(), [code])
        assert gated(found, code, "material_unresolved") == []

    def test_canonical_stainless_is_not_gated(self, code):
        """Regression: gating on GC-001's alias table would refuse this.

        ``SS_316_passive`` is the parser's canonical name and resolves against
        CC-001's table but not GC-001's, because the alias ``316`` is matched on
        a word boundary and the underscores in ``ss_316_passive`` are word
        characters. A gate keyed on that table would mark genuine stainless
        Undetermined, so the gate is keyed on the parser's identification.
        """
        element = service_element(
            material_a="SS_316_passive", material_source=MATERIAL_SOURCE_IFC
        )
        found = run(element, [code])
        assert verdicts(found, code)
        assert gated(found, code, "material_unresolved") == []

    def test_a_material_the_engine_knows_is_not_gated(self, code):
        """Unmapped by the parser, but in GC-001's table: the engine can answer.

        PVC is the sharp case. GC-001 maps the non-metallics to ``None`` on
        purpose so it can report "no galvanic risk" -- a verdict. Refusing it
        would replace a correct finding with an Undetermined.
        """
        element = service_element(
            material_a="PVC", material_b=None, material_source=MATERIAL_SOURCE_UNMAPPED
        )
        found = run(element, [code])
        assert gated(found, code, "material_unresolved") == []

    def test_camelcase_material_names_are_recognised(self, code):
        """Regression: IFC authoring tools write CarbonSteel, not "carbon steel".

        The Fire Sprinkler Riser in test_hospital_mep_scenario.ifc carries
        exactly this, and the first cut of the gate refused it -- a real, named
        material reported as unresolvable.
        """
        found = run(service_element(material_a="CarbonSteel", material_b=None), [code])
        assert gated(found, code, "material_unresolved") == []
        assert verdicts(found, code)

    def test_a_hand_built_element_is_not_gated_by_default_provenance(self, code):
        """Value first, provenance second.

        An element built without going through ``resolve_material_name`` carries
        the default ``material_source``. Keying the gate on provenance alone
        would refuse it despite a perfectly good material string.
        """
        found = run(service_element(material_a="Copper"), [code])
        assert verdicts(found, code)


# ---------------------------------------------------------------------------
# MC-001: hydraulics
# ---------------------------------------------------------------------------


class TestHydraulicsGate:
    def test_all_three_absent_is_refused(self):
        """``_mic_element`` supplies none of the three, so this is every element."""
        found = run(service_element(), ["MC-001"])
        assert verdicts(found, "MC-001") == []
        assert len(gated(found, "MC-001", "hydraulics_unavailable")) == 1

    def test_the_refusal_records_all_three_inputs(self):
        found = run(service_element(), ["MC-001"])
        meta = gated(found, "MC-001", "hydraulics_unavailable")[0].metadata
        assert meta["flow_velocity_ms"] is None
        assert meta["dead_leg_length_m"] is None
        assert meta["operating_temp_c"] is None

    def test_a_present_temperature_lets_the_engine_run(self, monkeypatch):
        """Partial data is legitimately scorable — only all-absent is refused."""
        import app.modules.phase_6.phase_6c_corrosion_ui as mod

        original = mod._mic_element

        def with_temperature(element):
            built = original(element)
            built.operating_temp_c = 28.0
            return built

        monkeypatch.setattr(mod, "_mic_element", with_temperature)
        found = run(service_element(), ["MC-001"])
        assert gated(found, "MC-001", "hydraulics_unavailable") == []
        assert verdicts(found, "MC-001")

    def test_a_present_velocity_lets_the_engine_run(self, monkeypatch):
        import app.modules.phase_6.phase_6c_corrosion_ui as mod

        original = mod._mic_element

        def with_velocity(element):
            built = original(element)
            built.flow_velocity_ms = 1.2
            return built

        monkeypatch.setattr(mod, "_mic_element", with_velocity)
        found = run(service_element(), ["MC-001"])
        assert gated(found, "MC-001", "hydraulics_unavailable") == []
        assert verdicts(found, "MC-001")

    def test_a_present_dead_leg_lets_the_engine_run(self, monkeypatch):
        import app.modules.phase_6.phase_6c_corrosion_ui as mod

        original = mod._mic_element

        def with_dead_leg(element):
            built = original(element)
            built.dead_leg_length_m = 0.4
            return built

        monkeypatch.setattr(mod, "_mic_element", with_dead_leg)
        found = run(service_element(), ["MC-001"])
        assert gated(found, "MC-001", "hydraulics_unavailable") == []
        assert verdicts(found, "MC-001")

    def test_material_gate_does_not_apply_to_mc(self, monkeypatch):
        """MC-001 is gated on hydraulics, not material — the two are separate."""
        import app.modules.phase_6.phase_6c_corrosion_ui as mod

        original = mod._mic_element

        def with_temperature(element):
            built = original(element)
            built.operating_temp_c = 28.0
            return built

        monkeypatch.setattr(mod, "_mic_element", with_temperature)
        found = run(service_element(material_a="Unknown", material_b=None), ["MC-001"])
        assert gated(found, "MC-001", "material_unresolved") == []


# ---------------------------------------------------------------------------
# The record the gate leaves behind
# ---------------------------------------------------------------------------


class TestGateProvenance:
    """A CSV or BCF row must say why the element is Undetermined."""

    def test_the_reason_names_the_raw_material(self):
        element = service_element(
            material_a="Unobtainium_Grade_7",
            material_b=None,
            material_source=MATERIAL_SOURCE_UNMAPPED,
        )
        meta = gated(run(element, ["GC-001"]), "GC-001", "material_unresolved")[0].metadata
        assert "Unobtainium_Grade_7" in meta["reason"]

    def test_the_inputs_the_gate_saw_are_recorded(self):
        element = service_element(material_a="Unknown", material_b=None)
        meta = gated(run(element, ["GC-001"]), "GC-001", "material_unresolved")[0].metadata
        assert meta["material_a_raw"] == "Unknown"
        assert "material_source" in meta

    def test_the_mechanism_is_named(self):
        element = service_element(material_a="Unknown", material_b=None)
        meta = gated(run(element, ["CC-001"]), "CC-001", "material_unresolved")[0].metadata
        assert meta["mechanism_code"] == "CC-001"

    def test_a_gated_issue_is_never_a_verdict(self):
        """The separation the four-step rule exists to protect."""
        found = run(service_element(material_a="Unknown", material_b=None), ["GC-001", "CC-001"])
        for issue in found:
            assert issue.mechanism == DATA_QUALITY

    def test_gated_issues_survive_the_include_low_filter(self):
        """Step 4: without the exemption the gate's output is deleted downstream."""
        found = run_corrosion_analysis(
            parsed([service_element(material_a="Unknown", material_b=None)]),
            engines=["GC-001", "CC-001", "MC-001"],
            include_low=False,
            run_id="GATE",
        )["audit_issues"]
        assert len(found) == 3, "one refusal per mechanism should survive include_low=False"
