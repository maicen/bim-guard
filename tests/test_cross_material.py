"""
Tests for the XM-001 cross-material contamination comparator.

GALVANIC SERIES IN THESE TESTS
    The project's real series lives in the Supabase static asset
    'ruleset:BIMGUARD-GC-001' and is unreachable without a database. The table
    below is TEST DATA ONLY - deliberately round numbers, clearly not a
    published series - injected through load_rule_pack(galvanic_series=...).
    It must never be copied into a rule pack or treated as authoritative;
    there is exactly one real series and this is not it.

    The `noble` flags are what XM-001 uses to name the anode. Their ordering
    here follows standard electrochemistry (copper and stainless noble, zinc
    and steel active), which is the ordering any real series will agree with
    regardless of its sign convention.

Run: uv run pytest tests/test_cross_material.py -v
"""

import json

import pytest

from app.modules.module2_ifc_read import piping_fixtures as fx
from app.modules.module2_ifc_read import piping_producer as pp
from app.modules.module2_ifc_read.piping_schema import (
    EnvironmentClass,
    JointType,
    PipingElement,
    PipingSystem,
)
from app.modules.module4_comparator.cross_material import compare, load_rule_pack
from app.modules.module4_comparator.issue_schema import RiskBand

# TEST DATA ONLY - see module docstring. Not a published galvanic series.
# Values mirror the real GC-001 series, which is an ANODIC INDEX: every entry is
# positive and ascends from the noble end (titanium 0.05) to the active end
# (galvanised steel 0.82), so HIGHER is more anodic. Verified against the seeded
# payload by scripts/verify_anode_convention.py; see
# docs/defects/defect_report_anode_convention.md.
#
# An earlier version of this fixture was authored in electrode-potential form
# (all negative, more-negative-is-anodic), which is the opposite convention from
# the data the engines actually read. The ordering was right and every relative
# verdict held, but a fixture in the wrong convention cannot catch a convention
# defect - which is the one thing this file most needs to catch.
TEST_SERIES = {
    "GalvanisedSteel": {"potential_v": 0.82, "noble": False, "label": "Galvanised steel"},
    "CarbonSteel": {"potential_v": 0.55, "noble": False, "label": "Carbon steel"},
    "CastIron": {"potential_v": 0.52, "noble": False, "label": "Cast iron"},
    "Brass_C46400": {"potential_v": 0.32, "noble": True, "label": "Naval brass"},
    "Copper_C12200": {"potential_v": 0.28, "noble": True, "label": "Copper"},
    "SS304": {"potential_v": 0.12, "noble": True, "label": "SS304 passive"},
    "SS316": {"potential_v": 0.08, "noble": True, "label": "SS316 passive"},
    "Titanium": {"potential_v": 0.05, "noble": True, "label": "Titanium"},
}


# TEST DATA ONLY - the NASA-STD-6012 compatibility thresholds GC-001 carries.
# Injected the same way as the series so XM-001 embeds no galvanic constants.
TEST_THRESHOLDS = {
    "controlled": {"max_safe_voltage_v": 0.50},
    "normal": {"max_safe_voltage_v": 0.25},
    "harsh": {"max_safe_voltage_v": 0.15},
}


@pytest.fixture(scope="module")
def rule_pack():
    """Assemble the XM-001 pack with the test tables injected."""
    return load_rule_pack(
        galvanic_series=TEST_SERIES,
        compatibility_thresholds=TEST_THRESHOLDS,
    )


@pytest.fixture(scope="module")
def network():
    """Return the fixture scenario network."""
    return fx.generate_synthetic_piping_network()


@pytest.fixture(scope="module")
def issues(network, rule_pack):
    """All Issues XM-001 raises against the scenario network."""
    return compare(network, rule_pack)


@pytest.fixture(scope="module")
def couples(issues):
    """Couple findings keyed by (anode_material, cathode_material)."""
    return [i for i in issues if i.mechanism != "data_quality"]


