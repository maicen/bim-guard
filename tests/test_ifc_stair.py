"""Per-riser/tread/landing/handrail geometry analysis (``ifc_stair.py``).

Two layers, matching the module's own split and ``test_ifc_seismic.py``'s
precedent:

* The classes up to ``TestAgainstModel`` need no IFC file. They exercise the
  pure numpy algorithms directly against hand-built point clouds -- this is
  where a wrong riser count or a fabricated uniformity verdict would
  actually come from, so it must be provable without a model.
* ``TestAgainstModel`` builds a small IFC4 model in-memory: one straight
  3-tread stair flight (uniform 175 mm risers, 280 mm goings, 900 mm wide),
  built as an explicit triangulated mesh so the expected riser/tread values
  are exact, not dependent on extrusion-placement arithmetic.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.modules.ifc_reader import ifc_stair as st

# ── Local frame (PCA) ──────────────────────────────────────────────────────────


class TestLocalFrameFromXY:
    def test_dominant_axis_is_the_long_direction(self):
        # A 1000 x 100 mm rectangle-ish point cloud aligned with world X.
        rng = np.linspace(0, 1000, 50)
        xy = np.column_stack([rng, np.zeros_like(rng)])
        xy = np.vstack([xy, xy + [0, 100]])  # give it some lateral spread too
        frame = st.local_frame_from_xy(xy)
        assert frame is not None
        origin, u, v = frame
        assert abs(abs(u[0]) - 1.0) < 0.05  # u ~ (+-1, 0)
        assert abs(abs(v[1]) - 1.0) < 0.05  # v ~ (0, +-1)

    def test_too_few_points_is_none(self):
        assert st.local_frame_from_xy([[0, 0], [1, 1]]) is None


# ── Step-band clustering ────────────────────────────────────────────────────


def _synthetic_treads(n_treads=4, riser=175.0, going=280.0, width=900.0, points_per_tread=6):
    """Build (run, lateral, z) arrays for n_treads uniform tread-top rectangles."""
    run, lateral, z = [], [], []
    for i in range(n_treads):
        z_i = (i + 1) * riser
        run_lo, run_hi = i * going, i * going + going
        for r in np.linspace(run_lo, run_hi, points_per_tread):
            for lat in (0.0, width / 2.0, width):
                run.append(r)
                lateral.append(lat)
                z.append(z_i)
    return np.array(run), np.array(lateral), np.array(z)


class TestClusterStepBands:
    def test_detects_correct_number_of_treads(self):
        run, _lateral, z = _synthetic_treads(n_treads=4)
        bands = st.cluster_step_bands(run, z)
        assert len(bands) == 4

    def test_band_run_and_z_match_input(self):
        run, _lateral, z = _synthetic_treads(n_treads=3, riser=175.0, going=280.0)
        bands = st.cluster_step_bands(run, z)
        assert [round(b["z_mean"]) for b in bands] == [175, 350, 525]
        assert bands[0]["run_min"] == pytest.approx(0.0, abs=1.0)
        assert bands[0]["run_max"] == pytest.approx(280.0, abs=1.0)

    def test_noise_within_tolerance_stays_one_band(self):
        z = np.array([175.0, 175.5, 174.7, 175.2])
        run = np.array([0.0, 50.0, 100.0, 150.0])
        bands = st.cluster_step_bands(run, z, z_gap_mm=40.0)
        assert len(bands) == 1

    def test_bands_sorted_by_run_not_z(self):
        # Two bands whose Z order and run order happen to agree except this
        # checks the sort key is explicitly run_min, not insertion/Z order.
        run = np.array([500.0, 501.0, 0.0, 1.0])
        z = np.array([350.0, 350.0, 175.0, 175.0])
        bands = st.cluster_step_bands(run, z, z_gap_mm=40.0)
        assert len(bands) == 2
        assert bands[0]["run_min"] < bands[1]["run_min"]

    def test_empty_input_returns_empty_list(self):
        assert st.cluster_step_bands(np.array([]), np.array([])) == []

    def test_lateral_mean_reported_when_lateral_supplied(self):
        run = np.array([0.0, 0.0, 300.0, 300.0])
        z = np.array([175.0, 175.0, 350.0, 350.0])
        lateral = np.array([0.0, 900.0, 100.0, 1000.0])
        bands = st.cluster_step_bands(run, z, lateral=lateral, z_gap_mm=40.0)
        assert len(bands) == 2
        assert bands[0]["lateral_mean"] == pytest.approx(450.0)
        assert bands[1]["lateral_mean"] == pytest.approx(550.0)

    def test_lateral_mean_absent_when_not_supplied(self):
        run = np.array([0.0, 300.0])
        z = np.array([175.0, 350.0])
        bands = st.cluster_step_bands(run, z, z_gap_mm=40.0)
        assert "lateral_mean" not in bands[0]


# ── Riser/going derivation ──────────────────────────────────────────────────


class TestDeriveFlightSteps:
    def test_uniform_stair_reports_zero_difference(self):
        run, _lateral, z = _synthetic_treads(n_treads=4, riser=175.0, going=280.0)
        bands = st.cluster_step_bands(run, z)
        steps = st.derive_flight_steps(bands)
        assert steps["tread_count"] == 4
        assert steps["riser_count"] == 3
        assert steps["riser_difference_mm"] == 0.0
        assert steps["going_difference_mm"] == 0.0
        assert steps["min_riser_mm"] == pytest.approx(175.0, abs=0.5)
        assert steps["min_going_mm"] == pytest.approx(280.0, abs=0.5)

    def test_non_uniform_riser_is_detected(self):
        # Build 3 bands by hand: risers 175, 200 -- a 25 mm code violation.
        bands = [
            {"z_mean": 0.0, "run_min": 0.0, "run_max": 280.0},
            {"z_mean": 175.0, "run_min": 280.0, "run_max": 560.0},
            {"z_mean": 375.0, "run_min": 560.0, "run_max": 840.0},
        ]
        steps = st.derive_flight_steps(bands)
        assert steps["risers_mm"] == [175.0, 200.0]
        assert steps["riser_difference_mm"] == 25.0

    def test_single_band_has_no_series(self):
        bands = [{"z_mean": 175.0, "run_min": 0.0, "run_max": 280.0}]
        steps = st.derive_flight_steps(bands)
        assert steps["tread_count"] == 1
        assert steps["riser_count"] is None
        assert steps["goings_mm"] == []
        assert steps["min_riser_mm"] is None


# ── Minimum clear width sampling ─────────────────────────────────────────────


class TestMinClearWidthByBand:
    def test_uniform_width_returns_that_width(self):
        rng = np.linspace(0, 1000, 200)
        run = np.tile(rng, 2)
        lateral = np.concatenate([np.zeros_like(rng), np.full_like(rng, 900.0)])
        width = st.min_clear_width_by_band(run, lateral, band_mm=100.0)
        assert width == pytest.approx(900.0, abs=1.0)

    def test_pinch_point_is_caught_not_averaged_away(self):
        # Full 900 mm width everywhere except a 700 mm pinch around run=500
        # (e.g. a mid-flight newel post) -- a whole-footprint min-rect would
        # miss this; banded sampling must not.
        run, lateral = [], []
        for r in np.linspace(0, 1000, 200):
            lo, hi = (100.0, 800.0) if 450 <= r <= 550 else (0.0, 900.0)
            run.extend([r, r])
            lateral.extend([lo, hi])
        width = st.min_clear_width_by_band(np.array(run), np.array(lateral), band_mm=50.0)
        assert width == pytest.approx(700.0, abs=5.0)

    def test_too_few_points_returns_none(self):
        assert st.min_clear_width_by_band(np.array([1.0]), np.array([1.0])) is None


# ── Gap / continuity detection ────────────────────────────────────────────────


class TestMergeRunIntervals:
    def test_continuous_intervals_merge_into_one_segment(self):
        # Face intervals from a solid run: e.g. two abutting faces [0,400], [400,900].
        segments, gaps = st.merge_run_intervals([(0.0, 400.0), (400.0, 900.0)], gap_mm=150.0)
        assert segments == [(0.0, 900.0)]
        assert gaps == []

    def test_real_gap_between_intervals_is_reported(self):
        # Two rail sections: [0,800] and [1200,2000] -- a genuine 400mm break.
        segments, gaps = st.merge_run_intervals([(0.0, 800.0), (1200.0, 2000.0)], gap_mm=150.0)
        assert segments == [(0.0, 800.0), (1200.0, 2000.0)]
        assert gaps == [(800.0, 1200.0)]

    def test_small_separation_below_threshold_still_merges(self):
        # A 50mm seam between two faces (ordinary tessellation gap) is not a
        # real break when the threshold is 150mm.
        segments, gaps = st.merge_run_intervals([(0.0, 400.0), (450.0, 900.0)], gap_mm=150.0)
        assert segments == [(0.0, 900.0)]
        assert gaps == []

    def test_empty_input_returns_empty(self):
        assert st.merge_run_intervals([]) == ([], [])


# ── Guard opening / baluster spacing ──────────────────────────────────────────

# Identity local frame (run=x, lateral=y) so these tests can hand-build
# vertices directly in "local" coordinates without a real footprint to run
# PCA against.
_ORIGIN = np.array([0.0, 0.0])
_U = np.array([1.0, 0.0])
_V = np.array([0.0, 1.0])


def _vertical_member_mesh(segments):
    """One flat quad face (2 triangles) per (x0, x1, z0, z1) segment, all at
    y=0 -- enough for guard_opening_gap_at_height, which only reads each
    face's run- and Z-extent, never true 3D volume."""
    verts: list[tuple[float, float, float]] = []
    faces: list[list[int]] = []
    for x0, x1, z0, z1 in segments:
        base = len(verts)
        verts.extend([(x0, 0.0, z0), (x1, 0.0, z0), (x1, 0.0, z1), (x0, 0.0, z1)])
        faces.append([base, base + 1, base + 2])
        faces.append([base, base + 2, base + 3])
    return np.array(verts, dtype=float), np.array(faces, dtype=np.intp)


