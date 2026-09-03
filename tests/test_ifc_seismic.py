"""Seismic restraint inputs: mass, coefficient, flexible couplings, detail flags.

Two layers, matching the module's own split:

* The classes up to ``TestAggregation`` need no IFC file. They cover the value
  parsing, the plausibility bands and the aggregation arithmetic -- which is
  where a fabricated verdict would actually come from, so it should be provable
  without a model.
* ``TestAgainstModel`` onwards build a small IFC4 model in ``tmp_path``: one
  24 m steel pipe run with a density-bearing material, two braces, two hangers
  carrying detailing properties, one flexible coupling beside the first brace,
  and a project-level seismic coefficient.

The model is built here rather than checked in so the numbers under test sit
beside the assertions that use them.
"""

from __future__ import annotations

import math

import pytest

from app.modules.ifc_reader import ifc_seismic as seis

# ── Value parsing: no IFC required ────────────────────────────────────────────


class TestTristateBool:
    def test_real_booleans_pass_through(self):
        assert seis.as_tristate_bool(True) is True
        assert seis.as_tristate_bool(False) is False

    def test_exporter_text_is_read(self):
        for token in ("TRUE", "Yes", "y", ".T.", " true "):
            assert seis.as_tristate_bool(token) is True
        for token in ("FALSE", "No", "n", ".F."):
            assert seis.as_tristate_bool(token) is False

    def test_missing_is_none_not_false(self):
        # The whole point of the tri-state: silence is not a denial.
        assert seis.as_tristate_bool(None) is None

    def test_unreadable_value_is_none_not_false(self):
        assert seis.as_tristate_bool("maybe") is None
        assert seis.as_tristate_bool("TBC") is None

    def test_only_one_and_zero_state_a_boolean(self):
        assert seis.as_tristate_bool(1) is True
        assert seis.as_tristate_bool(0) is False
        assert seis.as_tristate_bool(2) is None


class TestAsFloat:
    def test_numbers_and_numeric_text(self):
        assert seis.as_float(2.5) == 2.5
        assert seis.as_float("2.5") == 2.5

    def test_booleans_are_not_numbers(self):
        # True in a numeric slot is a mis-typed property, not the number one.
        assert seis.as_float(True) is None
        assert seis.as_float(False) is None

    def test_missing_and_unparseable_are_none(self):
        assert seis.as_float(None) is None
        assert seis.as_float("n/a") is None

    def test_nan_and_infinity_are_rejected(self):
        assert seis.as_float(float("nan")) is None
        assert seis.as_float(float("inf")) is None


# ── Plausibility bands ────────────────────────────────────────────────────────


class TestSpacingMultiplierBand:
    def test_band_starts_at_one(self):
        # Below 1 shortens the allowed spacing rather than extending it, which
        # is not what this property means.
        low, high = seis._PLAUSIBLE_SPACING_MULTIPLIER
        assert low == 1.0
        assert high >= 2.0


class TestDensityBand:
    def test_construction_materials_are_inside_the_band(self):
        low, high = seis._PLAUSIBLE_DENSITY_KG_M3
        for density in (7850.0, 2400.0, 8960.0, 11340.0, 25.0):
            assert low <= density <= high

    def test_wrong_unit_densities_fall_outside(self):
        # Steel as 7.85 (g/cm3) or 7.85e-6 (kg/mm3) would each be wrong by
        # orders of magnitude and each looks plausible once multiplied out.
        low, high = seis._PLAUSIBLE_DENSITY_KG_M3
        assert not low <= 7.85 <= high
        assert not low <= 7.85e-6 <= high


class TestCoefficientBand:
    def test_percentage_style_value_is_refused(self):
        low, high = seis._PLAUSIBLE_COEFFICIENT
        assert not low < 35.0 <= high

    def test_zero_is_refused_because_it_deletes_the_demand(self):
        low, _ = seis._PLAUSIBLE_COEFFICIENT
        assert not low < 0.0


