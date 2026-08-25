"""
app/modules/module2_producer/build_test_ifc.py

Blue Halo — Phase 5 Part A: build the minimal hospital MEP test IFC.

Generates data/test_hospital_mep_scenario.ifc: a small, fully synthetic
IFC4 model carrying one building storey, four structural elements, and
four MEP runs, each positioned to exercise one Blue Halo scenario
end-to-end against a real IFC file rather than mock dataclasses.

DETERMINISM
    Every run produces a byte-identical file. GlobalIds are UUID5-derived
    from stable element keys (not random uuid4), the header timestamp is
    pinned, and no OwnerHistory (which would carry a wall-clock stamp) is
    attached. This matters because the file is a test fixture: a
    nondeterministic fixture makes downstream diffs meaningless.

GEOMETRY REPRESENTATION
    Elements are IfcTriangulatedFaceSet boxes, not IfcExtrudedAreaSolid
    profiles. Deliberate: halo_volume_generator._local_vertices reduces a
    swept solid to its extrusion AXIS only (two points), which would give
    every pipe a zero-thickness bounding box and silently discard the
    diameters and duct cross-section this fixture exists to test. A
    tessellated box yields all eight corners, so the bounding box the
    algorithm reads back is exactly the one specified here.

UNITS
    The IFC is authored in metres (SI, no prefix) — the common real-world
    case, and the one that exercises halo_volume_generator.unit_scale_to_mm's
    metre->millimetre conversion rather than bypassing it.

Usage:
    uv run python app/modules/module2_producer/build_test_ifc.py
"""

from __future__ import annotations

import uuid
from pathlib import Path

import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.geometry
import ifcopenshell.api.material
import ifcopenshell.api.pset
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.unit
import ifcopenshell.guid

REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_PATH = REPO_ROOT / "data" / "test_hospital_mep_scenario.ifc"

# Fixed namespace so uuid5(NAMESPACE, key) — and therefore every GlobalId —
# is stable across runs and machines.
_GUID_NAMESPACE = uuid.UUID("b1ce4a10-0000-4000-8000-000000000001")

_FIXED_TIMESTAMP = "2026-01-01T00:00:00"


# GlobalIds this script assigns from a meaningful key (rather than from an
# entity id), so _normalise leaves them alone.
_EXPLICIT_GUIDS: set[str] = set()


def stable_guid(key: str) -> str:
    """Return a deterministic IFC GlobalId (22-char base64) for `key`."""
    guid = ifcopenshell.guid.compress(uuid.uuid5(_GUID_NAMESPACE, key).hex)
    _EXPLICIT_GUIDS.add(guid)
    return guid


# ---------------------------------------------------------------------------
# Element layout (metres, world coordinates)
# ---------------------------------------------------------------------------
# Each entry is (min_xyz, max_xyz) — an axis-aligned box in world space.
# Values are chosen so the Blue Halo algorithm's own clearance arithmetic
# produces the intended scenario outcomes; see SCENARIO NOTES below.
#
# SCENARIO NOTES / deviations from the Phase 5 brief, and why:
#
#   Hot water pipe (Scenario B) — the brief gives both a bounding range
#   ("X=2-5m, Y=0-2m") and an explicit intent ("crosses CHW near X=2.5m").
#   A diagonal run through that box would cross CHW's centreline at
#   X≈2.75m and give the pipe a misleadingly large axis-aligned bounding
#   box. Modelled instead as a clean perpendicular run along Y at X=2.5m,
#   which satisfies the stated crossing point exactly.
#
#   Fire sprinkler riser (Scenario C) — the brief's "X=7m" and "60mm from
#   the column" are mutually exclusive: the column is pinned at X=5m, so a
#   riser at X=7m sits ~1.8m clear of it, not 60mm, and Scenario C would
#   test nothing. The 60mm gap is the functional requirement (it is what
#   exercises the clearance buffer), so the riser is placed 60mm off the
#   column's +X face instead. Recorded in the element's Pset as
#   ClearGapToColumnMM so the intent is legible in the model itself.

