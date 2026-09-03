"""
Tier 3 geometric adjacency, and what it changes for XM-001.

WHAT THIS TIER IS FOR
    XM-001 reads PipingElement.joined_to to decide which pairs are in direct
    contact. That adjacency comes from piping_producer._build_adjacency:

      Tier 1  IFC ports - authoritative.
      Tier 2  Centerline endpoints, falling back to the placement centroid.
      Tier 3  Tessellated surface distance (this file). Opt-in.
      Tier 4  Indeterminable - XM-001 skips the element.

    Tier 2's inputs come from _local_vertices, which reads triangulated face
    sets and polylines, reduces a swept solid to its extrusion axis, and
    returns nothing at all for a BRep. A BRep element therefore has no
    centerline and no bounding box, so Tier 2 falls back to comparing
    placement origins - and two elements whose faces meet can have origins a
    metre apart. Tier 2 then reports joined_to == [], XM-001 reads that as
    "nothing to couple with", and a real dissimilar-metal contact goes
    unreported. BRep and CSG bodies are what most Revit and ArchiCAD MEP
    families export as, so this is the common case, not a corner one.

    The fixtures below are BRep boxes for exactly that reason.

TRI-STATE
    A distance of None from calculate_shortest_distance means "not
    measured", never "far apart". An element the mesher cannot tessellate
    must keep the status it arrived with - a previously indeterminable
    element stays indeterminable and is skipped, rather than being promoted
    to "measured, and found isolated".

Run: uv run pytest tests/test_xm001_geometric_adjacency.py -v
"""

import pytest

ifcopenshell = pytest.importorskip("ifcopenshell")
pytest.importorskip("ifcopenshell.geom")
pytest.importorskip("ifcopenshell.api")
pytest.importorskip("ifcopenshell.guid")
pytest.importorskip("scipy")
np = pytest.importorskip("numpy")

from app.modules.comparator.cross_material import compare, load_rule_pack  # noqa: E402
from app.modules.ifc_reader import piping_producer as pp  # noqa: E402
from app.modules.ifc_reader.piping_schema import (  # noqa: E402
    BoundingBox,
    EnvironmentClass,
    PipingSystem,
    Point3D,
)
from tests.test_cross_material import TEST_SERIES, TEST_THRESHOLDS  # noqa: E402

MM = {"is_metric": True, "raw": "MILLIMETERS"}


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _new_model():
    f = ifcopenshell.api.run("project.create_file", version="IFC4")
    ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcProject", name="XM001Geom")
    ifcopenshell.api.run("unit.assign_unit", f, length=MM)
    ctx = ifcopenshell.api.run("context.add_context", f, context_type="Model")
    body = ifcopenshell.api.run(
        "context.add_context", f,
        context_type="Model", context_identifier="Body",
        target_view="MODEL_VIEW", parent=ctx,
    )
    return f, body


def _brep_box(f, dx, dy, dz):
    """Return an IfcFacetedBrep box at the local origin.

    Deliberately a BRep: _local_vertices returns nothing for one, which is
    what pushes the element onto the placement-origin fallback this tier
    exists to correct.
    """
    corners = [
        (0, 0, 0), (dx, 0, 0), (dx, dy, 0), (0, dy, 0),
        (0, 0, dz), (dx, 0, dz), (dx, dy, dz), (0, dy, dz),
    ]
    points = [f.createIfcCartesianPoint((float(x), float(y), float(z))) for x, y, z in corners]
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    faces = [
        f.createIfcFace(
            [f.createIfcFaceOuterBound(f.createIfcPolyLoop([points[i] for i in quad]), True)]
        )
        for quad in quads
    ]
    return f.createIfcFacetedBrep(f.createIfcClosedShell(faces))