# ── Aggregation over a run's supports ─────────────────────────────────────────


class TestAllOrNone:
    def test_every_support_must_say_true(self):
        assert seis._all_or_none([True, True]) is True

    def test_one_explicit_false_governs(self):
        assert seis._all_or_none([True, False, True]) is False

    def test_partial_evidence_is_undetermined(self):
        # "Most of the hangers are detailed correctly" is not a statement any
        # of these rules accepts.
        assert seis._all_or_none([True, None]) is None

    def test_no_supports_at_all_is_undetermined(self):
        assert seis._all_or_none([]) is None


class TestGoverningMultiplier:
    def test_least_generous_authored_value_wins(self):
        assert seis._governing_multiplier([2.0, 1.5, 2.0]) == 1.5

    def test_one_silent_support_makes_the_run_undetermined(self):
        # A relaxation earned by a detail is only earned when every support
        # carries it.
        assert seis._governing_multiplier([2.0, None]) is None

    def test_nothing_authored_is_undetermined(self):
        assert seis._governing_multiplier([]) is None


# ── Flexible coupling distance, against a stubbed extractor ───────────────────


class _StubExtractor:
    """Returns preset centroids, so the distance arithmetic is exact."""

    def __init__(self, centroids: dict):
        self._centroids = centroids

    def get_centroid_or_none(self, element):
        return self._centroids.get(element)


def _index(*names) -> list[dict]:
    return [{"element": n, "guid": f"guid-{n}", "name": n, "evidence": "name:test"} for n in names]


class TestNearestCoupling:
    def test_nearest_of_several_is_reported(self):
        extractor = _StubExtractor({"near": (100.0, 0.0, 0.0), "far": (9000.0, 0.0, 0.0)})
        distance, detail = seis.nearest_flexible_coupling_mm(
            (0.0, 0.0, 0.0), _index("near", "far"), extractor
        )
        assert distance == pytest.approx(100.0)
        assert detail["nearest_name"] == "near"
        assert detail["positioned_coupling_count"] == 2

    def test_distance_is_three_dimensional(self):
        extractor = _StubExtractor({"c": (3.0, 4.0, 12.0)})
        distance, _ = seis.nearest_flexible_coupling_mm(
            (0.0, 0.0, 0.0), _index("c"), extractor
        )
        assert distance == pytest.approx(13.0)

    def test_a_model_with_no_couplings_is_undetermined_not_far_away(self):
        # An empty index far more often means the couplings were never
        # modelled than that the run has none. None is the only reading that is
        # safe as BOTH a waiver predicate and a scope predicate.
        distance, detail = seis.nearest_flexible_coupling_mm(
            (0.0, 0.0, 0.0), [], _StubExtractor({})
        )
        assert distance is None
        assert "no flexible coupling" in detail["reason"]

    def test_couplings_present_but_distant_is_a_real_answer(self):
        # This one IS determinate: the model says where they are and none is
        # near, so the exemption correctly fails to apply.
        extractor = _StubExtractor({"c": (50000.0, 0.0, 0.0)})
        distance, _ = seis.nearest_flexible_coupling_mm(
            (0.0, 0.0, 0.0), _index("c"), extractor
        )
        assert distance == pytest.approx(50000.0)

    def test_unplaceable_reference_is_undetermined(self):
        distance, detail = seis.nearest_flexible_coupling_mm(
            None, _index("c"), _StubExtractor({"c": (0.0, 0.0, 0.0)})
        )
        assert distance is None
        assert "reference point" in detail["reason"]

    def test_unpositionable_couplings_are_undetermined(self):
        distance, detail = seis.nearest_flexible_coupling_mm(
            (0.0, 0.0, 0.0), _index("c"), _StubExtractor({})
        )
        assert distance is None
        assert "could be positioned" in detail["reason"]