class TestGuardOpeningGapAtHeight:
    def test_gap_between_two_balusters(self):
        # Balusters at x=[0,20] and x=[120,140], full height -- clear gap 100mm.
        verts, faces = _vertical_member_mesh([(0, 20, 0, 1000), (120, 140, 0, 1000)])
        gap = st.guard_opening_gap_at_height(verts, faces, _ORIGIN, _U, _V, 500.0, (0.0, 140.0))
        assert gap == pytest.approx(100.0, abs=1.0)

    def test_solid_panel_has_no_gap(self):
        verts, faces = _vertical_member_mesh([(0, 500, 0, 1000)])
        gap = st.guard_opening_gap_at_height(verts, faces, _ORIGIN, _U, _V, 500.0, (0.0, 500.0))
        assert gap == pytest.approx(0.0, abs=1.0)

    def test_completely_open_height_reports_full_span_not_none(self):
        # A baluster only in the LOWER half -- sampling above it finds
        # nothing there, which must read as "fully open" (worst case), not
        # "unmeasurable".
        verts, faces = _vertical_member_mesh([(0, 20, 0, 500)])
        gap = st.guard_opening_gap_at_height(verts, faces, _ORIGIN, _U, _V, 750.0, (0.0, 140.0))
        assert gap == pytest.approx(140.0, abs=1.0)

    def test_empty_mesh_is_none(self):
        assert st.guard_opening_gap_at_height(None, None, _ORIGIN, _U, _V, 500.0, (0.0, 100.0)) is None


