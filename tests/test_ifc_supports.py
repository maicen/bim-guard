"""Seismic support detection, brace spacing, and hanger-rod length.

Two layers, matching the module's own split:

* ``TestVectorMath`` .. ``TestBraceSpacing`` need no IFC file at all. They are
  the bulk of the coverage, because the spacing arithmetic is where a rule's
  verdict actually comes from and it should be provable without a model.
* ``TestAgainstModel`` builds a small IFC4 bracing model in ``tmp_path`` -- one
  24 m pipe run carrying two lateral braces, one longitudinal brace, one
  ambiguous brace and two hanger rods of known length -- and exercises the
  traversal against it.

The model is built here rather than checked in so the numbers under test are
visible beside the assertions that use them.
"""

from __future__ import annotations

import math
import pathlib

import pytest

from app.modules.ifc_reader import ifc_supports as sup

# ── Pure math: no IFC required ────────────────────────────────────────────────

X_AXIS = (1.0, 0.0, 0.0)


class TestVectorMath:
    def test_axis_from_points_is_unit_length(self):
        axis = sup.axis_from_points((0, 0, 0), (3, 4, 0))
        assert axis == pytest.approx((0.6, 0.8, 0.0))

    def test_coincident_points_have_no_axis(self):
        assert sup.axis_from_points((1, 2, 3), (1, 2, 3)) is None

    def test_station_measures_along_the_axis_only(self):
        # A brace sits well off to the side; its station is where it meets the
        # run, not how far away it is.
        station = sup.project_station_mm((5000, 900, 400), (0, 0, 0), X_AXIS)
        assert station == pytest.approx(5000)

    def test_station_is_signed_behind_the_origin(self):
        assert sup.project_station_mm((-250, 0, 0), (0, 0, 0), X_AXIS) == pytest.approx(-250)

    def test_perpendicular_distance_ignores_position_along_run(self):
        near = sup.perpendicular_distance_mm((1000, 300, 400), (0, 0, 0), X_AXIS)
        far = sup.perpendicular_distance_mm((90000, 300, 400), (0, 0, 0), X_AXIS)
        assert near == pytest.approx(500)
        assert near == pytest.approx(far)

    def test_angle_folds_onto_0_90(self):
        # A brace drawn from the pipe up and one drawn from the structure down
        # describe the same brace and must give the same angle.
        assert sup.angle_between_deg(X_AXIS, (-1, 0, 0)) == pytest.approx(0.0)
        assert sup.angle_between_deg(X_AXIS, (0, 0, 1)) == pytest.approx(90.0)

    def test_angle_of_zero_length_vector_is_none(self):
        assert sup.angle_between_deg((0, 0, 0), X_AXIS) is None


class TestOrientationClassification:
    def test_brace_across_the_run_is_lateral(self):
        assert sup.classify_orientation((0, 1, 1), X_AXIS) == sup.LATERAL_BRACE

    def test_brace_along_the_run_is_longitudinal(self):
        assert sup.classify_orientation((1, 0, 0.3), X_AXIS) == sup.LONGITUDINAL_BRACE

    def test_forty_five_degrees_is_unknown_not_a_guess(self):
        # The dead band exists so an ambiguous brace is reported as ambiguous.
        assert sup.classify_orientation((1, 0, 1), X_AXIS) == sup.UNKNOWN

    def test_direction_sign_does_not_change_the_answer(self):
        assert sup.classify_orientation((-1, 0, -0.3), X_AXIS) == sup.LONGITUDINAL_BRACE


