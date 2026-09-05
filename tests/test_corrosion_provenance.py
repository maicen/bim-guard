"""Every corrosion finding must say where its inputs came from.

WHY THIS FILE EXISTS

    A GC-001 Critical band is decided by two values: the element's material and
    its environment class. Neither is guaranteed to have been read from the
    model. An IFC carrying no material yields ``"Unknown"``; a space name
    matching no ``SPACE_TO_ENV`` keyword yields ``interior_dry``; and the
    engine then re-resolves that tag and falls back again to ``E2_NORMAL`` when
    it recognises nothing. By the time a band exists, a reading and a
    double-defaulted assumption are the same string.

    The finding is what a reviewer acts on, so the finding is where the
    difference has to survive. These tests assert it does -- for all five
    mechanisms, on findings and on data-quality Issues alike.

    They are deliberately about *presence and truthfulness of the annotation*,
    not about the bands. A test that asserted a band here would fail whenever a
    rule pack was retuned, and the annotation would be no better checked.

NO LIVE DATABASE. Elements are hand-built or come from the synthetic fixtures.

Run: uv run pytest tests/test_corrosion_provenance.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.modules.comparator.material_media import compare as mm_compare
from app.modules.ifc_reader import piping_fixtures as fx
from app.modules.ifc_reader.ifc_parser import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_NONE,
    DEFAULT_ENVIRONMENT,
    ENVIRONMENT_SOURCE_DEFAULT,
    ENVIRONMENT_SOURCE_SPATIAL,
    MATERIAL_SOURCE_ABSENT,
    MATERIAL_SOURCE_IFC,
    MATERIAL_SOURCE_UNMAPPED,
    SOURCE_SYNTHETIC,
    ServiceElement,
    classify_environment_from_space,
    generate_synthetic_elements,
    normalise_material_name,
    resolve_environment_from_space,
    resolve_material_name,
)
from app.modules.ifc_reader.piping_producer import (
    CONFIDENCE_NONE as PIPING_CONFIDENCE_NONE,
)
from app.modules.ifc_reader.piping_producer import (
    CONNECTIVITY_SOURCE_KEY,
    MATERIAL_SOURCE_KEY,
    SOURCE_ABSENT,
    element_provenance,
)
from app.modules.ifc_reader.piping_schema import (
    EnvironmentClass,
    PipingElement,
    PipingSystem,
)
from app.modules.phase_6.phase_6c_corrosion_ui import run_corrosion_analysis

#: The four keys every ServiceElement-derived Issue must carry.
ELEMENT_KEYS = (
    "material_source",
    "material_confidence",
    "environment_source",
    "environment_confidence",
)


# ---------------------------------------------------------------------------
# The parser resolvers
# ---------------------------------------------------------------------------


class TestMaterialProvenance:
    """A material key alone cannot say whether it was read or passed through."""

    def test_a_recognised_grade_is_a_reading(self):
        material, source, confidence = resolve_material_name("Stainless Steel 316")
        assert material == "SS_316_passive"
        assert source == MATERIAL_SOURCE_IFC
        assert confidence == CONFIDENCE_HIGH

    def test_an_absent_material_says_so(self):
        """get_material_name returns "Unknown" when the IFC associates none."""
        material, source, confidence = resolve_material_name("Unknown")
        assert material == "Unknown"
        assert source == MATERIAL_SOURCE_ABSENT
        assert confidence == CONFIDENCE_NONE

    def test_an_empty_string_is_absent_not_unmapped(self):
        assert resolve_material_name("")[1] == MATERIAL_SOURCE_ABSENT

    def test_free_text_from_the_ifc_is_unmapped_not_absent(self):
        """The distinction the split exists for: read, but resolvable by nothing."""
        material, source, confidence = resolve_material_name("Unobtainium Grade 7")
        assert source == MATERIAL_SOURCE_UNMAPPED
        assert confidence == CONFIDENCE_LOW
        assert material == "Unobtainium_Grade_7"

    def test_an_unmapped_material_is_not_reported_as_high_confidence(self):
        assert resolve_material_name("Some Alloy")[2] != CONFIDENCE_HIGH

    @pytest.mark.parametrize(
        "raw",
        ["Stainless Steel 316", "Unknown", "", "Unobtainium Grade 7", "Copper", "cast iron"],
    )
    def test_the_old_entry_point_is_unchanged(self, raw):
        """normalise_material_name is public; adding provenance must not move it."""
        assert normalise_material_name(raw) == resolve_material_name(raw)[0]


class TestEnvironmentProvenance:
    """A keyword match and a fallback are not comparable evidence."""

    def test_a_matched_space_name_is_an_inference(self):
        env, source, confidence = resolve_environment_from_space("Pool Plant Room", "Level 01")
        assert env == "swimming_pool"
        assert source == ENVIRONMENT_SOURCE_SPATIAL
        assert confidence == CONFIDENCE_MEDIUM

    def test_a_spatial_match_is_not_claimed_as_high_confidence(self):
        """A name matched a keyword; the model did not state the class."""
        assert resolve_environment_from_space("Roof Terrace", "")[2] == CONFIDENCE_MEDIUM

    def test_an_unrecognised_space_is_a_default(self):
        env, source, confidence = resolve_environment_from_space("Room 214", "Level 03")
        assert env == DEFAULT_ENVIRONMENT
        assert source == ENVIRONMENT_SOURCE_DEFAULT
        assert confidence == CONFIDENCE_LOW

    def test_nothing_at_all_is_a_default(self):
        assert resolve_environment_from_space("", "")[1] == ENVIRONMENT_SOURCE_DEFAULT

    def test_the_floor_tag_can_carry_the_match(self):
        """The storey name is searched too, so a match there is still spatial."""
        assert resolve_environment_from_space("", "Roof Level")[1] == ENVIRONMENT_SOURCE_SPATIAL

    @pytest.mark.parametrize(
        "space,floor",
        [("Pool Plant Room", "Level 01"), ("Room 214", "Level 03"), ("", "")],
    )
    def test_the_old_entry_point_is_unchanged(self, space, floor):
        assert (
            classify_environment_from_space(space, floor)
            == resolve_environment_from_space(space, floor)[0]
        )


# ---------------------------------------------------------------------------
# GC-001, CC-001, MC-001 -- the per-element mechanisms
# ---------------------------------------------------------------------------


def _service_element(**overrides) -> ServiceElement:
    """Build one element by hand, so the provenance under test is explicit."""
    base = dict(
        guid="GUID-01",
        name="CHW-Supply-01",
        ifc_type="IfcPipeSegment",
        description="Pipework",
        material_a="stainless_316",
        material_b="galvanised_steel",
        location_tag="swimming_pool",
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


class TestServiceElementDefaults:
    """An element built without the resolvers must not claim to be a reading."""

    def test_an_unannotated_element_reports_no_material_reading(self):
        element = _service_element()
        assert element.material_source == MATERIAL_SOURCE_ABSENT
        assert element.material_confidence == CONFIDENCE_NONE

    def test_an_unannotated_element_reports_a_defaulted_environment(self):
        element = _service_element()
        assert element.environment_source == ENVIRONMENT_SOURCE_DEFAULT
        assert element.environment_confidence == CONFIDENCE_LOW

    def test_demo_elements_are_marked_synthetic(self):
        """A demo finding must never be mistaken for an assessment of a building."""
        for element in generate_synthetic_elements(3):
            assert element.material_source == SOURCE_SYNTHETIC
            assert element.environment_source == SOURCE_SYNTHETIC


def _parsed(elements: list[ServiceElement]) -> dict:
    """Build a minimal ParsedIFC with no piping view, so only GC/CC/MC run."""
    return {
        "source_ref": "uploads/ifc/test.ifc",
        "source_sha256": "0" * 64,
        "schema": "IFC4",
        "schema_note": None,
        "elements": elements,
        "piping_elements": [],
        "quality": {"valid": True, "error": None},
    }


@pytest.fixture(scope="module")
def read_issues():
    """Issues for an element whose material and environment were both read.

    GC-001 and CC-001 reach verdicts; MC-001 contributes a
    ``hydraulics_unavailable`` refusal rather than a verdict, because
    ``_mic_element`` supplies none of the three inputs the pre-flight gate
    requires. Both kinds carry the provenance block, which is what this file
    asserts.
    """
    element = _service_element(
        material_source=MATERIAL_SOURCE_IFC,
        material_confidence=CONFIDENCE_HIGH,
        environment_source=ENVIRONMENT_SOURCE_SPATIAL,
        environment_confidence=CONFIDENCE_MEDIUM,
    )
    return run_corrosion_analysis(_parsed([element]), include_low=True)["audit_issues"]


@pytest.fixture(scope="module")
def assumed_issues():
    """Issues for an element carrying neither a read material nor a read class."""
    element = _service_element(material_a="Unknown", material_b=None)
    return run_corrosion_analysis(_parsed([element]), include_low=True)["audit_issues"]


@pytest.mark.slow
class TestPerElementFindingsCarryProvenance:
    def test_the_run_produced_something_to_assert_on(self, read_issues):
        """Guard: an empty list would make every test below vacuously pass."""
        assert read_issues

    @pytest.mark.parametrize("key", ELEMENT_KEYS)
    def test_every_issue_carries_every_key(self, read_issues, key):
        for issue in read_issues:
            assert key in issue.metadata, f"{issue.rule_id} omits {key}"

    def test_a_read_input_is_reported_as_read(self, read_issues):
        for issue in read_issues:
            assert issue.metadata["material_source"] == MATERIAL_SOURCE_IFC
            assert issue.metadata["environment_source"] == ENVIRONMENT_SOURCE_SPATIAL

    def test_an_assumed_input_is_reported_as_assumed(self, assumed_issues):
        """The case the whole file is for: nothing was read, and it shows."""
        assert assumed_issues
        for issue in assumed_issues:
            assert issue.metadata["material_source"] == MATERIAL_SOURCE_ABSENT
            assert issue.metadata["material_confidence"] == CONFIDENCE_NONE
            assert issue.metadata["environment_source"] == ENVIRONMENT_SOURCE_DEFAULT

    def test_the_two_runs_are_distinguishable(self, read_issues, assumed_issues):
        """The point of the annotation is that these two do not look alike."""
        read = {i.metadata["material_source"] for i in read_issues}
        assumed = {i.metadata["material_source"] for i in assumed_issues}
        assert read != assumed

    def test_data_quality_issues_carry_it_too(self, assumed_issues):
        """Usually the explanation for the absence, so it must not be dropped."""
        for issue in [i for i in assumed_issues if i.mechanism == "data_quality"]:
            for key in ELEMENT_KEYS:
                assert key in issue.metadata, f"{issue.rule_id} omits {key}"

    def test_every_mechanism_that_ran_is_covered(self, read_issues):
        """Not one engine's findings -- all of the per-element ones."""
        codes = {i.metadata.get("mechanism_code") for i in read_issues}
        assert {"GC-001", "CC-001", "MC-001"} <= codes

    def test_the_mic_diameter_assumption_survives(self, monkeypatch):
        """The provenance block is merged in beside it, not over it.

        MC-001 has to be given a hydraulic input to reach a verdict at all:
        since the pre-flight gate landed, an element with no flow velocity, no
        dead-leg length and no operating temperature is refused before the
        engine is entered, and ``_mic_element`` supplies none of the three. The
        assertion here is about what a *finding* carries, so the finding has to
        exist — hence the temperature.
        """
        import app.modules.phase_6.phase_6c_corrosion_ui as mod

        original = mod._mic_element

        def with_temperature(element):
            built = original(element)
            built.operating_temp_c = 28.0
            return built

        monkeypatch.setattr(mod, "_mic_element", with_temperature)
        element = _service_element(
            material_source=MATERIAL_SOURCE_IFC,
            material_confidence=CONFIDENCE_HIGH,
            environment_source=ENVIRONMENT_SOURCE_SPATIAL,
            environment_confidence=CONFIDENCE_MEDIUM,
        )
        issues = run_corrosion_analysis(_parsed([element]), include_low=True)["audit_issues"]
        mic = [
            i
            for i in issues
            if i.metadata.get("mechanism_code") == "MC-001" and i.mechanism != "data_quality"
        ]
        assert mic
        assert all("assumed_nominal_diameter_m" in i.metadata for i in mic)
        assert all("material_source" in i.metadata for i in mic)


