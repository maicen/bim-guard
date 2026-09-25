"""Digital Inspector geometry tools and the per-process IFCReader cache.

Builds a tiny in-memory IFC4 model with two boxes at a known separation
(mirrors tests/test_ifc_geometry_units.py's `_build_model` pattern), so the
tools can be exercised against real ifcopenshell geometry rather than mocks.
"""

from __future__ import annotations

import numpy as np
import pytest

ifcopenshell = pytest.importorskip("ifcopenshell")
pytest.importorskip("ifcopenshell.geom")
pytest.importorskip("ifcopenshell.api")

from app.digital_inspector import tools as dit  # noqa: E402


def _build_two_wall_model(gap_mm: float = 500.0):
    """One IfcWall at the origin, a second IfcWall offset gap_mm along X.

    Both are 1000x200x2000mm boxes authored directly in millimetres (no unit
    conversion surprises), so the second wall's near face sits exactly
    gap_mm from the first wall's far face.
    """
    f = ifcopenshell.api.run("project.create_file", version="IFC4")
    ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcProject", name="ToolTest")
    ifcopenshell.api.run("unit.assign_unit", f, length={"is_metric": True, "raw": "MILLIMETRE"})
    ctx = ifcopenshell.api.run("context.add_context", f, context_type="Model")
    body = ifcopenshell.api.run(
        "context.add_context", f,
        context_type="Model", context_identifier="Body",
        target_view="MODEL_VIEW", parent=ctx,
    )

    def _wall(name: str, x_offset: float):
        element = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWall", name=name)
        ifcopenshell.api.run("geometry.edit_object_placement", f, product=element)
        if x_offset:
            # edit_object_placement's matrix is interpreted in SI (metres) by
            # default regardless of the model's declared length unit -- the
            # model is authored in millimetres, so convert.
            matrix = np.eye(4)
            matrix[0, 3] = x_offset / 1000.0
            ifcopenshell.api.geometry.edit_object_placement(f, product=element, matrix=matrix)
        pts = [(0.0, 0.0), (1000.0, 0.0), (1000.0, 200.0), (0.0, 200.0), (0.0, 0.0)]
        poly = f.createIfcPolyline([f.createIfcCartesianPoint(p) for p in pts])
        prof = f.createIfcArbitraryClosedProfileDef("AREA", None, poly)
        solid = f.createIfcExtrudedAreaSolid(
            prof,
            f.createIfcAxis2Placement3D(f.createIfcCartesianPoint((0.0, 0.0, 0.0))),
            f.createIfcDirection((0.0, 0.0, 1.0)),
            2000.0,
        )
        rep = f.createIfcShapeRepresentation(body, "Body", "SweptSolid", [solid])
        ifcopenshell.api.run("geometry.assign_representation", f, product=element, representation=rep)
        return element

    wall_a = _wall("Wall-A", 0.0)
    wall_b = _wall("Wall-B", 1000.0 + gap_mm)  # starts right after wall_a's far face (x=1000)
    return f, wall_a, wall_b


@pytest.fixture
def reader(monkeypatch):
    """Build a real IFCReader over the two-wall model, injected via the tools cache (no disk I/O)."""
    from app.modules.ifc_reader import IFCReader

    ifc_file, wall_a, wall_b = _build_two_wall_model(gap_mm=500.0)
    r = IFCReader.__new__(IFCReader)
    r.file_path = None
    r.ifc_file = ifc_file
    from app.modules.ifc_reader.ifc_geometry import IFCGeometryExtractor

    r.geometry_extractor = IFCGeometryExtractor(ifc_file)

    monkeypatch.setattr(dit, "_get_cached_reader", lambda project_id: r)
    return r, wall_a, wall_b


def test_find_elements_returns_all_walls(reader):
    r, wall_a, wall_b = reader

    result = dit.find_elements.invoke({"project_id": 1, "ifc_class": "IfcWall"})

    assert result["match_count"] == 2
    guids = {m["guid"] for m in result["matches"]}
    assert guids == {wall_a.GlobalId, wall_b.GlobalId}


