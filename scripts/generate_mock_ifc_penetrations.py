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

    Pipe C  IfcPipeSegment on a 100 mm hanger rod, assigned to a
            FIREPROTECTION IfcDistributionSystem named "Sprinkler System".
    Pipe D  identical to C but on a 450 mm rod.
    Pipe E  identical to C but on a DOMESTICCOLDWATER system.

    The three suspended runs carry no penetration at all. They exist for the
    predicates the penetration fixtures cannot exercise -- `is_suspended`,
    `hanger_rod_length_below_mm` and `system_type_any_of` -- and each pair
    isolates one variable, the same discipline Wall A / Wall B follow: C vs D
    differs only in rod length, C vs E only in system type.

    NZS 4219 5.8.1 exempts rods under 150 mm and FEMA E-74 6.4.3.1 under
    305 mm; 100 mm is below both and 450 mm above both, so C is exempt and D
    is not under either standard.

    Each hanger is an IfcDiscreteAccessory carrying three agreeing signals --
    PredefinedType BRACKET, a name reading "Hanger Rod", and a HangerType
    property -- so `ifc_supports.classify_support` reaches HANGER by any of its
    routes. BRACKET rather than HANGER because IfcDiscreteAccessoryTypeEnum has
    no HANGER member; it is `_PREDEFINED_SIGNALS` that maps the two. The rod is
    a vertical extrusion, so `rod_length_mm` reports method "extrusion" rather
    than falling back to a bounding box.

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
import sys
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

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

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

#: ── Suspended runs ───────────────────────────────────────────────────────────
#: Hanger rod diameter, millimetres. Only the rod's LENGTH is under test; the
#: diameter just has to be plausible enough to extrude.
ROD_DIAMETER_MM = 10.0

#: NZS 4219 5.8.1 exempts piping on hanger rods shorter than 150 mm; FEMA E-74
#: 6.4.3.1 uses 305 mm (12 in). SHORT_ROD_MM sits below both thresholds and
#: LONG_ROD_MM above both, so one run is exempt under either standard and the
#: other under neither -- the verdict cannot depend on which one is applied.
SHORT_ROD_MM = 100.0
LONG_ROD_MM = 450.0

#: Where the suspended runs sit, millimetres. Well clear of the walls in y so
#: nothing here can interfere with the penetration fixtures above.
RUN_Y0 = 8000.0
RUN_LENGTH = 4000.0
RUN_Z = 2500.0

#: ── Braced run ───────────────────────────────────────────────────────────────
#: A single long run carrying several supports, which the suspended runs above
#: cannot provide: each of those has exactly one hanger, and one support has no
#: spacing at all. A spacing rule needs at least two.
#:
#: NominalDiameter is exactly 50.0, not the 50.8 mm true outside diameter of
#: NB50, because NZS 4219 Table 6a is tabulated against the nominal
#: designation and the comparator matches a scalar `nominal_diameter_mm`
#: exactly. A run at 50.8 would fall out of scope -- correctly, but it would
#: prove nothing about the spacing arithmetic.
BRACED_NOMINAL_DIAMETER_MM = 50.0
BRACED_RUN_X = 12000.0
BRACED_RUN_Y0 = 16000.0
BRACED_RUN_LENGTH = 20000.0
BRACED_RUN_Z = 2500.0

#: Stations along the braced run, millimetres from its start. The gaps are the
#: whole point of the fixture, so each series is chosen to land on a known side
#: of the rule that governs it:
#:
#:   lateral       7000 mm gaps -- OVER the 6100 mm NZS Table 6a limit  -> FAIL
#:   longitudinal 15000 mm gap  -- under the 18000 mm Table 7a limit    -> PASS
#:   all supports  7000 mm gap  -- over the 4000 mm BS EN 17.2.2 limit  -> FAIL
LATERAL_BRACE_STATIONS = (1000.0, 8000.0, 15000.0)
LONGITUDINAL_BRACE_STATIONS = (2000.0, 17000.0)
BRACED_HANGER_STATIONS = (1000.0, 19000.0)