def pair(element_id, **overrides) -> PipingElement:
    """Build an element for hand-built couple tests."""
    base = dict(
        id=element_id,
        ifc_class="IfcPipeSegment",
        subtype="pipe_segment",
        material="CarbonSteel",
        system=PipingSystem.DOMESTIC_HOT_WATER,
        environment_class=EnvironmentClass.T1_INDOOR_DAMP,
        joint_type=JointType.JT003_THREADED,
        properties={pp.CONNECTIVITY_SOURCE_KEY: "centerline"},
    )
    base.update(overrides)
    return PipingElement(**base)


def linked(left: PipingElement, right: PipingElement):
    """Join two elements bidirectionally and return them."""
    left.joined_to.append(right.id)
    right.joined_to.append(left.id)
    return [left, right]


class TestSingleSourceContract:
    """XM-001 must not carry its own galvanic series or environment table."""

    def test_pack_file_holds_no_potentials(self):
        """The on-disk pack must contain no material potentials."""
        raw = json.loads(
            __import__("pathlib").Path("data/rulesets/xm_001_cross_material.json").read_text(
                encoding="utf-8"
            )
        )
        assert "galvanic_series" not in raw["parameters"]
        assert "environment_severity" not in raw["parameters"]

    def test_loader_injects_both_tables(self, rule_pack):
        """load_rule_pack supplies what the file deliberately omits."""
        assert rule_pack["parameters"]["galvanic_series"] is TEST_SERIES
        assert "T3_chloride" in rule_pack["parameters"]["environment_severity"]

    def test_environment_table_comes_from_mm001(self, rule_pack):
        """The environment table must be the approved MM-001 one, unaltered."""
        mm = json.loads(
            __import__("pathlib").Path("data/rulesets/mm_001_material_media.json").read_text(
                encoding="utf-8"
            )
        )
        assert (
            rule_pack["parameters"]["environment_severity"]
            == mm["parameters"]["environment_severity"]
        )

    def test_missing_key_raises(self):
        """An incomplete pack must fail loudly."""
        with pytest.raises(ValueError, match="missing required keys"):
            compare([pair("A")], {"parameters": {"weights": {}}})