# --- Structure ---
COLUMN_SECTION = 0.400  # 400x400mm column, centred on (5.0, 0.0)
COLUMN_CX, COLUMN_CY = 5.0, 0.0
COLUMN = (
    (COLUMN_CX - COLUMN_SECTION / 2, COLUMN_CY - COLUMN_SECTION / 2, 0.0),
    (COLUMN_CX + COLUMN_SECTION / 2, COLUMN_CY + COLUMN_SECTION / 2, 5.0),
)
BEAM_LOW = ((0.0, 4.8, 2.8), (10.0, 5.2, 3.2))
BEAM_HIGH = ((0.0, 4.8, 3.8), (10.0, 5.2, 4.2))
SLAB = ((0.0, 0.0, 2.8), (10.0, 10.0, 3.0))

# --- MEP ---
# A: chilled water, 50mm OD, along X at Y=0.5m, Z=1.0m.
CHW_OD = 0.050
CHW = ((0.0, 0.5 - CHW_OD / 2, 1.0 - CHW_OD / 2), (3.0, 0.5 + CHW_OD / 2, 1.0 + CHW_OD / 2))

# B: hot water, 38mm OD, along Y at X=2.5m, Z=1.0m — crosses CHW at X=2.5m.
HW_OD = 0.038
HW = ((2.5 - HW_OD / 2, 0.0, 1.0 - HW_OD / 2), (2.5 + HW_OD / 2, 2.0, 1.0 + HW_OD / 2))

# C: fire sprinkler riser, DN32 steel (~40mm OD), vertical, 60mm clear of
# the column's +X face (see SCENARIO NOTES above).
RISER_OD = 0.040
RISER_GAP = 0.060
_riser_x0 = COLUMN[1][0] + RISER_GAP  # 60mm beyond the column's +X face
RISER = ((_riser_x0, -RISER_OD / 2, 0.0), (_riser_x0 + RISER_OD, RISER_OD / 2, 3.0))

# D: exhaust duct, rectangular 1.5m x 0.5m (0.75 sqm > the 0.56 sqm
# bracing threshold), along X at Y=7.0m, Z=2.0m.
DUCT_W, DUCT_H = 1.5, 0.5
DUCT = ((0.0, 7.0 - DUCT_W / 2, 2.0 - DUCT_H / 2), (8.0, 7.0 + DUCT_W / 2, 2.0 + DUCT_H / 2))


def _box_mesh(file: ifcopenshell.file, lo: tuple, hi: tuple) -> ifcopenshell.entity_instance:
    """Build an IfcTriangulatedFaceSet box spanning lo..hi in world metres.

    Coordinates are written in world space with an identity placement, so
    the bounding box the halo algorithm reads back needs no placement
    round-trip to match the values above.
    """
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    coords = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    ]
    # 12 triangles, 1-indexed per IFC's IfcPositiveInteger CoordIndex.
    faces = [
        (1, 3, 2), (1, 4, 3),  # bottom
        (5, 6, 7), (5, 7, 8),  # top
        (1, 2, 6), (1, 6, 5),  # -Y
        (2, 3, 7), (2, 7, 6),  # +X
        (3, 4, 8), (3, 8, 7),  # +Y
        (4, 1, 5), (4, 5, 8),  # -X
    ]
    point_list = file.create_entity("IfcCartesianPointList3D", CoordList=coords)
    return file.create_entity(
        "IfcTriangulatedFaceSet",
        Coordinates=point_list,
        Closed=True,
        CoordIndex=faces,
    )


def _add_element(
    file: ifcopenshell.file,
    context: ifcopenshell.entity_instance,
    storey: ifcopenshell.entity_instance,
    *,
    key: str,
    ifc_class: str,
    name: str,
    box: tuple,
    material_name: str | None = None,
    predefined_type: str | None = None,
    psets: dict[str, dict] | None = None,
) -> ifcopenshell.entity_instance:
    """Create one spatially-contained element with a tessellated box body."""
    element = ifcopenshell.api.root.create_entity(
        file, ifc_class=ifc_class, name=name, predefined_type=predefined_type
    )
    element.GlobalId = stable_guid(key)

    # Identity placement. Required, not incidental: halo_volume_generator's
    # element_bbox_mm returns None outright for an element with no
    # ObjectPlacement, so without this every element would silently produce
    # no bounding box and no halo. Identity is correct here because
    # _box_mesh writes world coordinates directly.
    ifcopenshell.api.geometry.edit_object_placement(file, product=element, matrix=None, is_si=True)

    representation = file.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=context,
        RepresentationIdentifier="Body",
        RepresentationType="Tessellation",
        Items=[_box_mesh(file, box[0], box[1])],
    )
    ifcopenshell.api.geometry.assign_representation(file, product=element, representation=representation)
    ifcopenshell.api.spatial.assign_container(file, products=[element], relating_structure=storey)

    if material_name:
        material = ifcopenshell.api.material.add_material(file, name=material_name)
        ifcopenshell.api.material.assign_material(
            file, products=[element], type="IfcMaterial", material=material
        )

    for pset_name, properties in (psets or {}).items():
        pset = ifcopenshell.api.pset.add_pset(file, product=element, name=pset_name)
        pset.GlobalId = stable_guid(f"{key}:{pset_name}")
        ifcopenshell.api.pset.edit_pset(file, pset=pset, properties=properties)

    return element


