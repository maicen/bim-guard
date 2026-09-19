"""Tests for how Blue Halo reads element geometry, and for SB-001's Stage 2 progress.

WHAT WENT WRONG, SO IT IS CLEAR WHAT THESE PIN

    A seismic run over a seven-model project sat at "IFC Parsing", 33%, for
    minutes on end with the backend near 0% CPU in Task Manager, which reads as a
    hang. It was not blocked. On a 32-thread machine one busy thread is ~3% of
    the total, and the thread was computing: reading every vertex of every
    faceted brep in an 80 MB architecture model one wrapper call at a time, and
    re-reading a shared ``IfcRepresentationMap`` once per element that
    instantiates it. Measured on that model: ~580 ms per proxy element, 209 of
    15,306 elements in 120 s; after the fix the whole model takes ~10 s.

    Nothing reported progress inside a model, so the slowness was also
    invisible. The tests below pin each half:

    **The reader gives the same boxes.** The walker now reads raw arguments and
    transforms with numpy, so the numbers are asserted exactly, shape by shape.
    ``_apply_many`` is compared against the scalar formula bit for bit, because a
    box that moves in its last digit can flip a clash that only just touches.

    **A shared source is read once.** That is the multiplier behind the hang, and
    the cheapest way to lose it again is to drop the cache argument.

    **Progress is reported within a model**, so a slow model reads as slow.

NO LIVE DATABASE, NO CACHED FILES. Models are synthesised in memory.

Run: uv run pytest tests/test_halo_geometry_extraction.py -v
"""

from __future__ import annotations

import numpy as np
import pytest

from app.modules.blue_halo import halo_volume_generator as hvg
from app.modules.phase_6 import phase_6d_seismic as seismic
from app.services import pipeline_tracker as pt
from app.services.pipeline_tracker import SB_ENGINE, SEISMIC_RUN_KEY, Stage

ifcopenshell = pytest.importorskip("ifcopenshell", reason="Blue Halo needs ifcopenshell")

#: A 0.1 x 0.2 x 0.3 m box in a model whose unit is the metre, so 1000 converts to mm.
CUBE_M = (0.1, 0.2, 0.3)
METRES_TO_MM = 1000.0


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _point(model, *xyz):
    return model.create_entity("IfcCartesianPoint", Coordinates=tuple(float(v) for v in xyz))


def _placement(model, x=0.0, y=0.0, z=0.0):
    axes = model.create_entity("IfcAxis2Placement3D", Location=_point(model, x, y, z))
    return model.create_entity("IfcLocalPlacement", RelativePlacement=axes)


def _brep_box(model, width, depth, height):
    """A closed faceted brep with one corner at the origin."""
    corners = [
        (0, 0, 0), (width, 0, 0), (width, depth, 0), (0, depth, 0),
        (0, 0, height), (width, 0, height), (width, depth, height), (0, depth, height),
    ]  # fmt: skip
    points = [_point(model, *c) for c in corners]
    faces = []
    for ring in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        loop = model.create_entity("IfcPolyLoop", Polygon=[points[i] for i in ring])
        bound = model.create_entity("IfcFaceOuterBound", Bound=loop, Orientation=True)
        faces.append(model.create_entity("IfcFace", Bounds=[bound]))
    shell = model.create_entity("IfcClosedShell", CfsFaces=faces)
    return model.create_entity("IfcFacetedBrep", Outer=shell)


def _proxy(model, items, placement):
    """A building element proxy whose body is *items*, placed at *placement*."""
    body = model.create_entity(
        "IfcShapeRepresentation",
        RepresentationIdentifier="Body",
        RepresentationType="Brep",
        Items=list(items),
    )
    shape = model.create_entity("IfcProductDefinitionShape", Representations=[body])
    return model.create_entity(
        "IfcBuildingElementProxy",
        GlobalId=ifcopenshell.guid.new(),
        ObjectPlacement=placement,
        Representation=shape,
    )


