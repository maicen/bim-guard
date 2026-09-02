"""Generate a minimal IFC4X3 model of two pipe penetrations for NFPA 13 tests.

The model exists to prove one thing: the comparator's breakaway / frangible
exemption (NFPA 13 §9.3.4.5 style) waives an annular-clearance failure when
the host wall is gypsum board, and does not waive it when the host wall is
concrete. Everything else about the two penetrations is identical, so any
difference in verdict can only come from the wall material.

WHAT IS IN THE FILE

    Wall A  IfcWall, material ``Concrete`` (single IfcMaterial, Category
            ``concrete``), 5 m long, 200 mm thick, 3 m high.
    Pipe A  IfcPipeSegment, ``Pset_PipeSegmentTypeCommon.NominalDiameter``
            = 50.8 mm (2 in), runs through Wall A perpendicular to its face.

    Wall B  IfcWall, material ``Gypsum Board`` (single IfcMaterial, Category
            ``gypsum``) -- the literal name the comparator's exemption
            predicate ``material_any_of: ["gypsum", "plasterboard"]`` matches.
    Pipe B  IfcPipeSegment, NominalDiameter = 50.8 mm, runs through Wall B.

    Each penetration is modelled three ways so any resolver strategy in
    Module 2 can find the host wall:

    * an ``IfcOpeningElement`` cut from the wall (``IfcRelVoidsElement``) and
      filled by the pipe (``IfcRelFillsElement``);
    * an ``IfcRelInterferesElements`` between pipe and wall with
      ``InterferenceType = "PENETRATION"``;
    * real geometry -- the pipe's cylinder physically crosses the wall's
      extruded box, so a bounding-box or boolean test also finds it.

    The openings are deliberately undersized. NFPA 13 requires the hole to be
    nominally 2 in larger than the pipe for pipes 1 in through 3½ in, so a 2 in
    pipe needs a 4 in (101.6 mm) hole. Both openings here are 63.5 mm
    (2½ in). Both penetrations therefore FAIL the clearance rule on geometry
    alone; only Pipe B should be waived, by the gypsum exemption.

UNITS

    The project length unit is millimetres, so every measure in the file --
    NominalDiameter, geometry, opening size -- is a literal millimetre value
    and needs no conversion when read back.

Run:
    uv run python scripts/generate_mock_ifc_penetrations.py
    uv run python scripts/generate_mock_ifc_penetrations.py --out some/where.ifc
"""

from __future__ import annotations

import argparse
from pathlib import Path

import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.feature
import ifcopenshell.api.geometry
import ifcopenshell.api.material
import ifcopenshell.api.pset
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.unit
import ifcopenshell.guid
import ifcopenshell.util.element
import numpy as np
from ifcopenshell.api import run

#: Default output, relative to the repository root. ``data/test_models/`` is
#: gitignored, so the generated file is never committed; the script is.
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "data" / "test_models" / "nfpa13_test.ifc"

#: The schema the file declares. ifcopenshell resolves this to the current
#: IFC4X3 addendum it ships with.
SCHEMA = "IFC4X3"

#: 2 in nominal, in millimetres.
PIPE_NOMINAL_DIAMETER_MM = 50.8
#: 2½ in hole -- undersized against the 4 in NFPA 13 requires for a 2 in pipe.
OPENING_DIAMETER_MM = 63.5

#: Wall envelope, millimetres.
WALL_LENGTH = 5000.0
WALL_THICKNESS = 200.0
WALL_HEIGHT = 3000.0

#: How far the pipe sticks out on each side of the wall, millimetres.
PIPE_OVERHANG = 1000.0

#: Material names. ``"Gypsum Board"`` is load-bearing: it is the literal string
#: the exemption test matches on, and it is what the parser reports verbatim.
CONCRETE = "Concrete"
GYPSUM = "Gypsum Board"
PIPE_STEEL = "Carbon Steel"

#: (label, wall name, wall material, wall Category, pipe name, wall origin y)
#: The two walls are parallel, 4 m apart in y, so the two penetrations never
#: interact with each other.
PENETRATIONS = (
    ("A", "Wall A - Concrete", CONCRETE, "concrete", "Pipe A - 2in through concrete", 0.0),
    ("B", "Wall B - Gypsum Board", GYPSUM, "gypsum", "Pipe B - 2in through gypsum", 4000.0),
)