def build_model() -> ifcopenshell.file:
    """Author the complete test model in memory."""
    file = ifcopenshell.file(schema="IFC4")

    project = ifcopenshell.api.root.create_entity(file, ifc_class="IfcProject", name="Blue Halo Test Project")
    project.GlobalId = stable_guid("project-001")

    # Metres, SI — exercises the mm conversion downstream. Must follow the
    # IfcProject: assign_unit writes into project.UnitsInContext.
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

    site = ifcopenshell.api.root.create_entity(file, ifc_class="IfcSite", name="Test Site")
    site.GlobalId = stable_guid("site-001")
    building = ifcopenshell.api.root.create_entity(file, ifc_class="IfcBuilding", name="Test Hospital")
    building.GlobalId = stable_guid("building-001")
    storey = ifcopenshell.api.root.create_entity(file, ifc_class="IfcBuildingStorey", name="Level 1")
    storey.GlobalId = stable_guid("storey-001")
    storey.Elevation = 0.0

    ifcopenshell.api.aggregate.assign_object(file, products=[site], relating_object=project)
    ifcopenshell.api.aggregate.assign_object(file, products=[building], relating_object=site)
    ifcopenshell.api.aggregate.assign_object(file, products=[storey], relating_object=building)

    add = lambda **kw: _add_element(file, body_context, storey, **kw)  # noqa: E731

    # --- Structure ---
    add(
        key="column-001", ifc_class="IfcColumn", name="Column C1 (X=5.0m)",
        box=COLUMN, material_name="Concrete",
        psets={"Pset_BlueHaloTest": {"Role": "structure", "SectionMM": 400.0}},
    )
    add(
        key="beam-001", ifc_class="IfcBeam", name="Beam B1 (Y=5.0m, Z=3.0m)",
        box=BEAM_LOW, material_name="Steel",
        psets={"Pset_BlueHaloTest": {"Role": "structure"}},
    )
    add(
        key="beam-002", ifc_class="IfcBeam", name="Beam B2 (Y=5.0m, Z=4.0m)",
        box=BEAM_HIGH, material_name="Steel",
        psets={"Pset_BlueHaloTest": {"Role": "structure"}},
    )
    add(
        key="slab-001", ifc_class="IfcSlab", name="Slab L1 (Z=3.0m)",
        box=SLAB, material_name="Concrete", predefined_type="FLOOR",
        psets={"Pset_BlueHaloTest": {"Role": "structure"}},
    )

    # --- MEP ---
    add(
        key="pipe-chw-001", ifc_class="IfcPipeSegment", name="CHW Pipe (Scenario A - isolated)",
        box=CHW, material_name="Copper_C12200",
        psets={
            "Pset_PipeSegmentTypeCommon": {"NominalDiameter": CHW_OD * 1000, "OuterDiameter": CHW_OD * 1000},
            "Pset_BlueHaloTest": {
                "Role": "mep", "Scenario": "A - isolated",
                "SystemType": "chilled_water", "Material": "Copper_C12200",
            },
        },
    )
    add(
        key="pipe-hw-001", ifc_class="IfcPipeSegment", name="HW Pipe (Scenario B - crosses CHW)",
        box=HW, material_name="Copper_C12200",
        psets={
            "Pset_PipeSegmentTypeCommon": {"NominalDiameter": HW_OD * 1000, "OuterDiameter": HW_OD * 1000},
            "Pset_BlueHaloTest": {
                "Role": "mep", "Scenario": "B - crosses CHW at X=2.5m",
                "SystemType": "hot_water", "Material": "Copper_C12200",
            },
        },
    )
    add(
        key="pipe-sprinkler-001", ifc_class="IfcPipeSegment",
        name="Fire Sprinkler Riser (Scenario C - near column)",
        box=RISER, material_name="CarbonSteel",
        psets={
            "Pset_PipeSegmentTypeCommon": {"NominalDiameter": 32.0, "OuterDiameter": RISER_OD * 1000},
            "Pset_BlueHaloTest": {
                "Role": "mep", "Scenario": "C - 60mm clear of column C1",
                "SystemType": "fire_sprinkler", "Material": "CarbonSteel",
                "AppliesNFPA13": True, "ClearGapToColumnMM": RISER_GAP * 1000,
            },
        },
    )
    add(
        key="duct-exhaust-001", ifc_class="IfcDuctSegment",
        name="Exhaust Duct (Scenario D - duct threshold)",
        box=DUCT, material_name="GalvanisedSteel",
        psets={
            "Pset_DuctSegmentTypeCommon": {
                "NominalWidth": DUCT_W * 1000, "NominalHeight": DUCT_H * 1000,
            },
            "Pset_BlueHaloTest": {
                "Role": "mep", "Scenario": "D - duct threshold",
                "SystemType": "exhaust_air", "Material": "GalvanisedSteel",
                "CrossSectionSQM": DUCT_W * DUCT_H,
            },
        },
    )

    return file