class TestGuardOpeningProfile:
    def test_worst_height_wins(self):
        # Balusters full height except a wider gap band around z=600-700.
        verts, faces = _vertical_member_mesh([
            (0, 20, 0, 1000), (60, 80, 0, 550), (60, 80, 750, 1000),
            (120, 140, 0, 1000),
        ])
        profile = st.guard_opening_profile(verts, faces, _ORIGIN, _U, _V, 0.0, 1000.0, (0.0, 140.0))
        # At z~625 (inside the 550-750 missing band for the middle member),
        # the middle member contributes nothing, widening that sample's gap
        # beyond the uniform 40mm gaps elsewhere.
        assert profile["max_opening_mm"] > 40.0

    def test_uniform_baluster_spacing(self):
        # 5 balusters, 20mm wide, evenly spaced with a 90mm clear gap.
        segments = [(i * 110, i * 110 + 20, 0, 1000) for i in range(5)]
        verts, faces = _vertical_member_mesh(segments)
        profile = st.guard_opening_profile(
            verts, faces, _ORIGIN, _U, _V, 0.0, 1000.0, (0.0, 4 * 110 + 20)
        )
        assert profile["max_opening_mm"] == pytest.approx(90.0, abs=1.0)

    def test_degenerate_height_range_returns_none(self):
        verts, faces = _vertical_member_mesh([(0, 20, 0, 1000)])
        profile = st.guard_opening_profile(verts, faces, _ORIGIN, _U, _V, 500.0, 500.0, (0.0, 20.0))
        assert profile["max_opening_mm"] is None


# ── End-to-end against a real (small) IFC4 model ──────────────────────────────

ifcopenshell = pytest.importorskip("ifcopenshell")

# Realistic stair proportions matter here: PCA-based walking-direction
# detection (local_frame_from_xy) picks the direction of GREATEST horizontal
# spread as "run". A real stair flight is always much longer than it is
# wide; a toy fixture with only 2-3 treads can end up narrower in run than
# in width, which flips run/lateral and is a known v1 limitation (see
# ifc_stair.py's module docstring), not something this test should exercise.
RISER_MM = 175.0
GOING_MM = 280.0
WIDTH_MM = 800.0
N_TREADS = 6


def _tread_quad_triangles(x0, x1, y0, y1, z):
    """Two CCW-from-above triangles for one tread-top rectangle (+Z normal)."""
    return [
        [(x0, y0, z), (x1, y0, z), (x1, y1, z)],
        [(x0, y0, z), (x1, y1, z), (x0, y1, z)],
    ]


def _riser_quad_triangles(x, z0, z1, y0, y1):
    """Two triangles for a vertical riser face (near-horizontal Z-normal ~ 0)."""
    return [
        [(x, y0, z0), (x, y1, z0), (x, y1, z1)],
        [(x, y0, z0), (x, y1, z1), (x, y0, z1)],
    ]


def _build_stair_model():
    from ifcopenshell.api import run

    model = ifcopenshell.file(schema="IFC4")
    run("root.create_entity", model, ifc_class="IfcProject", name="Stair")
    run("unit.assign_unit", model, length={"is_metric": True, "raw": "MILLIMETERS"})
    ctx = run("context.add_context", model, context_type="Model")
    body = run(
        "context.add_context",
        model,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=ctx,
    )
    site = run("root.create_entity", model, ifc_class="IfcSite", name="Site")
    building = run("root.create_entity", model, ifc_class="IfcBuilding", name="B")
    storey = run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="L1")
    run("aggregate.assign_object", model, products=[site], relating_object=model.by_type("IfcProject")[0])
    run("aggregate.assign_object", model, products=[building], relating_object=site)
    run("aggregate.assign_object", model, products=[storey], relating_object=building)

    triangles: list[list[tuple[float, float, float]]] = []
    for i in range(N_TREADS):
        z = (i + 1) * RISER_MM
        x0, x1 = i * GOING_MM, i * GOING_MM + GOING_MM
        triangles += _tread_quad_triangles(x0, x1, 0.0, WIDTH_MM, z)
        triangles += _riser_quad_triangles(x0, z - RISER_MM, z, 0.0, WIDTH_MM)

    coord_list: list[tuple[float, float, float]] = []
    coord_index: list[tuple[int, int, int]] = []
    for tri in triangles:
        base = len(coord_list)
        coord_list.extend(tri)
        coord_index.append((base + 1, base + 2, base + 3))  # IFC CoordIndex is 1-based

    points = model.create_entity("IfcCartesianPointList3D", CoordList=coord_list)
    mesh = model.create_entity(
        "IfcTriangulatedFaceSet", Coordinates=points, CoordIndex=coord_index
    )
    rep = model.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=body,
        RepresentationIdentifier="Body",
        RepresentationType="Tessellation",
        Items=[mesh],
    )

    flight = run("root.create_entity", model, ifc_class="IfcStairFlight", name="Flight 1")
    run("spatial.assign_container", model, products=[flight], relating_structure=storey)
    run("geometry.assign_representation", model, product=flight, representation=rep)
    run(
        "geometry.edit_object_placement",
        model,
        product=flight,
        matrix=np.eye(4),
        is_si=False,
    )
    return model, flight


def _build_stair_model_variant(include_risers: bool):
    """Same shape as ``_build_stair_model`` but lets the caller omit riser
    faces entirely, to prove open-riser detection fires on a genuinely open
    stair and not just clears a closed one."""
    from ifcopenshell.api import run

    model = ifcopenshell.file(schema="IFC4")
    run("root.create_entity", model, ifc_class="IfcProject", name="Stair")
    run("unit.assign_unit", model, length={"is_metric": True, "raw": "MILLIMETERS"})
    ctx = run("context.add_context", model, context_type="Model")
    body = run(
        "context.add_context",
        model,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=ctx,
    )
    site = run("root.create_entity", model, ifc_class="IfcSite", name="Site")
    building = run("root.create_entity", model, ifc_class="IfcBuilding", name="B")
    storey = run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="L1")
    run("aggregate.assign_object", model, products=[site], relating_object=model.by_type("IfcProject")[0])
    run("aggregate.assign_object", model, products=[building], relating_object=site)
    run("aggregate.assign_object", model, products=[storey], relating_object=building)

    triangles: list[list[tuple[float, float, float]]] = []
    for i in range(N_TREADS):
        z = (i + 1) * RISER_MM
        x0, x1 = i * GOING_MM, i * GOING_MM + GOING_MM
        triangles += _tread_quad_triangles(x0, x1, 0.0, WIDTH_MM, z)
        if include_risers:
            triangles += _riser_quad_triangles(x0, z - RISER_MM, z, 0.0, WIDTH_MM)

    coord_list: list[tuple[float, float, float]] = []
    coord_index: list[tuple[int, int, int]] = []
    for tri in triangles:
        base = len(coord_list)
        coord_list.extend(tri)
        coord_index.append((base + 1, base + 2, base + 3))

    points = model.create_entity("IfcCartesianPointList3D", CoordList=coord_list)
    mesh = model.create_entity(
        "IfcTriangulatedFaceSet", Coordinates=points, CoordIndex=coord_index
    )
    rep = model.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=body,
        RepresentationIdentifier="Body",
        RepresentationType="Tessellation",
        Items=[mesh],
    )

    flight = run("root.create_entity", model, ifc_class="IfcStairFlight", name="Flight 1")
    run("spatial.assign_container", model, products=[flight], relating_structure=storey)
    run("geometry.assign_representation", model, product=flight, representation=rep)
    run("geometry.edit_object_placement", model, product=flight, matrix=np.eye(4), is_si=False)
    return model, flight


