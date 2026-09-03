"""
Tests for the synthetic PipingElement scenario network.

These are the test-first contract for MM-001 and XM-001. Each EXPECTED_SCENARIOS
entry names a situation with a known correct verdict; the tests here assert the
fixture actually creates the preconditions for that verdict, so the rule-pack
cell values can be reviewed against named cases rather than abstract numbers.

The verdict assertions themselves are marked xfail until the engines exist.

Run: uv run pytest tests/test_piping_fixtures.py -v
"""

import pytest

from app.modules.ifc_reader import piping_fixtures as fx
from app.modules.ifc_reader import piping_producer as pp
from app.modules.ifc_reader import piping_schema as ps
from app.modules.ifc_reader.piping_schema import (
    CANONICAL_MATERIALS,
    EnvironmentClass,
    PipingSystem,
)


@pytest.fixture(scope="module")
def network():
    """Return the generated scenario network."""
    return fx.generate_synthetic_piping_network()


@pytest.fixture(scope="module")
def by_id(network):
    """Return the network keyed by element id."""
    return {e.id: e for e in network}


def pairs(network):
    """Return adjacent id pairs as a set of sorted tuples."""
    return {tuple(sorted((e.id, other))) for e in network for other in e.joined_to}


class TestNetworkShape:
    """Structural guarantees the scenarios depend on."""

    def test_group_counts(self, network):
        """Each specified group contributes its stated element count."""
        prefixes = {"DHW": 8, "CHW": 6, "POOL": 5, "FIRE": 4}
        for prefix, expected in prefixes.items():
            actual = sum(1 for e in network if e.id.startswith(prefix))
            assert actual == expected, f"{prefix}: expected {expected}, got {actual}"
        probes = sum(1 for e in network if e.id.startswith(("PORT", "NOGEO")))
        assert probes == 3
        assert sum(1 for e in network if e.id.startswith("COND")) == 1
        assert len(network) == 27

    def test_deterministic(self):
        """Repeat calls produce identical networks."""
        a = fx.generate_synthetic_piping_network()
        b = fx.generate_synthetic_piping_network()
        assert [(e.id, e.material, e.joined_to) for e in a] == [
            (e.id, e.material, e.joined_to) for e in b
        ]

    def test_all_materials_canonical(self, network):
        """Every material must be scoreable by the rule packs."""
        assert {e.material for e in network} <= CANONICAL_MATERIALS

    def test_material_raw_round_trips(self, network):
        """Fixture material_raw must normalise back through the real producer.

        Ties the fixture to production code: if the generator and the
        normaliser diverge, this fails rather than silently drifting.
        """
        for element in network:
            if element.material_raw:
                assert pp.normalise_material(element.material_raw) == element.material

    def test_diameters_within_spec_range(self, network):
        """Dimensions stay within the DN15-DN100 range specified."""
        diameters = [e.nominal_diameter_mm for e in network if e.nominal_diameter_mm]
        assert diameters
        assert all(15.0 <= d <= 100.0 for d in diameters), sorted(set(diameters))

    def test_lanes_do_not_cross_link(self, network, by_id):
        """Groups are 6 m apart in Y, so no adjacency may cross groups.

        PORT-A/PORT-B are exempt: they are linked by authored ports, not
        geometry, and are the only intended cross-distance link.
        """
        for a, b in pairs(network):
            if {a, b} == {"PORT-A", "PORT-B"}:
                continue
            assert abs(by_id[a].centroid.y - by_id[b].centroid.y) < 0.01, (a, b)

    def test_adjacency_actually_exercised(self, network):
        """Endpoint-coincident geometry must yield real adjacencies.

        The real drainage model yields zero; that is the gap this closes.
        """
        assert len(pairs(network)) >= 15