def _add(f, body, ifc_class, name, material, dims, at, *, with_body=True):
    """Add a BRep element of *dims* mm placed at *at* mm, carrying *material*."""
    element = ifcopenshell.api.run("root.create_entity", f, ifc_class=ifc_class, name=name)
    matrix = np.eye(4)
    matrix[0][3], matrix[1][3], matrix[2][3] = at
    ifcopenshell.api.run(
        "geometry.edit_object_placement", f, product=element, matrix=matrix, is_si=False
    )
    if with_body:
        representation = f.createIfcShapeRepresentation(
            body, "Body", "Brep", [_brep_box(f, *dims)]
        )
        ifcopenshell.api.run(
            "geometry.assign_representation", f, product=element, representation=representation
        )
    if material is not None:
        entity = ifcopenshell.api.run("material.add_material", f, name=material)
        ifcopenshell.api.run("material.assign_material", f, products=[element], material=entity)
    return element


def _touching_pair():
    """Return a copper pipe and a galvanised valve whose end faces meet.

    Their placement origins are 1 m apart, so Tier 2's centroid fallback
    cannot see the contact; their BRep faces are coincident, so Tier 3 reads
    0 mm.
    """
    f, body = _new_model()
    _add(f, body, "IfcPipeSegment", "P1", "Copper", (1000, 100, 100), (0, 0, 0))
    _add(f, body, "IfcValve", "V1", "Galvanised Steel", (200, 100, 100), (1000, 0, 0))
    return f


def _scored(elements):
    """Give elements the system and environment XM-001 needs to score a couple.

    A real model carries these from spatial names; setting them here keeps
    each test about adjacency rather than about environment classification.
    """
    for element in elements:
        element.system = PipingSystem.DOMESTIC_HOT_WATER
        element.environment_class = EnvironmentClass.T1_INDOOR_DAMP
    return elements


@pytest.fixture(scope="module")
def rule_pack():
    return load_rule_pack(
        galvanic_series=TEST_SERIES,
        compatibility_thresholds=TEST_THRESHOLDS,
    )


def _source(element):
    return (element.properties or {}).get(pp.CONNECTIVITY_SOURCE_KEY)


# ---------------------------------------------------------------------------
# The gap the tier closes
# ---------------------------------------------------------------------------


def test_without_the_tier_touching_elements_look_isolated():
    """Baseline: Tier 2 sees two BRep elements 1 m apart and links nothing."""
    elements = pp.produce_piping_elements_from_model(_touching_pair())

    assert len(elements) == 2
    assert {e.material for e in elements} == {"Copper_C12200", "GalvanisedSteel"}
    for element in elements:
        assert element.joined_to == []
        assert _source(element) == "centerline"


def test_the_tier_links_them_by_measured_surface_contact():
    elements = pp.produce_piping_elements_from_model(
        _touching_pair(), geometric_adjacency=True
    )

    by_id = {e.id: e for e in elements}
    for element in elements:
        assert len(element.joined_to) == 1
        assert by_id[element.joined_to[0]].material != element.material
        assert _source(element) == "centerline+geometry"


def test_xm001_reports_no_couple_without_the_tier(rule_pack):
    """The point of the wiring: the couple is invisible to XM-001 today."""
    elements = _scored(pp.produce_piping_elements_from_model(_touching_pair()))

    couples = [i for i in compare(elements, rule_pack) if i.mechanism != "data_quality"]
    assert couples == []


def test_xm001_reports_the_couple_with_the_tier(rule_pack):
    """With Tier 3 the same model yields one direct-contact galvanic couple."""
    elements = _scored(
        pp.produce_piping_elements_from_model(_touching_pair(), geometric_adjacency=True)
    )

    couples = [i for i in compare(elements, rule_pack) if i.mechanism != "data_quality"]
    assert len(couples) == 1

    metadata = couples[0].metadata or {}
    # Galvanised steel is the active member of the pair, so it sacrifices.
    assert metadata.get("anode_material") == "GalvanisedSteel"
    assert metadata.get("cathode_material") == "Copper_C12200"


# ---------------------------------------------------------------------------
# Tri-state
# ---------------------------------------------------------------------------


def test_unmeasurable_element_stays_indeterminable():
    """No body means no tessellation, so the element must stay skipped.

    The failure this guards is promoting it to "measured, found isolated",
    which would hand XM-001 an element it believes has nothing to couple.
    """
    f, body = _new_model()
    _add(f, body, "IfcPipeSegment", "P1", "Copper", (1000, 100, 100), (0, 0, 0))
    bodiless = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcValve", name="V1")
    material = ifcopenshell.api.run("material.add_material", f, name="Galvanised Steel")
    ifcopenshell.api.run("material.assign_material", f, products=[bodiless], material=material)

    elements = pp.produce_piping_elements_from_model(f, geometric_adjacency=True)
    valve = next(e for e in elements if e.name == "V1")

    assert _source(valve) == "indeterminable"
    assert valve.joined_to == []
    assert pp.CONNECTIVITY_INDETERMINABLE in valve.extraction_warnings


