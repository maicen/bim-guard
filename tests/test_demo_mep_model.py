"""The demo MEP model, the properties it writes, and the gate it opens.

WHY THIS FILE EXISTS

    scripts/generate_demo_mep_model.py exists to give the corrosion engines a
    model that carries real material and hydraulic data, so each mechanism is
    exercised in both directions: scored where the data is there, Undetermined
    where it is not. Three things have to hold for that to be true, and each is
    easy to break silently:

      1. The parser reads the hydraulic properties into ServiceElement, with
         provenance, and leaves absent ones as None.
      2. The MC-001 pre-flight gate opens for an element that carries
         hydraulics and still refuses one that does not.
      3. The generator writes the proportions it claims.

    (1) breaking gives every element None and sends MC-001 back to refusing the
    whole model. (2) breaking is worse: it produces confident MIC verdicts
    computed from a substituted stagnant velocity, which is the failure the
    gate was added to stop. (3) breaking makes the demo model quietly stop
    covering one of the cases.

NO LIVE DATABASE for the gate tests: elements are hand-built so the gated
input is explicit, matching tests/test_corrosion_preflight_gate.py.

Run: uv run pytest tests/test_demo_mep_model.py -v
"""

from __future__ import annotations

import ifcopenshell
import pytest

from app.modules.ifc_reader.ifc_parser import (
    CONFIDENCE_HIGH,
    CONFIDENCE_NONE,
    HYDRAULIC_SOURCE_ABSENT,
    HYDRAULIC_SOURCE_IFC,
    MATERIAL_SOURCE_ABSENT,
    MATERIAL_SOURCE_IFC_PROPERTY,
    MATERIAL_SOURCE_IFC_PROPERTY_UNMAPPED,
    ServiceElement,
    parse_ifc_model,
    read_hydraulics,
    read_secondary_material,
)
from app.modules.phase_6.phase_6c_corrosion_ui import (
    CREVICE,
    GALVANIC,
    MIC,
    _mic_element,
    _preflight,
)
from scripts.generate_demo_mep_model import (
    ELEMENTS_PER_SYSTEM,
    SYSTEMS,
    build_model,
    has_couple,
    has_hydraulics,
    has_material,
    secondary_material_for,
)


@pytest.fixture(scope="module")
def demo_elements() -> list[ServiceElement]:
    """Parse the generated model once; building it costs ~2s."""
    return parse_ifc_model(build_model())


def service_element(**overrides) -> ServiceElement:
    """Build one element by hand, so the gated input is explicit."""
    base = dict(
        guid="GUID-01",
        name="CHW-Supply-01",
        ifc_type="IfcPipeSegment",
        description="Pipework",
        material_a="SS_316_passive",
        material_b=None,
        location_tag="interior_conditioned",
        floor="Level 02",
        system="Chilled Water",
        joint_type="JT-001",
        anode_area_m2=0.05,
        cathode_area_m2=0.50,
        position=(1.0, 2.0, 3.0),
        length_m=2.5,
    )
    base.update(overrides)
    return ServiceElement(**base)


# ---------------------------------------------------------------------------
# 1. The parser reads the new properties
# ---------------------------------------------------------------------------


def test_parser_reads_hydraulics_with_provenance(demo_elements):
    """An element carrying the pset yields all three values, sourced to IFC."""
    scored = [e for e in demo_elements if e.flow_velocity_ms is not None]
    assert scored, "no element carried a flow velocity"

    element = scored[0]
    assert element.operating_temp_c is not None
    assert element.dead_leg_length_m is not None
    assert element.velocity_source == HYDRAULIC_SOURCE_IFC
    assert element.temperature_source == HYDRAULIC_SOURCE_IFC
    assert element.dead_leg_source == HYDRAULIC_SOURCE_IFC


def test_parser_leaves_absent_properties_none(demo_elements):
    """An element with no hydraulic pset is None throughout, never defaulted.

    The assertion that matters is ``is None`` rather than falsiness: 0.0 is a
    legitimate velocity (stagnant, MC-001's worst class) and would pass a
    truthiness check while meaning the opposite of "not stated".
    """
    absent = [e for e in demo_elements if e.velocity_source == HYDRAULIC_SOURCE_ABSENT]
    assert absent, "every element carried hydraulics; the 30% split is broken"

    for element in absent:
        assert element.flow_velocity_ms is None
        assert element.operating_temp_c is None
        assert element.dead_leg_length_m is None
        assert element.temperature_source == HYDRAULIC_SOURCE_ABSENT
        assert element.dead_leg_source == HYDRAULIC_SOURCE_ABSENT


