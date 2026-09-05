"""Emergency-escape-and-rescue window opening (``ifc_spatial.py``).

Two layers, matching the split ``ifc_stair.py`` uses and for the same
reason -- the arithmetic that could produce a wrong verdict should be
provable without an IFC model:

* ``TestComputeEgressClearOpening`` / ``TestIsSleepingRoom`` exercise the
  pure functions directly with plain values.
* ``TestCheckEgressWindowOpenings`` builds a real small IFC4 window (so its
  Pset-based OperationType resolution is genuinely exercised) paired with a
  fake geometry extractor (fixed width/height/sill numbers -- no tessellated
  mesh needed to prove this function's own threshold logic) and a
  duck-typed fake adjacency (this function only ever reads
  ``.has_boundaries`` / ``._space_data``, so a full IfcRelSpaceBoundary
  parse isn't needed to exercise it).
"""

from __future__ import annotations

import pytest

from app.modules.ifc_reader.ifc_spatial import (
    _is_sleeping_room,
    compute_egress_clear_opening,
    check_egress_window_openings,
)

ifcopenshell = pytest.importorskip("ifcopenshell")


# ── Pure layer ────────────────────────────────────────────────────────────────


class TestIsSleepingRoom:
    def test_bedroom_names_match(self):
        assert _is_sleeping_room("Master Bedroom") is True
        assert _is_sleeping_room("Guest Bedroom 2") is True
        assert _is_sleeping_room("bedroom") is True

    def test_non_sleeping_rooms_do_not_match(self):
        assert _is_sleeping_room("Living Room") is False
        assert _is_sleeping_room("Kitchen") is False
        assert _is_sleeping_room("") is False
        assert _is_sleeping_room(None) is False


class TestComputeEgressClearOpening:
    def test_hinged_sash_keeps_most_of_both_dimensions(self):
        result = compute_egress_clear_opening("SIDEHUNGLEFTHAND", 900.0, 1200.0)
        assert result["assessed"] is True
        assert result["clear_width_mm"] == pytest.approx(810.0, abs=0.5)
        assert result["clear_height_mm"] == pytest.approx(1080.0, abs=0.5)
        assert result["clear_area_m2"] == pytest.approx(0.8748, abs=0.001)

    def test_sliding_vertical_sash_halves_only_the_height(self):
        # A single/double-hung window: only ONE sash's height ever opens at
        # once, but the full width is always available -- the two
        # dimensions must NOT shrink by the same fraction.
        result = compute_egress_clear_opening("SlidingVertical", 900.0, 1200.0)
        assert result["assessed"] is True
        assert result["clear_width_mm"] == pytest.approx(810.0, abs=0.5)  # 0.90 fraction
        assert result["clear_height_mm"] == pytest.approx(552.0, abs=0.5)  # 0.46 fraction
        assert result["clear_area_m2"] == pytest.approx(0.44712, abs=0.001)

    def test_sliding_horizontal_sash_halves_only_the_width(self):
        result = compute_egress_clear_opening("SLIDING_HORIZONTAL", 1500.0, 1000.0)
        assert result["clear_width_mm"] == pytest.approx(720.0, abs=0.5)  # 0.48 fraction
        assert result["clear_height_mm"] == pytest.approx(900.0, abs=0.5)  # 0.90 fraction

    def test_fixed_sash_never_opens(self):
        result = compute_egress_clear_opening("FixedCasement", 900.0, 1200.0)
        assert result["assessed"] is True
        assert result["clear_area_m2"] == 0.0

    def test_missing_operation_type_is_undetermined_not_guessed(self):
        result = compute_egress_clear_opening(None, 900.0, 1200.0)
        assert result["assessed"] is False
        assert "not declared" in result["reason"]

    def test_unrecognised_operation_type_is_undetermined_not_guessed(self):
        result = compute_egress_clear_opening("SOME_EXOTIC_MECHANISM", 900.0, 1200.0)
        assert result["assessed"] is False
        assert "unrecognised" in result["reason"]

    def test_missing_geometry_is_undetermined(self):
        result = compute_egress_clear_opening("SIDEHUNGLEFTHAND", None, 1200.0)
        assert result["assessed"] is False


# ── ifcopenshell-facing layer ───────────────────────────────────────────────


class _FakeGeometryExtractor:
    """Fixed width/height/bottom-Z -- this suite is proving
    check_egress_window_openings' own threshold/classification logic, not
    ifc_geometry's mesh math (already covered by test_ifc_stair.py's
    equivalent split)."""

    def __init__(self, width_mm, height_mm, bottom_z_mm, unit_scale: float = 1.0):
        self._width_mm = width_mm
        self._height_mm = height_mm
        self._bottom_z_mm = bottom_z_mm
        self._unit_scale = unit_scale

    def get_width_mm(self, element):
        return self._width_mm

    def get_height_mm(self, element):
        return self._height_mm

    def get_bottom_z_mm(self, element):
        return self._bottom_z_mm


class _FakeAdjacency:
    def __init__(self, space_data: dict):
        self.has_boundaries = True
        self._space_data = space_data