def _placement3d(model, location, axis=None, ref_direction=None):
    """Return an IfcAxis2Placement3D at ``location`` with optional orientation."""
    return model.create_entity(
        "IfcAxis2Placement3D",
        Location=model.create_entity(
            "IfcCartesianPoint", Coordinates=tuple(float(c) for c in location)
        ),
        Axis=model.create_entity("IfcDirection", DirectionRatios=axis) if axis else None,
        RefDirection=model.create_entity("IfcDirection", DirectionRatios=ref_direction)
        if ref_direction
        else None,
    )


def _shape(model, context, solid):
    """Wrap one solid in a Body / SweptSolid shape representation."""
    return model.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=context,
        RepresentationIdentifier="Body",
        RepresentationType="SweptSolid",
        Items=[solid],
    )


def _box(model, context, size):
    """Extruded rectangle of ``size`` = (x, y, z) mm, with its corner at the origin."""
    x, y, z = size
    profile = model.create_entity(
        "IfcRectangleProfileDef",
        ProfileType="AREA",
        Position=model.create_entity(
            "IfcAxis2Placement2D",
            Location=model.create_entity("IfcCartesianPoint", Coordinates=(x / 2.0, y / 2.0)),
        ),
        XDim=x,
        YDim=y,
    )
    solid = model.create_entity(
        "IfcExtrudedAreaSolid",
        SweptArea=profile,
        Position=_placement3d(model, (0.0, 0.0, 0.0)),
        ExtrudedDirection=model.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0)),
        Depth=z,
    )
    return _shape(model, context, solid)


def _cylinder_along_y(model, context, diameter, length):
    """Circular solid of ``diameter`` extruded ``length`` mm along the local +Y axis.

    Extrusion must be along the solid's local Z, so the solid's Position is
    rotated to put local Z on global Y. That is what lets a pipe cross a wall
    whose thickness runs in y.
    """
    profile = model.create_entity(
        "IfcCircleProfileDef",
        ProfileType="AREA",
        Position=model.create_entity(
            "IfcAxis2Placement2D",
            Location=model.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0)),
        ),
        Radius=diameter / 2.0,
    )
    solid = model.create_entity(
        "IfcExtrudedAreaSolid",
        SweptArea=profile,
        Position=_placement3d(
            model, (0.0, 0.0, 0.0), axis=(0.0, 1.0, 0.0), ref_direction=(1.0, 0.0, 0.0)
        ),
        ExtrudedDirection=model.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0)),
        Depth=length,
    )
    return _shape(model, context, solid)


def _translation(position):
    """Return a 4x4 placement matrix translating to ``position``."""
    matrix = np.eye(4)
    matrix[:3, 3] = position
    return matrix


def _place(model, product, body, representation, position):
    """Attach a representation to ``product`` and place it at ``position`` (mm).

    ``is_si=False`` is essential: the API otherwise reads the matrix in metres
    and scales it into project units, which would put a wall 4 km away.
    """
    run("geometry.assign_representation", model, product=product, representation=representation)
    run(
        "geometry.edit_object_placement",
        model,
        product=product,
        matrix=_translation(position),
        is_si=False,
    )