class TestWorstReferenceGoverns:
    def test_the_brace_furthest_from_a_coupling_decides(self):
        extractor = _StubExtractor(
            {"coupling": (0.0, 0.0, 0.0), "brace-a": (100.0, 0.0, 0.0)}
        )
        distance, detail = seis._worst_coupling_distance(
            supports=[],
            reference_points=[("near", (100.0, 0.0, 0.0)), ("far", (4000.0, 0.0, 0.0))],
            coupling_index=_index("coupling"),
            geometry_extractor=extractor,
        )
        assert distance == pytest.approx(4000.0)
        assert detail["reference_count"] == 2

    def test_one_unresolved_reference_makes_the_run_undetermined(self):
        extractor = _StubExtractor({"coupling": (0.0, 0.0, 0.0)})
        distance, detail = seis._worst_coupling_distance(
            supports=[],
            reference_points=[("ok", (100.0, 0.0, 0.0)), ("lost", None)],
            coupling_index=_index("coupling"),
            geometry_extractor=extractor,
        )
        assert distance is None
        assert "lost" in detail["reason"]

    def test_no_reference_at_all_is_undetermined(self):
        distance, detail = seis._worst_coupling_distance(
            supports=[], reference_points=[], coupling_index=_index("c"),
            geometry_extractor=_StubExtractor({}),
        )
        assert distance is None
        assert "no brace or support" in detail["reason"]


# ── Against a real model ──────────────────────────────────────────────────────

ifcopenshell = pytest.importorskip("ifcopenshell")

PIPE_LENGTH_MM = 24000.0
PIPE_DIAMETER_MM = 100.0
PIPE_Z_MM = 3000.0
STEEL_DENSITY = 7850.0
SEISMIC_COEFFICIENT = 2.0
#: Braces at these stations along the run; the coupling sits beside the first.
BRACE_STATIONS = (2000.0, 14000.0)
COUPLING_STATION = 2100.0
#: Authored on the second hanger only, so the run's aggregate stays partial.
HANGER_MULTIPLIERS = (2.0, 1.5)