def test_find_elements_filters_by_name_contains(reader):
    r, wall_a, wall_b = reader

    result = dit.find_elements.invoke(
        {"project_id": 1, "ifc_class": "IfcWall", "name_contains": "Wall-B"}
    )

    assert result["match_count"] == 1
    assert result["matches"][0]["guid"] == wall_b.GlobalId


def test_find_elements_on_unknown_class_returns_error_not_exception(reader):
    result = dit.find_elements.invoke({"project_id": 1, "ifc_class": "NotARealIfcClass"})
    assert "error" in result


def test_get_element_geometry_returns_bbox_and_centroid(reader):
    r, wall_a, _wall_b = reader

    result = dit.get_element_geometry.invoke({"project_id": 1, "guid": wall_a.GlobalId})

    assert result["ifc_class"] == "IfcWall"
    bbox = result["bounding_box_mm"]
    assert bbox["min_x"] == pytest.approx(0.0, abs=1.0)
    assert bbox["max_x"] == pytest.approx(1000.0, abs=1.0)
    assert result["centroid_mm"]["x"] == pytest.approx(500.0, abs=1.0)


def test_get_element_geometry_unknown_guid_returns_error(reader):
    result = dit.get_element_geometry.invoke({"project_id": 1, "guid": "does-not-exist"})
    assert "error" in result


def test_get_distance_between_elements_matches_known_gap(reader):
    r, wall_a, wall_b = reader

    result = dit.get_distance_between_elements.invoke(
        {"project_id": 1, "guid_a": wall_a.GlobalId, "guid_b": wall_b.GlobalId}
    )

    assert result["distance_mm"] == pytest.approx(500.0, abs=2.0)


def test_get_distance_between_elements_unknown_guid_returns_error(reader):
    r, wall_a, _wall_b = reader

    result = dit.get_distance_between_elements.invoke(
        {"project_id": 1, "guid_a": wall_a.GlobalId, "guid_b": "does-not-exist"}
    )

    assert "error" in result


def test_geometry_tools_registered_in_digital_inspector_tools():
    names = {t.name for t in dit.DIGITAL_INSPECTOR_TOOLS}
    assert {"find_elements", "get_element_geometry", "get_distance_between_elements"} <= names


class TestReaderCache:
    def test_second_call_with_same_hash_reuses_the_same_reader(self, monkeypatch):
        dit._READER_CACHE.clear()
        calls = []

        class FakeProjectsService:
            def get_project(self, project_id):
                return {"ifc_md5_hash": "abc123"}

        class FakeModelsService:
            def resolve_primary_path(self, project_id):
                calls.append(project_id)
                return __file__  # any real path; IFCReader() itself is monkeypatched away below

        class FakeContainer:
            projects_service = FakeProjectsService()
            models_service = FakeModelsService()

        monkeypatch.setattr("app.bootstrap.get_container", lambda: FakeContainer())
        monkeypatch.setattr("app.modules.ifc_reader.IFCReader", lambda path: object())

        first = dit._get_cached_reader(project_id=7)
        second = dit._get_cached_reader(project_id=7)

        assert first is second
        assert len(calls) == 1  # resolve_primary_path (and therefore the parse) only ran once

    def test_hash_change_invalidates_the_cache(self, monkeypatch):
        dit._READER_CACHE.clear()
        hashes = iter(["hash-1", "hash-2"])

        class FakeProjectsService:
            def get_project(self, project_id):
                return {"ifc_md5_hash": next(hashes)}

        class FakeModelsService:
            def resolve_primary_path(self, project_id):
                return __file__

        class FakeContainer:
            projects_service = FakeProjectsService()
            models_service = FakeModelsService()

        monkeypatch.setattr("app.bootstrap.get_container", lambda: FakeContainer())
        monkeypatch.setattr("app.modules.ifc_reader.IFCReader", lambda path: object())

        first = dit._get_cached_reader(project_id=9)
        second = dit._get_cached_reader(project_id=9)

        assert first is not second