class TestAnodeIdentification:
    """The finding must name the material that sacrifices."""

    def test_carbon_steel_sacrifices_to_copper(self, rule_pack):
        """Copper is noble, carbon steel is active - the steel is the victim."""
        elements = linked(
            pair("A", material="CarbonSteel"),
            pair("B", material="Copper_C12200"),
        )
        issue = compare(elements, rule_pack)[0]
        assert issue.metadata["anode_material"] == "CarbonSteel"
        assert issue.metadata["cathode_material"] == "Copper_C12200"
        assert "CarbonSteel sacrifices to Copper_C12200" in issue.title

    def test_anode_order_independent_of_input_order(self, rule_pack):
        """Swapping the inputs must not swap the victim."""
        forward = compare(
            linked(pair("A", material="CarbonSteel"), pair("B", material="SS316")), rule_pack
        )[0]
        reverse = compare(
            linked(pair("B", material="SS316"), pair("A", material="CarbonSteel")), rule_pack
        )[0]
        assert forward.metadata["anode_material"] == reverse.metadata["anode_material"]

    def test_declared_convention_resolves_noble_noble_pairs(self, rule_pack):
        """Two noble materials still form a couple and must be resolvable.

        Nobility alone cannot separate brass from stainless, so the pack's
        declared series_convention breaks the tie. Brass 0.32 against SS316
        0.08 is a 0.24 V gap, placed in T3_CHLORIDE so it clears the harsh
        threshold (0.15) and survives the compatibility floor — indoors it
        would correctly be suppressed.
        """
        issue = compare(
            linked(
                pair(
                    "A",
                    material="Brass_C46400",
                    environment_class=EnvironmentClass.T3_CHLORIDE,
                ),
                pair("B", material="SS316", environment_class=EnvironmentClass.T3_CHLORIDE),
            ),
            rule_pack,
        )[0]
        assert issue.mechanism != "data_quality"
        assert issue.metadata["anode_material"] == "Brass_C46400"

    def test_no_convention_and_no_nobility_is_data_quality(self, rule_pack):
        """With neither discriminator, XM-001 must refuse to guess the victim.

        The two existing engines read the shared series with opposite sign
        conventions, so inferring direction unaided would be wrong half the
        time.
        """
        pack = json.loads(json.dumps(rule_pack))
        pack["parameters"].pop("series_convention")
        pack["parameters"]["galvanic_series"] = {
            "CarbonSteel": {"potential_v": -0.60},
            "Copper_C12200": {"potential_v": -0.20},
        }
        issues = compare(
            linked(pair("A", material="CarbonSteel"), pair("B", material="Copper_C12200")), pack
        )
        assert issues[0].metadata["check"] == "anode_unresolvable"

    def test_convention_direction_is_honoured(self, rule_pack):
        """Flipping the declared convention must flip the named victim.

        The local series is deliberately signed against TEST_SERIES: negative
        values, no noble flags. That is the point — it proves the resolver
        follows the pack's declaration rather than any property of the numbers
        or a convention hardcoded in the engine.
        """
        pack = json.loads(json.dumps(rule_pack))
        pack["parameters"]["series_convention"]["value"] = "more_positive_is_anodic"
        pack["parameters"]["galvanic_series"] = {
            "CarbonSteel": {"potential_v": -0.60},
            "Copper_C12200": {"potential_v": -0.20},
        }
        issue = compare(
            linked(pair("A", material="CarbonSteel"), pair("B", material="Copper_C12200")), pack
        )[0]
        assert issue.metadata["anode_material"] == "Copper_C12200"

    def test_material_absent_from_series_is_data_quality(self, rule_pack):
        """An unlisted material must not be assumed benign."""
        issues = compare(
            linked(pair("A", material="CarbonSteel"), pair("B", material="PVC")), rule_pack
        )
        assert issues[0].metadata["check"] == "material_not_in_series"


class TestMitigation:
    """Mitigated couples score with credit; they do not vanish."""

    def test_dielectric_union_still_reports(self, rule_pack):
        """A mitigated couple must produce an Issue, not silence."""
        elements = linked(
            pair("A", material="CarbonSteel"),
            pair("B", material="Copper_C12200", joint_type=JointType.JT014_DIELECTRIC_UNION),
        )
        issues = compare(elements, rule_pack)
        assert len(issues) == 1
        assert issues[0].metadata["mitigated"] is True

    def test_mitigation_bands_low(self, rule_pack):
        """Dielectric credit drops the couple to Low."""
        mitigated = compare(
            linked(
                pair("A", material="CarbonSteel"),
                pair("B", material="Copper_C12200", joint_type=JointType.JT014_DIELECTRIC_UNION),
            ),
            rule_pack,
        )[0]
        assert mitigated.band is RiskBand.LOW

    def test_identical_couple_unmitigated_scores_higher(self, rule_pack):
        """The same couple without a union must score ten times higher."""
        unmitigated = compare(
            linked(pair("A", material="CarbonSteel"), pair("B", material="Copper_C12200")),
            rule_pack,
        )[0]
        mitigated = compare(
            linked(
                pair("C", material="CarbonSteel"),
                pair("D", material="Copper_C12200", joint_type=JointType.JT014_DIELECTRIC_UNION),
            ),
            rule_pack,
        )[0]
        assert unmitigated.metadata["raw_score_exact"] == pytest.approx(
            mitigated.metadata["raw_score_exact"]
        )
        assert mitigated.metadata["composite_score_exact"] == pytest.approx(
            unmitigated.metadata["composite_score_exact"] * 0.10
        )

    def test_mitigated_finding_carries_commissioning_note(self, rule_pack):
        """The commissioning verification must be stated, not implied."""
        issue = compare(
            linked(
                pair("A", material="CarbonSteel"),
                pair("B", material="Copper_C12200", joint_type=JointType.JT014_DIELECTRIC_UNION),
            ),
            rule_pack,
        )[0]
        assert "verify union integrity at commissioning" in issue.description.lower()
        assert "commissioning" in issue.mitigation.lower()

    def test_union_on_either_side_counts(self, rule_pack):
        """A union breaks continuity regardless of which side records it."""
        left_side = compare(
            linked(
                pair("A", material="CarbonSteel", joint_type=JointType.JT014_DIELECTRIC_UNION),
                pair("B", material="Copper_C12200"),
            ),
            rule_pack,
        )[0]
        assert left_side.metadata["mitigated"] is True


