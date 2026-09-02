"""
XM-001 cross-material extraction primitives.

Covers the two Module 2 reads the cross-material comparator depends on:

  * IFCGeometryExtractor.calculate_shortest_distance — vertex-to-vertex
    separation between two elements, in millimetres, via scipy cKDTree.
  * piping_producer.extract_normalized_material — IfcRelAssociatesMaterial
    traversal normalised to a CANONICAL_MATERIALS key.

TRI-STATE IS THE POINT OF THIS FILE
    Both reads must answer None (Undetermined) rather than a falsy or
    defaulted value when the model cannot supply the input. A 0.0 distance
    means "touching" and a defaulted material scores as a real galvanic
    couple, so either substituted for missing data fabricates a verdict.
    Every "missing input" case below therefore asserts `is None`, and the
    distance cases additionally pin that a genuine 0.0 stays distinguishable
    from it.

Run: uv run pytest tests/test_xm001_extraction.py -v
"""

import pytest

ifcopenshell = pytest.importorskip("ifcopenshell")
pytest.importorskip("ifcopenshell.geom")
pytest.importorskip("ifcopenshell.api")  # attaches ifcopenshell.api submodule
pytest.importorskip("scipy")

from app.modules.module2_ifc_read.ifc_geometry import IFCGeometryExtractor  # noqa: E402
from app.modules.module2_ifc_read.piping_producer import (  # noqa: E402
    extract_normalized_material,
    normalise_material,
)
from app.modules.module2_ifc_read.piping_schema import CANONICAL_MATERIALS  # noqa: E402

# ---------------------------------------------------------------------------
# Model builders
# ---------------------------------------------------------------------------

MM = {"is_metric": True, "raw": "MILLIMETERS"}
M = {"is_metric": True, "raw": "METERS"}


def _new_model(unit: dict | None = None):
    """Return (file, body_context) for an IFC4 model in the given length unit."""
    f = ifcopenshell.api.run("project.create_file", version="IFC4")
    ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcProject", name="XM001")
    if unit is not None:
        ifcopenshell.api.run("unit.assign_unit", f, length=unit)
    ctx = ifcopenshell.api.run("context.add_context", f, context_type="Model")
    body = ifcopenshell.api.run(
        "context.add_context", f,
        context_type="Model", context_identifier="Body",
        target_view="MODEL_VIEW", parent=ctx,
    )
    return f, body


def _add_box(f, body, x0, x1, y0, y1, height, ifc_class="IfcPipeSegment"):
    """Add an extruded box spanning [x0,x1] x [y0,y1] with the given height.

    Coordinates are raw model units written straight into IfcCartesianPoints,
    so the numbers in the file are exactly these — no API-side unit
    conversion sits between the fixture and what the mesher reads.
    """
    el = ifcopenshell.api.run("root.create_entity", f, ifc_class=ifc_class)
    ifcopenshell.api.run("geometry.edit_object_placement", f, product=el)
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    poly = f.createIfcPolyline([f.createIfcCartesianPoint(p) for p in pts])
    prof = f.createIfcArbitraryClosedProfileDef("AREA", None, poly)
    solid = f.createIfcExtrudedAreaSolid(
        prof,
        f.createIfcAxis2Placement3D(f.createIfcCartesianPoint((0.0, 0.0, 0.0))),
        f.createIfcDirection((0.0, 0.0, 1.0)),
        height,
    )
    rep = f.createIfcShapeRepresentation(body, "Body", "SweptSolid", [solid])
    ifcopenshell.api.run("geometry.assign_representation", f, product=el, representation=rep)
    return el


def _add_bodiless(f, ifc_class="IfcPipeSegment"):
    """Add an element with no shape representation at all."""
    return ifcopenshell.api.run("root.create_entity", f, ifc_class=ifc_class)


# ---------------------------------------------------------------------------
# calculate_shortest_distance — measurement
# ---------------------------------------------------------------------------


def test_separated_boxes_report_the_gap_in_mm():
    """Two boxes 150 mm apart in X measure 150 mm, not their centroid distance."""
    f, body = _new_model(MM)
    a = _add_box(f, body, 0.0, 100.0, 0.0, 100.0, 100.0)
    b = _add_box(f, body, 250.0, 350.0, 0.0, 100.0, 100.0)

    ex = IFCGeometryExtractor(f)
    assert ex.calculate_shortest_distance(a, b) == pytest.approx(150.0, abs=0.01)


def test_touching_boxes_measure_zero():
    """Face-sharing boxes give exactly 0.0 — a real measurement, not None."""
    f, body = _new_model(MM)
    a = _add_box(f, body, 0.0, 100.0, 0.0, 100.0, 100.0)
    b = _add_box(f, body, 100.0, 200.0, 0.0, 100.0, 100.0)

    ex = IFCGeometryExtractor(f)
    distance = ex.calculate_shortest_distance(a, b)
    assert distance is not None  # 0.0 is falsy; the contract keeps them distinct
    assert distance == pytest.approx(0.0, abs=1e-6)