def _normalise(file: ifcopenshell.file) -> None:
    """Make the authored model byte-reproducible.

    Two sources of run-to-run variation survive plain authoring, both from
    ifcopenshell rather than from this script:

      1. Relationship entities (IfcRelAggregates, IfcRelContainedInSpatial-
         Structure, IfcRelAssociatesMaterial, IfcRelDefinesByProperties)
         get random uuid4 GlobalIds. Only the entities this script names
         explicitly were pinned; these are created for us. Entity ids (#N)
         ARE deterministic here because creation order is, so deriving each
         GlobalId from its entity id is stable.
      2. A few aggregate attributes are populated from Python sets, so
         their serialised order varies. Sorting by entity id fixes them.

    Anything not listed here already serialises deterministically.
    """
    for entity in sorted(file.by_type("IfcRoot"), key=lambda e: e.id()):
        if entity.GlobalId in _EXPLICIT_GUIDS:
            continue
        entity.GlobalId = stable_guid(f"{entity.is_a()}-{entity.id()}")

    for unit_assignment in file.by_type("IfcUnitAssignment"):
        unit_assignment.Units = tuple(sorted(unit_assignment.Units, key=lambda u: u.id()))

    for rel in file.by_type("IfcRelContainedInSpatialStructure"):
        rel.RelatedElements = tuple(sorted(rel.RelatedElements, key=lambda e: e.id()))


def write_model(output_path: Path = OUTPUT_PATH) -> Path:
    """Author the model and write it to `output_path` deterministically."""
    file = build_model()
    _normalise(file)

    header = file.header.file_name
    header.name = output_path.name
    header.time_stamp = _FIXED_TIMESTAMP
    header.author = ("BIMGUARD AI Blue Halo",)
    header.organization = ("BIMGUARD AI",)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    file.write(str(output_path))
    return output_path


if __name__ == "__main__":
    print("=" * 70)
    print("  build_test_ifc.py — Blue Halo Phase 5 Part A")
    print("=" * 70)

    path = write_model()
    print(f"\nWrote {path} ({path.stat().st_size:,} bytes)")

    # Round-trip: prove the file we just wrote actually loads and carries
    # the elements and geometry the pipeline will look for.
    reloaded = ifcopenshell.open(str(path))
    pipes = reloaded.by_type("IfcPipeSegment")
    ducts = reloaded.by_type("IfcDuctSegment")
    structure = (
        reloaded.by_type("IfcColumn") + reloaded.by_type("IfcBeam") + reloaded.by_type("IfcSlab")
    )
    print(f"\nRound-trip load OK — schema {reloaded.schema}")
    print(f"  IfcPipeSegment: {len(pipes)}")
    print(f"  IfcDuctSegment: {len(ducts)}")
    print(f"  structure (column/beam/slab): {len(structure)}")
    print(f"  IfcBuildingStorey: {len(reloaded.by_type('IfcBuildingStorey'))}")

    print("\nMEP elements:")
    for element in pipes + ducts:
        print(f"  {element.GlobalId}  {element.is_a():16s} {element.Name}")