# ---------------------------------------------------------------------------
# MM-001 and XM-001 -- the network mechanisms
# ---------------------------------------------------------------------------


def _piping_element(**overrides) -> PipingElement:
    base = dict(
        id="PIPE-01",
        ifc_class="IfcPipeSegment",
        subtype="pipe_segment",
        material="CarbonSteel",
        system=PipingSystem.DOMESTIC_HOT_WATER,
        environment_class=EnvironmentClass.T1_INDOOR_DAMP,
        operating_temperature_c=60.0,
    )
    base.update(overrides)
    return PipingElement(**base)


class TestElementProvenanceHelper:
    def test_a_bare_element_reports_absence_not_null(self):
        """A null in a metadata table reads as a missing field, not an absent input."""
        provenance = element_provenance(_piping_element())
        assert set(provenance.values()) <= {SOURCE_ABSENT, PIPING_CONFIDENCE_NONE}
        assert None not in provenance.values()

    def test_recorded_provenance_is_reported(self):
        element = _piping_element(
            properties={MATERIAL_SOURCE_KEY: "ifc_metadata"},
            material_confidence="high",
            environment_source="ifc_property",
            environment_confidence="high",
            temperature_source="system_inference",
            temperature_confidence="established",
        )
        provenance = element_provenance(element)
        assert provenance["material_source"] == "ifc_metadata"
        assert provenance["environment_confidence"] == "high"
        assert provenance["temperature_source"] == "system_inference"

    def test_temperature_can_be_left_out(self):
        """XM-001 reads none, so naming a source would imply one was consulted."""
        provenance = element_provenance(_piping_element(), include_temperature=False)
        assert not any(k.startswith("temperature_") for k in provenance)

    def test_a_prefix_namespaces_every_key(self):
        provenance = element_provenance(_piping_element(), prefix="anode_")
        assert all(k.startswith("anode_") for k in provenance)

    def test_a_partial_element_does_not_raise(self):
        """The orchestrator hands the comparators whatever Path A was given."""

        class Partial:
            material = "CarbonSteel"

        assert element_provenance(Partial())["material_source"] == SOURCE_ABSENT