class TestScenarioVerdicts:
    """The fixture scenarios must produce their expected bands."""

    def test_copper_carbon_steel_junctions_flagged(self, couples):
        """DHW-S05 forms two Cu/Fe couples: one mitigated, one not.

        Identical materials, identical environment, identical raw score. The
        only difference is the dielectric union on DHW-P06, so this is the
        like-for-like control on the mitigation factor.
        """
        steel_couples = {
            i.metadata["cathode_id"]: i
            for i in couples
            if "DHW-S05" in (i.metadata["anode_id"], i.metadata["cathode_id"])
            and {i.metadata["anode_material"], i.metadata["cathode_material"]}
            == {"CarbonSteel", "Copper_C12200"}
        }
        assert set(steel_couples) == {"DHW-P04", "DHW-P06"}
        assert all(i.metadata["anode_material"] == "CarbonSteel" for i in steel_couples.values())

        unmitigated = steel_couples["DHW-P04"]
        mitigated = steel_couples["DHW-P06"]
        assert unmitigated.band is RiskBand.MEDIUM
        assert mitigated.band is RiskBand.LOW
        assert unmitigated.metadata["raw_score_exact"] == pytest.approx(
            mitigated.metadata["raw_score_exact"]
        )
        assert mitigated.metadata["composite_score_exact"] == pytest.approx(
            unmitigated.metadata["composite_score_exact"] * 0.10
        )

    def test_pool_group_produces_no_couples(self, couples):
        """Uniform SS316 means no galvanic driving voltage."""
        pool = [
            i
            for i in couples
            if i.metadata["anode_id"].startswith("POOL")
            or i.metadata["cathode_id"].startswith("POOL")
        ]
        assert pool == []

    def test_fire_loop_produces_no_couples(self, couples):
        """The XM-001 negative control: uniform galvanised steel."""
        fire = [
            i
            for i in couples
            if i.metadata["anode_id"].startswith("FIRE")
            or i.metadata["cathode_id"].startswith("FIRE")
        ]
        assert fire == []

    def test_chilled_water_stainless_couple_found(self, couples):
        """CHW-M06 SS316 pump against carbon steel run."""
        found = [
            i
            for i in couples
            if {i.metadata["anode_id"], i.metadata["cathode_id"]} == {"CHW-P05", "CHW-M06"}
        ]
        assert len(found) == 1
        assert found[0].metadata["anode_material"] == "CarbonSteel"

    def test_port_linked_pair_assessed(self, couples):
        """Tier 1 connectivity must feed XM-001 like any other adjacency."""
        found = [
            i
            for i in couples
            if {i.metadata["anode_id"], i.metadata["cathode_id"]} == {"PORT-A", "PORT-B"}
        ]
        assert len(found) == 1
        assert found[0].metadata["anode_material"] == "CarbonSteel"