def test_indeterminable_elements_are_skipped_not_scored(rule_pack):
    """XM-001 must raise a data-quality issue, never a couple, for those."""
    f, body = _new_model()
    _add(f, body, "IfcPipeSegment", "P1", "Copper", (1000, 100, 100), (0, 0, 0))
    bodiless = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcValve", name="V1")
    material = ifcopenshell.api.run("material.add_material", f, name="Galvanised Steel")
    ifcopenshell.api.run("material.assign_material", f, products=[bodiless], material=material)

    elements = _scored(pp.produce_piping_elements_from_model(f, geometric_adjacency=True))
    issues = compare(elements, rule_pack)

    assert [i for i in issues if i.mechanism != "data_quality"] == []
    assert any(
        (i.metadata or {}).get("check") == "connectivity_indeterminable" for i in issues
    )


def test_tier_is_off_by_default():
    """Enabling a tessellation pass must be an explicit choice."""
    default = pp.produce_piping_elements_from_model(_touching_pair())
    assert all(e.joined_to == [] for e in default)


# ---------------------------------------------------------------------------
# The tier must only ever add
# ---------------------------------------------------------------------------


def test_tier_never_removes_an_existing_link():
    """An element Tier 2 already joined is not a candidate, so it is untouched."""
    f, body = _new_model()
    # Swept solids: _local_vertices reads their extrusion axis, so Tier 2
    # resolves these two as a normal end-to-end riser joint.
    for name, material, z in (("R1", "Copper", 0.0), ("R2", "Galvanised Steel", 2000.0)):
        element = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcPipeSegment", name=name)
        ifcopenshell.api.run("geometry.edit_object_placement", f, product=element)
        points = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0), (0.0, 0.0)]
        poly = f.createIfcPolyline([f.createIfcCartesianPoint(p) for p in points])
        profile = f.createIfcArbitraryClosedProfileDef("AREA", None, poly)
        solid = f.createIfcExtrudedAreaSolid(
            profile,
            f.createIfcAxis2Placement3D(f.createIfcCartesianPoint((0.0, 0.0, z))),
            f.createIfcDirection((0.0, 0.0, 1.0)),
            2000.0,
        )
        representation = f.createIfcShapeRepresentation(body, "Body", "SweptSolid", [solid])
        ifcopenshell.api.run(
            "geometry.assign_representation", f, product=element, representation=representation
        )
        entity = ifcopenshell.api.run("material.add_material", f, name=material)
        ifcopenshell.api.run("material.assign_material", f, products=[element], material=entity)

    without = pp.produce_piping_elements_from_model(f)
    with_tier = pp.produce_piping_elements_from_model(f, geometric_adjacency=True)

    assert all(e.joined_to for e in without), "fixture must be linked by Tier 2"
    for before, after in zip(
        sorted(without, key=lambda e: e.name), sorted(with_tier, key=lambda e: e.name)
    ):
        assert set(before.joined_to) <= set(after.joined_to)
        assert _source(after) == "centerline"  # not a candidate, so not re-sourced