def _build_winder_like_model(lateral_shift_per_tread: float):
    """Same shape as ``_build_stair_model``, but each tread's lateral (Y)
    range is shifted by *lateral_shift_per_tread* mm relative to the last --
    a stand-in for a winder's rotating walking line, sufficient to exercise
    the drift DETECTOR without modelling true winder/spiral geometry (a
    bigger task deferred to v2 -- see the module docstring)."""
    from ifcopenshell.api import run

    model = ifcopenshell.file(schema="IFC4")
    run("root.create_entity", model, ifc_class="IfcProject", name="Stair")
    run("unit.assign_unit", model, length={"is_metric": True, "raw": "MILLIMETERS"})
    ctx = run("context.add_context", model, context_type="Model")
    body = run(
        "context.add_context", model, context_type="Model",
        context_identifier="Body", target_view="MODEL_VIEW", parent=ctx,
    )
    site = run("root.create_entity", model, ifc_class="IfcSite", name="Site")
    building = run("root.create_entity", model, ifc_class="IfcBuilding", name="B")
    storey = run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="L1")
    run("aggregate.assign_object", model, products=[site], relating_object=model.by_type("IfcProject")[0])
    run("aggregate.assign_object", model, products=[building], relating_object=site)
    run("aggregate.assign_object", model, products=[storey], relating_object=building)

    triangles: list[list[tuple[float, float, float]]] = []
    for i in range(N_TREADS):
        z = (i + 1) * RISER_MM
        x0, x1 = i * GOING_MM, i * GOING_MM + GOING_MM
        y_shift = i * lateral_shift_per_tread
        triangles += _tread_quad_triangles(x0, x1, y_shift, y_shift + WIDTH_MM, z)
        triangles += _riser_quad_triangles(x0, z - RISER_MM, z, y_shift, y_shift + WIDTH_MM)

    coord_list: list[tuple[float, float, float]] = []
    coord_index: list[tuple[int, int, int]] = []
    for tri in triangles:
        base = len(coord_list)
        coord_list.extend(tri)
        coord_index.append((base + 1, base + 2, base + 3))

    points = model.create_entity("IfcCartesianPointList3D", CoordList=coord_list)
    mesh = model.create_entity("IfcTriangulatedFaceSet", Coordinates=points, CoordIndex=coord_index)
    rep = model.create_entity(
        "IfcShapeRepresentation", ContextOfItems=body, RepresentationIdentifier="Body",
        RepresentationType="Tessellation", Items=[mesh],
    )
    flight = run("root.create_entity", model, ifc_class="IfcStairFlight", name="Flight 1")
    run("spatial.assign_container", model, products=[flight], relating_structure=storey)
    run("geometry.assign_representation", model, product=flight, representation=rep)
    run("geometry.edit_object_placement", model, product=flight, matrix=np.eye(4), is_si=False)
    return model, flight


class TestCurvatureDetection:
    def test_straight_flight_is_not_flagged(self):
        from app.modules.ifc_reader.ifc_geometry import IFCGeometryExtractor

        model, flight = _build_winder_like_model(lateral_shift_per_tread=0.0)
        analysis = st.analyze_stair_flight(flight, IFCGeometryExtractor(model))
        assert analysis.get("winder_suspected") is not True
        assert not any("curvature" in w or "winder" in w for w in analysis["warnings"])

    def test_drifting_treads_are_flagged(self):
        from app.modules.ifc_reader.ifc_geometry import IFCGeometryExtractor

        # 40mm lateral shift per tread x 5 gaps between 6 treads = 200mm
        # total drift -- well above DEFAULT_CURVATURE_DRIFT_MM (75mm).
        model, flight = _build_winder_like_model(lateral_shift_per_tread=40.0)
        analysis = st.analyze_stair_flight(flight, IFCGeometryExtractor(model))
        assert analysis["winder_suspected"] is True
        assert any("curvature" in w or "winder" in w for w in analysis["warnings"])
        # Not pinned to an exact value -- PCA re-centres/rotates its axes
        # once the footprint itself is skewed by the shift, so the drift
        # doesn't come out as a clean 40mm x 5 gaps. What matters is that
        # it's clearly and substantially above the 75mm threshold.
        assert analysis["tread_lateral_drift_mm"] > 150.0

    def test_small_drift_below_threshold_is_not_flagged(self):
        from app.modules.ifc_reader.ifc_geometry import IFCGeometryExtractor

        # 5mm/tread x 5 gaps = 25mm total -- real-world noise territory,
        # well under the 75mm threshold.
        model, flight = _build_winder_like_model(lateral_shift_per_tread=5.0)
        analysis = st.analyze_stair_flight(flight, IFCGeometryExtractor(model))
        assert analysis.get("winder_suspected") is not True