class TestTierSemantics:
    """Connectivity tier drives whether an element can be assessed."""

    def test_indeterminable_element_skipped_with_issue(self, issues):
        """NOGEO-01 must be skipped WITH a data-quality Issue."""
        nogeo = [i for i in issues if i.element_id == "NOGEO-01"]
        assert len(nogeo) == 1
        assert nogeo[0].mechanism == "data_quality"
        assert nogeo[0].metadata["check"] == "connectivity_indeterminable"

    def test_isolated_tier2_element_is_silent(self, rule_pack):
        """joined_to == [] on a Tier 2 element means genuinely isolated."""
        element = pair("LONE", properties={pp.CONNECTIVITY_SOURCE_KEY: "centerline"})
        assert compare([element], rule_pack) == []

    def test_empty_joined_to_is_not_conflated(self, rule_pack):
        """Isolated and indeterminable both have joined_to == [].

        Only the tier marker separates them, so XM-001 must branch on that
        rather than on the empty list.
        """
        isolated = pair("ISO", properties={pp.CONNECTIVITY_SOURCE_KEY: "centerline"})
        unknown = pair("UNK", properties={pp.CONNECTIVITY_SOURCE_KEY: "indeterminable"})
        issues = compare([isolated, unknown], rule_pack)
        assert len(issues) == 1
        assert issues[0].element_id == "UNK"


class TestSeparation:
    """Direct contact and same-loop couples score differently."""

    def test_direct_contact_factor(self, rule_pack):
        """Joined elements are direct contact."""
        issue = compare(
            linked(pair("A", material="CarbonSteel"), pair("B", material="Copper_C12200")),
            rule_pack,
        )[0]
        assert issue.metadata["separation"] == "direct_contact"
        assert issue.metadata["separation_factor"] == 1.00

    def test_same_loop_scores_lower(self, rule_pack):
        """Materials that share a loop but never touch are still coupled.

        Steel - brass - copper: steel and copper never meet at a joint, so
        the steel/copper couple exists only through the shared electrolyte.
        """
        a = pair("A", material="CarbonSteel")
        b = pair("B", material="Brass_C46400")
        c = pair("C", material="Copper_C12200")
        a.joined_to.append("B")
        b.joined_to.extend(["A", "C"])
        c.joined_to.append("B")

        issues = compare([a, b, c], rule_pack)
        same_loop = [i for i in issues if i.metadata.get("separation") == "same_loop"]
        assert len(same_loop) == 1
        assert same_loop[0].metadata["separation_factor"] == 0.80
        assert {same_loop[0].metadata["anode_id"], same_loop[0].metadata["cathode_id"]} == {
            "A",
            "C",
        }

    def test_same_loop_suppressed_when_pair_touches_directly(self, rule_pack):
        """Repeat same-loop pairs of a material combination add no action.

        Steel - steel - copper: the steel/copper couple already exists at a
        joint, so the second steel's same-loop pairing with the copper is
        redundant. Substituting the copper resolves both.
        """
        a = pair("A", material="CarbonSteel")
        b = pair("B", material="CarbonSteel")
        c = pair("C", material="Copper_C12200")
        a.joined_to.append("B")
        b.joined_to.extend(["A", "C"])
        c.joined_to.append("B")

        issues = compare([a, b, c], rule_pack)
        assert [i for i in issues if i.metadata.get("separation") == "same_loop"] == []
        direct = [i for i in issues if i.metadata.get("separation") == "direct_contact"]
        assert len(direct) == 1

    def test_different_systems_not_same_loop(self, rule_pack):
        """Elements on different systems share no electrolyte path."""
        a = pair("A", material="CarbonSteel", system=PipingSystem.DOMESTIC_HOT_WATER)
        b = pair("B", material="CarbonSteel", system=PipingSystem.DOMESTIC_HOT_WATER)
        c = pair("C", material="Copper_C12200", system=PipingSystem.FIRE_SPRINKLER)
        a.joined_to.append("B")
        b.joined_to.extend(["A", "C"])
        c.joined_to.append("B")

        issues = compare([a, b, c], rule_pack)
        assert [i for i in issues if i.metadata.get("separation") == "same_loop"] == []