class TestBraceSpacing:
    """The arithmetic a spacing rule reads its verdict from."""

    def test_even_spacing(self):
        result = sup.brace_spacing([0, 12000, 24000])
        assert result["gaps_mm"] == [12000, 12000]
        assert result["max_gap_mm"] == 12000

    def test_input_order_does_not_matter(self):
        assert sup.brace_spacing([24000, 0, 12000])["gaps_mm"] == [12000, 12000]

    def test_max_gap_governs(self):
        result = sup.brace_spacing([0, 3000, 20000])
        assert result["max_gap_mm"] == 17000

    def test_no_supports_has_no_spacing_not_zero(self):
        # An unbraced run is a finding about absence. Reporting 0 mm would make
        # it look like the tightest possible bracing instead.
        result = sup.brace_spacing([])
        assert result["max_gap_mm"] is None
        assert result["gaps_mm"] == []
        assert result["count"] == 0
        assert result["span_mm"] is None

    def test_single_support_has_no_gap_but_real_end_offsets(self):
        # A 30 m run held by one brace passes any max_gap check, which is
        # exactly why the end offsets have to be reported too.
        result = sup.brace_spacing([15000], run_start_mm=0, run_end_mm=30000)
        assert result["max_gap_mm"] is None
        assert result["start_offset_mm"] == 15000
        assert result["end_offset_mm"] == 15000

    def test_end_offsets_are_measured_from_the_run_not_the_first_brace(self):
        result = sup.brace_spacing([2000, 14000], run_start_mm=0, run_end_mm=24000)
        assert result["start_offset_mm"] == 2000
        assert result["end_offset_mm"] == 10000
        assert result["span_mm"] == 12000

    def test_offsets_are_none_without_a_known_run_extent(self):
        result = sup.brace_spacing([2000, 14000])
        assert result["start_offset_mm"] is None
        assert result["end_offset_mm"] is None

    def test_coincident_braces_report_a_real_zero_gap(self):
        # Two braces modelled at the same station is a modelling error worth
        # seeing, not something to deduplicate away.
        result = sup.brace_spacing([5000, 5000, 17000])
        assert result["gaps_mm"] == [0, 12000]
        assert result["count"] == 3

    def test_negative_stations_are_ordered_correctly(self):
        result = sup.brace_spacing([1000, -4000])
        assert result["gaps_mm"] == [5000]


# ── Against a real model ──────────────────────────────────────────────────────

ifcopenshell = pytest.importorskip("ifcopenshell")

PIPE_LENGTH_MM = 24000.0
PIPE_Z_MM = 3000.0
LATERAL_STATIONS = (2000.0, 14000.0)
LONGITUDINAL_STATION = 8000.0
AMBIGUOUS_STATION = 20000.0
ROD_STATIONS_AND_LENGTHS = ((1000.0, 900.0), (5000.0, 1800.0))