def _build_space_and_window(space_name: str, operation_type: str | None, storey_elevation_mm: float = 0.0):
    from ifcopenshell.api import run

    model = ifcopenshell.file(schema="IFC4")
    run("root.create_entity", model, ifc_class="IfcProject", name="P")
    run("unit.assign_unit", model, length={"is_metric": True, "raw": "MILLIMETERS"})
    site = run("root.create_entity", model, ifc_class="IfcSite", name="Site")
    building = run("root.create_entity", model, ifc_class="IfcBuilding", name="B")
    storey = run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="L1")
    storey.Elevation = storey_elevation_mm
    run("aggregate.assign_object", model, products=[site], relating_object=model.by_type("IfcProject")[0])
    run("aggregate.assign_object", model, products=[building], relating_object=site)
    run("aggregate.assign_object", model, products=[storey], relating_object=building)

    space = run("root.create_entity", model, ifc_class="IfcSpace", name=space_name)
    run("aggregate.assign_object", model, products=[space], relating_object=storey)

    window = run("root.create_entity", model, ifc_class="IfcWindow", name="W1")
    run("spatial.assign_container", model, products=[window], relating_structure=storey)
    if operation_type is not None:
        pset = run("pset.add_pset", model, product=window, name="Pset_WindowPanelProperties")
        run("pset.edit_pset", model, pset=pset, properties={"OperationType": operation_type})

    return space, window


def _adjacency_for(space, window):
    return _FakeAdjacency({
        space.GlobalId: {
            "space": space,
            "boundaries": [{"element": window, "element_type": "IfcWindow", "physical": True}],
        }
    })


_THRESHOLDS = dict(
    min_clear_area_m2=0.35, min_clear_width_mm=380.0,
    min_clear_height_mm=380.0, max_sill_height_mm=1100.0,
)


class TestCheckEgressWindowOpenings:
    def test_compliant_sliding_window_passes_with_exact_measurements(self):
        space, window = _build_space_and_window("Master Bedroom", "SLIDINGVERTICAL")
        adjacency = _adjacency_for(space, window)
        geo = _FakeGeometryExtractor(width_mm=900.0, height_mm=1200.0, bottom_z_mm=200.0)

        results = check_egress_window_openings(adjacency, geo, **_THRESHOLDS)
        assert len(results) == 1
        r = results[0]
        assert r["passes"] is True
        assert r["best_window"]["clear_width_mm"] == pytest.approx(810.0, abs=0.5)
        assert r["best_window"]["clear_height_mm"] == pytest.approx(552.0, abs=0.5)
        assert r["best_window"]["sill_height_mm"] == pytest.approx(200.0, abs=0.5)

    def test_fixed_window_fails_on_zero_clear_area_not_undetermined(self):
        # A FIXEDCASEMENT window IS assessed -- its operation type is known
        # and its clear opening is a determinate zero, not "undetermined".
        # It must still fail the room (nothing to escape through), just via
        # the clear_area check rather than a missing-data reason.
        space, window = _build_space_and_window("Bedroom 2", "FIXEDCASEMENT")
        adjacency = _adjacency_for(space, window)
        geo = _FakeGeometryExtractor(width_mm=900.0, height_mm=1200.0, bottom_z_mm=200.0)

        results = check_egress_window_openings(adjacency, geo, **_THRESHOLDS)
        assert results[0]["passes"] is False
        assert results[0]["best_window"]["clear_area_m2"] == 0.0
        assert results[0]["checks"]["clear_area"] is False

    def test_window_with_no_declared_operation_type_is_undetermined(self):
        space, window = _build_space_and_window("Bedroom 3", operation_type=None)
        adjacency = _adjacency_for(space, window)
        geo = _FakeGeometryExtractor(width_mm=900.0, height_mm=1200.0, bottom_z_mm=200.0)

        results = check_egress_window_openings(adjacency, geo, **_THRESHOLDS)
        assert results[0]["passes"] is False
        assert results[0]["windows"][0]["assessed"] is False

    def test_sill_above_maximum_fails_that_check_specifically(self):
        space, window = _build_space_and_window("Master Bedroom", "SLIDINGVERTICAL")
        adjacency = _adjacency_for(space, window)
        # 1300mm sill -- well above the 1100mm max in _THRESHOLDS, while
        # clear area/width/height all still comfortably pass.
        geo = _FakeGeometryExtractor(width_mm=900.0, height_mm=1200.0, bottom_z_mm=1300.0)

        results = check_egress_window_openings(adjacency, geo, **_THRESHOLDS)
        r = results[0]
        assert r["passes"] is False
        assert r["checks"]["sill_height"] is False
        # Area/width/height all still comfortably pass on their own -- only
        # the sill check is what fails this room.
        assert r["checks"]["clear_area"] is True
        assert r["checks"]["clear_width"] is True
        assert r["checks"]["clear_height"] is True

    def test_non_sleeping_room_is_not_included_at_all(self):
        space, window = _build_space_and_window("Living Room", "SLIDINGVERTICAL")
        adjacency = _adjacency_for(space, window)
        geo = _FakeGeometryExtractor(width_mm=900.0, height_mm=1200.0, bottom_z_mm=200.0)

        results = check_egress_window_openings(adjacency, geo, **_THRESHOLDS)
        assert results == []

    def test_no_boundaries_returns_empty(self):
        adjacency = _FakeAdjacency({})
        adjacency.has_boundaries = False
        geo = _FakeGeometryExtractor(900.0, 1200.0, 200.0)
        assert check_egress_window_openings(adjacency, geo, **_THRESHOLDS) == []
