"""Daylight and escape-window checks when the model never names a window as a space boundary.

Revit's IFC2X3 export bounds spaces by walls and slabs only -- often by thin finish
walls, while the window sits in a separate structural wall behind them -- so no
explicit relationship places a window in a room. Such a room must come out
undetermined, never a measured "0 m2 of window" failure.
"""

from __future__ import annotations

import ifcopenshell
import ifcopenshell.api

from app.modules.ifc_reader.ifc_spatial import (
    IFCSpatialAdjacency,
    _get_storey_name,
    check_daylight_ratios,
)


def _model(*, window_bounds_space: bool):
    """A storey aggregating one 20 m2 room bounded by a wall, plus one 2 m2 window."""
    f = ifcopenshell.api.run("project.create_file", version="IFC4")
    ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcProject", name="Test")
    storey = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBuildingStorey", name="LEVEL 01")
    space = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcSpace", name="BEDROOM")
    ifcopenshell.api.run("aggregate.assign_object", f, products=[space], relating_object=storey)
    qto = ifcopenshell.api.run("pset.add_qto", f, product=space, name="Qto_SpaceBaseQuantities")
    ifcopenshell.api.run("pset.edit_qto", f, qto=qto, properties={"NetFloorArea": 20.0})

    finish_wall = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWall")
    window = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWindow")
    wqto = ifcopenshell.api.run("pset.add_qto", f, product=window, name="Qto_WindowBaseQuantities")
    ifcopenshell.api.run("pset.edit_qto", f, qto=wqto, properties={"Area": 2.0})

    bounded = [finish_wall, window] if window_bounds_space else [finish_wall]
    for element in bounded:
        f.createIfcRelSpaceBoundary(
            ifcopenshell.guid.new(), None, None, None, space, element, None, "PHYSICAL", "INTERNAL"
        )
    return f, space


def test_storey_is_found_through_aggregation():
    _f, space = _model(window_bounds_space=False)

    assert _get_storey_name(space) == "LEVEL 01"


def test_room_with_an_unplaced_window_is_undetermined_not_failed():
    f, _space = _model(window_bounds_space=False)

    [room] = check_daylight_ratios(IFCSpatialAdjacency(f).build(), min_ratio=0.1)

    assert room["passes"] is False
    assert room["undetermined"] is True
    assert "1 of 1 windows" in room["undetermined_reason"]
    assert room["storey_name"] == "LEVEL 01"


def test_room_whose_window_is_a_boundary_is_measured():
    f, _space = _model(window_bounds_space=True)

    [room] = check_daylight_ratios(IFCSpatialAdjacency(f).build(), min_ratio=0.1)

    assert room["total_window_area_m2"] == 2.0
    assert room["passes"] is True
    assert room["undetermined"] is False


def test_room_linker_windows_count_toward_the_room():
    f, space = _model(window_bounds_space=False)
    window = f.by_type("IfcWindow")[0]

    class _Linker:
        def windows_for(self, space_guid):
            return [window] if space_guid == space.GlobalId else []

    [room] = check_daylight_ratios(IFCSpatialAdjacency(f).build(), min_ratio=0.1, room_linker=_Linker())

    assert room["total_window_area_m2"] == 2.0
    assert room["undetermined"] is False


def test_engine_reports_an_undetermined_room_as_not_assessed():
    from unittest.mock import MagicMock

    from app.engines.bimguard_arch_engine import SpatialDaylightEngine

    engine = SpatialDaylightEngine(rules_service=MagicMock())
    engine._get_min_daylight_ratio = lambda: 0.1
    engine._get_min_fire_rating = lambda: None

    result = engine.evaluate({
        "space_guid": "SP-1",
        "space_name": "BEDROOM",
        "floor_area_m2": 20.0,
        "total_window_area_m2": 0.0,
        "undetermined": True,
        "undetermined_reason": "1 of 1 windows in the model could not be placed in any room",
    })

    assert result.status == "NOT_ASSESSED"
    assert "could not be placed" in result.action