def _build_bracing_model(path):
    """Write a 24 m braced pipe run with hangers, in millimetres."""
    import ifcopenshell.api.context
    import ifcopenshell.api.geometry
    import ifcopenshell.api.root
    import ifcopenshell.api.spatial
    import ifcopenshell.api.unit
    import numpy as np
    from ifcopenshell.api import run

    model = ifcopenshell.file(schema="IFC4")
    project = run("root.create_entity", model, ifc_class="IfcProject", name="Bracing")
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
    run("aggregate.assign_object", model, products=[site], relating_object=project)
    run("aggregate.assign_object", model, products=[building], relating_object=site)
    run("aggregate.assign_object", model, products=[storey], relating_object=building)

    def _cylinder(diameter, length, direction):
        """Circular solid extruded `length` mm along world `direction`."""
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
            Position=model.create_entity(
                "IfcAxis2Placement3D",
                Location=model.create_entity(
                    "IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0)
                ),
                # The solid extrudes along its own local Z, so putting local Z
                # on `direction` is what aims it in world space.
                Axis=model.create_entity("IfcDirection", DirectionRatios=direction),
                RefDirection=model.create_entity(
                    "IfcDirection",
                    DirectionRatios=(1.0, 0.0, 0.0)
                    if abs(direction[0]) < 0.9
                    else (0.0, 1.0, 0.0),
                ),
            ),
            ExtrudedDirection=model.create_entity(
                "IfcDirection", DirectionRatios=(0.0, 0.0, 1.0)
            ),
            Depth=length,
        )
        return model.create_entity(
            "IfcShapeRepresentation",
            ContextOfItems=body,
            RepresentationIdentifier="Body",
            RepresentationType="SweptSolid",
            Items=[solid],
        )

    def _place(product, representation, position):
        run("geometry.assign_representation", model, product=product, representation=representation)
        matrix = np.eye(4)
        matrix[:3, 3] = position
        run(
            "geometry.edit_object_placement",
            model,
            product=product,
            matrix=matrix,
            is_si=False,
        )

    def _connect(support, pipe_element):
        model.create_entity(
            "IfcRelConnectsElements",
            GlobalId=ifcopenshell.guid.new(),
            RelatingElement=pipe_element,
            RelatedElement=support,
        )

    # The run: a cylinder along +X. The solid extrudes FROM its local origin,
    # so placing it at x=0 makes the run span 0..PIPE_LENGTH_MM in world
    # coordinates and every support station below is read straight off the
    # x-coordinate it was placed at.
    pipe = run("root.create_entity", model, ifc_class="IfcPipeSegment", name="Main run")
    run("spatial.assign_container", model, products=[pipe], relating_structure=storey)
    _place(pipe, _cylinder(100.0, PIPE_LENGTH_MM, (1.0, 0.0, 0.0)), (0.0, 0.0, PIPE_Z_MM))

    unit = 1.0 / math.sqrt(2.0)
    for index, station in enumerate(LATERAL_STATIONS):
        brace = run(
            "root.create_entity",
            model,
            ifc_class="IfcMember",
            name=f"Sway Brace {index + 1}",
        )
        brace.PredefinedType = "BRACE"
        run("spatial.assign_container", model, products=[brace], relating_structure=storey)
        # Across the run: no X component at all.
        _place(brace, _cylinder(40.0, 1200.0, (0.0, unit, unit)), (station, 0.0, PIPE_Z_MM))
        _connect(brace, pipe)

    longitudinal = run(
        "root.create_entity", model, ifc_class="IfcMember", name="Sway Brace 3"
    )
    longitudinal.PredefinedType = "BRACE"
    run("spatial.assign_container", model, products=[longitudinal], relating_structure=storey)
    # ~16.7 degrees off the run: unambiguously longitudinal.
    _place(
        longitudinal,
        _cylinder(40.0, 1200.0, (0.958, 0.0, 0.287)),
        (LONGITUDINAL_STATION, 0.0, PIPE_Z_MM),
    )
    _connect(longitudinal, pipe)

    ambiguous = run("root.create_entity", model, ifc_class="IfcMember", name="Sway Brace 4")
    ambiguous.PredefinedType = "BRACE"
    run("spatial.assign_container", model, products=[ambiguous], relating_structure=storey)
    # Exactly 45 degrees: the dead band.
    _place(
        ambiguous,
        _cylinder(40.0, 1200.0, (unit, 0.0, unit)),
        (AMBIGUOUS_STATION, 0.0, PIPE_Z_MM),
    )
    _connect(ambiguous, pipe)

    for index, (station, length) in enumerate(ROD_STATIONS_AND_LENGTHS):
        rod = run(
            "root.create_entity",
            model,
            ifc_class="IfcDiscreteAccessory",
            name=f"Hanger Rod {index + 1}",
        )
        run("spatial.assign_container", model, products=[rod], relating_structure=storey)
        _place(
            rod,
            _cylinder(10.0, length, (0.0, 0.0, 1.0)),
            (station, 0.0, PIPE_Z_MM),
        )
        _connect(rod, pipe)

    model.write(str(path))
    return path


@pytest.fixture(scope="module")
def braced_model(tmp_path_factory):
    path = tmp_path_factory.mktemp("bracing") / "bracing.ifc"
    _build_bracing_model(path)
    return ifcopenshell.open(str(path))