class TestScenarioPreconditions:
    """Each EXPECTED_SCENARIOS entry must be physically set up correctly."""

    def test_every_scenario_references_real_elements(self, by_id):
        """No scenario may name an element the network does not contain."""
        for scenario in fx.EXPECTED_SCENARIOS:
            missing = [i for i in scenario.element_ids if i not in by_id]
            assert not missing, f"{scenario.name}: unknown ids {missing}"

    def test_copper_carbon_steel_junctions_exist(self, network, by_id):
        """DHW-S05 must touch copper on both sides — the XM-001 target."""
        steel = by_id["DHW-S05"]
        assert steel.material == "CarbonSteel"
        neighbours = {by_id[i].material for i in steel.joined_to}
        assert neighbours == {"Copper_C12200"}
        assert len(steel.joined_to) == 2

    def test_copper_steel_junction_is_unmitigated(self, by_id):
        """The couple must not carry a dielectric union.

        A dielectric union would break galvanic continuity and legitimately
        downgrade the finding, defeating the scenario.
        """
        steel = by_id["DHW-S05"]
        assert steel.joint_type is not ps.JointType.JT014_DIELECTRIC_UNION

    def test_chilled_water_stainless_couple_exists(self, by_id):
        """CHW-M06 SS316 pump must touch carbon steel."""
        pump = by_id["CHW-M06"]
        assert pump.material == "SS316"
        assert {by_id[i].material for i in pump.joined_to} == {"CarbonSteel"}

    def test_pool_group_is_uniform_ss316_in_chloride(self, network):
        """The MM-001 case study: all SS316, all T3_CHLORIDE, pool service."""
        pool = [e for e in network if e.id.startswith("POOL")]
        assert {e.material for e in pool} == {"SS316"}
        assert {e.environment_class for e in pool} == {EnvironmentClass.T3_CHLORIDE}
        assert {e.system for e in pool} == {PipingSystem.POOL_CIRCULATION}

    def test_pool_group_has_no_dissimilar_couples(self, network):
        """Uniform material means XM-001 must find nothing here."""
        pool_ids = {e.id for e in network if e.id.startswith("POOL")}
        dissimilar = [
            p for p in fx.dissimilar_material_pairs(network) if {p[0], p[2]} <= pool_ids
        ]
        assert dissimilar == []

    def test_fire_loop_is_uniform_and_connected(self, network):
        """The XM-001 negative control: same material, but genuinely adjacent.

        Adjacency matters — a control that is simply disconnected would pass
        for the wrong reason.
        """
        fire = [e for e in network if e.id.startswith("FIRE")]
        assert {e.material for e in fire} == {"GalvanisedSteel"}
        assert sum(len(e.joined_to) for e in fire) // 2 == 3

    def test_fire_loop_has_no_dissimilar_couples(self, network):
        """The negative control must contain zero XM-001 candidates."""
        fire_ids = {e.id for e in network if e.id.startswith("FIRE")}
        dissimilar = [
            p for p in fx.dissimilar_material_pairs(network) if {p[0], p[2]} <= fire_ids
        ]
        assert dissimilar == []

    def test_industrial_condenser_pins_provisional_cell(self, by_id):
        """COND-01 exists solely to pin the interpolated T5_INDUSTRIAL severity.

        That value has no CC-001 counterpart and is flagged provisional. Without
        an element exercising it, a future edit could move it unnoticed.
        """
        element = by_id["COND-01"]
        assert element.material == "CarbonSteel"
        assert element.system is PipingSystem.CONDENSER_WATER
        assert element.environment_class is EnvironmentClass.T5_INDUSTRIAL
        assert element.operating_temperature_c == 32.0

    def test_matrix_conflict_is_documented(self):
        """The fire loop is not an MM-001 control, and that must be recorded."""
        assert "MM-001" in fx.MATRIX_CONFLICT
        assert "stagnant_water" in fx.MATRIX_CONFLICT