def _build_seismic_model(path):
    """Write a braced steel run with density, couplings and detailing Psets."""
    import numpy as np
    from ifcopenshell.api import run

    model = ifcopenshell.file(schema="IFC4")
    project = run("root.create_entity", model, ifc_class="IfcProject", name="Seismic")
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

    def _pset(product, name, properties):
        pset = run("pset.add_pset", model, product=product, name=name)
        run("pset.edit_pset", model, pset=pset, properties=properties)
        return pset

    def _cylinder(diameter, length, direction):
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
        run(
            "geometry.assign_representation",
            model,
            product=product,
            representation=representation,
        )
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

    # The seismic coefficient lives on the building: a project default that a
    # rule reads once and applies to every component in it.
    _pset(building, "Pset_SeismicDesign", {"SeismicForceCoefficient": SEISMIC_COEFFICIENT})

    steel = run("material.add_material", model, name="Steel S275")
    _pset(steel, "Pset_MaterialCommon", {"MassDensity": STEEL_DENSITY})

    # The same steel with its density authored in g/cm3 -- the single most
    # common unit mistake, and one that is wrong by a factor of a thousand
    # while still looking like a perfectly ordinary number.
    mis_united = run("material.add_material", model, name="Steel S275 (g/cm3)")
    _pset(mis_united, "Pset_MaterialCommon", {"MassDensity": STEEL_DENSITY / 1000.0})

    pipe = run("root.create_entity", model, ifc_class="IfcPipeSegment", name="Main run")
    run("spatial.assign_container", model, products=[pipe], relating_structure=storey)
    _place(
        pipe,
        _cylinder(PIPE_DIAMETER_MM, PIPE_LENGTH_MM, (1.0, 0.0, 0.0)),
        (0.0, 0.0, PIPE_Z_MM),
    )
    run("material.assign_material", model, products=[pipe], material=steel)

    # A second run, identical but with an authored weight, to prove the
    # authored route is preferred over the arithmetic one.
    weighed = run("root.create_entity", model, ifc_class="IfcPipeSegment", name="Weighed run")
    run("spatial.assign_container", model, products=[weighed], relating_structure=storey)
    _place(
        weighed,
        _cylinder(PIPE_DIAMETER_MM, PIPE_LENGTH_MM, (1.0, 0.0, 0.0)),
        (0.0, 5000.0, PIPE_Z_MM),
    )
    run("material.assign_material", model, products=[weighed], material=steel)
    _pset(weighed, "Qto_PipeSegmentBaseQuantities", {"NetWeight": 640.0})

    # A third run with no material at all: mass must come back None, not zero.
    bare = run("root.create_entity", model, ifc_class="IfcPipeSegment", name="Bare run")
    run("spatial.assign_container", model, products=[bare], relating_structure=storey)
    _place(
        bare,
        _cylinder(PIPE_DIAMETER_MM, PIPE_LENGTH_MM, (1.0, 0.0, 0.0)),
        (0.0, 9000.0, PIPE_Z_MM),
    )

    # A fourth run stating a detailing flag on itself, which must outrank
    # anything folded from the hangers below.
    detailed = run(
        "root.create_entity", model, ifc_class="IfcPipeSegment", name="Detailed run"
    )
    run("spatial.assign_container", model, products=[detailed], relating_structure=storey)
    _place(
        detailed,
        _cylinder(PIPE_DIAMETER_MM, PIPE_LENGTH_MM, (1.0, 0.0, 0.0)),
        (0.0, 13000.0, PIPE_Z_MM),
    )
    _pset(detailed, "Pset_SeismicRestraintDetailing", {"DetailsPreventRodBending": False})

    # A fifth run carrying the mis-united density, to prove the band refuses it
    # rather than reporting a mass a thousand times too light.
    wrong_unit = run(
        "root.create_entity", model, ifc_class="IfcPipeSegment", name="Wrong unit run"
    )
    run("spatial.assign_container", model, products=[wrong_unit], relating_structure=storey)
    _place(
        wrong_unit,
        _cylinder(PIPE_DIAMETER_MM, PIPE_LENGTH_MM, (1.0, 0.0, 0.0)),
        (0.0, 17000.0, PIPE_Z_MM),
    )
    run("material.assign_material", model, products=[wrong_unit], material=mis_united)

    unit = 1.0 / math.sqrt(2.0)
    for index, station in enumerate(BRACE_STATIONS):
        brace = run(
            "root.create_entity", model, ifc_class="IfcMember", name=f"Sway Brace {index + 1}"
        )
        brace.PredefinedType = "BRACE"
        run("spatial.assign_container", model, products=[brace], relating_structure=storey)
        _place(brace, _cylinder(40.0, 1200.0, (0.0, unit, unit)), (station, 0.0, PIPE_Z_MM))
        _connect(brace, pipe)

    for index, multiplier in enumerate(HANGER_MULTIPLIERS):
        rod = run(
            "root.create_entity",
            model,
            ifc_class="IfcDiscreteAccessory",
            name=f"Hanger Rod {index + 1}",
        )
        run("spatial.assign_container", model, products=[rod], relating_structure=storey)
        _place(rod, _cylinder(10.0, 900.0, (0.0, 0.0, 1.0)), (1000.0 * (index + 1), 0.0, PIPE_Z_MM))
        _connect(rod, pipe)
        # Both hangers state the two booleans; only the second one is silent
        # on nothing -- the multipliers differ so the least generous governs.
        _pset(
            rod,
            "Pset_SeismicRestraintDetailing",
            {
                "DetailsPreventRodBending": True,
                "HasDualStructuralSupports": index == 0,
                "SpacingExtensionMultiplier": multiplier,
            },
        )

    coupling = run(
        "root.create_entity", model, ifc_class="IfcPipeFitting", name="Flexible Coupling 1"
    )
    run("spatial.assign_container", model, products=[coupling], relating_structure=storey)
    _place(coupling, _cylinder(110.0, 120.0, (1.0, 0.0, 0.0)), (COUPLING_STATION, 0.0, PIPE_Z_MM))

    # A rigid fitting that must NOT be picked up as flexible.
    elbow = run("root.create_entity", model, ifc_class="IfcPipeFitting", name="Grooved Elbow 90")
    elbow.PredefinedType = "BEND"
    run("spatial.assign_container", model, products=[elbow], relating_structure=storey)
    _place(elbow, _cylinder(110.0, 120.0, (1.0, 0.0, 0.0)), (12000.0, 0.0, PIPE_Z_MM))

    model.write(str(path))
    return path