@pytest.fixture(scope="module")
def extractor(braced_model):
    from app.modules.ifc_reader.ifc_geometry import IFCGeometryExtractor

    return IFCGeometryExtractor(braced_model)


@pytest.fixture(scope="module")
def pipe(braced_model):
    return braced_model.by_type("IfcPipeSegment")[0]


@pytest.fixture(scope="module")
def supports(pipe, extractor):
    return sup.find_supports(pipe, geometry_extractor=extractor)


class TestAgainstModel:
    def test_pipe_axis_is_resolved_exactly(self, pipe, extractor):
        axis = sup.element_axis(pipe, extractor)
        assert axis["method"] == "extrusion"
        assert axis["length_mm"] == pytest.approx(PIPE_LENGTH_MM, abs=1.0)
        assert sup.angle_between_deg(axis["axis"], X_AXIS) == pytest.approx(0.0, abs=0.5)

    def test_every_support_is_found_through_a_declared_relationship(self, supports):
        assert len(supports) == 6
        assert {s["route"] for s in supports} == {"connection"}

    def test_supports_are_ordered_along_the_run(self, supports):
        stations = [s["station_mm"] for s in supports]
        assert stations == sorted(stations)

    def test_stations_match_where_the_supports_were_placed(self, supports):
        by_name = {s["name"]: s["station_mm"] for s in supports}
        assert by_name["Sway Brace 1"] == pytest.approx(LATERAL_STATIONS[0], abs=1.0)
        assert by_name["Sway Brace 2"] == pytest.approx(LATERAL_STATIONS[1], abs=1.0)
        assert by_name["Hanger Rod 1"] == pytest.approx(1000.0, abs=1.0)

    def test_predefined_type_alone_only_proves_a_generic_brace(self, braced_model):
        brace = next(
            m for m in braced_model.by_type("IfcMember") if m.Name == "Sway Brace 1"
        )
        assert sup.classify_support(brace)["declared"] == sup.BRACE

    def test_geometry_resolves_lateral_from_a_generic_brace(self, supports):
        lateral = next(s for s in supports if s["name"] == "Sway Brace 1")
        assert lateral["declared"] == sup.BRACE
        assert lateral["measured"] == sup.LATERAL_BRACE
        assert lateral["kind"] == sup.LATERAL_BRACE

    def test_geometry_resolves_longitudinal_from_a_generic_brace(self, supports):
        longitudinal = next(s for s in supports if s["name"] == "Sway Brace 3")
        assert longitudinal["measured"] == sup.LONGITUDINAL_BRACE

    def test_ambiguous_brace_stays_generic(self, supports):
        # 45 degrees to the run: it must not be forced into either bucket.
        ambiguous = next(s for s in supports if s["name"] == "Sway Brace 4")
        assert ambiguous["measured"] == sup.UNKNOWN
        assert ambiguous["kind"] == sup.BRACE

    def test_hanger_is_identified_by_name(self, supports):
        rod = next(s for s in supports if s["name"] == "Hanger Rod 1")
        assert rod["kind"] == sup.HANGER

    def test_evidence_records_how_each_call_was_made(self, supports):
        lateral = next(s for s in supports if s["name"] == "Sway Brace 1")
        assert any("predefined" in e for e in lateral["evidence"])
        assert any("deg to the run" in e for e in lateral["evidence"])

    def test_pipe_is_not_its_own_support(self, supports):
        assert all(s["ifc_class"] != "IfcPipeSegment" for s in supports)