def test_parser_reads_the_property_names_the_generator_writes(demo_elements):
    """The velocities read back are the ones the generator wrote.

    Guards against the parser matching some *other* property and appearing to
    work: a dead leg is written as exactly 0.0 m/s and a live run is not.
    """
    dead_legs = [e for e in demo_elements if e.dead_leg_length_m]
    live = [
        e
        for e in demo_elements
        if e.flow_velocity_ms is not None and not e.dead_leg_length_m
    ]
    assert dead_legs and live

    assert all(e.flow_velocity_ms == 0.0 for e in dead_legs)
    assert all(e.flow_velocity_ms > 0.0 for e in live)
    # Temperatures must be one of the six system design values, not an artefact.
    expected = {s["temperature_c"] for s in SYSTEMS}
    read = {e.operating_temp_c for e in demo_elements if e.operating_temp_c is not None}
    assert read <= expected


def test_read_hydraulics_reports_a_dead_leg_flag_without_inventing_a_length():
    """A bare IsDeadLeg=True is provenance-tracked but yields no length.

    MC-001 classifies a dead leg by length-to-diameter ratio. Turning a boolean
    into a length would be exactly the substitution the gate exists to refuse,
    so the source records the reading and the value stays None.
    """
    model = ifcopenshell.file(schema="IFC4")
    element = model.create_entity("IfcPipeSegment", GlobalId=ifcopenshell.guid.new())
    pset = model.create_entity(
        "IfcPropertySet",
        GlobalId=ifcopenshell.guid.new(),
        Name="Pset_BimGuardHydraulics",
        HasProperties=[
            model.create_entity(
                "IfcPropertySingleValue",
                Name="IsDeadLeg",
                NominalValue=model.create_entity("IfcBoolean", True),
            )
        ],
    )
    model.create_entity(
        "IfcRelDefinesByProperties",
        GlobalId=ifcopenshell.guid.new(),
        RelatedObjects=[element],
        RelatingPropertyDefinition=pset,
    )

    read = read_hydraulics(element)
    assert read["dead_leg_length_m"] is None
    assert read["dead_leg_source"] == HYDRAULIC_SOURCE_IFC


# ---------------------------------------------------------------------------
# 1b. The declared second material at a junction
# ---------------------------------------------------------------------------


def _secondary_pset_element(value):
    """Build an IfcPipeSegment with SecondaryMaterial=``value`` (None = no pset)."""
    model = ifcopenshell.file(schema="IFC4")
    element = model.create_entity("IfcPipeSegment", GlobalId=ifcopenshell.guid.new())
    if value is None:
        return element
    pset = model.create_entity(
        "IfcPropertySet",
        GlobalId=ifcopenshell.guid.new(),
        Name="Pset_BimGuardCouple",
        HasProperties=[
            model.create_entity(
                "IfcPropertySingleValue",
                Name="SecondaryMaterial",
                NominalValue=model.create_entity("IfcLabel", value),
            )
        ],
    )
    model.create_entity(
        "IfcRelDefinesByProperties",
        GlobalId=ifcopenshell.guid.new(),
        RelatedObjects=[element],
        RelatingPropertyDefinition=pset,
    )
    return element


def test_parser_reads_secondary_material_with_provenance(demo_elements):
    """A declared second material lands in material_b, sourced to the property."""
    coupled = [e for e in demo_elements if e.material_b is not None]
    assert coupled, "no element declared a second material"

    for element in coupled:
        assert element.material_b_source == MATERIAL_SOURCE_IFC_PROPERTY
        assert element.material_b_confidence == CONFIDENCE_HIGH
        # The vocabulary is shared with material_a: both sides of a couple are
        # canonical keys, not one key and one free-text string.
        assert element.material_b == element.material_b.strip()
        assert " " not in element.material_b


def test_parser_leaves_absent_secondary_material_none(demo_elements):
    """No SecondaryMaterial property means None, never the element's own material.

    Defaulting material_b to material_a would read as a declared self-couple
    rather than as "the model says nothing about a junction here", and GC-001
    tags those two cases differently.
    """
    uncoupled = [e for e in demo_elements if e.material_b is None]
    assert uncoupled

    for element in uncoupled:
        assert element.material_b_source == MATERIAL_SOURCE_ABSENT
        assert element.material_b_confidence == CONFIDENCE_NONE