#: (system name, IfcDistributionSystemEnum PredefinedType)
#:
#: The enumeration has FIREPROTECTION but NO SPRINKLER member, so a rule
#: predicate asking for "sprinkler" can only ever match the system NAME. Both
#: are set deliberately: the PredefinedType carries "fire_protection" and the
#: name carries "sprinkler", which is what lets one predicate
#: ``system_type_any_of: ["fire_protection", "sprinkler"]`` be satisfied by
#: either half and proves the extractor has to read both.
FIRE_SYSTEM = ("Sprinkler System - Wet Pipe", "FIREPROTECTION")
WATER_SYSTEM = ("Domestic Cold Water", "DOMESTICCOLDWATER")

#: (label, pipe name, x offset, rod length, system)
#:
#: Each pair differs in exactly one variable, the same discipline the two
#: penetrations above follow: C vs D isolates rod length (same system), C vs E
#: isolates system type (same rod). A verdict that changes between C and D can
#: only be the hanger exemption; one that changes between C and E can only be
#: the system-type predicate.
SUSPENDED = (
    ("C", "Pipe C - sprinkler, 100 mm rod", 0.0, SHORT_ROD_MM, FIRE_SYSTEM),
    ("D", "Pipe D - sprinkler, 450 mm rod", 2000.0, LONG_ROD_MM, FIRE_SYSTEM),
    ("E", "Pipe E - domestic water, 100 mm rod", 4000.0, SHORT_ROD_MM, WATER_SYSTEM),
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


def _cylinder_along_z(model, context, diameter, length):
    """Circular solid of ``diameter`` extruded ``length`` mm along global +Z.

    Used for hanger rods. ``ifc_supports.rod_length_mm`` reads the extrusion
    directly through ``_extrusion_axis``, so both the rod's length and its
    angle from vertical come from this solid rather than from a bounding box
    -- which is what lets the fixture exercise the exact ("extrusion") path
    the method field reports, not the bounding-box fallback.
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
        Position=_placement3d(model, (0.0, 0.0, 0.0)),
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

    # ── Suspended runs: distribution systems + hanger rods ────────────────
    # These carry no penetration at all. They exist so the system-type and
    # is_suspended predicates have something to resolve against, which the two
    # penetration fixtures above cannot provide: neither is assigned to a
    # system, and neither is supported by anything.
    systems: dict[str, object] = {}
    for _label, _name, _px, _rod, (system_name, system_type) in SUSPENDED:
        if system_name in systems:
            continue
        system = run("system.add_system", model, ifc_class="IfcDistributionSystem")
        system.Name = system_name
        system.PredefinedType = system_type
        systems[system_name] = system

    suspended = []
    for label, pipe_name, px, rod_length, (system_name, _system_type) in SUSPENDED:
        pipe = run("root.create_entity", model, ifc_class="IfcPipeSegment", name=pipe_name)
        pipe.PredefinedType = "RIGIDSEGMENT"
        run("spatial.assign_container", model, products=[pipe], relating_structure=storey)
        run("material.assign_material", model, products=[pipe], material=materials[PIPE_STEEL])
        # Horizontal, running along y, so a vertical rod is perpendicular to it
        # and `classify_orientation` has a real axis to measure against.
        _place(
            model,
            pipe,
            body,
            _cylinder_along_y(model, body, PIPE_NOMINAL_DIAMETER_MM, RUN_LENGTH),
            (px, RUN_Y0, RUN_Z),
        )
        pipe_pset = run("pset.add_pset", model, product=pipe, name="Pset_PipeSegmentTypeCommon")
        run(
            "pset.edit_pset",
            model,
            pset=pipe_pset,
            properties={"NominalDiameter": PIPE_NOMINAL_DIAMETER_MM},
        )
        run("system.assign_system", model, products=[pipe], system=systems[system_name])

        # ── Hanger rod, rising from the pipe to the structure above ───────
        # Three agreeing signals, for the same reason each penetration is
        # modelled three ways: whichever route `classify_support` takes, it
        # reaches HANGER.
        #
        #   PredefinedType  BRACKET  -- IfcDiscreteAccessoryTypeEnum has no
        #                               HANGER member, and BRACKET is the value
        #                               `_PREDEFINED_SIGNALS` maps to HANGER.
        #                               Using a bare "HANGER" string here would
        #                               be schema-invalid.
        #   Name            "Hanger Rod ..." -- matches `_NAME_SIGNALS`.
        #   HangerType      "Clevis Hanger"  -- matches `_KIND_PROPERTY_NAMES`.
        hanger = run(
            "root.create_entity",
            model,
            ifc_class="IfcDiscreteAccessory",
            name=f"Hanger Rod {label} - {rod_length:g} mm",
        )
        hanger.PredefinedType = "BRACKET"
        run("spatial.assign_container", model, products=[hanger], relating_structure=storey)
        _place(
            model,
            hanger,
            body,
            _cylinder_along_z(model, body, ROD_DIAMETER_MM, rod_length),
            (px, RUN_Y0 + RUN_LENGTH / 2.0, RUN_Z),
        )
        hanger_pset = run("pset.add_pset", model, product=hanger, name="Pset_SupportCommon")
        run(
            "pset.edit_pset",
            model,
            pset=hanger_pset,
            properties={"HangerType": "Clevis Hanger"},
        )

        # IfcRelConnectsElements is the "connection" route in
        # `ifc_supports.find_supports` -- the most trusted of the three, and
        # the only one that works with proximity matching left off.
        model.create_entity(
            "IfcRelConnectsElements",
            GlobalId=ifcopenshell.guid.new(),
            Name=f"Hanger {label}",
            Description=f"{hanger.Name} supports {pipe_name}",
            RelatingElement=hanger,
            RelatedElement=pipe,
        )
        suspended.append((label, pipe, hanger, rod_length))

    # ── Braced run: several supports at known spacing ─────────────────────
    # Runs along +y like the suspended runs, so a vertical member is
    # perpendicular to it (lateral) and a member along y is parallel to it
    # (longitudinal). `classify_support` measures that angle rather than
    # trusting the name, so the geometry is what decides each brace's kind.
    braced = run(
        "root.create_entity", model, ifc_class="IfcPipeSegment", name="Pipe F - braced run NB50"
    )
    braced.PredefinedType = "RIGIDSEGMENT"
    run("spatial.assign_container", model, products=[braced], relating_structure=storey)
    run("material.assign_material", model, products=[braced], material=materials[PIPE_STEEL])
    _place(
        model,
        braced,
        body,
        _cylinder_along_y(model, body, PIPE_NOMINAL_DIAMETER_MM, BRACED_RUN_LENGTH),
        (BRACED_RUN_X, BRACED_RUN_Y0, BRACED_RUN_Z),
    )
    braced_pset = run(
        "pset.add_pset", model, product=braced, name="Pset_PipeSegmentTypeCommon"
    )
    run(
        "pset.edit_pset",
        model,
        pset=braced_pset,
        properties={"NominalDiameter": BRACED_NOMINAL_DIAMETER_MM},
    )
    run("system.assign_system", model, products=[braced], system=systems[FIRE_SYSTEM[0]])

    def _support(ifc_class, name, predefined, solid, position, psets=None):
        """Create one support, place it, and connect it to the braced run."""
        element = run("root.create_entity", model, ifc_class=ifc_class, name=name)
        element.PredefinedType = predefined
        run("spatial.assign_container", model, products=[element], relating_structure=storey)
        _place(model, element, body, solid, position)
        if psets:
            pset = run("pset.add_pset", model, product=element, name=psets[0])
            run("pset.edit_pset", model, pset=pset, properties=psets[1])
        model.create_entity(
            "IfcRelConnectsElements",
            GlobalId=ifcopenshell.guid.new(),
            Name=f"Support {name}",
            Description=f"{name} supports {braced.Name}",
            RelatingElement=element,
            RelatedElement=braced,
        )
        return element

    supports = []
    for index, station in enumerate(LATERAL_BRACE_STATIONS, start=1):
        # Vertical: 90 degrees to a run along y, so geometry reads it LATERAL.
        supports.append(
            _support(
                "IfcMember",
                f"Sway Brace L{index}",
                "BRACE",
                _cylinder_along_z(model, body, ROD_DIAMETER_MM * 4, 1200.0),
                (BRACED_RUN_X, BRACED_RUN_Y0 + station, BRACED_RUN_Z),
            )
        )
    for index, station in enumerate(LONGITUDINAL_BRACE_STATIONS, start=1):
        # Along y: parallel to the run, so geometry reads it LONGITUDINAL.
        supports.append(
            _support(
                "IfcMember",
                f"Sway Brace G{index}",
                "BRACE",
                _cylinder_along_y(model, body, ROD_DIAMETER_MM * 4, 1200.0),
                (BRACED_RUN_X + 400.0, BRACED_RUN_Y0 + station, BRACED_RUN_Z),
            )
        )
    for index, station in enumerate(BRACED_HANGER_STATIONS, start=1):
        supports.append(
            _support(
                "IfcDiscreteAccessory",
                f"Hanger Rod F{index} - {SHORT_ROD_MM:g} mm",
                "BRACKET",
                _cylinder_along_z(model, body, ROD_DIAMETER_MM, SHORT_ROD_MM),
                (BRACED_RUN_X, BRACED_RUN_Y0 + station, BRACED_RUN_Z),
                psets=("Pset_SupportCommon", {"HangerType": "Clevis Hanger"}),
            )
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    model.write(str(out_path))

    return {
        "path": out_path,
        "schema": model.schema,
        "walls": len(created),
        "pipes": len(created) + len(suspended) + 1,
        "openings": len(created),
        "materials": len(materials),
        "systems": len(systems),
        "hangers": len(suspended),
        "braced_supports": len(supports),
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


def verify_suspended(path: Path) -> list[str]:
    """Re-open the file and report it through ``ifc_supports`` itself.

    Reading the fixture back with the production support reader rather than
    with a bespoke traversal is the point: it proves the hangers are findable
    by the code that will actually gate ``is_suspended``, not merely present in
    the file. A fixture that only a purpose-written checker can see would pass
    here and still leave the predicate UNDETERMINED in a real run.
    """
    from app.modules.ifc_reader import ifc_supports
    from app.modules.ifc_reader.ifc_geometry import IFCGeometryExtractor

    model = ifcopenshell.open(str(path))
    # element_axis needs a centroid to turn an extrusion direction into a
    # positioned centreline, so the extractor is not optional here: without it
    # every rod length comes back None and the fixture would look broken when
    # it is only unmeasured.
    geometry = IFCGeometryExtractor(model)
    lines = []
    for pipe in model.by_type("IfcPipeSegment"):
        supports = ifc_supports.find_supports(pipe, geometry_extractor=geometry)
        if not supports:
            continue
        systems = [
            rel.RelatingGroup
            for rel in getattr(pipe, "HasAssignments", None) or []
            if rel.is_a("IfcRelAssignsToGroup")
            and rel.RelatingGroup.is_a("IfcDistributionSystem")
        ]
        system_text = ", ".join(
            f"{s.Name} [{s.PredefinedType}]" for s in systems
        ) or "unassigned"
        rods = []
        for support in supports:
            length, detail = ifc_supports.rod_length_mm(
                support["element"], geometry_extractor=geometry
            )
            rods.append(
                f"{support['kind']} via {support['route']} "
                f"station={support['station_mm']} "
                f"rod={length if length is None else f'{length:g} mm'} "
                f"({detail['method']}, plumb={detail['is_plumb']})"
            )
        lines.append(f"{pipe.Name}: system={system_text}; {'; '.join(rods)}")
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
    print(f"  systems:   {stats['systems']}")
    print(f"  hangers:   {stats['hangers']}")
    print(f"  size:      {stats['size_bytes'] / 1024:.1f} KB")
    print("Read-back (penetrations):")
    for line in verify(args.out):
        print(f"  {line}")
    print("Read-back (suspended runs, via ifc_supports):")
    for line in verify_suspended(args.out):
        print(f"  {line}")


if __name__ == "__main__":
    main()