@pytest.fixture(scope="module")
def piping_network():
    return fx.generate_synthetic_piping_network()


@pytest.fixture(scope="module")
def mm_issues(piping_network):
    pack = json.loads(
        Path("data/rulesets/mm_001_material_media.json").read_text(encoding="utf-8")
    )
    return mm_compare(piping_network, pack)


@pytest.fixture(scope="module")
def xm_issues():
    """XM-001 over a hand-built couple, through the production path.

    Not the synthetic fixture network: that one carries no resolved
    connectivity, so XM-001 correctly refuses to name an anode and raises only
    data-quality Issues. A couple has to exist for anode_/cathode_ provenance
    to have anything to attach to.

    Run through run_corrosion_analysis rather than compare() so the rule pack
    is assembled the way production assembles it -- with the galvanic series
    and thresholds injected from the GC-001 catalog -- instead of from tables
    restated here.
    """
    anode = _piping_element(
        id="XM-ANODE",
        material="CarbonSteel",
        properties={CONNECTIVITY_SOURCE_KEY: "centerline"},
    )
    cathode = _piping_element(
        id="XM-CATHODE",
        material="Copper_C12200",
        properties={CONNECTIVITY_SOURCE_KEY: "centerline"},
    )
    anode.joined_to.append(cathode.id)
    cathode.joined_to.append(anode.id)
    # A third element whose material the series does not carry, so the run also
    # produces the data-quality Issue the last test in this class asserts on.
    unlisted = _piping_element(
        id="XM-UNLISTED",
        material="Unknown",
        properties={CONNECTIVITY_SOURCE_KEY: "centerline"},
    )
    unlisted.joined_to.append(anode.id)
    anode.joined_to.append(unlisted.id)

    parsed = _parsed([])
    parsed["piping_elements"] = [anode, cathode, unlisted]
    return run_corrosion_analysis(parsed, include_low=True, engines=["XM"])["audit_issues"]