class TestOpenRiserDetection:
    def test_closed_riser_stair_is_not_flagged(self):
        from app.modules.ifc_reader.ifc_geometry import IFCGeometryExtractor

        model, flight = _build_stair_model_variant(include_risers=True)
        analysis = st.analyze_stair_flight(flight, IFCGeometryExtractor(model))
        assert analysis["open_riser"] is False

    def test_genuinely_open_riser_stair_is_flagged(self):
        from app.modules.ifc_reader.ifc_geometry import IFCGeometryExtractor

        model, flight = _build_stair_model_variant(include_risers=False)
        analysis = st.analyze_stair_flight(flight, IFCGeometryExtractor(model))
        assert analysis["open_riser"] is True
        # Riser/going/rise values must still resolve from tread-top faces
        # alone -- the absence of riser faces should not break those.
        assert analysis["tread_count"] == N_TREADS


def _tessellated_representation(model, body, triangles):
    coord_list: list[tuple[float, float, float]] = []
    coord_index: list[tuple[int, int, int]] = []
    for tri in triangles:
        base = len(coord_list)
        coord_list.extend(tri)
        coord_index.append((base + 1, base + 2, base + 3))
    points = model.create_entity("IfcCartesianPointList3D", CoordList=coord_list)
    mesh = model.create_entity(
        "IfcTriangulatedFaceSet", Coordinates=points, CoordIndex=coord_index
    )
    return model.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=body,
        RepresentationIdentifier="Body",
        RepresentationType="Tessellation",
        Items=[mesh],
    )


def _box_triangles(x0, x1, y0, y1, z0, z1):
    """12 triangles (2 per face) for an axis-aligned box, with each face
    wound to give a genuinely OUTWARD-pointing normal (bottom -Z, top +Z,
    y0 -Y, y1 +Y, x0 -X, x1 +X). This matters since _face_up_points (used
    by analyze_landing's slope measurement) selects faces by their normal's
    Z-component -- an earlier version of this helper left three faces
    inward-wound, which a flat landing's "top" face alone should have
    isolated to z-constant points (slope 0) instead picked up the bottom
    face too (whose normal was accidentally also +Z), reading the box's
    own THICKNESS as slope. Caught by test_clear_dimensions_match_footprint
    asserting slope_deg == 0 on a flat slab and getting ~5.7 degrees back."""
    corners = {
        (0, 0, 0): (x0, y0, z0), (1, 0, 0): (x1, y0, z0),
        (1, 1, 0): (x1, y1, z0), (0, 1, 0): (x0, y1, z0),
        (0, 0, 1): (x0, y0, z1), (1, 0, 1): (x1, y0, z1),
        (1, 1, 1): (x1, y1, z1), (0, 1, 1): (x0, y1, z1),
    }
    faces = [
        [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)],  # bottom (-Z)
        [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)],  # top (+Z)
        [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)],  # y0 side (-Y)
        [(0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)],  # y1 side (+Y)
        [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)],  # x0 side (-X)
        [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)],  # x1 side (+X)
    ]
    triangles = []
    for quad in faces:
        a, b, c, d = (corners[k] for k in quad)
        triangles.append([a, b, c])
        triangles.append([a, c, d])
    return triangles


def _base_model():
    from ifcopenshell.api import run

    model = ifcopenshell.file(schema="IFC4")
    run("root.create_entity", model, ifc_class="IfcProject", name="P")
    run("unit.assign_unit", model, length={"is_metric": True, "raw": "MILLIMETERS"})
    ctx = run("context.add_context", model, context_type="Model")
    body = run(
        "context.add_context", model, context_type="Model",
        context_identifier="Body", target_view="MODEL_VIEW", parent=ctx,
    )
    site = run("root.create_entity", model, ifc_class="IfcSite", name="Site")
    building = run("root.create_entity", model, ifc_class="IfcBuilding", name="B")
    storey = run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="L1")
    run("aggregate.assign_object", model, products=[site], relating_object=model.by_type("IfcProject")[0])
    run("aggregate.assign_object", model, products=[building], relating_object=site)
    run("aggregate.assign_object", model, products=[storey], relating_object=building)
    return model, body, storey


class TestAnalyzeLanding:
    def test_clear_dimensions_match_footprint(self):
        from ifcopenshell.api import run
        from app.modules.ifc_reader.ifc_geometry import IFCGeometryExtractor

        model, body, storey = _base_model()
        # A 2000 (long, run) x 1200 (short, lateral) x 200mm-thick landing slab.
        triangles = _box_triangles(0.0, 2000.0, 0.0, 1200.0, 0.0, 200.0)
        rep = _tessellated_representation(model, body, triangles)
        slab = run("root.create_entity", model, ifc_class="IfcSlab", name="Landing", predefined_type="LANDING")
        run("spatial.assign_container", model, products=[slab], relating_structure=storey)
        run("geometry.assign_representation", model, product=slab, representation=rep)
        run("geometry.edit_object_placement", model, product=slab, matrix=np.eye(4), is_si=False)

        analysis = st.analyze_landing(slab, IFCGeometryExtractor(model))
        assert analysis["clear_width_mm"] == pytest.approx(1200.0, abs=5.0)
        assert analysis["clear_length_mm"] == pytest.approx(2000.0, abs=5.0)
        assert analysis["elevation_mm"] == pytest.approx(200.0, abs=1.0)
        assert analysis["clear_area_mm2"] == pytest.approx(2000.0 * 1200.0, rel=0.02)
        assert analysis["slope_deg"] == pytest.approx(0.0, abs=1.0)