def build(out_path: Path) -> dict:
    """Build the model and write it to ``out_path``.

    Returns:
        Stats about what was written, for the caller to print.
    """
    model = ifcopenshell.file(schema=SCHEMA)

    project = run(
        "root.create_entity",
        model,
        ifc_class="IfcProject",
        name="BIMGUARD NFPA 13 Penetration Test",
    )
    # Millimetres, so every measure in the file is literal.
    run("unit.assign_unit", model, length={"is_metric": True, "raw": "MILLIMETERS"})

    context = run("context.add_context", model, context_type="Model")
    body = run(
        "context.add_context",
        model,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=context,
    )

    site = run("root.create_entity", model, ifc_class="IfcSite", name="Test Site")
    building = run("root.create_entity", model, ifc_class="IfcBuilding", name="Test Building")
    storey = run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="Level 1")
    run("aggregate.assign_object", model, products=[site], relating_object=project)
    run("aggregate.assign_object", model, products=[building], relating_object=site)
    run("aggregate.assign_object", model, products=[storey], relating_object=building)

    materials = {}
    for name, category in ((CONCRETE, "concrete"), (GYPSUM, "gypsum"), (PIPE_STEEL, "steel")):
        materials[name] = run("material.add_material", model, name=name, category=category)

    created = []
    for label, wall_name, wall_material, _category, pipe_name, wall_y in PENETRATIONS:
        # ── Wall: box with its length along x, thickness along y ─────────
        wall = run("root.create_entity", model, ifc_class="IfcWall", name=wall_name)
        run("spatial.assign_container", model, products=[wall], relating_structure=storey)
        run("material.assign_material", model, products=[wall], material=materials[wall_material])
        _place(
            model,
            wall,
            body,
            _box(model, body, (WALL_LENGTH, WALL_THICKNESS, WALL_HEIGHT)),
            (0.0, wall_y, 0.0),
        )

        wall_pset = run("pset.add_pset", model, product=wall, name="Pset_WallCommon")
        run(
            "pset.edit_pset",
            model,
            pset=wall_pset,
            properties={"IsExternal": False, "LoadBearing": wall_material == CONCRETE},
        )

        # ── Penetration point: mid-length, mid-height, at the wall's near face
        px = WALL_LENGTH / 2.0
        pz = WALL_HEIGHT / 2.0

        # ── Opening: undersized cylinder cut straight through the wall ───
        opening = run(
            "root.create_entity",
            model,
            ifc_class="IfcOpeningElement",
            name=f"Opening {label} - {OPENING_DIAMETER_MM:g} mm",
        )
        _place(
            model,
            opening,
            body,
            _cylinder_along_y(model, body, OPENING_DIAMETER_MM, WALL_THICKNESS),
            (px, wall_y, pz),
        )
        run("feature.add_feature", model, feature=opening, element=wall)

        # ── Pipe: crosses the wall with an overhang either side ───────────
        pipe = run("root.create_entity", model, ifc_class="IfcPipeSegment", name=pipe_name)
        pipe.PredefinedType = "RIGIDSEGMENT"
        run("spatial.assign_container", model, products=[pipe], relating_structure=storey)
        run("material.assign_material", model, products=[pipe], material=materials[PIPE_STEEL])
        _place(
            model,
            pipe,
            body,
            _cylinder_along_y(
                model, body, PIPE_NOMINAL_DIAMETER_MM, WALL_THICKNESS + 2 * PIPE_OVERHANG
            ),
            (px, wall_y - PIPE_OVERHANG, pz),
        )

        pipe_pset = run("pset.add_pset", model, product=pipe, name="Pset_PipeSegmentTypeCommon")
        run(
            "pset.edit_pset",
            model,
            pset=pipe_pset,
            properties={"NominalDiameter": PIPE_NOMINAL_DIAMETER_MM},
        )

        # ── Explicit penetration links ────────────────────────────────────
        run("feature.add_filling", model, opening=opening, element=pipe)
        model.create_entity(
            "IfcRelInterferesElements",
            GlobalId=ifcopenshell.guid.new(),
            Name=f"Penetration {label}",
            Description=f"{pipe_name} penetrates {wall_name}",
            RelatingElement=pipe,
            RelatedElement=wall,
            InterferenceType="PENETRATION",
            ImpliedOrder=False,
        )

        created.append((label, wall, opening, pipe))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    model.write(str(out_path))

    return {
        "path": out_path,
        "schema": model.schema,
        "walls": len(created),
        "pipes": len(created),
        "openings": len(created),
        "materials": len(materials),
        "size_bytes": out_path.stat().st_size,
    }


def verify(path: Path) -> list[str]:
    """Re-open the written file and report what a reader will actually see.

    Returns:
        One line per penetration: pipe, its nominal diameter, and the host
        wall's material as resolved through IfcRelFillsElement/IfcRelVoidsElement.
    """
    model = ifcopenshell.open(str(path))
    lines = []
    for pipe in model.by_type("IfcPipeSegment"):
        psets = ifcopenshell.util.element.get_psets(pipe)
        nd = psets.get("Pset_PipeSegmentTypeCommon", {}).get("NominalDiameter")
        hosts = []
        for rel in pipe.FillsVoids:
            opening = rel.RelatingOpeningElement
            for voids in opening.VoidsElements:
                wall = voids.RelatingBuildingElement
                mat = ifcopenshell.util.element.get_material(wall)
                hosts.append(f"{wall.Name} [{mat.Name if mat else 'no material'}]")
        lines.append(f"{pipe.Name}: NominalDiameter={nd} mm, host={'; '.join(hosts) or 'none'}")
    return lines


def main() -> None:
    """Build the file, re-read it, and report what was written."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Where to write the model (default: {DEFAULT_OUT})",
    )
    args = parser.parse_args()

    stats = build(args.out)
    print(f"IFC file created: {stats['path']}")
    print(f"  schema:    {stats['schema']}")
    print(f"  walls:     {stats['walls']}")
    print(f"  pipes:     {stats['pipes']}")
    print(f"  openings:  {stats['openings']}")
    print(f"  materials: {stats['materials']}")
    print(f"  size:      {stats['size_bytes'] / 1024:.1f} KB")
    print("Read-back:")
    for line in verify(args.out):
        print(f"  {line}")


if __name__ == "__main__":
    main()