@pytest.fixture(scope="module")
def seismic_model(tmp_path_factory):
    path = tmp_path_factory.mktemp("seismic") / "seismic.ifc"
    _build_seismic_model(path)
    return ifcopenshell.open(str(path))


@pytest.fixture(scope="module")
def extractor(seismic_model):
    from app.modules.ifc_reader.ifc_geometry import IFCGeometryExtractor

    return IFCGeometryExtractor(seismic_model)


def _by_name(model, ifc_class, name):
    return next(e for e in model.by_type(ifc_class) if e.Name == name)


@pytest.fixture(scope="module")
def pipe(seismic_model):
    return _by_name(seismic_model, "IfcPipeSegment", "Main run")


# ── Mass ──────────────────────────────────────────────────────────────────────


class TestMassAgainstModel:
    def test_density_is_read_from_the_material(self, pipe, seismic_model):
        density, detail = seis.material_density_kg_m3(pipe, seismic_model)
        assert density == pytest.approx(STEEL_DENSITY)
        assert detail["material"] == "Steel S275"

    def test_volume_is_meshed_when_no_quantity_is_authored(self, pipe, extractor):
        volume, detail = seis.element_volume_m3(pipe, extractor)
        expected_m3 = math.pi * (PIPE_DIAMETER_MM / 2.0) ** 2 * PIPE_LENGTH_MM / 1e9
        assert volume == pytest.approx(expected_m3, rel=0.02)
        assert detail["source"] == "geometry"

    def test_mass_is_derived_from_density_and_volume(self, pipe, seismic_model, extractor):
        mass, detail = seis.element_mass_kg(
            pipe, ifc_file=seismic_model, geometry_extractor=extractor
        )
        expected = STEEL_DENSITY * math.pi * (PIPE_DIAMETER_MM / 2.0) ** 2 * PIPE_LENGTH_MM / 1e9
        assert mass == pytest.approx(expected, rel=0.02)
        assert detail["method"] == "density_x_volume"

    def test_the_derived_route_is_flagged_as_an_estimate(self, pipe, seismic_model, extractor):
        # A rule that must not rest on arithmetic has to be able to tell.
        _, detail = seis.element_mass_kg(
            pipe, ifc_file=seismic_model, geometry_extractor=extractor
        )
        assert detail["is_estimate"] is True

    def test_an_authored_weight_beats_the_arithmetic(self, seismic_model, extractor):
        weighed = _by_name(seismic_model, "IfcPipeSegment", "Weighed run")
        mass, detail = seis.element_mass_kg(
            weighed, ifc_file=seismic_model, geometry_extractor=extractor
        )
        assert mass == pytest.approx(640.0)
        assert detail["method"] == "authored"
        assert detail["is_estimate"] is False
        assert "NetWeight" in detail["source"]

    def test_no_material_gives_none_not_zero(self, seismic_model, extractor):
        # Zero mass generates zero seismic force and would pass every
        # restraint rule ever written.
        bare = _by_name(seismic_model, "IfcPipeSegment", "Bare run")
        mass, detail = seis.element_mass_kg(
            bare, ifc_file=seismic_model, geometry_extractor=extractor
        )
        assert mass is None
        assert "density x volume is incomplete" in detail["reason"]

    def test_a_density_in_the_wrong_unit_is_refused_not_used(
        self, seismic_model, extractor
    ):
        # 7.85 kg/m3 would give a 24 m steel run a mass of about 1.5 kg. It is
        # a plausible-looking number and a catastrophic seismic force, so the
        # band refuses it rather than passing it on.
        wrong = _by_name(seismic_model, "IfcPipeSegment", "Wrong unit run")
        density, density_detail = seis.material_density_kg_m3(wrong, seismic_model)
        assert density is None
        assert "unit is ambiguous" in density_detail["reason"]

        mass, _ = seis.element_mass_kg(
            wrong, ifc_file=seismic_model, geometry_extractor=extractor
        )
        assert mass is None

    def test_without_geometry_the_derived_route_declines(self, pipe, seismic_model):
        mass, _ = seis.element_mass_kg(pipe, ifc_file=seismic_model, geometry_extractor=None)
        assert mass is None

    def test_millimetre_model_declares_no_mass_unit_and_defaults_to_kg(self, seismic_model):
        assert seis.mass_unit_scale_kg(seismic_model) == 1.0