class TestAnalyzeRailing:
    def test_height_and_path_length(self):
        from ifcopenshell.api import run
        from app.modules.ifc_reader.ifc_geometry import IFCGeometryExtractor

        model, body, storey = _base_model()
        # A straight 2000mm handrail, 40mm-square profile, top at z=920mm.
        triangles = _box_triangles(0.0, 2000.0, 0.0, 40.0, 880.0, 920.0)
        rep = _tessellated_representation(model, body, triangles)
        railing = run(
            "root.create_entity", model, ifc_class="IfcRailing", name="Rail 1",
            predefined_type="HANDRAIL",
        )
        run("spatial.assign_container", model, products=[railing], relating_structure=storey)
        run("geometry.assign_representation", model, product=railing, representation=rep)
        run("geometry.edit_object_placement", model, product=railing, matrix=np.eye(4), is_si=False)

        analysis = st.analyze_railing(railing, IFCGeometryExtractor(model), floor_z_mm=0.0)
        assert analysis["path_length_mm"] == pytest.approx(2000.0, abs=5.0)
        # A level rail: top-of-rail height (920mm) is uniform along its
        # length, so min/max height above the floor are equal -- 880mm is
        # the rail's own underside, reported separately.
        assert analysis["max_height_mm"] == pytest.approx(920.0, abs=5.0)
        assert analysis["min_height_mm"] == pytest.approx(920.0, abs=5.0)
        assert analysis["min_bottom_elevation_mm"] == pytest.approx(880.0, abs=5.0)
        assert analysis["continuous_segments"] == 1
        # A plain HANDRAIL gets no "guard checks not computed" caveat.
        assert not any("baluster" in w for w in analysis["warnings"])

    def test_gap_in_rail_produces_two_segments(self):
        from ifcopenshell.api import run
        from app.modules.ifc_reader.ifc_geometry import IFCGeometryExtractor

        model, body, storey = _base_model()
        # Two separate rail sections with a 400mm gap between them.
        triangles = _box_triangles(0.0, 800.0, 0.0, 40.0, 880.0, 920.0)
        triangles += _box_triangles(1200.0, 2000.0, 0.0, 40.0, 880.0, 920.0)
        rep = _tessellated_representation(model, body, triangles)
        railing = run(
            "root.create_entity", model, ifc_class="IfcRailing", name="Rail 2",
            predefined_type="HANDRAIL",
        )
        run("spatial.assign_container", model, products=[railing], relating_structure=storey)
        run("geometry.assign_representation", model, product=railing, representation=rep)
        run("geometry.edit_object_placement", model, product=railing, matrix=np.eye(4), is_si=False)

        analysis = st.analyze_railing(railing, IFCGeometryExtractor(model))
        assert analysis["continuous_segments"] == 2
        assert analysis.get("gap_locations_mm")
        assert analysis["max_gap_length_mm"] == pytest.approx(400.0, abs=5.0)

    def test_no_gap_reports_zero_length_not_missing(self):
        from ifcopenshell.api import run
        from app.modules.ifc_reader.ifc_geometry import IFCGeometryExtractor

        model, body, storey = _base_model()
        triangles = _box_triangles(0.0, 2000.0, 0.0, 40.0, 880.0, 920.0)
        rep = _tessellated_representation(model, body, triangles)
        railing = run(
            "root.create_entity", model, ifc_class="IfcRailing", name="Rail Continuous",
            predefined_type="HANDRAIL",
        )
        run("spatial.assign_container", model, products=[railing], relating_structure=storey)
        run("geometry.assign_representation", model, product=railing, representation=rep)
        run("geometry.edit_object_placement", model, product=railing, matrix=np.eye(4), is_si=False)

        analysis = st.analyze_railing(railing, IFCGeometryExtractor(model))
        assert analysis["max_gap_length_mm"] == 0.0
        assert "gap_locations_mm" not in analysis

    def test_guardrail_carries_the_not_yet_computed_warning(self):
        from ifcopenshell.api import run
        from app.modules.ifc_reader.ifc_geometry import IFCGeometryExtractor

        model, body, storey = _base_model()
        triangles = _box_triangles(0.0, 2000.0, 0.0, 40.0, 900.0, 1100.0)
        rep = _tessellated_representation(model, body, triangles)
        railing = run(
            "root.create_entity", model, ifc_class="IfcRailing", name="Guard 1",
            predefined_type="GUARDRAIL",
        )
        run("spatial.assign_container", model, products=[railing], relating_structure=storey)
        run("geometry.assign_representation", model, product=railing, representation=rep)
        run("geometry.edit_object_placement", model, product=railing, matrix=np.eye(4), is_si=False)

        analysis = st.analyze_railing(railing, IFCGeometryExtractor(model))
        assert analysis["predefined_type"] == "GUARDRAIL"
        assert any("baluster" in w for w in analysis["warnings"])
        # The caveat doesn't block ordinary checks from still resolving.
        assert analysis.get("max_height_mm") is None  # no floor_z_mm supplied here
        assert analysis["max_top_elevation_mm"] == pytest.approx(1100.0, abs=5.0)

    def test_unset_predefined_type_is_treated_as_possibly_a_guard(self):
        from ifcopenshell.api import run
        from app.modules.ifc_reader.ifc_geometry import IFCGeometryExtractor

        model, body, storey = _base_model()
        triangles = _box_triangles(0.0, 2000.0, 0.0, 40.0, 900.0, 1100.0)
        rep = _tessellated_representation(model, body, triangles)
        # No predefined_type given -- defaults to NOTDEFINED/unset.
        railing = run("root.create_entity", model, ifc_class="IfcRailing", name="Rail 3")
        run("spatial.assign_container", model, products=[railing], relating_structure=storey)
        run("geometry.assign_representation", model, product=railing, representation=rep)
        run("geometry.edit_object_placement", model, product=railing, matrix=np.eye(4), is_si=False)

        analysis = st.analyze_railing(railing, IFCGeometryExtractor(model))
        assert any("baluster" in w for w in analysis["warnings"])

    def test_baluster_spacing_measured_from_real_geometry(self):
        from ifcopenshell.api import run
        from app.modules.ifc_reader.ifc_geometry import IFCGeometryExtractor

        model, body, storey = _base_model()
        # Top rail (z 980-1000) + bottom rail at floor (z 0-20), both
        # continuous, plus 5 balusters (20mm wide) with a known 90mm clear
        # gap between them (pitch 110mm), spanning the rails' full height.
        triangles = _box_triangles(0.0, 460.0, 0.0, 40.0, 980.0, 1000.0)  # top rail
        triangles += _box_triangles(0.0, 460.0, 0.0, 40.0, 0.0, 20.0)      # bottom rail
        for i in range(5):
            x0 = i * 110.0
            triangles += _box_triangles(x0, x0 + 20.0, 0.0, 40.0, 0.0, 1000.0)
        rep = _tessellated_representation(model, body, triangles)
        railing = run(
            "root.create_entity", model, ifc_class="IfcRailing", name="Guard Balusters",
            predefined_type="GUARDRAIL",
        )
        run("spatial.assign_container", model, products=[railing], relating_structure=storey)
        run("geometry.assign_representation", model, product=railing, representation=rep)
        run("geometry.edit_object_placement", model, product=railing, matrix=np.eye(4), is_si=False)

        analysis = st.analyze_railing(railing, IFCGeometryExtractor(model), floor_z_mm=0.0)
        assert analysis["max_opening_mm"] == pytest.approx(90.0, abs=10.0)
        # Bottom rail is continuous at floor level -- no gap underneath it.
        assert analysis["bottom_clear_gap_mm"] == pytest.approx(0.0, abs=5.0)
        assert analysis["guard_max_opening_mm"] == pytest.approx(90.0, abs=10.0)

    def test_bottom_clear_gap_when_bottom_rail_is_elevated(self):
        from ifcopenshell.api import run
        from app.modules.ifc_reader.ifc_geometry import IFCGeometryExtractor

        model, body, storey = _base_model()
        # Top rail (z 980-1000) + bottom rail raised 100mm off the floor
        # (z 100-120), both continuous -- the classic "gap a small object
        # could pass under" design.
        triangles = _box_triangles(0.0, 2000.0, 0.0, 40.0, 980.0, 1000.0)
        triangles += _box_triangles(0.0, 2000.0, 0.0, 40.0, 100.0, 120.0)
        rep = _tessellated_representation(model, body, triangles)
        railing = run(
            "root.create_entity", model, ifc_class="IfcRailing", name="Guard Raised Rail",
            predefined_type="GUARDRAIL",
        )
        run("spatial.assign_container", model, products=[railing], relating_structure=storey)
        run("geometry.assign_representation", model, product=railing, representation=rep)
        run("geometry.edit_object_placement", model, product=railing, matrix=np.eye(4), is_si=False)

        analysis = st.analyze_railing(railing, IFCGeometryExtractor(model), floor_z_mm=0.0)
        assert analysis["bottom_clear_gap_mm"] == pytest.approx(100.0, abs=5.0)

    def test_handrail_does_not_compute_opening_fields(self):
        from ifcopenshell.api import run
        from app.modules.ifc_reader.ifc_geometry import IFCGeometryExtractor

        model, body, storey = _base_model()
        triangles = _box_triangles(0.0, 2000.0, 0.0, 40.0, 880.0, 920.0)
        rep = _tessellated_representation(model, body, triangles)
        railing = run(
            "root.create_entity", model, ifc_class="IfcRailing", name="Plain Handrail",
            predefined_type="HANDRAIL",
        )
        run("spatial.assign_container", model, products=[railing], relating_structure=storey)
        run("geometry.assign_representation", model, product=railing, representation=rep)
        run("geometry.edit_object_placement", model, product=railing, matrix=np.eye(4), is_si=False)

        analysis = st.analyze_railing(railing, IFCGeometryExtractor(model))
        assert "max_opening_mm" not in analysis
        assert "guard_max_opening_mm" not in analysis


