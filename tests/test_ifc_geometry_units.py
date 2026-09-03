"""
Unit-scaling regression tests for IFCGeometryExtractor.

ifcopenshell.geom normalises tessellated coordinates to SI metres whenever
the model declares a length unit.  The extractor used to multiply mesher
output by the model-unit → mm factor, so a millimetre model (factor 1.0)
produced bounding boxes, heights and centroids 1000x too small.

Each test builds a tiny IFC4 file in memory with one extruded box whose raw
file coordinates are known, then checks that the extractor reports the box
in millimetres regardless of the authoring unit.
"""

import math

import pytest

ifcopenshell = pytest.importorskip("ifcopenshell")
pytest.importorskip("ifcopenshell.geom")
pytest.importorskip("ifcopenshell.api")  # attaches ifcopenshell.api submodule

from app.modules.ifc_reader.ifc_geometry import IFCGeometryExtractor  # noqa: E402


def _build_model(
    unit: dict | None, length: float, width: float, height: float,
    ifc_class: str = "IfcWall",
):
    """Return (ifc_file, element) with a box authored in raw model units.

    The profile is written directly as IfcCartesianPoints so the numbers in
    the file are exactly *length*, *width*, *height* -- no API-side unit
    conversion.
    """
    f = ifcopenshell.api.run("project.create_file", version="IFC4")
    ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcProject", name="UnitTest")
    if unit is not None:
        ifcopenshell.api.run("unit.assign_unit", f, length=unit)
    ctx = ifcopenshell.api.run("context.add_context", f, context_type="Model")
    body = ifcopenshell.api.run(
        "context.add_context", f,
        context_type="Model", context_identifier="Body",
        target_view="MODEL_VIEW", parent=ctx,
    )
    element = ifcopenshell.api.run("root.create_entity", f, ifc_class=ifc_class)
    ifcopenshell.api.run("geometry.edit_object_placement", f, product=element)

    pts = [(0.0, 0.0), (length, 0.0), (length, width), (0.0, width), (0.0, 0.0)]
    poly = f.createIfcPolyline([f.createIfcCartesianPoint(p) for p in pts])
    prof = f.createIfcArbitraryClosedProfileDef("AREA", None, poly)
    solid = f.createIfcExtrudedAreaSolid(
        prof,
        f.createIfcAxis2Placement3D(f.createIfcCartesianPoint((0.0, 0.0, 0.0))),
        f.createIfcDirection((0.0, 0.0, 1.0)),
        height,
    )
    rep = f.createIfcShapeRepresentation(body, "Body", "SweptSolid", [solid])
    ifcopenshell.api.run("geometry.assign_representation", f, product=element, representation=rep)
    return f, element


def _extent(bbox: dict, axis: str) -> float:
    return bbox[f"max_{axis}"] - bbox[f"min_{axis}"]


# ── Parametrised over authoring units ────────────────────────────────────────
# (unit spec, raw L, raw W, raw H, model-unit → mm factor)
CASES = [
    pytest.param({"is_metric": True, "raw": "MILLIMETERS"}, 5000.0, 200.0, 2500.0, 1.0, id="millimetre"),
    pytest.param({"is_metric": True, "raw": "METERS"}, 5.0, 0.2, 2.5, 1000.0, id="metre"),
    pytest.param({"is_metric": False, "raw": "FEET"}, 10.0, 1.0, 8.0, 304.8, id="foot"),
    pytest.param({"is_metric": False, "raw": "INCHES"}, 120.0, 12.0, 96.0, 25.4, id="inch"),
]


@pytest.mark.parametrize("unit,L,W,H,to_mm", CASES)
def test_bounding_box_is_in_millimetres(unit, L, W, H, to_mm):
    f, wall = _build_model(unit, L, W, H)
    ex = IFCGeometryExtractor(f)

    bbox = ex.get_bounding_box(wall)
    assert bbox is not None
    assert _extent(bbox, "x") == pytest.approx(L * to_mm, rel=1e-6)
    assert _extent(bbox, "y") == pytest.approx(W * to_mm, rel=1e-6)
    assert _extent(bbox, "z") == pytest.approx(H * to_mm, rel=1e-6)


@pytest.mark.parametrize("unit,L,W,H,to_mm", CASES)
def test_linear_measurements_are_in_millimetres(unit, L, W, H, to_mm):
    f, wall = _build_model(unit, L, W, H)
    ex = IFCGeometryExtractor(f)

    assert ex.get_height_mm(wall) == pytest.approx(H * to_mm, rel=1e-6)
    assert ex.get_width_mm(wall) == pytest.approx(L * to_mm, rel=1e-6)
    assert ex.get_bottom_z_mm(wall) == pytest.approx(0.0, abs=1e-6)
    assert ex.get_top_z_mm(wall) == pytest.approx(H * to_mm, rel=1e-6)
    assert ex.get_corridor_width_mm(wall) == pytest.approx(W * to_mm, rel=1e-6)
    assert ex.get_footprint_perimeter_mm(wall) == pytest.approx(2 * (L + W) * to_mm, rel=1e-6)

    cx, cy, cz = ex.get_centroid(wall)
    assert cx == pytest.approx(L * to_mm / 2, rel=1e-6)
    assert cy == pytest.approx(W * to_mm / 2, rel=1e-6)
    assert cz == pytest.approx(H * to_mm / 2, rel=1e-6)