def test_read_secondary_material_maps_through_the_shared_vocabulary():
    """The property is resolved by resolve_material_name, as material_a is."""
    read = read_secondary_material(_secondary_pset_element("Galvanised Steel"))
    assert read["material_b"] == "Galvanized_steel"
    assert read["material_b_source"] == MATERIAL_SOURCE_IFC_PROPERTY
    assert read["material_b_confidence"] == CONFIDENCE_HIGH


def test_read_secondary_material_marks_an_unmapped_value_as_such():
    """Free text that matches no key is kept, but not dressed up as a reading."""
    read = read_secondary_material(_secondary_pset_element("Unobtanium"))
    assert read["material_b_source"] == MATERIAL_SOURCE_IFC_PROPERTY_UNMAPPED
    assert read["material_b_confidence"] != CONFIDENCE_HIGH


def test_read_secondary_material_absent_is_none():
    """An element with no such property reads as absent."""
    read = read_secondary_material(_secondary_pset_element(None))
    assert read["material_b"] is None
    assert read["material_b_source"] == MATERIAL_SOURCE_ABSENT
    assert read["material_b_confidence"] == CONFIDENCE_NONE


def test_generator_couple_proportion(demo_elements):
    """Roughly 40% of the elements that carry a material declare a couple."""
    with_material = [e for e in demo_elements if e.material_a != "Unknown"]
    coupled = [e for e in with_material if e.material_b is not None]
    assert len(coupled) == pytest.approx(len(with_material) * 0.40, abs=8)


def test_no_element_without_a_material_declares_a_couple(demo_elements):
    """A couple needs two sides. One-sided couples would be unreadable noise."""
    assert not [
        e for e in demo_elements if e.material_a == "Unknown" and e.material_b
    ]


def test_generator_writes_both_severe_and_benign_couples(demo_elements):
    """The model carries dissimilar-metal couples and same-family ones.

    Not asserted as bands: which band a pairing lands in is the engine's call
    and a retuned rule pack would move it. What this pins is that the *model*
    offers the engine both kinds to distinguish.
    """
    pairs = {(e.material_a, e.material_b) for e in demo_elements if e.material_b}
    assert ("Copper", "Galvanized_steel") in pairs
    assert ("Carbon_steel_mild", "SS_316_passive") in pairs
    assert ("Copper", "Brass_naval") in pairs
    # A declared self-couple: same material both sides, stated rather than assumed.
    assert ("Carbon_steel_mild", "Carbon_steel_mild") in pairs


def test_plastic_pipe_declares_no_couple(demo_elements):
    """HDPE has no galvanic couple, so no bracket material is declared on it."""
    assert not [e for e in demo_elements if e.material_a == "HDPE" and e.material_b]


def test_couple_helpers_agree_with_the_written_model(demo_elements):
    """has_couple/secondary_material_for describe the file the generator writes."""
    expected = sum(
        1
        for system in SYSTEMS
        for i in range(ELEMENTS_PER_SYSTEM)
        if has_couple(i)
        and secondary_material_for(system["materials"][i % len(system["materials"])], i)
        is not None
    )
    assert sum(1 for e in demo_elements if e.material_b is not None) == expected


# ---------------------------------------------------------------------------
# 2. The gate opens for hydraulics and still refuses their absence
# ---------------------------------------------------------------------------


def test_gate_admits_an_element_carrying_hydraulics():
    """MC-001 runs when the parser supplied real hydraulic inputs."""
    element = service_element(
        flow_velocity_ms=1.4,
        operating_temp_c=60.0,
        dead_leg_length_m=0.0,
        velocity_source=HYDRAULIC_SOURCE_IFC,
        temperature_source=HYDRAULIC_SOURCE_IFC,
        dead_leg_source=HYDRAULIC_SOURCE_IFC,
    )
    assert _preflight(element, MIC) is None


def test_gate_refuses_an_element_with_no_hydraulics():
    """MC-001 is still refused when all three inputs are absent."""
    gated = _preflight(service_element(), MIC)
    assert gated is not None
    check, reason, inputs = gated
    assert check == "hydraulics_unavailable"
    assert inputs == {
        "flow_velocity_ms": None,
        "dead_leg_length_m": None,
        "operating_temp_c": None,
    }
    assert "stagnant" in reason


@pytest.mark.parametrize(
    "field, value",
    [
        ("flow_velocity_ms", 0.8),
        ("operating_temp_c", 45.0),
        ("dead_leg_length_m", 1.2),
    ],
)
def test_gate_admits_on_any_one_of_the_three(field, value):
    """Partial hydraulic data is scorable; only the all-absent case is refused."""
    assert _preflight(service_element(**{field: value}), MIC) is None


