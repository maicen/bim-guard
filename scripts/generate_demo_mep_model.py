"""Generate data/test_hospital_mep_demo.ifc: an MEP model that carries real data.

WHY THIS FILE EXISTS

    The existing fixtures leave the corrosion engines nothing to read. The
    minimal model from ``scripts/generate_minimal_corrosion_ifc.py`` has five
    elements and no hydraulic data at all, and
    ``app/modules/blue_halo/build_test_ifc.py`` (which produces
    ``data/test_hospital_mep_scenario.ifc``) is a Blue Halo clearance fixture
    that happens to contain pipes. Neither exercises the pre-flight gate in
    ``phase_6c_corrosion_ui.py`` in both directions, because on both of them
    MC-001 is refused for *every* element: no velocity, no temperature, no
    dead leg.

    This model is built so each of the five mechanisms sees both cases. Some
    elements carry material and hydraulics and are scored; some carry neither
    and come out Undetermined. The proportions are deliberate, deterministic,
    and asserted in tests/test_demo_mep_model.py.

WHAT DECIDES THE SHAPE OF THIS FILE

    Every naming choice below is driven by what the readers actually match on,
    verified against the source rather than assumed:

      - Material strings must resolve in TWO independent tables. The corrosion
        path uses MATERIAL_ALIASES (bimguard_corrosion_engine.py:54) via
        ifc_parser._match_material_key (ifc_parser.py:213); the network path
        uses _MATERIAL_RULES (piping_producer.py:147). "Stainless Steel 316"
        hits both ("316" / "316"); a bare "SS316" would hit both too, but
        "Inox" would hit neither. The strings in MATERIALS are chosen to
        resolve in both.

      - System classification is by keyword against the IFC system name, the
        element name and the predefined type (piping_producer.classify_system,
        _SYSTEM_RULES at piping_producer.py:438). There is no rule for "DCW" or
        "DHW", so the *spelled-out* service appears in both the system name and
        every element name: "Cold Water", "Hot Water", "Chilled", "LTHW",
        "Condensate", "Fire".

      - Elements are contained in the STOREY, not in the space, and the zone
        word is carried in the element name. This is not tidiness, it is forced:
        get_floor_name (ifc_parser.py:295) returns a floor only for an element
        contained directly in an IfcBuildingStorey, while the environment is
        resolved from ``space_name + " " + element.Name``
        (ifc_parser.py:359-361). Containing in the space would give a good
        environment and "Unknown floor"; this way both are populated.

      - "Ceiling Void" matches no SPACE_TO_ENV keyword (ifc_parser.py:125), so
        those elements resolve to the module's indoor default with
        ENVIRONMENT_SOURCE_DEFAULT. That is intentional: a model where every
        environment is a confident reading would not exercise the provenance
        fields either.

PROPERTY SETS WRITTEN

    Pset_PipeSegmentOccurrence   OperatingTemperature, InnerDiameter,
                                 OuterDiameter
    Pset_BimGuardHydraulics      FlowVelocity, DeadLegLength, IsDeadLeg,
                                 SystemType
    Pset_BimGuardCouple          SecondaryMaterial

    ``OperatingTemperature`` is not a new invention: it is the first entry in
    TEMPERATURE_PROPERTY_KEYS (piping_producer.py:810), so the network path
    already reads it and tags it TEMPERATURE_SOURCE_IFC ("ifc_property").
    Pset_PipeSegmentOccurrence is a real IFC4 pset and InnerDiameter /
    OuterDiameter are its real properties.

    FlowVelocity, DeadLegLength and IsDeadLeg have no buildingSMART equivalent
    for a pipe segment — IFC4 defines no flow-velocity property on
    IfcPipeSegment — so they go in a clearly vendor-prefixed pset rather than
    being smuggled into a standard one under a plausible-looking name. A reader
    can tell at a glance which of these values came from a standard and which
    is this project's own convention.

    SecondaryMaterial gets its own pset for the same reason plus one more: it
    is not hydraulic data, and it has to vary independently of the hydraulic
    set. A couple must be able to land on an element carrying no flow data,
    which sharing one pset would force into writing a half-empty hydraulics
    block. IFC has no standard property here either — models express contact
    through geometry, and which bracket a pipe is clamped to is a design
    statement rather than something derivable from the pipe's own IfcMaterial.

DETERMINISM

    GlobalIds come from uuid5 over a fixed namespace, and the data mix is
    chosen by element index rather than by a random draw, so two runs on two
    machines produce byte-identical output and the proportions below are exact
    rather than approximate.

Usage:
    uv run python scripts/generate_demo_mep_model.py
    uv run python scripts/generate_demo_mep_model.py --out some/where.ifc
"""