class TestTierExercises:
    """The connectivity probes must exercise all three tiers."""

    def test_tier1_ports_link_across_distance(self, by_id):
        """Authored ports link elements no proximity test could reach."""
        a, b = by_id["PORT-A"], by_id["PORT-B"]
        assert a.joined_to == ["PORT-B"]
        assert b.joined_to == ["PORT-A"]
        assert a.properties[pp.CONNECTIVITY_SOURCE_KEY] == "ports"
        # Confirm geometry alone could never have produced this link.
        assert abs(a.centroid.x - b.centroid.x) > 100.0

    def test_tier2_used_for_geometric_groups(self, network):
        """Ordinary segments resolve through centerline proximity."""
        dhw = [e for e in network if e.id.startswith("DHW")]
        assert {e.properties[pp.CONNECTIVITY_SOURCE_KEY] for e in dhw} == {"centerline"}

    def test_tier3_flags_geometryless_element(self, by_id):
        """NOGEO-01 must be marked indeterminable, not treated as isolated."""
        element = by_id["NOGEO-01"]
        assert element.joined_to == []
        assert element.properties[pp.CONNECTIVITY_SOURCE_KEY] == "indeterminable"
        assert pp.CONNECTIVITY_INDETERMINABLE in element.extraction_warnings

    def test_all_three_tiers_present(self, network):
        """The network must exercise every tier, not just the common one."""
        sources = {e.properties.get(pp.CONNECTIVITY_SOURCE_KEY) for e in network}
        assert sources == {"ports", "centerline", "indeterminable"}


class TestFixtureAnchors:
    """The three piping_schema fixtures are the validation reference."""

    @pytest.fixture
    def anchors(self):
        """Return the canonical fixtures from piping_schema."""
        return [ps.example_ss316_pipe_in_plant_room(), ps.example_valve(), ps.example_pump()]

    def test_anchors_use_canonical_materials(self, anchors):
        """The fixtures themselves must satisfy the material contract."""
        assert {a.material for a in anchors} <= CANONICAL_MATERIALS

    def test_synthetic_covers_anchor_fields(self, anchors, by_id):
        """Synthetic pipe segments populate what the anchor pipe populates.

        Compared against the pipe anchor only: the valve and pump anchors
        legitimately omit centerline, since equipment subtypes carry none.
        """
        anchor = next(a for a in anchors if a.subtype == "pipe_segment")
        synthetic = by_id["POOL-P01"]
        fields = (
            "id", "ifc_class", "subtype", "name", "bbox", "centroid", "centerline",
            "level_name", "space_name", "material", "material_raw", "pren",
            "nominal_diameter_mm", "outside_diameter_mm", "wall_thickness_mm",
            "system", "operating_temperature_c", "design_pressure_bar",
            "environment_class", "environment_source", "joint_type",
            "wetted_surface_area_m2", "exposed_surface_area_m2",
        )
        missing = [
            f for f in fields if getattr(anchor, f) is not None and getattr(synthetic, f) is None
        ]
        assert not missing, f"synthetic missing anchor fields: {missing}"

    def test_synthetic_matches_anchor_types(self, anchors, by_id):
        """Shared fields must hold the same types in both sources."""
        anchor = next(a for a in anchors if a.subtype == "pipe_segment")
        synthetic = by_id["POOL-P01"]
        for field in ("material", "system", "environment_class", "joint_type", "centerline"):
            assert isinstance(getattr(synthetic, field), type(getattr(anchor, field))), field

    def test_pool_scenario_mirrors_anchor(self, anchors, by_id):
        """The pool group reproduces the anchor's material and environment.

        The SS316-in-chloride anchor is the thesis case; the fixture group
        must represent the same situation for the matrix review to transfer.
        """
        anchor = next(a for a in anchors if a.subtype == "pipe_segment")
        synthetic = by_id["POOL-P01"]
        assert synthetic.material == anchor.material == "SS316"
        assert synthetic.environment_class == anchor.environment_class
        assert synthetic.system == anchor.system