def _port_resolved_but_isolated():
    """Return a pipe Tier 1 claims whose only authored neighbour is out of scope.

    This is the one way an element reaches "ports" with an empty joined_to:
    IfcRelConnectsPorts links it to an IfcBuildingElementProxy, which is not
    in PIPING_IFC_CLASSES, so Tier 1 records the source but finds nothing in
    the network to link. A valve's face meets the pipe end regardless.
    """
    f, body = _new_model()
    pipe = _add(f, body, "IfcPipeSegment", "P1", "Copper", (1000, 100, 100), (0, 0, 0))
    _add(f, body, "IfcValve", "V1", "Galvanised Steel", (200, 100, 100), (1000, 0, 0))
    proxy = _add(
        f, body, "IfcBuildingElementProxy", "X1", None, (100, 100, 100), (5000, 0, 0)
    )

    port_a = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcDistributionPort")
    port_b = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcDistributionPort")
    f.create_entity(
        "IfcRelNests", GlobalId=ifcopenshell.guid.new(), RelatingObject=pipe,
        RelatedObjects=[port_a],
    )
    f.create_entity(
        "IfcRelNests", GlobalId=ifcopenshell.guid.new(), RelatingObject=proxy,
        RelatedObjects=[port_b],
    )
    f.create_entity(
        "IfcRelConnectsPorts", GlobalId=ifcopenshell.guid.new(),
        RelatingPort=port_a, RelatedPort=port_b,
    )
    return f


def test_port_resolved_elements_are_never_candidates():
    """Tier 3 does not measure outward from an element Tier 1 claimed.

    Its provenance must stay "ports": authored connectivity is authoritative,
    and this tier does not go looking for links the authoring tool omitted.
    """
    elements = pp.produce_piping_elements_from_model(
        _port_resolved_but_isolated(), geometric_adjacency=True
    )
    pipe = next(e for e in elements if e.name == "P1")

    assert _source(pipe) == "ports"
    assert "geometry" not in _source(pipe)


def test_a_candidate_may_still_link_to_a_port_resolved_element():
    """Contact measured from the valve's side is recorded on both elements.

    Ports describe flow connectivity and geometry describes physical contact;
    a galvanic cell needs the latter, so the link is kept rather than
    suppressed because Tier 1 happened to claim the other end.
    """
    elements = pp.produce_piping_elements_from_model(
        _port_resolved_but_isolated(), geometric_adjacency=True
    )
    by_name = {e.name: e for e in elements}

    assert by_name["V1"].id in by_name["P1"].joined_to
    assert by_name["P1"].id in by_name["V1"].joined_to
    assert _source(by_name["V1"]) == "centerline+geometry"


def test_port_resolved_element_stays_isolated_without_the_tier():
    """Baseline for the two tests above."""
    elements = pp.produce_piping_elements_from_model(_port_resolved_but_isolated())
    assert all(e.joined_to == [] for e in elements)


# ---------------------------------------------------------------------------
# Bounding-box prune
# ---------------------------------------------------------------------------


def _bbox(lo, hi):
    return BoundingBox(min=Point3D(*lo), max=Point3D(*hi))


def test_bbox_gap_is_zero_when_boxes_overlap():
    a = _bbox((0, 0, 0), (1, 1, 1))
    b = _bbox((0.5, 0.5, 0.5), (2, 2, 2))
    assert pp._bbox_gap_m(a, b) == pytest.approx(0.0)


def test_bbox_gap_measures_the_axis_separation():
    a = _bbox((0, 0, 0), (1, 1, 1))
    b = _bbox((4, 0, 0), (5, 1, 1))
    assert pp._bbox_gap_m(a, b) == pytest.approx(3.0)


def test_bbox_gap_is_a_lower_bound_on_surface_distance():
    """Diagonal separation: the true gap is the 3-D diagonal, not one axis."""
    a = _bbox((0, 0, 0), (1, 1, 1))
    b = _bbox((4, 5, 1), (5, 6, 2))
    assert pp._bbox_gap_m(a, b) == pytest.approx(5.0)  # sqrt(3^2 + 4^2)


def test_missing_bbox_cannot_prune():
    """None means "cannot prune" - the caller must measure, never assume."""
    assert pp._bbox_gap_m(None, _bbox((0, 0, 0), (1, 1, 1))) is None
    assert pp._bbox_gap_m(_bbox((0, 0, 0), (1, 1, 1)), None) is None
    assert pp._bbox_gap_m(None, None) is None


# ---------------------------------------------------------------------------
# Mid-span contact (narrow-phase point-to-triangle measurement)
# ---------------------------------------------------------------------------