class TestRodLength:
    def test_rod_length_matches_the_modelled_rod(self, supports, extractor):
        rods = {s["name"]: s["element"] for s in supports if s["kind"] == sup.HANGER}
        for index, (_, expected) in enumerate(ROD_STATIONS_AND_LENGTHS):
            length, detail = sup.rod_length_mm(rods[f"Hanger Rod {index + 1}"], extractor)
            assert length == pytest.approx(expected, abs=1.0)
            assert detail["method"] == "extrusion"

    def test_vertical_rod_reads_as_plumb(self, supports, extractor):
        rod = next(s["element"] for s in supports if s["name"] == "Hanger Rod 1")
        _, detail = sup.rod_length_mm(rod, extractor)
        assert detail["angle_from_vertical_deg"] == pytest.approx(0.0, abs=0.5)
        assert detail["is_plumb"] is True

    def test_a_diagonal_brace_is_not_plumb(self, supports, extractor):
        brace = next(s["element"] for s in supports if s["name"] == "Sway Brace 1")
        _, detail = sup.rod_length_mm(brace, extractor)
        assert detail["is_plumb"] is False

    def test_unbraced_length_is_reported_as_undistinguished(self, supports, extractor):
        # The function must not let a caller mistake total length for unbraced
        # length, so both fields stay explicitly unknown.
        rod = next(s["element"] for s in supports if s["name"] == "Hanger Rod 1")
        _, detail = sup.rod_length_mm(rod, extractor)
        assert detail["intermediate_restraints"] is None
        assert detail["unbraced_equals_total"] is None

    def test_element_without_geometry_gives_none_not_zero(self, braced_model):
        storey = braced_model.by_type("IfcBuildingStorey")[0]
        length, detail = sup.rod_length_mm(storey, geometry_extractor=None)
        assert length is None
        assert "not resolvable" in detail["reason"]


@pytest.fixture(scope="module")
def context(pipe, extractor):
    return sup.support_context(pipe, geometry_extractor=extractor)


class TestSupportContext:
    """The aggregate a future extraction hook would attach to an element."""

    def test_run_length_is_measured(self, context):
        assert context["run_length_mm"] == pytest.approx(PIPE_LENGTH_MM, abs=1.0)
        assert context["run_axis_method"] == "extrusion"

    def test_lateral_spacing_is_the_gap_between_lateral_braces_only(self, context):
        expected = LATERAL_STATIONS[1] - LATERAL_STATIONS[0]
        assert context["lateral_spacing"]["max_gap_mm"] == pytest.approx(expected, abs=1.0)

    def test_a_single_longitudinal_brace_yields_no_spacing(self, context):
        assert context["longitudinal_spacing"]["count"] == 1
        assert context["longitudinal_spacing"]["max_gap_mm"] is None

    def test_kinds_are_not_mixed_into_one_series(self, context):
        # Lateral and longitudinal limits differ, so pooling them would compare
        # each brace against the wrong one.
        assert context["lateral_spacing"]["count"] == 2
        assert context["hanger_spacing"]["count"] == 2

    def test_end_offsets_come_from_the_run_extent(self, context):
        spacing = context["lateral_spacing"]
        assert spacing["start_offset_mm"] == pytest.approx(LATERAL_STATIONS[0], abs=1.0)
        assert spacing["end_offset_mm"] == pytest.approx(
            PIPE_LENGTH_MM - LATERAL_STATIONS[1], abs=1.0
        )

    def test_rod_lengths_are_collected_per_hanger(self, context):
        lengths = sorted(r["length_mm"] for r in context["rod_lengths"])
        assert lengths == pytest.approx([900.0, 1800.0], abs=1.0)

    def test_nothing_is_left_unpositioned(self, context):
        assert context["unpositioned_support_count"] == 0


# ── End to end: spacing rules against the mock model ──────────────────────────

#: The SEISMIC-GLOBAL spacing rules, in the shape RuleService stores them after
#: import. Held here rather than fetched so the test needs no database.
NZS_TABLE_6A = {
    "reference": "NZS-4219-Table-6a-NB50",
    "description": "Maximum lateral sway brace spacing, C = 2.0",
    "target_ifc_class": "IfcPipeSegment",
    "property_name": "LateralBraceSpacing",
    "operator": "<=",
    "check_value": 6100.0,
    "unit": "mm",
    "applies_when": {
        "target_ifc_class": "IfcPipeSegment",
        "material_any_of": ["steel"],
        "nominal_diameter_mm": 50.0,
    },
    "exceptions": [],
}