class TestEndToEndThroughIFCReader:
    """Proves the wiring, not just the module: a rule asking for a
    stair-derived property (MinRiserHeight) resolves through
    IFCReader.extract_for_compliance() -> ComplianceComparator, the same
    path every other rule family takes -- not just through calling
    ifc_stair functions directly."""

    @pytest.fixture(scope="class")
    def model_path(self, tmp_path_factory):
        model, _flight = _build_stair_model()
        path = tmp_path_factory.mktemp("stair") / "flight.ifc"
        model.write(str(path))
        return path

    @staticmethod
    def _evaluate(model_path, rules):
        from app.modules.ifc_reader import IFCReader
        from app.modules.comparator import ComplianceComparator

        extraction = IFCReader(model_path).extract_for_compliance(rules)
        results = ComplianceComparator().validate_metadata(extraction)
        return {r["rule_ref"]: r for r in results}

    def test_rule_within_tolerance_passes(self, model_path):
        rule = {
            "rule_id": 1,
            "reference": "TEST-1",
            "target_ifc_class": "IfcStairFlight",
            "property_name": "MinRiserHeight",
            "operator": ">=",
            "check_value": 150.0,
            "unit": "mm",
        }
        results = self._evaluate(model_path, [rule])
        assert results["TEST-1"]["status"] == "PASS"

    def test_rule_violated_by_the_model_fails(self, model_path):
        rule = {
            "rule_id": 2,
            "reference": "TEST-2",
            "target_ifc_class": "IfcStairFlight",
            "property_name": "MaxRiserHeight",
            "operator": "<=",
            "check_value": 100.0,  # the model's risers are 175mm
            "unit": "mm",
        }
        results = self._evaluate(model_path, [rule])
        assert results["TEST-2"]["status"] == "FAIL"

    def test_riser_difference_is_zero_for_a_uniform_stair(self, model_path):
        rule = {
            "rule_id": 3,
            "reference": "TEST-3",
            "target_ifc_class": "IfcStairFlight",
            "property_name": "RiserHeightDifference",
            "operator": "<=",
            "check_value": 6.0,
            "unit": "mm",
        }
        results = self._evaluate(model_path, [rule])
        assert results["TEST-3"]["status"] == "PASS"

    def test_winder_warning_reaches_the_final_result_not_just_the_module(self, tmp_path_factory):
        """The gap this closes: ifc_stair.analyze_stair_flight() has always
        computed the winder warning, but until now it was discarded inside
        rich_detail and never reached extract_for_compliance()'s output --
        so a PASS on a winder stair looked exactly like a PASS on a straight
        one. This proves the warning survives the whole pipeline."""
        model, _flight = _build_winder_like_model(lateral_shift_per_tread=40.0)
        path = tmp_path_factory.mktemp("winder") / "winder.ifc"
        model.write(str(path))

        rule = {
            "rule_id": 4,
            "reference": "TEST-4",
            "target_ifc_class": "IfcStairFlight",
            "property_name": "MinTreadDepth",
            "operator": ">=",
            "check_value": 200.0,
            "unit": "mm",
        }
        results = self._evaluate(path, [rule])
        result = results["TEST-4"]
        # The value itself still resolves and can still pass -- the warning
        # is a caveat riding alongside it, not a status override.
        assert result["status"] == "PASS"
        element = result["all_elements"][0]
        assert element["data_quality_warnings"]
        assert any(
            "winder" in w or "curvature" in w for w in element["data_quality_warnings"]
        )

    def test_straight_stair_carries_no_data_quality_warnings(self, model_path):
        rule = {
            "rule_id": 5,
            "reference": "TEST-5",
            "target_ifc_class": "IfcStairFlight",
            "property_name": "MinRiserHeight",
            "operator": ">=",
            "check_value": 150.0,
            "unit": "mm",
        }
        results = self._evaluate(model_path, [rule])
        element = results["TEST-5"]["all_elements"][0]
        assert not element["data_quality_warnings"]

    def test_newly_wired_quick_fix_properties_resolve(self, model_path):
        """FlightStartElevation, NumberOfRisersDetected -- computed since the
        first stair-engine commit, only wired to a queryable property name
        just now. Prove they reach a real verdict, not just the raw
        analysis dict."""
        rule_elevation = {
            "rule_id": 8,
            "reference": "TEST-8",
            "target_ifc_class": "IfcStairFlight",
            "property_name": "FlightStartElevation",
            "operator": "<=",
            "check_value": 10.0,  # the model's flight starts at z~0
            "unit": "mm",
        }
        rule_riser_count = {
            "rule_id": 9,
            "reference": "TEST-9",
            "target_ifc_class": "IfcStairFlight",
            "property_name": "NumberOfRisersDetected",
            "operator": "==",
            "check_value": N_TREADS - 1,
        }
        results = self._evaluate(model_path, [rule_elevation, rule_riser_count])
        assert results["TEST-8"]["status"] == "PASS"
        assert results["TEST-9"]["status"] == "PASS"

    def test_guard_max_opening_resolves_through_the_full_pipeline(self, tmp_path_factory):
        """GuardMaxOpening is a brand new derived property (baluster/opening
        analysis) -- prove it reaches a real rule verdict through
        IFCReader.extract_for_compliance(), not just through calling
        ifc_stair.analyze_railing() directly."""
        from ifcopenshell.api import run as ifc_run

        model, body, storey = _base_model()
        # 90mm clear baluster gap -- a 100mm sphere-passing rule must FAIL,
        # a 150mm one must PASS.
        triangles = _box_triangles(0.0, 460.0, 0.0, 40.0, 980.0, 1000.0)
        triangles += _box_triangles(0.0, 460.0, 0.0, 40.0, 0.0, 20.0)
        for i in range(5):
            x0 = i * 110.0
            triangles += _box_triangles(x0, x0 + 20.0, 0.0, 40.0, 0.0, 1000.0)
        rep = _tessellated_representation(model, body, triangles)
        railing = ifc_run(
            "root.create_entity", model, ifc_class="IfcRailing", name="Guard",
            predefined_type="GUARDRAIL",
        )
        ifc_run("spatial.assign_container", model, products=[railing], relating_structure=storey)
        ifc_run("geometry.assign_representation", model, product=railing, representation=rep)
        ifc_run("geometry.edit_object_placement", model, product=railing, matrix=np.eye(4), is_si=False)

        path = tmp_path_factory.mktemp("guard") / "guard.ifc"
        model.write(str(path))

        rule_fails = {
            "rule_id": 6,
            "reference": "TEST-6",
            "target_ifc_class": "IfcRailing",
            "property_name": "GuardMaxOpening",
            "operator": "<=",
            "check_value": 50.0,  # the guard's real gap is ~90mm
            "unit": "mm",
        }
        rule_passes = {
            "rule_id": 7,
            "reference": "TEST-7",
            "target_ifc_class": "IfcRailing",
            "property_name": "GuardMaxOpening",
            "operator": "<=",
            "check_value": 150.0,
            "unit": "mm",
        }
        results = self._evaluate(path, [rule_fails, rule_passes])
        assert results["TEST-6"]["status"] == "FAIL"
        assert results["TEST-7"]["status"] == "PASS"