def test_distance_is_symmetric():
    """The min over cross pairs cannot depend on which cloud builds the tree."""
    f, body = _new_model(MM)
    a = _add_box(f, body, 0.0, 100.0, 0.0, 100.0, 100.0)
    b = _add_box(f, body, 400.0, 500.0, 0.0, 100.0, 100.0)

    ex = IFCGeometryExtractor(f)
    assert ex.calculate_shortest_distance(a, b) == ex.calculate_shortest_distance(b, a)


def test_distance_is_reported_in_mm_regardless_of_authoring_unit():
    """A metre-authored model and a mm-authored model agree, both in mm.

    Guards the same mesher-scale defect test_ifc_geometry_units.py covers for
    bounding boxes: ifcopenshell normalises tessellated output to SI metres,
    so an unscaled distance would be 1000x wrong on a millimetre model.
    """
    f_mm, body_mm = _new_model(MM)
    a_mm = _add_box(f_mm, body_mm, 0.0, 100.0, 0.0, 100.0, 100.0)
    b_mm = _add_box(f_mm, body_mm, 250.0, 350.0, 0.0, 100.0, 100.0)

    f_m, body_m = _new_model(M)
    a_m = _add_box(f_m, body_m, 0.0, 0.1, 0.0, 0.1, 0.1)
    b_m = _add_box(f_m, body_m, 0.25, 0.35, 0.0, 0.1, 0.1)

    d_mm = IFCGeometryExtractor(f_mm).calculate_shortest_distance(a_mm, b_mm)
    d_m = IFCGeometryExtractor(f_m).calculate_shortest_distance(a_m, b_m)

    assert d_mm == pytest.approx(150.0, abs=0.01)
    assert d_m == pytest.approx(150.0, abs=0.01)


# ---------------------------------------------------------------------------
# calculate_shortest_distance — tri-state
# ---------------------------------------------------------------------------


def test_missing_geometry_returns_none_not_zero():
    """An element with no representation is Undetermined, never 0.0.

    0.0 would read as "these are touching" and flag a galvanic couple the
    model never described.
    """
    f, body = _new_model(MM)
    a = _add_box(f, body, 0.0, 100.0, 0.0, 100.0, 100.0)
    bodiless = _add_bodiless(f)

    ex = IFCGeometryExtractor(f)
    assert ex.calculate_shortest_distance(a, bodiless) is None
    assert ex.calculate_shortest_distance(bodiless, a) is None
    assert ex.calculate_shortest_distance(bodiless, bodiless) is None


@pytest.mark.parametrize(
    "left_is_none, right_is_none",
    [(True, False), (False, True), (True, True)],
    ids=["left-none", "right-none", "both-none"],
)
def test_none_arguments_return_none(left_is_none, right_is_none):
    f, body = _new_model(MM)
    real = _add_box(f, body, 0.0, 100.0, 0.0, 100.0, 100.0)
    ex = IFCGeometryExtractor(f)

    left = None if left_is_none else real
    right = None if right_is_none else real
    assert ex.calculate_shortest_distance(left, right) is None


def test_extractor_without_a_model_returns_none():
    """No settings means no tessellation, so every pair is Undetermined."""
    f, body = _new_model(MM)
    a = _add_box(f, body, 0.0, 100.0, 0.0, 100.0, 100.0)
    b = _add_box(f, body, 250.0, 350.0, 0.0, 100.0, 100.0)

    assert IFCGeometryExtractor(None).calculate_shortest_distance(a, b) is None


# ---------------------------------------------------------------------------
# calculate_shortest_distance — caching identity
# ---------------------------------------------------------------------------


def test_cache_keys_on_step_id_not_object_address():
    """Repeated queries must not hand one element another's vertex cloud.

    ifcopenshell returns a fresh entity_instance wrapper per lookup and frees
    it when the caller drops it, so CPython recycles those addresses. A cache
    keyed on id(element) answers the second element with the first one's
    geometry; keyed on element.id() it cannot. Re-fetching by STEP id every
    round is what makes the address churn happen.
    """
    f, body = _new_model(MM)
    a = _add_box(f, body, 0.0, 100.0, 0.0, 100.0, 100.0)
    b = _add_box(f, body, 250.0, 350.0, 0.0, 100.0, 100.0)
    c = _add_box(f, body, 800.0, 900.0, 0.0, 100.0, 100.0)
    id_a, id_b, id_c = a.id(), b.id(), c.id()
    del a, b, c

    ex = IFCGeometryExtractor(f)
    for _ in range(5):
        assert ex.calculate_shortest_distance(f.by_id(id_a), f.by_id(id_b)) == pytest.approx(
            150.0, abs=0.01
        )
        assert ex.calculate_shortest_distance(f.by_id(id_a), f.by_id(id_c)) == pytest.approx(
            700.0, abs=0.01
        )


def test_cached_result_is_stable_across_repeat_calls():
    f, body = _new_model(MM)
    a = _add_box(f, body, 0.0, 100.0, 0.0, 100.0, 100.0)
    b = _add_box(f, body, 250.0, 350.0, 0.0, 100.0, 100.0)

    ex = IFCGeometryExtractor(f)
    assert len({ex.calculate_shortest_distance(a, b) for _ in range(4)}) == 1