NZS_TABLE_7A = dict(
    NZS_TABLE_6A,
    reference="NZS-4219-Table-7a-NB50",
    property_name="LongitudinalBraceSpacing",
    check_value=18000.0,
)

BS_EN_STEEL = dict(
    NZS_TABLE_6A,
    reference="BS-EN-12845-Clause-17.2.2-Steel",
    property_name="SupportSpacing",
    check_value=4000.0,
)

BS_EN_COPPER = dict(
    BS_EN_STEEL,
    reference="BS-EN-12845-Clause-17.2.2-Copper",
    check_value=2000.0,
    applies_when={
        "target_ifc_class": "IfcPipeSegment",
        "material_any_of": ["copper"],
        "nominal_diameter_mm": 50.0,
    },
)

#: The NZS hanger exemption, as its own rule row, cited by Table 6a below.
NZS_HANGER_EXEMPTION = {
    "reference": "NZS-4219-5.8.1-Hanger-Seismic-Exemption",
    "description": "Seismic restraint exclusion for short individual hanger rods",
    "target_ifc_class": "IfcPipeSegment",
    "property_name": "HangerRodLength",
    "operator": "exempt",
    "applies_when": {"is_suspended": True, "hanger_rod_length_below_mm": 150.0},
    "exceptions": [],
}