class TestExpectedVerdicts:
    """Verdicts the engines must produce. xfail until MM-001/XM-001 exist."""

    def _scenario(self, name_fragment):
        return next(s for s in fx.EXPECTED_SCENARIOS if name_fragment in s.name)

    def test_scenarios_cover_both_mechanisms(self):
        """The contract must exercise MM-001, XM-001, and the tiering."""
        mechanisms = {s.mechanism for s in fx.EXPECTED_SCENARIOS}
        assert {"MM-001", "XM-001", "tiering"} <= mechanisms

    def test_scenarios_include_a_negative_control(self):
        """At least one scenario must expect no finding."""
        assert any(s.expected_band == "None" for s in fx.EXPECTED_SCENARIOS)

    def test_every_scenario_states_a_rationale(self):
        """A verdict without engineering justification is not reviewable."""
        for scenario in fx.EXPECTED_SCENARIOS:
            assert len(scenario.rationale) > 80, scenario.name

    def test_copper_steel_couple_flagged(self, network):
        """Cu/carbon-steel in a wet system must be flagged, steel as anode."""
        from app.modules.comparator.cross_material import compare, load_rule_pack
        from tests.test_cross_material import TEST_SERIES, TEST_THRESHOLDS

        issues = compare(network, load_rule_pack(
            galvanic_series=TEST_SERIES, compatibility_thresholds=TEST_THRESHOLDS
        ))
        couples = [
            i
            for i in issues
            if i.mechanism != "data_quality"
            and {i.metadata["anode_material"], i.metadata["cathode_material"]}
            == {"CarbonSteel", "Copper_C12200"}
            and "DHW-S05" in (i.metadata["anode_id"], i.metadata["cathode_id"])
        ]
        assert len(couples) == 2
        assert all(c.metadata["anode_material"] == "CarbonSteel" for c in couples)

    def test_ss316_in_chloride_flagged(self, network):
        """SS316 in T3_CHLORIDE pool service must reach High under MM-001."""
        import json
        from pathlib import Path

        from app.modules.comparator.issue_schema import RiskBand
        from app.modules.comparator.material_media import compare

        pack = json.loads(
            Path("data/rulesets/mm_001_material_media.json").read_text(encoding="utf-8")
        )
        findings = {
            i.element_id: i for i in compare(network, pack) if i.mechanism != "data_quality"
        }
        for element_id in ("POOL-P01", "POOL-F02", "POOL-P03", "POOL-F04", "POOL-P05"):
            assert findings[element_id].band is RiskBand.HIGH

    def test_fire_loop_clean_under_xm001(self, network):
        """The uniform galvanised loop must produce no XM-001 couple."""
        from app.modules.comparator.cross_material import compare, load_rule_pack
        from tests.test_cross_material import TEST_SERIES, TEST_THRESHOLDS

        issues = compare(network, load_rule_pack(
            galvanic_series=TEST_SERIES, compatibility_thresholds=TEST_THRESHOLDS
        ))
        fire = [
            i
            for i in issues
            if i.mechanism != "data_quality"
            and (
                i.metadata["anode_id"].startswith("FIRE")
                or i.metadata["cathode_id"].startswith("FIRE")
            )
        ]
        assert fire == []

    def test_nogeo_excluded_with_data_quality_issue(self, network):
        """NOGEO-01 must be skipped with a data-quality issue, not passed."""
        from app.modules.comparator.cross_material import compare, load_rule_pack
        from tests.test_cross_material import TEST_SERIES, TEST_THRESHOLDS

        issues = compare(network, load_rule_pack(
            galvanic_series=TEST_SERIES, compatibility_thresholds=TEST_THRESHOLDS
        ))
        nogeo = [i for i in issues if i.element_id == "NOGEO-01"]
        assert len(nogeo) == 1
        assert nogeo[0].mechanism == "data_quality"
        assert nogeo[0].metadata["check"] == "connectivity_indeterminable"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