def _mapped_box_source(model):
    """An ``IfcRepresentationMap`` holding one brep box, plus a way to instantiate it."""
    body = model.create_entity(
        "IfcShapeRepresentation",
        RepresentationIdentifier="Body",
        RepresentationType="Brep",
        Items=[_brep_box(model, *CUBE_M)],
    )
    origin = model.create_entity("IfcAxis2Placement3D", Location=_point(model, 0, 0, 0))
    source = model.create_entity(
        "IfcRepresentationMap", MappingOrigin=origin, MappedRepresentation=body
    )

    def instance(x=0.0, y=0.0, z=0.0):
        target = model.create_entity(
            "IfcCartesianTransformationOperator3D",
            LocalOrigin=_point(model, x, y, z),
            Scale=1.0,
        )
        return model.create_entity("IfcMappedItem", MappingSource=source, MappingTarget=target)

    return instance


def _corners(box):
    return (box.min.x, box.min.y, box.min.z), (box.max.x, box.max.y, box.max.z)


# ---------------------------------------------------------------------------
# The transform is the scalar formula, bit for bit
# ---------------------------------------------------------------------------


def test_apply_many_is_bit_identical_to_transforming_one_point_at_a_time():
    """A product would reorder the sums; a touching clash cannot survive that."""
    rng = np.random.default_rng(7)
    matrix = rng.normal(size=(4, 4))
    points = rng.normal(scale=5e4, size=(500, 3))

    def scalar(m, x, y, z):
        return (
            float(m[0][0] * x + m[0][1] * y + m[0][2] * z + m[0][3]),
            float(m[1][0] * x + m[1][1] * y + m[1][2] * z + m[1][3]),
            float(m[2][0] * x + m[2][1] * y + m[2][2] * z + m[2][3]),
        )

    expected = np.array([scalar(matrix, *p) for p in points])

    assert np.array_equal(hvg._apply_many(matrix, points), expected)


# ---------------------------------------------------------------------------
# Same boxes as before, shape by shape
# ---------------------------------------------------------------------------


def test_a_faceted_brep_gives_its_exact_box_in_mm():
    model = ifcopenshell.file(schema="IFC4")
    element = _proxy(model, [_brep_box(model, *CUBE_M)], _placement(model, 1.0, 2.0, 3.0))

    low, high = _corners(hvg.element_bbox_mm(element, METRES_TO_MM))

    assert low == pytest.approx((1000.0, 2000.0, 3000.0))
    assert high == pytest.approx((1100.0, 2200.0, 3300.0))


def test_a_triangulated_face_set_gives_its_exact_box():
    model = ifcopenshell.file(schema="IFC4")
    coords = model.create_entity(
        "IfcCartesianPointList3D",
        CoordList=[(0.0, 0.0, 0.0), (0.4, 0.0, 0.0), (0.0, 0.5, 0.0), (0.0, 0.0, 0.6)],
    )
    faces = model.create_entity("IfcTriangulatedFaceSet", Coordinates=coords)
    element = _proxy(model, [faces], _placement(model))

    low, high = _corners(hvg.element_bbox_mm(element, METRES_TO_MM))

    assert low == pytest.approx((0.0, 0.0, 0.0))
    assert high == pytest.approx((400.0, 500.0, 600.0))


def test_a_mapped_item_is_placed_by_its_target_and_the_element():
    model = ifcopenshell.file(schema="IFC4")
    instance = _mapped_box_source(model)
    element = _proxy(model, [instance(x=1.0)], _placement(model, y=2.0))

    low, high = _corners(hvg.element_bbox_mm(element, METRES_TO_MM, {}))

    assert low == pytest.approx((1000.0, 2000.0, 0.0))
    assert high == pytest.approx((1100.0, 2200.0, 300.0))


def test_an_element_with_no_placement_or_no_shape_has_no_box():
    model = ifcopenshell.file(schema="IFC4")
    unplaced = _proxy(model, [_brep_box(model, *CUBE_M)], None)
    shapeless = model.create_entity(
        "IfcBuildingElementProxy", GlobalId=ifcopenshell.guid.new(), ObjectPlacement=_placement(model)
    )

    assert hvg.element_bbox_mm(unplaced, METRES_TO_MM) is None
    assert hvg.element_bbox_mm(shapeless, METRES_TO_MM) is None


# ---------------------------------------------------------------------------
# A shared source is read once -- the multiplier behind the hang
# ---------------------------------------------------------------------------