class TestAgainstModel:
    @pytest.fixture(scope="class")
    def analysis(self):
        from app.modules.ifc_reader.ifc_geometry import IFCGeometryExtractor

        model, flight = _build_stair_model()
        extractor = IFCGeometryExtractor(model)
        return st.analyze_stair_flight(flight, extractor)

    def test_detects_all_treads(self, analysis):
        assert analysis["tread_count"] == N_TREADS

    def test_riser_and_going_values_are_uniform(self, analysis):
        assert analysis["risers_mm"] == pytest.approx([RISER_MM] * (N_TREADS - 1), abs=1.0)
        assert analysis["goings_mm"] == pytest.approx([GOING_MM] * (N_TREADS - 1), abs=1.0)
        assert analysis["riser_difference_mm"] == pytest.approx(0.0, abs=1.0)
        assert analysis["going_difference_mm"] == pytest.approx(0.0, abs=1.0)

    def test_total_rise_matches_top_minus_bottom(self, analysis):
        assert analysis["total_rise_mm"] == pytest.approx(N_TREADS * RISER_MM, abs=1.0)

    def test_start_and_end_elevation_are_reported(self, analysis):
        assert analysis["start_elevation_mm"] == pytest.approx(0.0, abs=1.0)
        assert analysis["end_elevation_mm"] == pytest.approx(N_TREADS * RISER_MM, abs=1.0)
        assert analysis["end_elevation_mm"] - analysis["start_elevation_mm"] == pytest.approx(
            analysis["total_rise_mm"], abs=0.1
        )

    def test_riser_count_matches_uniform_series(self, analysis):
        assert analysis["riser_count"] == N_TREADS - 1

    def test_min_clear_width_matches_flight_width(self, analysis):
        assert analysis["min_clear_width_mm"] == pytest.approx(WIDTH_MM, abs=5.0)

    def test_no_open_riser_detected(self, analysis):
        assert analysis["open_riser"] is False
