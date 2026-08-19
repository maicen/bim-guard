"""
Synthetic PipingElement fixtures for comparator development and testing.

WHY THIS EXISTS
    The only MEP model available for testing (Infra-Plumbing.ifc) is concrete
    drainage: every material normalises to "Unknown", no two endpoints are
    closer than 1.31 m, and the model carries no IFC ports. It exercises
    neither the corrosion comparators nor adjacency detection. This module
    supplies a network that does.

TEST-FIRST CONTRACT
    EXPECTED_SCENARIOS declares, per scenario, what MM-001 and XM-001 are
    supposed to conclude and why. The fixture asserts only the preconditions
    (materials adjacent, environment set, tier resolved); the verdicts become
    executable assertions once the engines exist. Rule-pack cell values are
    reviewed against these named scenarios rather than against abstract
    numbers.

NETWORK LAYOUT
    Five groups, each on its own Y lane 6 m apart so lanes never cross-link.
    Segments run along +X with endpoints exactly coincident, so Tier 2
    adjacency resolves at any tolerance.

        y= 0   Domestic hot water   8 elements  Cu + brass, one carbon steel
        y= 6   Chilled water        6 elements  carbon steel, one SS316
        y=12   Pool plant room      5 elements  SS316 throughout, T3_CHLORIDE
        y=18   Fire protection      4 elements  galvanised, no couples
        y=24   Connectivity probes  3 elements  2 port-linked, 1 geometry-less

    Total 26 elements. The issue text says 25; the per-group counts sum to 26
    and are what the scenarios depend on, so the counts win.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from app.modules.module2_ifc_read.piping_producer import _build_adjacency
from app.modules.module2_ifc_read.piping_schema import (
    BoundingBox,
    Centerline,
    ElementSubtype,
    EnvironmentClass,
    JointType,
    PipingElement,
    PipingSystem,
    Point3D,
)

SEGMENT_LENGTH_M = 2.5
LANE_SPACING_M = 6.0
PIPE_HEIGHT_M = 3.0

_MATERIAL_RAW = {
    "Copper_C12200": "Copper C12200",
    "Brass_C46400": "Naval Brass",
    "CarbonSteel": "Carbon Steel S275",
    "SS316": "Stainless Steel, Grade 316",
    "GalvanisedSteel": "Hot Dip Galvanised Steel",
}

_PREN = {"SS316": 25.2, "SS304": 18.0}


# ---------------------------------------------------------------------------
# Expected outcomes — the review contract
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Scenario:
    """One named situation the comparators must reach a known verdict on.

    Attributes:
        name: Human-readable scenario label.
        mechanism: "MM-001", "XM-001", or "tiering" for producer behaviour.
        expected_band: Verdict the mechanism must return — "Critical",
            "High", "Medium", "Low", or "None" for no finding.
        element_ids: Elements the verdict applies to.
        rationale: Why this outcome is expected, in engineering terms.
    """

    name: str
    mechanism: str
    expected_band: str
    element_ids: tuple[str, ...]
    rationale: str


EXPECTED_SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        name="Copper to carbon steel in domestic hot water",
        mechanism="XM-001",
        expected_band="High",
        element_ids=("DHW-P04", "DHW-S05", "DHW-P06"),
        rationale=(
            "Carbon steel section spliced into a copper hot-water run with plain "
            "threaded joints. Copper is strongly cathodic to steel and the two "
            "share a continuous electrolyte, so the steel corrodes preferentially "
            "at both junctions. No dielectric union is present to break continuity."
        ),
    ),
    Scenario(
        name="Carbon steel to SS316 pump connection in chilled water",
        mechanism="XM-001",
        expected_band="Medium",
        element_ids=("CHW-P05", "CHW-M06"),
        rationale=(
            "Stainless is cathodic to carbon steel, but the chilled-water loop is "
            "closed and oxygen-depleted, and the stainless area is small relative "
            "to the steel run. Real but materially less severe than the copper case."
        ),
    ),
    Scenario(
        name="SS316 in chlorinated pool plant room",
        mechanism="MM-001",
        expected_band="High",
        element_ids=("POOL-P01", "POOL-F02", "POOL-P03", "POOL-F04", "POOL-P05"),
        rationale=(
            "SS316 (PREN 25.2) in T3_CHLORIDE pool service. Chloride pitting and "
            "stress-corrosion cracking are the governing mechanisms; IMOA directs "
            "designers to 2205 or higher for pool-hall environments. This is the "
            "thesis case study, so the matrix must flag it rather than pass it."
        ),
    ),
    Scenario(
        name="SS316 to SS316 pool flanges",
        mechanism="XM-001",
        expected_band="None",
        element_ids=("POOL-P01", "POOL-F02", "POOL-P03", "POOL-F04", "POOL-P05"),
        rationale=(
            "Identical materials throughout. No galvanic driving voltage exists, "
            "so XM-001 must stay silent here even though MM-001 flags the same "
            "elements on media grounds. Separates the two mechanisms cleanly."
        ),
    ),
    Scenario(
        name="Galvanised fire loop, no dissimilar couples",
        mechanism="XM-001",
        expected_band="None",
        element_ids=("FIRE-P01", "FIRE-P02", "FIRE-P03", "FIRE-P04"),
        rationale=(
            "Uniform galvanised steel with no other material in contact. The "
            "negative control for XM-001. See MATRIX_CONFLICT below: this is NOT "
            "a negative control for MM-001 under the current draft matrix."
        ),
    ),
    Scenario(
        name="Port-connected pair beyond geometric range",
        mechanism="tiering",
        expected_band="Tier1",
        element_ids=("PORT-A", "PORT-B"),
        rationale=(
            "Placed 400 m apart so no proximity test can link them. Only authored "
            "IfcRelConnectsPorts can, proving Tier 1 overrides geometry rather "
            "than merely supplementing it."
        ),
    ),
    Scenario(
        name="Element with no geometry",
        mechanism="tiering",
        expected_band="Tier3",
        element_ids=("NOGEO-01",),
        rationale=(
            "No centerline, no centroid, no ports. Connectivity is indeterminable, "
            "so XM-001 must skip it with a data-quality issue rather than read "
            "joined_to == [] as proof of isolation."
        ),
    ),
)

# Flagged during fixture construction, before the matrix was finalised.
MATRIX_CONFLICT = (
    "The fire-protection loop is specified as a negative control, and it is a "
    "clean one for XM-001 (uniform material, no couples). It is NOT one for "
    "MM-001: FIRE_SPRINKLER maps to media 'stagnant_water', and the draft matrix "
    "scores GalvanisedSteel/stagnant_water at 0.70, which lands in the High band. "
    "That is arguably correct engineering - corrosion and MIC in wet sprinkler "
    "systems is a documented failure mode - but it means the loop cannot serve as "
    "an all-mechanisms negative control. Resolve by either scoping the control to "
    "XM-001, or revisiting that cell."
)


# ---------------------------------------------------------------------------
# Tier 1 support
# ---------------------------------------------------------------------------


class _Port:
    """Minimal IfcDistributionPort stand-in with a stable entity id."""

    def __init__(self, entity_id: int) -> None:
        self._id = entity_id

    def id(self) -> int:
        """Return the entity id used to key port ownership."""
        return self._id

    def is_a(self, name: str = "") -> object:
        """Report this object as an IfcPort."""
        return "IfcPort" if not name else name in ("IfcPort", "IfcDistributionPort")


class _Owner:
    """An element that owns a port, identified by GlobalId."""

    def __init__(self, global_id: str) -> None:
        self.GlobalId = global_id


class _RelPortToElement:
    """IfcRelConnectsPortToElement stand-in."""

    def __init__(self, port: _Port, owner: _Owner) -> None:
        self.RelatingPort = port
        self.RelatedElement = owner


class _RelConnectsPorts:
    """IfcRelConnectsPorts stand-in."""

    def __init__(self, a: _Port, b: _Port) -> None:
        self.RelatingPort = a
        self.RelatedPort = b


class SyntheticPortModel:
    """Model stand-in exposing authored port connectivity for named elements.

    Lets the fixture exercise Tier 1 without an IFC file behind it.
    """

    def __init__(self, connected_pairs: tuple[tuple[str, str], ...] = ()) -> None:
        """Build port relationships for each (element_id, element_id) pair."""
        self._port_rels: list[_RelPortToElement] = []
        self._connections: list[_RelConnectsPorts] = []
        next_id = 1
        for left, right in connected_pairs:
            port_left, port_right = _Port(next_id), _Port(next_id + 1)
            next_id += 2
            self._port_rels.append(_RelPortToElement(port_left, _Owner(left)))
            self._port_rels.append(_RelPortToElement(port_right, _Owner(right)))
            self._connections.append(_RelConnectsPorts(port_left, port_right))

    def by_type(self, name: str) -> list:
        """Return the stand-in entities for a requested IFC type."""
        if name == "IfcRelConnectsPortToElement":
            return self._port_rels
        if name == "IfcRelConnectsPorts":
            return self._connections
        return []


# ---------------------------------------------------------------------------
# Element construction
# ---------------------------------------------------------------------------


def _segment(
    element_id: str,
    *,
    name: str,
    material: str,
    system: PipingSystem,
    environment: EnvironmentClass,
    diameter_mm: float,
    lane_y: float,
    position: int,
    subtype: ElementSubtype = "pipe_segment",
    ifc_class: str = "IfcPipeSegment",
    joint_type: Optional[JointType] = JointType.JT003_THREADED,
    temperature_c: Optional[float] = None,
    space_name: str = "",
) -> PipingElement:
    """Build one endpoint-coincident segment on a lane.

    Segment *position* n spans x from n*2.5 to (n+1)*2.5, so segment n's end
    point is exactly segment n+1's start point.
    """
    x0 = position * SEGMENT_LENGTH_M
    x1 = x0 + SEGMENT_LENGTH_M
    radius_m = (diameter_mm / 1000.0) / 2.0
    surface_area = math.pi * (diameter_mm / 1000.0) * SEGMENT_LENGTH_M

    return PipingElement(
        id=element_id,
        ifc_class=ifc_class,
        subtype=subtype,
        name=name,
        bbox=BoundingBox(
            min=Point3D(x=x0, y=lane_y - radius_m, z=PIPE_HEIGHT_M - radius_m),
            max=Point3D(x=x1, y=lane_y + radius_m, z=PIPE_HEIGHT_M + radius_m),
        ),
        centroid=Point3D(x=(x0 + x1) / 2.0, y=lane_y, z=PIPE_HEIGHT_M),
        centerline=Centerline(
            points=[
                Point3D(x=x0, y=lane_y, z=PIPE_HEIGHT_M),
                Point3D(x=x1, y=lane_y, z=PIPE_HEIGHT_M),
            ]
        ),
        level_name="L01 Plant room",
        space_name=space_name,
        material=material,
        material_raw=_MATERIAL_RAW.get(material, material),
        pren=_PREN.get(material),
        nominal_diameter_mm=diameter_mm,
        outside_diameter_mm=diameter_mm,
        wall_thickness_mm=2.6 if diameter_mm <= 28 else 3.2,
        system=system,
        operating_temperature_c=temperature_c,
        design_pressure_bar=6.0,
        environment_class=environment,
        environment_source="synthetic_fixture",
        joint_type=joint_type,
        wetted_surface_area_m2=round(surface_area, 3),
        exposed_surface_area_m2=round(surface_area, 3),
        properties={"synthetic": True},
    )


def _domestic_hot_water() -> list[PipingElement]:
    """Lane 1 — copper run with brass valves and one carbon steel section.

    DHW-S05 is the deliberate XM-001 target: carbon steel spliced between
    copper, giving two dissimilar junctions with no dielectric break.
    """
    lane = 0.0
    spec: tuple[tuple[str, str, str, ElementSubtype, str], ...] = (
        ("DHW-P01", "DHW riser seg 1", "Copper_C12200", "pipe_segment", "IfcPipeSegment"),
        ("DHW-V02", "DHW isolation valve", "Brass_C46400", "valve", "IfcValve"),
        ("DHW-P03", "DHW riser seg 2", "Copper_C12200", "pipe_segment", "IfcPipeSegment"),
        ("DHW-P04", "DHW riser seg 3", "Copper_C12200", "pipe_segment", "IfcPipeSegment"),
        ("DHW-S05", "DHW steel section", "CarbonSteel", "pipe_segment", "IfcPipeSegment"),
        ("DHW-P06", "DHW riser seg 4", "Copper_C12200", "pipe_segment", "IfcPipeSegment"),
        ("DHW-V07", "DHW regulating valve", "Brass_C46400", "valve", "IfcValve"),
        ("DHW-P08", "DHW riser seg 5", "Copper_C12200", "pipe_segment", "IfcPipeSegment"),
    )
    return [
        _segment(
            element_id,
            name=name,
            material=material,
            system=PipingSystem.DOMESTIC_HOT_WATER,
            environment=EnvironmentClass.T1_INDOOR_DAMP,
            diameter_mm=22.0,
            lane_y=lane,
            position=index,
            subtype=subtype,
            ifc_class=ifc_class,
            temperature_c=60.0,
            space_name="RISER-01",
        )
        for index, (element_id, name, material, subtype, ifc_class) in enumerate(spec)
    ]


def _chilled_water() -> list[PipingElement]:
    """Lane 2 — carbon steel loop with one SS316 pump connection."""
    lane = LANE_SPACING_M
    spec: tuple[tuple[str, str, str, ElementSubtype, str], ...] = (
        ("CHW-P01", "CHW flow seg 1", "CarbonSteel", "pipe_segment", "IfcPipeSegment"),
        ("CHW-P02", "CHW flow seg 2", "CarbonSteel", "pipe_segment", "IfcPipeSegment"),
        ("CHW-P03", "CHW flow seg 3", "CarbonSteel", "pipe_segment", "IfcPipeSegment"),
        ("CHW-P04", "CHW flow seg 4", "CarbonSteel", "pipe_segment", "IfcPipeSegment"),
        ("CHW-P05", "CHW flow seg 5", "CarbonSteel", "pipe_segment", "IfcPipeSegment"),
        ("CHW-M06", "CHW pump connection", "SS316", "pump", "IfcPump"),
    )
    return [
        _segment(
            element_id,
            name=name,
            material=material,
            system=PipingSystem.CHILLED_WATER_FLOW,
            environment=EnvironmentClass.T2_HUMID,
            diameter_mm=100.0,
            lane_y=lane,
            position=index,
            subtype=subtype,
            ifc_class=ifc_class,
            temperature_c=6.0,
            space_name="PLT-CHW",
        )
        for index, (element_id, name, material, subtype, ifc_class) in enumerate(spec)
    ]


def _pool_plant_room() -> list[PipingElement]:
    """Lane 3 — all-SS316 pool circulation in a chlorinated plant room.

    Uniform material, so XM-001 must stay silent while MM-001 flags every
    element on media and environment grounds. This is the thesis case study.
    """
    lane = LANE_SPACING_M * 2
    spec: tuple[tuple[str, str, ElementSubtype, str], ...] = (
        ("POOL-P01", "Pool circulation header seg 1", "pipe_segment", "IfcPipeSegment"),
        ("POOL-F02", "Pool header flange A", "flange", "IfcFlowFitting"),
        ("POOL-P03", "Pool circulation header seg 2", "pipe_segment", "IfcPipeSegment"),
        ("POOL-F04", "Pool header flange B", "flange", "IfcFlowFitting"),
        ("POOL-P05", "Pool circulation header seg 3", "pipe_segment", "IfcPipeSegment"),
    )
    return [
        _segment(
            element_id,
            name=name,
            material="SS316",
            system=PipingSystem.POOL_CIRCULATION,
            environment=EnvironmentClass.T3_CHLORIDE,
            diameter_mm=80.0,
            lane_y=lane,
            position=index,
            subtype=subtype,
            ifc_class=ifc_class,
            joint_type=JointType.JT004_FLANGED_FULL_GASKET,
            temperature_c=28.0,
            space_name="POOL-PLT-01",
        )
        for index, (element_id, name, subtype, ifc_class) in enumerate(spec)
    ]


def _fire_protection() -> list[PipingElement]:
    """Lane 4 — uniform galvanised sprinkler loop, the XM-001 negative control.

    See MATRIX_CONFLICT: uniform material makes this a clean control for
    XM-001 but not for MM-001.
    """
    lane = LANE_SPACING_M * 3
    return [
        _segment(
            f"FIRE-P{index + 1:02d}",
            name=f"Sprinkler main seg {index + 1}",
            material="GalvanisedSteel",
            system=PipingSystem.FIRE_SPRINKLER,
            environment=EnvironmentClass.T1_INDOOR_DAMP,
            diameter_mm=50.0,
            lane_y=lane,
            position=index,
            temperature_c=15.0,
            space_name="FIRE-RISER",
        )
        for index in range(4)
    ]


def _connectivity_probes() -> list[PipingElement]:
    """Lane 5 — two port-linked elements far apart, plus one with no geometry."""
    lane = LANE_SPACING_M * 4
    port_a = _segment(
        "PORT-A",
        name="Port-linked segment A",
        material="CarbonSteel",
        system=PipingSystem.HEATING_FLOW,
        environment=EnvironmentClass.T1_INDOOR_DAMP,
        diameter_mm=15.0,
        lane_y=lane,
        position=0,
        temperature_c=82.0,
        space_name="PLT-HTG",
    )
    # 400 m away: no proximity test can link these, only authored ports.
    port_b = _segment(
        "PORT-B",
        name="Port-linked segment B",
        material="Copper_C12200",
        system=PipingSystem.HEATING_FLOW,
        environment=EnvironmentClass.T1_INDOOR_DAMP,
        diameter_mm=15.0,
        lane_y=lane,
        position=160,
        temperature_c=82.0,
        space_name="PLT-HTG",
    )
    no_geometry = PipingElement(
        id="NOGEO-01",
        ifc_class="IfcPipeSegment",
        subtype="pipe_segment",
        name="Segment with no placement",
        level_name="L01 Plant room",
        material="CarbonSteel",
        material_raw="Carbon Steel S275",
        nominal_diameter_mm=32.0,
        system=PipingSystem.HEATING_FLOW,
        operating_temperature_c=82.0,
        environment_class=EnvironmentClass.UNCLASSIFIED,
        environment_source="synthetic_fixture",
        properties={"synthetic": True},
    )
    return [port_a, port_b, no_geometry]


def generate_synthetic_piping_network(
    *,
    adjacency_tolerance_m: float = 0.05,
) -> list[PipingElement]:
    """Build the 26-element scenario network with adjacency resolved.

    Deterministic — no randomness, so scenario assertions are stable.

    Args:
        adjacency_tolerance_m: Tier 2 endpoint tolerance, default 50 mm.

    Returns:
        26 PipingElement instances with joined_to and connectivity tier
        markers populated, ordered by group.
    """
    elements = (
        _domestic_hot_water()
        + _chilled_water()
        + _pool_plant_room()
        + _fire_protection()
        + _connectivity_probes()
    )
    model = SyntheticPortModel(connected_pairs=(("PORT-A", "PORT-B"),))
    _build_adjacency(model, elements, adjacency_tolerance_m)
    return elements


def dissimilar_material_pairs(elements: list[PipingElement]) -> list[tuple[str, str, str, str]]:
    """List adjacent element pairs whose materials differ.

    Args:
        elements: A generated network.

    Returns:
        Sorted (id_a, material_a, id_b, material_b) tuples — the population
        XM-001 is responsible for assessing.
    """
    by_id = {e.id: e for e in elements}
    seen: set[tuple[str, str]] = set()
    pairs: list[tuple[str, str, str, str]] = []
    for element in elements:
        for other_id in element.joined_to:
            key = tuple(sorted((element.id, other_id)))
            if key in seen or other_id not in by_id:
                continue
            seen.add(key)
            a, b = by_id[key[0]], by_id[key[1]]
            if a.material != b.material:
                pairs.append((a.id, a.material, b.id, b.material))
    return sorted(pairs)