@pytest.fixture
def brep_walks(monkeypatch):
    """Count how many times a brep's vertices are actually read."""
    calls = []
    real = hvg._face_vertices

    def counting(faces):
        calls.append(1)
        return real(faces)

    monkeypatch.setattr(hvg, "_face_vertices", counting)
    return calls


def test_a_mapped_source_is_read_once_however_many_elements_instantiate_it(brep_walks):
    model = ifcopenshell.file(schema="IFC4")
    instance = _mapped_box_source(model)
    elements = [_proxy(model, [instance(x=float(i))], _placement(model)) for i in range(6)]

    shared: hvg.MappedSourceCache = {}
    for element in elements:
        hvg.element_bbox_mm(element, METRES_TO_MM, shared)

    assert len(brep_walks) == 1


def test_without_a_cache_every_instance_rereads_its_source(brep_walks):
    """The behaviour the cache exists to avoid, pinned so the test above means something."""
    model = ifcopenshell.file(schema="IFC4")
    instance = _mapped_box_source(model)
    elements = [_proxy(model, [instance(x=float(i))], _placement(model)) for i in range(6)]

    for element in elements:
        hvg.element_bbox_mm(element, METRES_TO_MM)

    assert len(brep_walks) == 6


def test_the_cache_changes_the_speed_and_never_the_box():
    model = ifcopenshell.file(schema="IFC4")
    instance = _mapped_box_source(model)
    elements = [
        _proxy(model, [instance(x=0.5 * i, z=0.25 * i)], _placement(model, y=float(i)))
        for i in range(5)
    ]

    shared: hvg.MappedSourceCache = {}
    cached = [hvg.element_bbox_mm(e, METRES_TO_MM, shared) for e in elements]
    fresh = [hvg.element_bbox_mm(e, METRES_TO_MM) for e in elements]

    assert cached == fresh


# ---------------------------------------------------------------------------
# Progress inside a model, so a slow model reads as slow rather than hung
# ---------------------------------------------------------------------------


def _bare_model(count: int):
    model = ifcopenshell.file(schema="IFC4")
    for i in range(count):
        model.create_entity("IfcBuildingElementProxy", GlobalId=ifcopenshell.guid.new(), Name=f"P{i}")
    return model


def _metrics(project_id: int = 1) -> dict:
    return pt.merged_snapshot(project_id)["engines"][SB_ENGINE]["metrics"]


@pytest.fixture(autouse=True)
def _clean_tracker_store():
    pt.TRACKERS.clear()
    yield
    pt.TRACKERS.clear()


def test_geometry_reading_reports_progress_within_a_model(monkeypatch):
    monkeypatch.setattr(seismic, "GEOMETRY_PROGRESS_INTERVAL", 2)
    seen = []
    real_emit = seismic.emit

    def recording(code, stage=None, **metrics):
        if "model_elements_scanned" in metrics:
            seen.append(metrics["model_elements_scanned"])
        real_emit(code, stage, **metrics)

    monkeypatch.setattr(seismic, "emit", recording)

    with pt.tracking(1, run_key=SEISMIC_RUN_KEY):
        # The kernel enters the stage before reading a model, and a metric alone
        # does not make an engine "touched" -- without it the snapshot reads
        # ``pending`` and carries no metrics.
        pt.emit(SB_ENGINE, Stage.IFC_PARSING)
        seismic._geometries(_bare_model(5), 1.0)

    # Announced at zero, ticked on the interval, and closed at the total.
    assert seen == [0, 2, 4, 5]
    assert _metrics()["model_elements"] == 5
    assert _metrics()["model_elements_scanned"] == 5


def test_the_kernel_says_which_model_it_is_reading():
    with pt.tracking(1, run_key=SEISMIC_RUN_KEY):
        seismic.run_seismic_analysis(
            _bare_model(2).to_string().encode("utf-8"),
            primary_label="ARC.ifc",
            extra_models=[("MEC.ifc", _bare_model(3).to_string().encode("utf-8"))],
        )

    metrics = _metrics()

    assert metrics["current_model"] == "MEC.ifc"
    assert metrics["models_read"] == 2
    assert metrics["model_elements"] == 3


def test_progress_reporting_is_inert_when_nothing_is_bound():
    """The CLI demos, the sweep and direct callers run untracked."""
    seismic._geometries(_bare_model(3), 1.0)

    assert pt.TRACKERS.for_project(1) == []