@pytest.fixture(scope="module")
def nfpa_model_path(tmp_path_factory):
    """Build the shared mock model, which carries the braced run 'Pipe F'."""
    import importlib.util
    import sys

    generator_path = (
        pathlib.Path(__file__).resolve().parent.parent
        / "scripts"
        / "generate_mock_ifc_penetrations.py"
    )
    if not generator_path.exists():
        pytest.skip("mock generator not present")
    spec = importlib.util.spec_from_file_location("_nfpa13_mock_supports", generator_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    out = tmp_path_factory.mktemp("supports") / "nfpa13_test.ifc"
    module.build(out)
    return out


def _evaluate(model_path, rules):
    from app.modules.ifc_reader import IFCReader
    from app.modules.comparator import ComplianceComparator

    extraction = IFCReader(model_path).extract_for_compliance(rules)
    results = ComplianceComparator().validate_metadata(extraction)
    return {r["rule_ref"]: r for r in results}


def _braced(result):
    return next(e for e in result["all_elements"] if "braced" in e["element_name"])


class TestSpacingRulesEndToEnd:
    """The spacing rules extract a measured value and reach a verdict."""

    @pytest.fixture(scope="class")
    def results(self, nfpa_model_path):
        return _evaluate(
            nfpa_model_path,
            [NZS_TABLE_6A, NZS_TABLE_7A, BS_EN_STEEL, BS_EN_COPPER],
        )

    def test_lateral_spacing_is_measured_from_the_model(self, results):
        # Braces at 1000 / 8000 / 15000 mm: two 7000 mm gaps.
        entry = _braced(results["NZS-4219-Table-6a-NB50"])
        assert entry["actual"] == pytest.approx(7000.0, abs=1.0)

    def test_lateral_spacing_over_the_limit_fails(self, results):
        assert _braced(results["NZS-4219-Table-6a-NB50"])["status"] == "FAIL"

    def test_longitudinal_spacing_under_the_limit_passes(self, results):
        entry = _braced(results["NZS-4219-Table-7a-NB50"])
        assert entry["actual"] == pytest.approx(15000.0, abs=1.0)
        assert entry["status"] == "PASS"

    def test_the_two_brace_series_are_not_pooled(self, results):
        # The whole reason there is no bare "Spacing" property: pooled, the
        # lateral series would be masked by the denser longitudinal one.
        lateral = _braced(results["NZS-4219-Table-6a-NB50"])["actual"]
        longitudinal = _braced(results["NZS-4219-Table-7a-NB50"])["actual"]
        assert lateral != longitudinal

    def test_merged_support_spacing_fails_the_tighter_limit(self, results):
        entry = _braced(results["BS-EN-12845-Clause-17.2.2-Steel"])
        assert entry["actual"] == pytest.approx(7000.0, abs=1.0)
        assert entry["status"] == "FAIL"

    def test_copper_rule_does_not_apply_to_a_steel_run(self, results):
        # Same property, tighter limit -- excluded by material, not by measure.
        assert results["BS-EN-12845-Clause-17.2.2-Copper"]["status"] == "NOT_APPLICABLE"

    def test_out_of_scope_pipes_are_never_measured(self, results):
        # The penetration pipes are 50.8 mm (the true NB50 outside diameter),
        # so the rule's scalar 50.0 scope excludes them before the operator
        # runs. NOT_APPLICABLE, not a spacing verdict.
        entries = [
            e
            for e in results["BS-EN-12845-Clause-17.2.2-Steel"]["all_elements"]
            if "through" in e["element_name"]
        ]
        assert entries
        assert all(e["status"] == "NOT_APPLICABLE" for e in entries)


class TestTooFewSupportsIsMissingNotZero:
    """A run with no gap between supports has no spacing, which is not 0 mm."""

    @pytest.fixture(scope="class")
    def results(self, nfpa_model_path):
        # Same rule with the diameter scope dropped, so every pipe in the
        # model is measured rather than gated out on nominal size.
        rule = dict(BS_EN_STEEL, applies_when={"target_ifc_class": "IfcPipeSegment"})
        return _evaluate(nfpa_model_path, [rule])

    def test_pipes_with_no_supports_report_missing(self, results):
        entries = [
            e
            for e in results["BS-EN-12845-Clause-17.2.2-Steel"]["all_elements"]
            if "through" in e["element_name"]
        ]
        assert entries
        assert all(e["status"] == "MISSING" for e in entries)
        assert all(e["actual"] is None for e in entries)

    def test_a_single_support_still_has_no_spacing(self, results):
        # Pipes C, D and E each carry exactly one hanger. One support cannot
        # produce a gap, and reporting 0 mm would pass every spacing limit
        # there is.
        single = [
            e
            for e in results["BS-EN-12845-Clause-17.2.2-Steel"]["all_elements"]
            if "rod" in e["element_name"]
        ]
        assert len(single) == 3
        assert all(e["status"] == "MISSING" for e in single)

    def test_the_braced_run_still_measures(self, results):
        assert _braced(results["BS-EN-12845-Clause-17.2.2-Steel"])["actual"] == (
            pytest.approx(7000.0, abs=1.0)
        )


class TestHangerExemptionWaivesSpacing:
    """The full chain: scope, measure, then waive on the hanger exemption."""

    @pytest.fixture(scope="class")
    def results(self, nfpa_model_path):
        rule = dict(
            NZS_TABLE_6A,
            exceptions=["NZS-4219-5.8.1-Hanger-Seismic-Exemption"],
        )
        return _evaluate(nfpa_model_path, [rule, NZS_HANGER_EXEMPTION])

    def test_exemption_is_not_evaluated_standalone(self, results):
        assert "NZS-4219-5.8.1-Hanger-Seismic-Exemption" not in results

    def test_short_rods_waive_the_spacing_failure(self, results):
        # The braced run's 100 mm rods clear the 150 mm threshold, so the
        # 7000 mm brace spacing is excused rather than reported.
        entry = _braced(results["NZS-4219-Table-6a-NB50"])
        assert entry["status"] == "WAIVED"
        assert "NZS-4219-5.8.1" in entry["reason"]

    def test_the_waived_measurement_is_still_reported(self, results):
        # A waiver excuses a finding; it must not erase what was measured.
        assert _braced(results["NZS-4219-Table-6a-NB50"])["actual"] == pytest.approx(
            7000.0, abs=1.0
        )
