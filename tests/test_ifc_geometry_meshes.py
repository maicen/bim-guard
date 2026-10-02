"""Mesh prefetch and point-to-surface distance on IFCGeometryExtractor.

Each test builds real extruded boxes in an IFC4 millimetre model, so the
tessellation, world coordinates and unit scaling are ifcopenshell's own.
"""

import pytest

ifcopenshell = pytest.importorskip("ifcopenshell")
pytest.importorskip("ifcopenshell.geom")
pytest.importorskip("ifcopenshell.api")
pytest.importorskip("scipy")

from app.modules.ifc_reader.ifc_geometry import IFCGeometryExtractor  # noqa: E402


def _model(boxes: list[tuple[float, float, float, float, float, float]]):
    """Return (file, walls): one IfcWall per (x, y, z, dx, dy, dz) box, in mm."""
    f = ifcopenshell.api.run("project.create_file", version="IFC4")
    ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcProject", name="MeshTest")
    ifcopenshell.api.run("unit.assign_unit", f, length={"is_metric": True, "raw": "MILLIMETERS"})
    ctx = ifcopenshell.api.run("context.add_context", f, context_type="Model")
    body = ifcopenshell.api.run(
        "context.add_context", f,
        context_type="Model", context_identifier="Body", target_view="MODEL_VIEW", parent=ctx,
    )
    walls = []
    for x, y, z, dx, dy, dz in boxes:
        wall = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWall")
        ifcopenshell.api.run("geometry.edit_object_placement", f, product=wall)
        pts = [(x, y), (x + dx, y), (x + dx, y + dy), (x, y + dy), (x, y)]
        poly = f.createIfcPolyline([f.createIfcCartesianPoint(p) for p in pts])
        solid = f.createIfcExtrudedAreaSolid(
            f.createIfcArbitraryClosedProfileDef("AREA", None, poly),
            f.createIfcAxis2Placement3D(f.createIfcCartesianPoint((0.0, 0.0, z))),
            f.createIfcDirection((0.0, 0.0, 1.0)),
            dz,
        )
        rep = f.createIfcShapeRepresentation(body, "Body", "SweptSolid", [solid])
        ifcopenshell.api.run("geometry.assign_representation", f, product=wall, representation=rep)
        walls.append(wall)
    return f, walls


def test_point_distance_is_exact_opposite_the_middle_of_a_large_face():
    # A 10 m long face has vertices only at its ends; a point 300 mm off its
    # middle is 5 m from every vertex but 300 mm from the surface.
    f, [wall] = _model([(0.0, 0.0, 0.0, 10000.0, 200.0, 3000.0)])
    ex = IFCGeometryExtractor(f)

    assert ex.distance_from_point_mm(wall, (5000.0, 500.0, 1500.0)) == pytest.approx(300.0, abs=0.5)


def test_point_distance_without_geometry_is_none():
    f, [wall] = _model([(0.0, 0.0, 0.0, 1000.0, 200.0, 3000.0)])
    ex = IFCGeometryExtractor(f)

    assert ex.distance_from_point_mm(wall, None) is None
    assert ex.distance_from_point_mm(f.createIfcWall(ifcopenshell.guid.new()), (0.0, 0.0, 0.0)) is None


def test_prefetched_meshes_answer_boxes_and_distances_like_sequential_tessellation():
    boxes = [(i * 2000.0, 0.0, 0.0, 1000.0, 200.0, 3000.0) for i in range(20)]
    f, walls = _model(boxes)
    sequential = IFCGeometryExtractor(f)
    prefetched = IFCGeometryExtractor(f)

    assert prefetched.prefetch_meshes(walls) == 20
    assert prefetched._shape_cache == {}  # served from meshes, never re-tessellated
    for wall in walls:
        assert prefetched.get_bounding_box(wall) == pytest.approx(sequential.get_bounding_box(wall))
    assert prefetched.calculate_shortest_distance(walls[0], walls[1]) == pytest.approx(1000.0, abs=0.5)
    assert prefetched._shape_cache == {}