from __future__ import annotations

import argparse
import uuid
from pathlib import Path

import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.geometry
import ifcopenshell.api.group
import ifcopenshell.api.material
import ifcopenshell.api.pset
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.unit
import ifcopenshell.guid

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO_ROOT / "data" / "test_hospital_mep_demo.ifc"

_GUID_NAMESPACE = uuid.UUID("b1ce4a10-0000-4000-8000-000000000002")

#: Written into the IFC header so the file does not change between runs.
_FIXED_TIMESTAMP = "2026-01-01T00:00:00"

# ---------------------------------------------------------------------------
# The data mix
# ---------------------------------------------------------------------------
# Chosen by index, not by random draw, so the proportions are exact and a test
# can assert them. Over each block of 20 elements:
#
#   hydraulics   14 of 20 carry them   (i % 10 < 7)          -> 70%
#   material     18 of 20 carry one    (i % 20 not in {3,17}) -> 90%
#
# The two absences are deliberately decorrelated. Index 3 has hydraulics but no
# material; index 17 has neither. Without that, "no material" would be a strict
# subset of "no hydraulics" and no element would ever exercise the case the
# gate is most likely to get wrong: hydraulics present, material absent, so
# MC-001 must run while GC-001 and CC-001 must not.

#: Fraction of elements carrying a full hydraulic property set.
HYDRAULICS_EVERY = 7  # of each 10
#: Indices within each block of 20 that carry no IfcMaterial association.
NO_MATERIAL_INDICES = frozenset({3, 17})


def has_hydraulics(index: int) -> bool:
    """Whether element ``index`` carries Pset_BimGuardHydraulics."""
    return index % 10 < HYDRAULICS_EVERY


def has_material(index: int) -> bool:
    """Whether element ``index`` carries an IfcMaterial association."""
    return (index % 20) not in NO_MATERIAL_INDICES


def has_couple(index: int) -> bool:
    """Whether element ``index`` declares a second material at its junction.

    Two of every five, which lands on no element in NO_MATERIAL_INDICES (3 and
    17, neither of which satisfies ``index % 5 < 2``). A bracket material on an
    element whose own material is unknown would be a couple with one side
    missing — GC-001 is refused on those by the material gate anyway, so the
    property would be unreadable noise.
    """
    return index % 5 < 2 and has_material(index)


# The second material at the junction: the bracket, hanger or fixing the pipe
# is clamped to. Chosen per primary material so the pairs are real ones rather
# than a random draw, and so the demo carries couples a reviewer can check by
# eye against the galvanic series:
#
#   copper on galvanised steel   severe    ~0.85 V apart, zinc is strongly anodic
#   carbon steel on SS316        severe    passive stainless is strongly cathodic
#   galvanised steel on copper   severe    the same couple from the other side
#   copper on brass              benign    both copper-base, ~0.05 V apart
#   carbon steel on carbon steel none      same material, no couple
#
# HDPE is deliberately absent: a plastic pipe has no galvanic couple, so
# declaring a bracket material against it would state something untrue.
SECONDARY_MATERIALS: dict[str, tuple[str, ...]] = {
    "Copper": ("Galvanised Steel", "Brass"),
    "Carbon Steel": ("Stainless Steel 316", "Carbon Steel"),
    "Galvanised Steel": ("Copper",),
    "Stainless Steel 316": ("Carbon Steel",),
    "Brass": ("Copper",),
    "HDPE": (),
}