# ── Seismic coefficient ───────────────────────────────────────────────────────


class TestCoefficientAgainstModel:
    def test_building_level_coefficient_is_found(self, seismic_model):
        value, detail = seis.seismic_force_coefficient(seismic_model)
        assert value == pytest.approx(SEISMIC_COEFFICIENT)
        assert detail["scope"] == "IfcBuilding"

    def test_element_without_its_own_value_falls_back_to_the_building(
        self, seismic_model, pipe
    ):
        value, detail = seis.seismic_force_coefficient(seismic_model, pipe)
        assert value == pytest.approx(SEISMIC_COEFFICIENT)
        assert detail["scope"] == "IfcBuilding"

    def test_no_model_is_undetermined_not_zero(self):
        value, detail = seis.seismic_force_coefficient(None)
        assert value is None
        assert "no model" in detail["reason"]


# ── Flexible couplings ────────────────────────────────────────────────────────


class TestCouplingsAgainstModel:
    def test_the_flexible_fitting_is_indexed(self, seismic_model):
        index = seis.build_flexible_coupling_index(seismic_model)
        assert [entry["name"] for entry in index] == ["Flexible Coupling 1"]

    def test_a_rigid_elbow_is_not_a_coupling(self, seismic_model):
        elbow = _by_name(seismic_model, "IfcPipeFitting", "Grooved Elbow 90")
        matched, evidence = seis.is_flexible_coupling(elbow)
        assert matched is False
        assert evidence is None

    def test_the_name_is_recorded_as_the_evidence(self, seismic_model):
        index = seis.build_flexible_coupling_index(seismic_model)
        assert index[0]["evidence"] == "name:flexible coupling"

    def test_the_far_brace_governs_the_run(self, pipe, seismic_model, extractor):
        # Brace 1 sits beside the coupling; brace 2 is 12 m away. The run only
        # qualifies for an exemption if EVERY brace has one nearby, so the
        # reported distance is brace 2's.
        context = seis.seismic_context(
            pipe,
            ifc_file=seismic_model,
            geometry_extractor=extractor,
            coupling_index=seis.build_flexible_coupling_index(seismic_model),
        )
        assert context["flexible_coupling_within_mm"] > 10000.0
        distances = [
            r["distance_mm"] for r in context["flexible_coupling_detail"]["references"]
        ]
        assert min(distances) < 1000.0

    def test_a_model_with_no_couplings_leaves_it_undetermined(
        self, pipe, seismic_model, extractor
    ):
        context = seis.seismic_context(
            pipe, ifc_file=seismic_model, geometry_extractor=extractor, coupling_index=[]
        )
        assert context["flexible_coupling_within_mm"] is None


# ── Detailing flags ───────────────────────────────────────────────────────────