def test_mic_element_passes_hydraulics_through_unchanged():
    """_mic_element hands the engine the parser's values, None included."""
    populated = _mic_element(
        service_element(flow_velocity_ms=2.0, operating_temp_c=15.0, dead_leg_length_m=0.5)
    )
    assert populated.flow_velocity_ms == 2.0
    assert populated.operating_temp_c == 15.0
    assert populated.dead_leg_length_m == 0.5

    empty = _mic_element(service_element())
    assert empty.flow_velocity_ms is None
    assert empty.operating_temp_c is None
    assert empty.dead_leg_length_m is None


def test_a_zero_velocity_is_a_reading_not_an_absence():
    """0.0 m/s opens the gate. It is the worst flow class, not a missing one.

    The distinction the whole gate rests on: a stagnant element that was
    *measured* as stagnant must be scored, while one that was never measured
    must not be scored as though it had been.
    """
    element = service_element(
        flow_velocity_ms=0.0, velocity_source=HYDRAULIC_SOURCE_IFC
    )
    assert _mic_element(element).flow_velocity_ms == 0.0
    assert _preflight(element, MIC) is None


def test_material_gate_is_unaffected_by_hydraulics():
    """Hydraulics do not open GC-001 or CC-001 on an element with no material."""
    element = service_element(
        material_a="Unknown",
        flow_velocity_ms=1.4,
        operating_temp_c=60.0,
        velocity_source=HYDRAULIC_SOURCE_IFC,
    )
    for spec in (GALVANIC, CREVICE):
        gated = _preflight(element, spec)
        assert gated is not None, f"{spec.code} ran on an element with no material"
        assert gated[0] == "material_unresolved"


# ---------------------------------------------------------------------------
# 3. The generator writes the proportions it claims
# ---------------------------------------------------------------------------


def test_generator_element_count(demo_elements):
    """300-500 MEP elements, across at least six systems."""
    assert len(demo_elements) == len(SYSTEMS) * ELEMENTS_PER_SYSTEM
    assert 300 <= len(demo_elements) <= 500
    assert len({e.system for e in demo_elements}) >= 6


def test_generator_hydraulic_proportion(demo_elements):
    """Roughly 70% of elements carry hydraulic data; exactly 70% by design."""
    with_hydraulics = sum(1 for e in demo_elements if e.flow_velocity_ms is not None)
    assert with_hydraulics == pytest.approx(len(demo_elements) * 0.70, abs=1)


def test_generator_missing_material_proportion(demo_elements):
    """Roughly 10% of elements carry no material at all."""
    without = sum(1 for e in demo_elements if e.material_a == "Unknown")
    assert without == pytest.approx(len(demo_elements) * 0.10, abs=1)


def test_generator_covers_the_six_required_materials(demo_elements):
    """Carbon steel, copper, SS316, galvanised, brass and HDPE all appear."""
    materials = {e.material_a for e in demo_elements}
    assert {
        "Carbon_steel_mild",
        "Copper",
        "SS_316_passive",
        "Galvanized_steel",
        "Brass_naval",
        "HDPE",
    } <= materials


def test_generator_covers_a_mix_of_environments(demo_elements):
    """More than one environment class, so the model is not uniformly indoor."""
    assert len({e.location_tag for e in demo_elements}) >= 3


def test_the_two_absences_are_decorrelated(demo_elements):
    """Some element has hydraulics but no material, and some has neither.

    Without both combinations the model cannot show MC-001 scoring an element
    that GC-001 and CC-001 refuse, which is the case most likely to be got
    wrong and the reason the two absences use different strides.
    """
    unknown = [e for e in demo_elements if e.material_a == "Unknown"]
    assert any(e.flow_velocity_ms is not None for e in unknown)
    assert any(e.flow_velocity_ms is None for e in unknown)


def test_proportion_helpers_agree_with_the_written_model(demo_elements):
    """has_hydraulics/has_material describe the file the generator writes.

    They are the functions the docstring's proportions are computed from, so a
    drift between them and the model would make the reported mix a fiction.
    """
    expected_hydraulics = sum(
        1 for i in range(ELEMENTS_PER_SYSTEM) if has_hydraulics(i)
    ) * len(SYSTEMS)
    expected_material = sum(
        1 for i in range(ELEMENTS_PER_SYSTEM) if not has_material(i)
    ) * len(SYSTEMS)

    assert sum(1 for e in demo_elements if e.flow_velocity_ms is not None) == (
        expected_hydraulics
    )
    assert sum(1 for e in demo_elements if e.material_a == "Unknown") == expected_material