class TestMaterialMediaCarriesProvenance:
    def test_the_run_produced_something_to_assert_on(self, mm_issues):
        assert mm_issues

    @pytest.mark.parametrize(
        "key",
        ELEMENT_KEYS + ("temperature_source", "temperature_confidence"),
    )
    def test_every_issue_carries_every_key(self, mm_issues, key):
        """MM-001 scores on all three inputs, so it reports all three."""
        for issue in mm_issues:
            assert key in issue.metadata, f"{issue.id} omits {key}"

    def test_the_pack_confidence_is_not_overwritten(self, mm_issues):
        """Keep both confidences: they answer different questions.

        The bare "confidence" key is the rule pack's, about the cell it looked
        up. The ``*_confidence`` keys are about the inputs it looked it up
        with.
        """
        findings = [i for i in mm_issues if i.mechanism != "data_quality"]
        assert findings
        assert all("confidence" in i.metadata for i in findings)

    def test_provenance_is_never_null(self, mm_issues):
        for issue in mm_issues:
            for key in ELEMENT_KEYS:
                assert issue.metadata[key] is not None


class TestCrossMaterialCarriesProvenance:
    def test_the_run_produced_something_to_assert_on(self, xm_issues):
        assert xm_issues

    def test_couples_name_both_ends(self, xm_issues):
        """One end read and the other defaulted is real, common, and must show."""
        couples = [i for i in xm_issues if "anode_material" in i.metadata]
        assert couples
        for issue in couples:
            for side in ("anode_", "cathode_"):
                for key in ELEMENT_KEYS:
                    assert side + key in issue.metadata, f"{issue.id} omits {side}{key}"

    def test_no_temperature_source_is_claimed(self, xm_issues):
        """XM-001 does not read one, so it must not appear to have."""
        for issue in xm_issues:
            assert not any(k.endswith("temperature_source") for k in issue.metadata)

    def test_data_quality_issues_carry_provenance(self, xm_issues):
        dq = [i for i in xm_issues if i.mechanism == "data_quality"]
        assert dq
        for issue in dq:
            for key in ELEMENT_KEYS:
                assert key in issue.metadata, f"{issue.id} omits {key}"