@pytest.mark.parametrize("unit,L,W,H,to_mm", CASES)
def test_volume_and_area_are_in_si(unit, L, W, H, to_mm):
    f, wall = _build_model(unit, L, W, H)
    ex = IFCGeometryExtractor(f)

    l_m, w_m, h_m = (v * to_mm / 1000.0 for v in (L, W, H))
    assert ex.get_volume_m3(wall) == pytest.approx(l_m * w_m * h_m, rel=1e-4)
    assert ex.get_footprint_area_m2(wall) == pytest.approx(l_m * w_m, rel=1e-4)
    # ifcopenshell.util.shape.get_outer_surface_area() excludes faces that
    # point straight up or down, so for a box it is the four side faces only.
    expected_surface = 2 * (l_m * h_m + w_m * h_m)
    assert ex.get_surface_area_m2(wall) == pytest.approx(expected_surface, rel=1e-4)


@pytest.mark.parametrize("unit,L,W,H,to_mm", CASES)
def test_geometry_value_dispatcher_uses_millimetres(unit, L, W, H, to_mm):
    f, wall = _build_model(unit, L, W, H)
    ex = IFCGeometryExtractor(f)

    assert ex.get_geometry_value(wall, "Height") == pytest.approx(H * to_mm, rel=1e-6)
    assert ex.get_geometry_value(wall, "ClearWidth") == pytest.approx(W * to_mm, rel=1e-6)
    # Sill / handrail heights are relative to a floor Z supplied in mm.
    assert ex.get_geometry_value(wall, "HandrailHeight", floor_z_mm=100.0) == pytest.approx(
        H * to_mm - 100.0, rel=1e-6
    )
    expected_slope = math.degrees(math.atan((H * to_mm) / (L * to_mm)))
    assert ex.get_geometry_value(wall, "Slope") == pytest.approx(expected_slope, abs=0.01)


# ── Scale semantics ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("unit,L,W,H,to_mm", CASES)
def test_unit_scale_keeps_model_unit_to_mm_meaning(unit, L, W, H, to_mm):
    """Module2 scales storey elevations with _unit_scale; it must stay model→mm."""
    f, _ = _build_model(unit, L, W, H)
    ex = IFCGeometryExtractor(f)

    assert ex._unit_scale == pytest.approx(to_mm)
    # Mesher normalises to SI metres for any declared unit → flat 1000 factor.
    assert ex._mesher_scale == pytest.approx(1000.0)


def test_millimetre_model_is_not_1000x_too_small():
    """The original defect: a 5 m wall in a mm model came back as 5 mm."""
    f, wall = _build_model({"is_metric": True, "raw": "MILLIMETERS"}, 5000.0, 200.0, 2500.0)
    ex = IFCGeometryExtractor(f)

    assert ex.get_height_mm(wall) == pytest.approx(2500.0)
    assert ex.get_height_mm(wall) != pytest.approx(2.5)


def test_unitless_model_treats_mesher_output_as_model_units():
    """With no IfcUnitAssignment the mesher passes raw coordinates through."""
    f, wall = _build_model(None, 5000.0, 200.0, 2500.0)
    ex = IFCGeometryExtractor(f)

    assert ex._unit_scale == 1.0
    assert ex._mesher_scale == 1.0
    bbox = ex.get_bounding_box(wall)
    assert _extent(bbox, "x") == pytest.approx(5000.0)
    assert ex.get_height_mm(wall) == pytest.approx(2500.0)


def test_convert_back_units_setting_falls_back_to_model_scale():
    """If the mesher is told to emit model units, the model→mm factor applies."""
    import ifcopenshell.geom

    f, wall = _build_model({"is_metric": True, "raw": "MILLIMETERS"}, 5000.0, 200.0, 2500.0)
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    settings.set("convert-back-units", True)

    scale = IFCGeometryExtractor._detect_mesher_scale_mm(f, settings, unit_scale=1.0)
    assert scale == 1.0

    # End-to-end: an extractor configured that way still reports mm.
    ex = IFCGeometryExtractor(f)
    ex._settings = settings
    ex._mesher_scale = scale
    ex._shape_cache.clear()
    assert ex.get_height_mm(wall) == pytest.approx(2500.0)


def test_extractor_without_model_is_inert():
    ex = IFCGeometryExtractor(None)
    assert ex._unit_scale == 1.0
    assert ex._mesher_scale == 1.0
    assert ex.get_bounding_box(None) is None


# ── ClearWidth on a door/window leaf ─────────────────────────────────────────

def test_clear_width_on_door_uses_overall_width_not_leaf_thickness():
    """A door leaf is a thin panel, not a room footprint.

    get_corridor_width_mm() returns the SHORTEST side of the element's own
    bounding footprint -- correct for a room/corridor (its narrow passable
    dimension), but wrong for a door: the shortest side of a 950mm-wide,
    50mm-thick leaf is the 50mm leaf thickness, not the openable width.
    ClearWidth on an IfcDoor/IfcWindow should resolve like OverallWidth
    (the larger horizontal span) instead.
    """
    unit = {"is_metric": True, "raw": "MILLIMETERS"}
    f, door = _build_model(unit, 950.0, 50.0, 2125.0, ifc_class="IfcDoor")
    ex = IFCGeometryExtractor(f)

    assert ex.get_width_mm(door) == pytest.approx(950.0)
    assert ex.get_corridor_width_mm(door) == pytest.approx(50.0)  # leaf thickness
    assert ex.get_geometry_value(door, "ClearWidth") == pytest.approx(950.0)
    assert ex.get_geometry_value(door, "OverallWidth") == pytest.approx(950.0)


def test_corridor_width_still_used_for_rooms():
    """Non-door/window elements keep the room/corridor narrow-passage algorithm."""
    unit = {"is_metric": True, "raw": "MILLIMETERS"}
    f, wall = _build_model(unit, 5000.0, 1200.0, 2500.0, ifc_class="IfcWall")
    ex = IFCGeometryExtractor(f)

    assert ex.get_geometry_value(wall, "ClearWidth") == pytest.approx(1200.0)