def secondary_material_for(primary: str, index: int) -> str | None:
    """Return the declared second material for ``primary``, or None."""
    candidates = SECONDARY_MATERIALS.get(primary, ())
    if not candidates:
        return None
    return candidates[(index // 5) % len(candidates)]


# ---------------------------------------------------------------------------
# Systems
# ---------------------------------------------------------------------------
# (key, IfcSystem name, name fragment carried by every element, predefined
#  type, design temperature C, design velocity m/s, materials in rotation)
#
# The name fragment is what classify_system matches on; see the module
# docstring. Materials are rotated per element so every system carries a mix
# and the galvanic pairings are not uniform.

SYSTEMS: tuple[dict, ...] = (
    {
        "key": "dcw",
        "system_name": "Domestic Cold Water",
        "fragment": "Cold Water",
        "predefined_type": "DOMESTICCOLDWATER",
        "temperature_c": 12.0,
        "velocity_ms": 1.2,
        "materials": ("Copper", "HDPE", "Galvanised Steel", "Brass"),
    },
    {
        "key": "dhw",
        "system_name": "Domestic Hot Water",
        "fragment": "Hot Water",
        "predefined_type": "DOMESTICHOTWATER",
        "temperature_c": 60.0,
        "velocity_ms": 0.9,
        "materials": ("Copper", "Stainless Steel 316", "Brass"),
    },
    {
        "key": "chw",
        "system_name": "Chilled Water",
        "fragment": "Chilled",
        "predefined_type": "CHILLEDWATER",
        "temperature_c": 6.0,
        "velocity_ms": 1.8,
        "materials": ("Carbon Steel", "Stainless Steel 316"),
    },
    {
        "key": "lthw",
        "system_name": "LTHW Heating",
        "fragment": "LTHW",
        "predefined_type": "HEATING",
        "temperature_c": 80.0,
        "velocity_ms": 1.5,
        "materials": ("Carbon Steel", "Copper"),
    },
    {
        "key": "cond",
        "system_name": "Condensate Drain",
        "fragment": "Condensate",
        "predefined_type": "CONDENSATE",
        "temperature_c": 30.0,
        "velocity_ms": 0.3,
        "materials": ("Stainless Steel 316", "HDPE", "Copper"),
    },
    {
        "key": "fire",
        "system_name": "Fire Main",
        "fragment": "Fire",
        "predefined_type": "FIREPROTECTION",
        "temperature_c": 15.0,
        "velocity_ms": 0.05,  # charged and static until a head operates
        "materials": ("Galvanised Steel", "Carbon Steel"),
    },
)

#: Zone word carried in the element name, and the environment it resolves to.
#: "Ceiling Void" is here precisely because it matches nothing — see docstring.
ZONES: tuple[str, ...] = ("Plant Room", "Riser", "Ceiling Void", "External Roof")

#: Storeys, in order. Elements are contained directly in one of these.
STOREYS: tuple[str, ...] = ("Level 00 Basement", "Level 01", "Level 02", "Level 03 Roof")

#: (IfcClass, predefined type or None) rotated across elements. Every class
#: here appears in IFC_SERVICE_LABELS (ifc_parser.py:94) so the parser scans it.
ELEMENT_CLASSES: tuple[tuple[str, str | None], ...] = (
    ("IfcPipeSegment", "RIGIDSEGMENT"),
    ("IfcPipeSegment", "RIGIDSEGMENT"),
    ("IfcPipeSegment", "RIGIDSEGMENT"),
    ("IfcPipeFitting", "BEND"),
    ("IfcValve", "ISOLATING"),
)

#: Elements per system. 6 systems x 70 = 420, inside the 300-500 target.
ELEMENTS_PER_SYSTEM = 70

#: Nominal bore in mm, rotated so dead-leg L/D ratios vary across classes.
DIAMETERS_MM: tuple[float, ...] = (15.0, 22.0, 28.0, 54.0, 108.0)

_EXPLICIT_GUIDS: set[str] = set()


def stable_guid(key: str) -> str:
    """Return a deterministic IFC GlobalId (22-char base64) for ``key``."""
    guid = ifcopenshell.guid.compress(uuid.uuid5(_GUID_NAMESPACE, key).hex)
    _EXPLICIT_GUIDS.add(guid)
    return guid


def _box_mesh(file: ifcopenshell.file, lo: tuple, hi: tuple):
    """Build an IfcTriangulatedFaceSet box spanning lo..hi in world metres."""
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    coords = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    ]
    faces = [
        (1, 3, 2), (1, 4, 3),
        (5, 6, 7), (5, 7, 8),
        (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6),
        (3, 4, 8), (3, 8, 7),
        (4, 1, 5), (4, 5, 8),
    ]
    point_list = file.create_entity("IfcCartesianPointList3D", CoordList=coords)
    return file.create_entity(
        "IfcTriangulatedFaceSet", Coordinates=point_list, Closed=True, CoordIndex=faces
    )


def hydraulic_properties(system: dict, index: int, diameter_mm: float) -> dict:
    """Return the Pset_BimGuardHydraulics values for one element.

    Every fourth element is a dead leg: velocity drops to near zero and a real
    length is written, so MC-001 sees a spread of flow and dead-leg classes
    rather than one value repeated 294 times.
    """
    is_dead_leg = index % 4 == 3
    if is_dead_leg:
        velocity = 0.0
        # L/D from ~2 to ~40, so DL1_SHORT through DL4_CRITICAL all occur.
        dead_leg_length = round((diameter_mm / 1000.0) * (2 + (index % 5) * 9), 3)
    else:
        # Vary around the system's design velocity so the flow classes spread.
        velocity = round(system["velocity_ms"] * (0.5 + 0.25 * (index % 5)), 3)
        dead_leg_length = 0.0
    return {
        "FlowVelocity": float(velocity),
        "DeadLegLength": float(dead_leg_length),
        "IsDeadLeg": bool(is_dead_leg),
        "SystemType": system["predefined_type"],
    }


def build_model() -> ifcopenshell.file:
    """Build the complete demo model in memory."""
    file = ifcopenshell.file(schema="IFC4")

    project = ifcopenshell.api.root.create_entity(
        file, ifc_class="IfcProject", name="BIM-Guard Corrosion Demo Hospital"
    )
    project.GlobalId = stable_guid("project")

    length_unit = ifcopenshell.api.unit.add_si_unit(file, unit_type="LENGTHUNIT")
    area_unit = ifcopenshell.api.unit.add_si_unit(file, unit_type="AREAUNIT")
    volume_unit = ifcopenshell.api.unit.add_si_unit(file, unit_type="VOLUMEUNIT")
    ifcopenshell.api.unit.assign_unit(file, units=[length_unit, area_unit, volume_unit])

    model_context = ifcopenshell.api.context.add_context(file, context_type="Model")
    body_context = ifcopenshell.api.context.add_context(
        file,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=model_context,
    )

    site = ifcopenshell.api.root.create_entity(file, ifc_class="IfcSite", name="Demo Site")
    site.GlobalId = stable_guid("site")
    building = ifcopenshell.api.root.create_entity(
        file, ifc_class="IfcBuilding", name="Demo Hospital"
    )
    building.GlobalId = stable_guid("building")
    ifcopenshell.api.aggregate.assign_object(file, products=[site], relating_object=project)
    ifcopenshell.api.aggregate.assign_object(file, products=[building], relating_object=site)

    storeys = []
    for level, storey_name in enumerate(STOREYS):
        storey = ifcopenshell.api.root.create_entity(
            file, ifc_class="IfcBuildingStorey", name=storey_name
        )
        storey.GlobalId = stable_guid(f"storey:{storey_name}")
        storey.Elevation = float(level * 4)
        ifcopenshell.api.aggregate.assign_object(
            file, products=[storey], relating_object=building
        )
        storeys.append(storey)

    # Materials are created once and shared, which is how a real authoring tool
    # writes them and keeps the file small.
    material_cache: dict[str, object] = {}

    def material_for(name: str):
        if name not in material_cache:
            material_cache[name] = ifcopenshell.api.material.add_material(file, name=name)
        return material_cache[name]

    for system in SYSTEMS:
        group = ifcopenshell.api.root.create_entity(
            file, ifc_class="IfcDistributionSystem", name=system["system_name"]
        )
        group.GlobalId = stable_guid(f"system:{system['key']}")
        members = []

        for index in range(ELEMENTS_PER_SYSTEM):
            ifc_class, predefined_type = ELEMENT_CLASSES[index % len(ELEMENT_CLASSES)]
            zone = ZONES[index % len(ZONES)]
            storey = storeys[index % len(storeys)]
            diameter_mm = DIAMETERS_MM[index % len(DIAMETERS_MM)]
            material_name = system["materials"][index % len(system["materials"])]

            # The name carries the service fragment (for classify_system) and
            # the zone word (for resolve_environment_from_space, which reads
            # space name and element name as one string).
            name = (
                f"{system['key'].upper()}-{index + 1:03d} "
                f"{system['fragment']} {zone} DN{int(diameter_mm)}"
            )
            key = f"{system['key']}:{index}"

            element = ifcopenshell.api.root.create_entity(
                file, ifc_class=ifc_class, name=name, predefined_type=predefined_type
            )
            element.GlobalId = stable_guid(key)

            ifcopenshell.api.geometry.edit_object_placement(
                file, product=element, matrix=None, is_si=True
            )

            # A 2 m run, laid out on a grid so no two elements are coincident.
            x0 = float(index % 10) * 3.0
            y0 = float(index // 10) * 2.0
            z0 = storey.Elevation + 2.5
            radius = diameter_mm / 2000.0
            representation = file.create_entity(
                "IfcShapeRepresentation",
                ContextOfItems=body_context,
                RepresentationIdentifier="Body",
                RepresentationType="Tessellation",
                Items=[
                    _box_mesh(
                        file,
                        (x0, y0 - radius, z0 - radius),
                        (x0 + 2.0, y0 + radius, z0 + radius),
                    )
                ],
            )
            ifcopenshell.api.geometry.assign_representation(
                file, product=element, representation=representation
            )
            ifcopenshell.api.spatial.assign_container(
                file, products=[element], relating_structure=storey
            )

            if has_material(index):
                ifcopenshell.api.material.assign_material(
                    file,
                    products=[element],
                    type="IfcMaterial",
                    material=material_for(material_name),
                )

            # Geometry pset is written for every element; only the hydraulic
            # one is withheld. Diameter is not a hydraulic input and its
            # absence would confound the gate test.
            psets: dict[str, dict] = {
                "Pset_PipeSegmentOccurrence": {
                    "InnerDiameter": float(diameter_mm),
                    "OuterDiameter": float(diameter_mm + 2.0),
                }
            }
            if has_hydraulics(index):
                psets["Pset_PipeSegmentOccurrence"]["OperatingTemperature"] = float(
                    system["temperature_c"]
                )
                psets["Pset_BimGuardHydraulics"] = hydraulic_properties(
                    system, index, diameter_mm
                )

            # A sibling pset rather than another key in Pset_BimGuardHydraulics.
            # The bracket material is not hydraulic data, and more practically
            # the two sets have to vary independently: a couple must be able to
            # appear on an element that carries no flow data, which a shared
            # pset would prevent without writing a half-empty hydraulics block.
            if has_couple(index):
                secondary = secondary_material_for(material_name, index)
                if secondary is not None:
                    psets["Pset_BimGuardCouple"] = {"SecondaryMaterial": secondary}

            for pset_name, properties in psets.items():
                pset = ifcopenshell.api.pset.add_pset(
                    file, product=element, name=pset_name
                )
                pset.GlobalId = stable_guid(f"{key}:{pset_name}")
                ifcopenshell.api.pset.edit_pset(file, pset=pset, properties=properties)

            members.append(element)

        ifcopenshell.api.group.assign_group(file, products=members, group=group)

    _normalise(file)
    return file


def _normalise(file: ifcopenshell.file) -> None:
    """Make the written file byte-stable across runs.

    ifcopenshell mints a random GlobalId for every entity it creates that this
    script does not name explicitly (the relationship objects, mostly) and
    stamps the current time into the header. Both would make every run produce
    a different file, which defeats committing the generator instead of the
    model: a reviewer could not tell a real change from a re-run.
    """
    for entity in sorted(file.by_type("IfcRoot"), key=lambda e: e.id()):
        if entity.GlobalId in _EXPLICIT_GUIDS:
            continue
        entity.GlobalId = stable_guid(f"{entity.is_a()}-{entity.id()}")

    # A few aggregate attributes are populated from Python sets, so their
    # serialised order varies between runs. Sorting by entity id fixes them.
    for unit_assignment in file.by_type("IfcUnitAssignment"):
        unit_assignment.Units = tuple(sorted(unit_assignment.Units, key=lambda u: u.id()))

    for rel in file.by_type("IfcRelContainedInSpatialStructure"):
        rel.RelatedElements = tuple(sorted(rel.RelatedElements, key=lambda e: e.id()))

    # The storeys aggregated into the building arrive in set order, so this one
    # relationship serialised differently between runs even with every GlobalId
    # pinned. Caught by regenerating twice and diffing, not by inspection.
    for rel in file.by_type("IfcRelAggregates"):
        rel.RelatedObjects = tuple(sorted(rel.RelatedObjects, key=lambda e: e.id()))

    for rel in file.by_type("IfcRelAssignsToGroup"):
        rel.RelatedObjects = tuple(sorted(rel.RelatedObjects, key=lambda e: e.id()))

    for rel in file.by_type("IfcRelAssociatesMaterial"):
        rel.RelatedObjects = tuple(sorted(rel.RelatedObjects, key=lambda e: e.id()))


def write_model(output_path: Path = DEFAULT_OUT) -> Path:
    """Build the model and write it to ``output_path``."""
    file = build_model()

    header = file.header.file_name
    header.name = output_path.name
    header.time_stamp = _FIXED_TIMESTAMP
    header.author = ("BIMGUARD AI",)
    header.organization = ("BIMGUARD AI",)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    file.write(str(output_path))
    return output_path


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Where to write the model (default: {DEFAULT_OUT})",
    )
    args = parser.parse_args()

    path = write_model(args.out)
    total = len(SYSTEMS) * ELEMENTS_PER_SYSTEM
    with_hydraulics = sum(
        1 for i in range(ELEMENTS_PER_SYSTEM) if has_hydraulics(i)
    ) * len(SYSTEMS)
    without_material = sum(
        1 for i in range(ELEMENTS_PER_SYSTEM) if not has_material(i)
    ) * len(SYSTEMS)
    with_material = total - without_material
    coupled = sum(
        1
        for system in SYSTEMS
        for i in range(ELEMENTS_PER_SYSTEM)
        if has_couple(i)
        and secondary_material_for(system["materials"][i % len(system["materials"])], i)
        is not None
    )
    print(f"Wrote {path} ({path.stat().st_size / 1024:.0f} KB)")
    print(f"  elements          {total}")
    print(f"  with hydraulics   {with_hydraulics} ({with_hydraulics / total:.0%})")
    print(f"  without material  {without_material} ({without_material / total:.0%})")
    print(
        f"  with couple       {coupled} "
        f"({coupled / with_material:.0%} of the {with_material} carrying a material)"
    )


if __name__ == "__main__":
    main()