def test_mid_span_contact_is_detected_by_surface_distance():
    """A branch landing mid-span on a riser reads 0 mm, not the corner gap.

    The two coarse boxes touch along a face interior, so neither mesh carries
    a vertex anywhere near the contact patch and the closest vertex pair sits
    900 mm apart. Only the narrow phase - point to triangle, over the faces
    incident on that pair - sees the contact.
    """
    from app.modules.ifc_reader.ifc_geometry import IFCGeometryExtractor

    f, body = _new_model()
    riser = _add(f, body, "IfcPipeSegment", "P1", "Copper", (100, 100, 2000), (0, 0, 0))
    branch = _add(f, body, "IfcPipeFitting", "T1", "Galvanised Steel", (500, 100, 100), (100, 0, 900))

    measured = IFCGeometryExtractor(f).calculate_shortest_distance(riser, branch)

    assert measured is not None
    assert measured == pytest.approx(0.0, abs=1e-6)


def test_mid_span_measurement_is_symmetric():
    """Both directions are measured, so argument order cannot change the answer."""
    from app.modules.ifc_reader.ifc_geometry import IFCGeometryExtractor

    f, body = _new_model()
    riser = _add(f, body, "IfcPipeSegment", "P1", "Copper", (100, 100, 2000), (0, 0, 0))
    branch = _add(f, body, "IfcPipeFitting", "T1", "Galvanised Steel", (500, 100, 100), (120, 0, 900))

    extractor = IFCGeometryExtractor(f)
    assert extractor.calculate_shortest_distance(riser, branch) == pytest.approx(
        extractor.calculate_shortest_distance(branch, riser)
    )


def test_mid_span_gap_is_measured_not_rounded_to_contact():
    """A branch stopped 20 mm short of the riser face measures 20 mm, not 0."""
    from app.modules.ifc_reader.ifc_geometry import IFCGeometryExtractor

    f, body = _new_model()
    riser = _add(f, body, "IfcPipeSegment", "P1", "Copper", (100, 100, 2000), (0, 0, 0))
    branch = _add(f, body, "IfcPipeFitting", "T1", "Galvanised Steel", (500, 100, 100), (120, 0, 900))

    measured = IFCGeometryExtractor(f).calculate_shortest_distance(riser, branch)

    assert measured == pytest.approx(20.0, abs=0.01)


# ---------------------------------------------------------------------------
# _point_to_triangle_distance
# ---------------------------------------------------------------------------


def test_point_to_triangle_measures_to_the_face_interior():
    """A point above the middle of a triangle measures its perpendicular height."""
    from app.modules.ifc_reader.ifc_geometry import _point_to_triangle_distance

    a = np.array([[0.0, 0.0, 0.0]])
    b = np.array([[10.0, 0.0, 0.0]])
    c = np.array([[0.0, 10.0, 0.0]])

    assert _point_to_triangle_distance(np.array([2.0, 2.0, 5.0]), a, b, c)[0] == pytest.approx(5.0)


def test_point_to_triangle_falls_back_to_edge_and_corner():
    """Outside the face, the nearest point is on an edge or at a corner."""
    from app.modules.ifc_reader.ifc_geometry import _point_to_triangle_distance

    a = np.array([[0.0, 0.0, 0.0]])
    b = np.array([[10.0, 0.0, 0.0]])
    c = np.array([[0.0, 10.0, 0.0]])

    # Beyond edge AB in -Y: nearest point is on the edge itself.
    assert _point_to_triangle_distance(np.array([5.0, -3.0, 0.0]), a, b, c)[0] == pytest.approx(3.0)
    # Beyond corner B in +X: nearest point is the corner.
    assert _point_to_triangle_distance(np.array([14.0, 0.0, 0.0]), a, b, c)[0] == pytest.approx(4.0)


def test_point_to_triangle_is_vectorised_over_a_batch():
    """One point against many triangles returns one distance per triangle."""
    from app.modules.ifc_reader.ifc_geometry import _point_to_triangle_distance

    a = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 100.0]])
    b = np.array([[10.0, 0.0, 0.0], [10.0, 0.0, 100.0]])
    c = np.array([[0.0, 10.0, 0.0], [0.0, 10.0, 100.0]])

    distances = _point_to_triangle_distance(np.array([1.0, 1.0, 40.0]), a, b, c)

    assert distances.shape == (2,)
    assert distances[0] == pytest.approx(40.0)
    assert distances[1] == pytest.approx(60.0)
