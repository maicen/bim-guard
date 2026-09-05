"""
Tests for the MM-001 material-media compatibility comparator.

Drives the approved rule pack against the fixture scenario network, so the
verdicts asserted here are the ones reviewed cell by cell rather than numbers
invented alongside the code.

Run: uv run pytest tests/test_material_media.py -v
"""

import json
from pathlib import Path

import pytest

from app.modules.ifc_reader import piping_fixtures as fx
from app.modules.ifc_reader.piping_schema import EnvironmentClass, PipingElement, PipingSystem
from app.modules.comparator.issue_schema import RiskBand
from app.modules.comparator.material_media import (
    DEFAULT_RULESET_VERSION,
    compare,
    ruleset_version,
)

RULE_PACK_PATH = Path("data/rulesets/mm_001_material_media.json")


@pytest.fixture(scope="module")
def rule_pack():
    """Load the approved MM-001 rule pack."""
    return json.loads(RULE_PACK_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def network():
    """Return the fixture scenario network."""
    return fx.generate_synthetic_piping_network()


@pytest.fixture(scope="module")
def issues(network, rule_pack):
    """All Issues MM-001 raises against the scenario network."""
    return compare(network, rule_pack)


@pytest.fixture(scope="module")
def findings(issues):
    """Compliance findings only, keyed by element id."""
    return {i.element_id: i for i in issues if i.mechanism != "data_quality"}


@pytest.fixture(scope="module")
def data_quality(issues):
    """Data-quality Issues, keyed by element id."""
    return {i.element_id: i for i in issues if i.mechanism == "data_quality"}


def element(**overrides) -> PipingElement:
    """Build a scoreable element, overriding selected fields."""
    base = dict(
        id="TEST-01",
        ifc_class="IfcPipeSegment",
        subtype="pipe_segment",
        material="CarbonSteel",
        system=PipingSystem.DOMESTIC_HOT_WATER,
        environment_class=EnvironmentClass.T1_INDOOR_DAMP,
        operating_temperature_c=60.0,
    )
    base.update(overrides)
    return PipingElement(**base)


class TestRulePackContract:
    """The pack must satisfy the contract the comparator relies on."""

    def test_pack_is_approved(self, rule_pack):
        """Only an approved pack should drive verdicts."""
        assert rule_pack["status"] == "APPROVED v1.0"

    def test_missing_key_raises(self, rule_pack):
        """An incomplete pack must fail loudly, not score partially."""
        broken = {"parameters": {"weights": rule_pack["parameters"]["weights"]}}
        with pytest.raises(ValueError, match="missing required keys"):
            compare([element()], broken)

    def test_every_matrix_cell_cited(self, rule_pack):
        """White-box audit trail requires a citation on every cell."""
        matrix = rule_pack["parameters"]["compatibility_matrix"]
        uncited = [
            (m, md) for m, row in matrix.items() for md, c in row.items() if not c.get("cite")
        ]
        assert uncited == []

    def test_weights_sum_to_one(self, rule_pack):
        """Composite weights must form a normalised 0-1 score."""
        assert sum(rule_pack["parameters"]["weights"].values()) == pytest.approx(1.0)


class TestScenarioVerdicts:
    """The reviewed scenarios must produce their approved bands."""

    def test_ss316_in_chloride_flagged_high(self, findings):
        """Thesis case study: SS316 in T3_CHLORIDE pool service."""
        for element_id in ("POOL-P01", "POOL-F02", "POOL-P03", "POOL-F04", "POOL-P05"):
            issue = findings[element_id]
            assert issue.band is RiskBand.HIGH, element_id
            assert issue.metadata["composite_score_exact"] == pytest.approx(0.7075)

    def test_industrial_condenser_pins_provisional_cell(self, findings):
        """COND-01 pins the interpolated T5_INDUSTRIAL severity.

        It sits just above the High threshold by design: any movement of the
        provisional 0.85 changes the band and fails here rather than passing
        silently.
        """
        issue = findings["COND-01"]
        assert issue.band is RiskBand.HIGH
        assert issue.metadata["composite_score_exact"] == pytest.approx(0.6650)
        assert issue.metadata["environment_severity"] == 0.85

    def test_galvanised_fire_loop_medium_not_clean(self, findings):
        """The fire loop is an XM-001 control, NOT an MM-001 one.

        Stagnation corrosion and MIC in wet sprinkler systems is a documented
        failure mode. Medium here is correct behaviour.
        """
        for element_id in ("FIRE-P01", "FIRE-P02", "FIRE-P03", "FIRE-P04"):
            issue = findings[element_id]
            assert issue.band is RiskBand.MEDIUM, element_id
            assert issue.metadata["composite_score_exact"] == pytest.approx(0.4000)

    def test_copper_dhw_is_clean(self, findings):
        """Copper in 60 C domestic hot water must NOT be flagged.

        60 C storage is mandated by HSE HSG274 and required by MC-001. The
        kinetics guard is what keeps MM-001 from contradicting it.
        """
        for element_id in ("DHW-P01", "DHW-P03", "DHW-P04", "DHW-P06", "DHW-P08"):
            assert element_id not in findings, f"{element_id} should be Low"

    def test_carbon_steel_dhw_still_flagged(self, findings):
        """The guard must not silence genuinely bad pairings."""
        issue = findings["DHW-S05"]
        assert issue.band is RiskBand.MEDIUM
        assert issue.metadata["composite_score_exact"] == pytest.approx(0.5700)
        assert issue.metadata["kinetics_guard_applied"] is False

    def test_brass_dhw_still_flagged(self, findings):
        """Dezincification in hot water is a real finding, cell 0.45."""
        issue = findings["DHW-V02"]
        assert issue.band is RiskBand.MEDIUM
        assert issue.metadata["kinetics_guard_applied"] is False

    def test_chilled_water_clean(self, findings):
        """Both materials in a cold closed loop score Low."""
        assert "CHW-P01" not in findings
        assert "CHW-M06" not in findings


class TestKineticsGuard:
    """The guard caps temperature only, and only for benign pairings."""

    def test_guard_applies_below_threshold(self, rule_pack):
        """Copper/hot_water (cell 0.30) is guarded."""
        issue = compare([element(material="Copper_C12200")], rule_pack)
        assert issue == [] or issue[0].metadata.get("kinetics_guard_applied")

    def test_guard_changes_the_band(self, rule_pack):
        """Without the guard copper DHW would be Medium; with it, Low."""
        guarded = compare([element(material="Copper_C12200")], rule_pack)
        assert guarded == []

        unguarded_pack = json.loads(json.dumps(rule_pack))
        unguarded_pack["parameters"].pop("kinetics_guard")
        unguarded = compare([element(material="Copper_C12200")], unguarded_pack)
        assert len(unguarded) == 1
        assert unguarded[0].band is RiskBand.MEDIUM

    def test_guard_does_not_touch_environment(self, rule_pack):
        """A benign pairing in a severe environment is still exposed.

        The guard caps the temperature term only: environment severity is an
        external driver that does not depend on the material-media mechanism.
        """
        issue = compare(
            [
                element(
                    material="Copper_C12200",
                    system=PipingSystem.POOL_CIRCULATION,
                    environment_class=EnvironmentClass.T4_MARINE,
                    operating_temperature_c=28.0,
                )
            ],
            rule_pack,
        )
        assert len(issue) == 1
        assert issue[0].metadata["environment_severity"] == 1.00

    def test_guard_records_its_citation(self, rule_pack):
        """A guarded finding must show the guard in its audit trail."""
        pack = json.loads(json.dumps(rule_pack))
        pack["parameters"]["risk_band_thresholds"]["medium"] = 0.01
        issue = compare([element(material="Copper_C12200")], pack)[0]
        clauses = [c["clause"] for c in issue.citations]
        assert "kinetics_guard" in clauses


class TestDataQuality:
    """Unscoreable elements produce Issues, never silent passes."""

    def test_unclassified_environment_flagged(self, data_quality):
        """NOGEO-01 has UNCLASSIFIED environment and cannot be scored."""
        issue = data_quality["NOGEO-01"]
        assert issue.band is RiskBand.LOW
        assert issue.metadata["check"] == "environment_unclassified"

    def test_unknown_material_flagged(self, rule_pack):
        """An unidentified material yields data-quality, not a verdict."""
        issues = compare([element(material="Unknown")], rule_pack)
        assert len(issues) == 1
        assert issues[0].metadata["check"] == "material_normalisation"

    def test_unmapped_pairing_never_scored_benign(self, rule_pack):
        """An absent matrix cell must not be treated as compliant.

        Medical gas has no MM-001 cells. Reporting it clean would state that
        an unassessed pairing is compliant.
        """
        issues = compare(
            [element(material="Copper_C12200", system=PipingSystem.MEDICAL_GAS_OXYGEN)],
            rule_pack,
        )
        assert len(issues) == 1
        assert issues[0].metadata["check"] == "unmapped_pairing"
        assert issues[0].mechanism == "data_quality"

    def test_missing_temperature_flagged(self, rule_pack):
        """A missing temperature must not default to a fabricated value."""
        issues = compare([element(operating_temperature_c=None)], rule_pack)
        assert len(issues) == 1
        assert issues[0].metadata["check"] == "temperature_missing"

    def test_data_quality_never_masquerades_as_a_verdict(self, issues):
        """Data-quality Issues must be distinguishable from findings."""
        for issue in issues:
            if issue.metadata.get("check"):
                assert issue.mechanism == "data_quality"


class TestAuditTrail:
    """Every finding must be traceable to its sources."""

    def test_findings_carry_citations(self, findings):
        """Each term contributing to a score names its standard."""
        for issue in findings.values():
            assert len(issue.citations) >= 3, issue.element_id
            assert all(c["standard"] for c in issue.citations), issue.element_id

    def test_citations_name_the_governing_terms(self, findings):
        """Material, environment, and temperature must each be cited."""
        clauses = " ".join(c["clause"] for c in findings["POOL-P01"].citations)
        assert "SS316 / pool_water" in clauses
        assert "T3_chloride" in clauses
        assert "28.0 C" in clauses

    def test_description_matches_stored_score(self, findings):
        """Prose and Issue.score must not disagree.

        make_issue rounds to 3 dp for display; the description quotes the
        same rounded value so a reviewer never sees two composites.
        """
        for issue in findings.values():
            assert str(issue.score) in issue.description, issue.element_id

    def test_metadata_carries_exact_score(self, findings):
        """Banding used full precision, so audits need it unrounded."""
        for issue in findings.values():
            exact = issue.metadata["composite_score_exact"]
            assert round(exact, 3) == issue.score

    def test_titles_are_console_safe(self, issues):
        """Runtime strings must print on a cp1252 console."""
        for issue in issues:
            issue.title.encode("cp1252")
            (issue.description or "").encode("cp1252")
            issue.mitigation.encode("cp1252")


class TestOutputShape:
    """Structural guarantees for Module 5 and the UI."""

    def test_low_band_elements_produce_nothing(self, network, findings):
        """Compliant elements must not generate noise."""
        assert len(findings) < len(network)

    def test_issue_ids_unique(self, issues):
        """Issue ids must be unique within a run."""
        ids = [i.id for i in issues]
        assert len(ids) == len(set(ids))

    def test_every_issue_references_a_real_element(self, issues, network):
        """No Issue may point at an element that does not exist."""
        valid = {e.id for e in network}
        assert all(i.element_id in valid for i in issues)

    def test_empty_input_yields_no_issues(self, rule_pack):
        """An empty model is not an error."""
        assert compare([], rule_pack) == []


class TestRulesetProvenance:
    """A scored verdict must name the matrix revision it came from.

    GC-001 and CC-001 already stamped ``ruleset_version`` on every finding;
    MM-001 did not, so the 2026-09-06 audit could not trace an MM-001 verdict
    back to the pack that produced it.
    """

    def test_scored_findings_carry_the_ruleset_version(self, findings, rule_pack):
        """Every compliance finding names the pack, formatted like the engines'."""
        expected = ruleset_version(rule_pack)
        assert findings, "no scored findings to check"
        for issue in findings.values():
            assert issue.metadata.get("ruleset_version") == expected

    def test_version_is_built_from_the_pack(self, rule_pack):
        """The stamp tracks the file rather than a constant that drifts from it."""
        assert ruleset_version(rule_pack) == "BIMGUARD-MM-001 v1.0.0"

    def test_scored_findings_carry_the_mechanism_code(self, findings):
        """The reader keys engine grouping on this, as it does for GC/CC/MC."""
        assert all(i.metadata.get("mechanism_code") == "MM-001" for i in findings.values())

    def test_a_pack_without_identity_falls_back(self, rule_pack):
        """An unstamped finding is worse than one stamped with the default."""
        anonymous = {k: v for k, v in rule_pack.items() if k != "ruleset_id"}
        assert ruleset_version(anonymous) == DEFAULT_RULESET_VERSION

    def test_data_quality_notes_do_not_claim_a_version(self, data_quality):
        """A note means no cell was selected, so no revision produced it."""
        assert all("ruleset_version" not in i.metadata for i in data_quality.values())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