class TestDetailFlagsAgainstModel:
    def test_a_flag_every_hanger_states_is_true(self, pipe, seismic_model, extractor):
        context = seis.seismic_context(
            pipe, ifc_file=seismic_model, geometry_extractor=extractor
        )
        assert context["details_prevent_rod_bending"] is True

    def test_one_explicit_false_governs_the_run(self, pipe, seismic_model, extractor):
        # Hanger 2 says False, so the run does not have dual supports even
        # though hanger 1 does.
        context = seis.seismic_context(
            pipe, ifc_file=seismic_model, geometry_extractor=extractor
        )
        assert context["has_dual_structural_supports"] is False

    def test_the_least_generous_multiplier_governs(self, pipe, seismic_model, extractor):
        context = seis.seismic_context(
            pipe, ifc_file=seismic_model, geometry_extractor=extractor
        )
        assert context["spacing_extension_multiplier"] == pytest.approx(
            min(HANGER_MULTIPLIERS)
        )

    def test_provenance_is_recorded_per_support(self, pipe, seismic_model, extractor):
        context = seis.seismic_context(
            pipe, ifc_file=seismic_model, geometry_extractor=extractor
        )
        per_support = context["restraint_detail"]["per_support"]
        assert len(per_support) >= 2
        assert any(
            "Pset_SeismicRestraintDetailing" in str(row["details_prevent_rod_bending_source"])
            for row in per_support
        )

    def test_braces_do_not_vote_on_hanger_properties(self, pipe, seismic_model, extractor):
        # The run carries two braces as well as two hangers. All three
        # properties describe a hanger, so a brace's silence about them must
        # not outvote the hangers that answered.
        supports = seis.find_supports(pipe, geometry_extractor=extractor)
        assert any(s["ifc_class"] == "IfcMember" for s in supports)
        context = seis.seismic_context(
            pipe, ifc_file=seismic_model, geometry_extractor=extractor
        )
        assert context["restraint_detail"]["evaluated_support_count"] == 2
        assert context["details_prevent_rod_bending"] is True

    def test_a_value_on_the_run_outranks_the_fold(self, seismic_model):
        # An explicit statement about the run beats this module's reasoning
        # from its parts -- here a False on the run over True on every hanger.
        rods = [
            e
            for e in seismic_model.by_type("IfcDiscreteAccessory")
            if str(e.Name or "").startswith("Hanger Rod")
        ]
        assert seis.aggregate_restraint_flags(rods)["details_prevent_rod_bending"] is True

        run_element = _by_name(seismic_model, "IfcPipeSegment", "Detailed run")
        flags = seis.aggregate_restraint_flags(rods, run_element=run_element)
        assert flags["details_prevent_rod_bending"] is False
        assert flags["folded_over_hangers"]["details_prevent_rod_bending"] is True
        assert flags["authored_on_run"]["details_prevent_rod_bending"] is False

    def test_a_run_with_no_supports_is_undetermined_not_false(self, seismic_model, extractor):
        bare = _by_name(seismic_model, "IfcPipeSegment", "Bare run")
        context = seis.seismic_context(
            bare, ifc_file=seismic_model, geometry_extractor=extractor
        )
        assert context["details_prevent_rod_bending"] is None
        assert context["has_dual_structural_supports"] is None
        assert context["spacing_extension_multiplier"] is None


# ── Property name matching ────────────────────────────────────────────────────


class TestPropertyNameMatching:
    def test_separators_and_case_do_not_matter(self, seismic_model):
        rod = _by_name(seismic_model, "IfcDiscreteAccessory", "Hanger Rod 1")
        for spelling in (
            ("details_prevent_rod_bending",),
            ("DETAILSPREVENTRODBENDING",),
            ("Details Prevent Rod Bending",),
        ):
            value, where = seis.find_property(rod, spelling)
            assert value is True, spelling
            assert "DetailsPreventRodBending" in where

    def test_an_absent_property_returns_nothing(self, seismic_model):
        rod = _by_name(seismic_model, "IfcDiscreteAccessory", "Hanger Rod 1")
        assert seis.find_property(rod, ("NoSuchProperty",)) == (None, None)