class TestCompatibilityFloor:
    """Pairs below the environment threshold are not couples at all."""

    def test_brass_copper_is_compatible(self, rule_pack):
        """0.05 V is compatible in every NASA-STD-6012 environment."""
        issues = compare(
            linked(pair("A", material="Brass_C46400"), pair("B", material="Copper_C12200")),
            rule_pack,
        )
        assert issues == []

    def test_compatible_pair_suppressed_not_downgraded(self, couples):
        """No brass/copper couple survives anywhere in the network.

        Suppression rather than a Low band: a mitigated couple is a design
        decision worth showing, a compatible material pair is not a couple.
        """
        brass_copper = [
            i
            for i in couples
            if {i.metadata["anode_material"], i.metadata["cathode_material"]}
            == {"Brass_C46400", "Copper_C12200"}
        ]
        assert brass_copper == []

    def test_carbon_steel_couples_survive_the_floor(self, couples):
        """0.35-0.55 V gaps clear every threshold and must still report."""
        steel = [i for i in couples if i.metadata["anode_material"] == "CarbonSteel"]
        assert len(steel) >= 4
        assert all(i.metadata["voltage_gap_v"] >= 0.15 for i in steel)

    def test_threshold_varies_by_environment(self, rule_pack):
        """A gap can be compatible indoors and a couple in a harsh space.

        0.20 V sits between the harsh threshold (0.15) and normal (0.25).
        The local series is contrived to hit that gap exactly; direction comes
        from the noble flags and magnitude from abs(gap), so its sign does not
        matter here.
        """
        gap_series = {
            "CarbonSteel": {"potential_v": -0.40, "noble": False},
            "Copper_C12200": {"potential_v": -0.20, "noble": True},
        }
        pack = load_rule_pack(
            galvanic_series=gap_series, compatibility_thresholds=TEST_THRESHOLDS
        )

        indoor = compare(
            linked(
                pair("A", material="CarbonSteel"),
                pair("B", material="Copper_C12200"),
            ),
            pack,
        )
        assert indoor == []

        harsh = compare(
            linked(
                pair("C", material="CarbonSteel", environment_class=EnvironmentClass.T3_CHLORIDE),
                pair("D", material="Copper_C12200", environment_class=EnvironmentClass.T3_CHLORIDE),
            ),
            pack,
        )
        assert len(harsh) == 1

    def test_floor_fails_open_on_unmapped_environment(self, rule_pack):
        """An unresolvable threshold must not silently suppress a couple."""
        pack = json.loads(json.dumps(rule_pack))
        pack["parameters"]["environment_threshold_class"] = {}
        issues = compare(
            linked(pair("A", material="Brass_C46400"), pair("B", material="Copper_C12200")),
            pack,
        )
        assert len(issues) == 1

    def test_floor_can_be_disabled(self, rule_pack):
        """Disabling the floor restores the pre-floor behaviour."""
        pack = json.loads(json.dumps(rule_pack))
        pack["parameters"]["compatibility_floor"]["enabled"] = False
        issues = compare(
            linked(pair("A", material="Brass_C46400"), pair("B", material="Copper_C12200")),
            pack,
        )
        assert len(issues) == 1


class TestAuditTrail:
    """Every couple must be traceable to its sources."""

    def test_findings_carry_four_citations(self, couples):
        """Voltage, separation, environment, and mitigation each cited."""
        for issue in couples:
            clauses = [c["clause"] for c in issue.citations]
            assert len(issue.citations) == 4, issue.id
            assert any("/" in c for c in clauses)

    def test_series_citation_names_single_source(self, couples):
        """The audit trail must point at the one real series."""
        for issue in couples:
            assert any("GC-001 galvanic series" in c["standard"] for c in issue.citations)

    def test_description_matches_stored_score(self, couples):
        """Prose and Issue.score must not disagree."""
        for issue in couples:
            assert str(issue.score) in issue.description, issue.id

    def test_strings_are_console_safe(self, issues):
        """Runtime strings must print on a cp1252 console."""
        for issue in issues:
            issue.title.encode("cp1252")
            (issue.description or "").encode("cp1252")
            issue.mitigation.encode("cp1252")

    def test_issue_ids_unique(self, issues):
        """Issue ids must be unique within a run."""
        ids = [i.id for i in issues]
        assert len(ids) == len(set(ids))

    def test_empty_input_yields_no_issues(self, rule_pack):
        """An empty model is not an error."""
        assert compare([], rule_pack) == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