# ---------------------------------------------------------------------------
# extract_normalized_material — traversal
# ---------------------------------------------------------------------------


def _element_with_material(name: str | None, ifc_class: str = "IfcPipeSegment"):
    """Return an element carrying *name* via IfcRelAssociatesMaterial."""
    f, _ = _new_model(MM)
    el = ifcopenshell.api.run("root.create_entity", f, ifc_class=ifc_class)
    if name is not None:
        material = ifcopenshell.api.run("material.add_material", f, name=name)
        ifcopenshell.api.run("material.assign_material", f, products=[el], material=material)
    return el


def test_reads_material_through_the_association():
    assert extract_normalized_material(_element_with_material("Copper")) == "Copper_C12200"


def test_inherits_material_from_the_element_type():
    """A pipe routinely carries its material on IfcPipeSegmentType."""
    f, _ = _new_model(MM)
    occurrence = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcPipeSegment")
    pipe_type = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcPipeSegmentType")
    material = ifcopenshell.api.run("material.add_material", f, name="Galvanised Steel")
    ifcopenshell.api.run("material.assign_material", f, products=[pipe_type], material=material)
    ifcopenshell.api.run(
        "type.assign_type", f, related_objects=[occurrence], relating_type=pipe_type
    )

    assert extract_normalized_material(occurrence) == "GalvanisedSteel"


# ---------------------------------------------------------------------------
# extract_normalized_material — tri-state
# ---------------------------------------------------------------------------


def test_no_material_association_returns_none():
    assert extract_normalized_material(_element_with_material(None)) is None


@pytest.mark.parametrize(
    "placeholder", ["TBC", "Default", "<By Category>", "PART-99321", "   "]
)
def test_unrecognised_material_name_returns_none(placeholder):
    """A name that maps to no rule is Undetermined, not a defaulted material.

    "Unknown" would be scoreable text; None forces the caller onto its
    data-quality path instead of into a fabricated galvanic verdict.
    """
    assert extract_normalized_material(_element_with_material(placeholder)) is None


def test_none_element_returns_none():
    assert extract_normalized_material(None) is None


def test_never_returns_a_falsy_non_none_value():
    """Missing data must be None — never False, "" or "Unknown"."""
    for element in (None, _element_with_material(None), _element_with_material("TBC")):
        result = extract_normalized_material(element)
        assert result is None
        assert result is not False


def test_result_is_always_a_canonical_key():
    for raw in ("Copper", "Cu", "ASTM B88", "Galvanised Steel", "316L", "API 5L"):
        result = extract_normalized_material(_element_with_material(raw))
        assert result in CANONICAL_MATERIALS
        assert result != "Unknown"


# ---------------------------------------------------------------------------
# normalise_material — the alias fallback added for XM-001
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        # Element symbols, matched as standalone words
        ("Cu", "Copper_C12200"),
        ("CU", "Copper_C12200"),
        ("Ti", "Titanium"),
        ("Al", "Aluminium"),
        # Product standards
        ("ASTM B88", "Copper_C12200"),
        ("ASTM B88 Type L", "Copper_C12200"),
        ("astm-b88", "Copper_C12200"),
        ("Copper tube to EN 1057", "Copper_C12200"),
        ("C11000", "Copper_C12200"),
        ("C70600", "CuNi_9010"),
        ("C71500", "CuNi_7030"),
        ("ASTM A106 Gr B", "CarbonSteel"),
        ("API 5L X42", "CarbonSteel"),
        ("ASTM A536", "DuctileIron"),
        ("EN 545", "DuctileIron"),
        ("ASTM A48", "CastIron"),
        ("ASTM D1785", "PVC"),
        ("ASTM F876", "PEX"),
        ("PE100", "HDPE"),
        ("PE80", "HDPE"),
    ],
)
def test_alias_fallback_resolves_designations_and_symbols(raw, expected):
    assert normalise_material(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "Vacuum insulated panel",  # contains "cu", but not as a word
        "PE1000",                  # must not collide with PE100
        "ASTM A53",                # covers black AND galvanised — ambiguous
        "ASTM A312",               # austenitic stainless pipe, grade-agnostic
        "TBC",
        "",
    ],
)
def test_alias_fallback_does_not_over_match(raw):
    assert normalise_material(raw) == "Unknown"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Copper", "Copper_C12200"),
        ("Galvanised Steel", "GalvanisedSteel"),
        ("Hot Dip Galvanised", "GalvanisedSteel"),
        ("Carbon Steel", "CarbonSteel"),
        ("Mild Steel", "CarbonSteel"),
        ("Stainless Steel 316L", "SS316L"),
        ("Duplex 2205", "Duplex2205"),
        ("Super Duplex 2507", "SuperDuplex2507"),
        ("Cupronickel 90/10", "CuNi_9010"),
        ("Naval Brass", "Brass_C46400"),
        ("Ductile Iron", "DuctileIron"),
        ("uPVC", "PVC"),
    ],
)
def test_existing_substring_rules_are_unchanged(raw, expected):
    """The alias table is a fallback; it must not alter any existing result."""
    assert normalise_material(raw) == expected
