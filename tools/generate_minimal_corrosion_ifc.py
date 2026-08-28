"""Generate a small, valid IFC4 model that exercises the corrosion pipeline.

Five MEP elements in a plant room, two materials, real geometry and a real
spatial hierarchy — enough to drive parse -> assess -> issues -> export without
being large enough to be tedious to inspect.

WHAT THE PIPELINE ACTUALLY READS, AND WHY THIS FILE IS SHAPED THIS WAY

    ``module2_ifc_read.ifc_parser`` decides three things from the file, and each
    one dictates something here:

    * **Material** comes from ``ifcopenshell.util.element.get_materials``, then
      through ``normalise_material_name``. That function matches on substrings,
      so the names below are chosen to hit its rules: ``"Carbon Steel"`` maps to
      ``Carbon_steel_mild`` and ``"SS316L"`` maps to ``SS_316_passive`` (it
      matches on ``"316"``). A name it does not recognise falls through to a
      slug and the engines score it as unknown.

    * **Environment** comes from ``ContainedInStructure`` — the
      ``IfcRelContainedInSpatialStructure`` relationship — not from aggregation.
      Elements are therefore *contained* in the space rather than aggregated
      into it; aggregating them would leave the parser with no space name and
      the environment unclassified. The space is called "Plant Room" because
      ``SPACE_TO_ENV`` maps ``"plant"`` to ``interior_conditioned``.

    * **Element type** decides both whether an element is seen at all and which
      joint code it gets: the parser only scans the classes in
      ``IFC_SERVICE_LABELS``, and ``IFC_TO_JOINT`` maps IfcPipeSegment to
      JT-012, IfcPipeFitting to JT-001 and IfcValve to JT-013.

    Geometry is real extruded solids rather than placements alone, so the
    seismic path (``phase_6d_seismic``) can read a bounding box from the same
    file instead of reporting every element as geometry-unavailable.

TWO THINGS THIS FILE CANNOT MAKE HAPPEN

    Both are parser limitations, not modelling ones, and no IFC file can work
    around them:

    * ``parse_ifc_model`` sets ``mat_b = None`` unconditionally
      (``ifc_parser.py:217``), so every element is assessed against *itself*.
      GC-001 therefore sees no dissimilar-metal couple, however the model is
      built, and reports no galvanic risk. Pairing adjacent elements by
      proximity is not implemented.

    * ``anode_area_m2`` and ``cathode_area_m2`` are hardcoded to 0.05 and 0.50
      (``ifc_parser.py:232-233``), so the area ratio is always 1:10 regardless
      of the geometry in the file.

Run:
    uv run python tools/generate_minimal_corrosion_ifc.py
    uv run python tools/generate_minimal_corrosion_ifc.py --out some/where.ifc
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.geometry
import ifcopenshell.api.material
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.unit
from ifcopenshell.api import run

#: Default output. Overridable with --out so nothing here is pinned to one machine.
DEFAULT_OUT = Path(r"D:\Zigurat Masters\test-data\minimal-corrosion-test.ifc")

#: Material names chosen to match ``normalise_material_name``'s substring rules.
#: Changing these strings changes which engine keys the elements resolve to.
CARBON_STEEL = "Carbon Steel"
STAINLESS = "SS316L"

#: (name, ifc_class, material, (x, y, z) metres, (length, width, height) metres)
#:
#: Positions put the two pipes 0.5 m apart on a horizontal run and the fittings
#: on a vertical riser, so the model reads as a plausible plant room rather than
#: five boxes at the origin.
ELEMENTS: tuple[tuple[str, str, str, tuple[float, float, float], tuple[float, float, float]], ...] = (
    ("Pipe 1 - Carbon Steel Riser", "IfcPipeSegment", CARBON_STEEL, (1.0, 1.0, 0.0), (0.05, 0.05, 2.0)),
    ("Pipe 2 - SS316L Riser", "IfcPipeSegment", STAINLESS, (1.5, 1.0, 0.0), (0.05, 0.05, 2.0)),
    ("Flange Fitting - SS316L", "IfcPipeFitting", STAINLESS, (1.0, 1.0, 2.0), (0.12, 0.12, 0.06)),
    ("Tee Joint - Carbon Steel", "IfcPipeFitting", CARBON_STEEL, (1.0, 1.0, 2.1), (0.10, 0.10, 0.10)),
    ("Gate Valve - SS316L", "IfcValve", STAINLESS, (1.5, 1.0, 2.0), (0.15, 0.10, 0.20)),
)


def _box(model, context, size: tuple[float, float, float]):
    """Return a rectangular extruded solid of ``size`` metres.

    A crude stand-in for pipe geometry: the pipeline reads bounding boxes, not
    swept profiles, so a box of the right extent carries the same information
    at a fraction of the file size.
    """
    length, width, height = size
    profile = model.create_entity(
        "IfcRectangleProfileDef",
        ProfileType="AREA",
        XDim=length,
        YDim=width,
    )
    direction = model.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0))
    solid = model.create_entity(
        "IfcExtrudedAreaSolid",
        SweptArea=profile,
        ExtrudedDirection=direction,
        Depth=height,
    )
    return model.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=context,
        RepresentationIdentifier="Body",
        RepresentationType="SweptSolid",
        Items=[solid],
    )


def build(out_path: Path) -> dict:
    """Build the model and write it to ``out_path``.

    Returns:
        Stats about what was written, for the caller to print.
    """
    model = ifcopenshell.file(schema="IFC4")

    # The project has to exist before units can be assigned to it, and before
    # any geometric context can hang off it.
    project = run("root.create_entity", model, ifc_class="IfcProject", name="BIMGUARD Test Model")

    # Units next: the parser converts to metres via the model's declared unit,
    # so an undeclared unit would make every dimension ambiguous.
    run("unit.assign_unit", model, length={"is_metric": True, "raw": "METERS"})

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
    storey = run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="Ground Floor")
    # "Plant Room" is load-bearing: SPACE_TO_ENV matches "plant" and classifies
    # the environment as interior_conditioned.
    space = run("root.create_entity", model, ifc_class="IfcSpace", name="Plant Room")

    run("aggregate.assign_object", model, products=[site], relating_object=project)
    run("aggregate.assign_object", model, products=[building], relating_object=site)
    run("aggregate.assign_object", model, products=[storey], relating_object=building)
    run("aggregate.assign_object", model, products=[space], relating_object=storey)

    materials = {
        name: run("material.add_material", model, name=name)
        for name in (CARBON_STEEL, STAINLESS)
    }

    created = []
    for name, ifc_class, material_name, position, size in ELEMENTS:
        element = run("root.create_entity", model, ifc_class=ifc_class, name=name)

        # Containment, not aggregation: this is the relationship the parser
        # reads to find the space, and therefore the environment.
        run("spatial.assign_container", model, products=[element], relating_structure=space)

        run(
            "material.assign_material",
            model,
            products=[element],
            material=materials[material_name],
        )

        run(
            "geometry.assign_representation",
            model,
            product=element,
            representation=_box(model, body, size),
        )
        run(
            "geometry.edit_object_placement",
            model,
            product=element,
            matrix=_translation(position),
        )
        created.append(element)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    model.write(str(out_path))

    return {
        "path": out_path,
        "elements": len(created),
        "materials": len(materials),
        "size_bytes": out_path.stat().st_size,
        "schema": model.schema,
    }


def _translation(position: tuple[float, float, float]):
    """Return a 4x4 placement matrix translating to ``position``."""
    import numpy as np

    matrix = np.eye(4)
    matrix[:3, 3] = position
    return matrix


def main() -> None:
    """Build the file and report what was written."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(os.environ.get("BIMGUARD_TEST_IFC", DEFAULT_OUT)),
        help=f"Where to write the model (default: {DEFAULT_OUT})",
    )
    args = parser.parse_args()

    stats = build(args.out)
    print(f"IFC file created: {stats['path']}")
    print(f"  schema:    {stats['schema']}")
    print(f"  elements:  {stats['elements']}")
    print(f"  materials: {stats['materials']}")
    print(f"  size:      {stats['size_bytes'] / 1024:.1f} KB")


if __name__ == "__main__":
    main()
