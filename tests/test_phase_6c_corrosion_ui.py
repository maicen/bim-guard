"""Tests for Session C's corrosion wiring.

The centre of this file is the four-step ``data_quality`` rule from data
contracts §4.2 failure mode 5, and in particular **step 4** — that a
``data_quality`` Issue survives ``include_low=False``. Steps 1-3 are visible in
a diff; step 4 is one line in a filter, and without it the Issue created by
step 2 is deleted immediately and the fix is silently undone.

Do not "fix" a failure here by passing ``include_low=True``. That disables the
filter under test, and the assertion would then hold whether or not step 4
exists — the trap §4.2 names explicitly.

NO LIVE DATABASE. Elements are hand-built, so the band under test is the band
asserted, and nothing here touches Supabase or storage.

Run: uv run pytest tests/test_phase_6c_corrosion_ui.py -v
"""

from __future__ import annotations

import pytest

from app.modules.comparator.issue_schema import RiskBand
from app.modules.ifc_reader import piping_fixtures
from app.modules.ifc_reader.ifc_parser import ServiceElement
from app.modules.ifc_reader.piping_schema import CANONICAL_MATERIALS
from app.modules.phase_6.phase_6c_corrosion_ui import (
    BAND_RANK,
    DATA_QUALITY,
    ELEMENT_MECHANISMS,
    GALVANIC,
    MECHANISMS,
    MIC,
    NETWORK_MECHANISMS,
    XM_MATERIAL_TO_SERIES_KEY,
    issue_stats,
    normalise_band,
    resolve_engine_codes,
    resolve_mechanisms,
    run_corrosion_analysis,
    worst_band,
)

pytestmark = pytest.mark.slow


def service_element(
    guid: str = "GUID-01",
    name: str = "CHW-Supply-01",
    material_a: str = "stainless_316",
    material_b: str | None = "galvanised_steel",
) -> ServiceElement:
    """Build one MEP element by hand, so the input under test is explicit."""
    return ServiceElement(
        guid=guid,
        name=name,
        ifc_type="IfcPipeSegment",
        description="Pipework",
        material_a=material_a,
        material_b=material_b,
        location_tag="interior_conditioned",
        floor="Level 02",
        system="Chilled water",
        joint_type="JT-001",
        anode_area_m2=0.05,
        cathode_area_m2=0.50,
        position=(1.0, 2.0, 3.0),
        length_m=2.5,
    )


def parsed_ifc(
    elements: list[ServiceElement] | None = None,
    valid: bool = True,
    piping_elements: list | None = None,
) -> dict:
    """Build a minimal ParsedIFC envelope around ``elements``.

    ``piping_elements`` defaults to empty, matching a parse that did not ask
    for the piping view. The network mechanisms then have nothing to assess,
    which is what keeps the per-element assertions in this file about the
    per-element engines.
    """
    elements = [service_element()] if elements is None else elements
    return {
        "source_ref": "uploads/ifc/test.ifc",
        "source_sha256": "0" * 64,
        "schema": "IFC4",
        "schema_note": None,
        "elements": elements,
        "element_count": len(elements),
        "type_counts": {"IfcPipeSegment": len(elements)},
        "piping_elements": piping_elements or [],
        "quality": {
            "valid": valid,
            "error": None if valid else "The file could not be read as IFC.",
            "warnings": [],
            "improvements": [],
        },
    }


# ---------------------------------------------------------------------------
# Band normalisation — one point, and it raises
# ---------------------------------------------------------------------------


class TestNormaliseBand:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("Critical", RiskBand.CRITICAL),
            ("critical", RiskBand.CRITICAL),
            ("CRITICAL", RiskBand.CRITICAL),
            ("  High  ", RiskBand.HIGH),
            ("Medium", RiskBand.MEDIUM),
            ("Low", RiskBand.LOW),
        ],
    )
    def test_every_casing_resolves(self, raw, expected):
        assert normalise_band(raw, element="E", mechanism="GC-001") is expected

    @pytest.mark.parametrize("raw", ["", "Criticial", "severe", "none", "0"])
    def test_unknown_band_raises(self, raw):
        with pytest.raises(ValueError):
            normalise_band(raw, element="E", mechanism="GC-001")

    def test_error_names_element_and_mechanism(self):
        """A bare enum error says only that a value was invalid."""
        with pytest.raises(ValueError) as excinfo:
            normalise_band("Criticial", element="Riser-07", mechanism="CC-001")
        assert "Riser-07" in str(excinfo.value)
        assert "CC-001" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Step 4 — the assertion that proves the fix
# ---------------------------------------------------------------------------


@pytest.fixture
def galvanic_engine_fails(monkeypatch):
    """Make GC-001 raise, so an engine the pre-flight gate admits then fails.

    Distinct from ``mic_engine_fails``: MC-001 is now refused by
    :func:`_preflight` before ``_assess`` is entered, because ``_mic_element``
    supplies no hydraulics, so monkeypatching the MIC engine no longer reaches
    it. GC-001 is admitted for an element carrying a real material, which makes
    it the mechanism that can still exercise ``check="band_unassessed"`` — the
    "engine ran and returned nothing usable" path, as opposed to the gate's
    "we declined to run the engine".
    """
    def boom(_element):
        raise RuntimeError("engine unavailable")

    monkeypatch.setattr(
        "app.modules.phase_6.phase_6c_corrosion_ui.assess_galvanic_risk", boom
    )


@pytest.fixture
def mic_engine_fails(monkeypatch):
    """Make MC-001 raise, so exactly one mechanism cannot be assessed.

    The three engines score even a degenerate element — blank materials still
    produce a band — so the data_quality path cannot be reached by feeding bad
    input. It is defensive code for an engine that genuinely fails, and the
    honest way to test it is to make one fail.

    NOTE: since the pre-flight gate landed, MC-001 is refused before the engine
    is called, so this fixture's patch is not what produces the data_quality
    Issue for MC-001 any more — the gate does. Tests that need a *failed*
    engine rather than a *refused* one use ``galvanic_engine_fails``.
    """
    def boom(_element):
        raise RuntimeError("engine unavailable")

    monkeypatch.setattr(
        "app.modules.phase_6.phase_6c_corrosion_ui.assess_mic_risk", boom
    )


@pytest.fixture
def all_engines_fail(monkeypatch):
    """Make every mechanism raise, so an element yields only data_quality."""
    def boom(_element):
        raise RuntimeError("engine unavailable")

    for name in ("assess_galvanic_risk", "assess_crevice_risk", "assess_mic_risk"):
        monkeypatch.setattr(f"app.modules.phase_6.phase_6c_corrosion_ui.{name}", boom)


class TestDataQualitySurvivesIncludeLowFilter:
    """The one test that distinguishes a working fix from an invisible one."""

    def test_unassessed_mechanism_produces_a_data_quality_issue(self, mic_engine_fails):
        """An element the engine could not score must not vanish."""
        result = run_corrosion_analysis(parsed_ifc(), include_low=False)
        issues = result["audit_issues"]
        assert any(i.mechanism == DATA_QUALITY for i in issues), (
            "a mechanism that could not be assessed disappeared entirely under "
            "the default filter — failure mode 5 has reappeared"
        )

    def test_data_quality_is_low_band_by_doctrine(self, mic_engine_fails):
        """Which is exactly why the include_low exemption is needed."""
        result = run_corrosion_analysis(parsed_ifc(), include_low=False)
        dq = [i for i in result["audit_issues"] if i.mechanism == DATA_QUALITY]
        assert dq
        assert all(i.band is RiskBand.LOW for i in dq)

    def test_data_quality_count_is_identical_either_way(self, mic_engine_fails):
        """include_low must not change how many data_quality Issues appear."""
        strict = run_corrosion_analysis(parsed_ifc(), include_low=False)["audit_issues"]
        loose = run_corrosion_analysis(parsed_ifc(), include_low=True)["audit_issues"]
        assert sum(1 for i in strict if i.mechanism == DATA_QUALITY) == sum(
            1 for i in loose if i.mechanism == DATA_QUALITY
        )

    def test_the_other_mechanisms_still_report(self, mic_engine_fails):
        """One engine failing must not suppress the two that worked."""
        issues = run_corrosion_analysis(parsed_ifc(), include_low=True)["audit_issues"]
        assert [i for i in issues if i.mechanism != DATA_QUALITY]


# ---------------------------------------------------------------------------
# Steps 1-3 — never invent, report, make visible
# ---------------------------------------------------------------------------


class TestDataQualityShape:
    @pytest.fixture
    def dq_issue(self, galvanic_engine_fails):
        """Return the Issue raised when an engine ran and produced nothing usable.

        Selected by check rather than by position: the run now also emits the
        gate's ``hydraulics_unavailable`` Issue for MC-001, and taking
        ``issues[0]`` would silently start asserting the shape of whichever one
        happened to be allocated first.
        """
        result = run_corrosion_analysis(parsed_ifc(), include_low=False)
        issues = [
            i
            for i in result["audit_issues"]
            if i.mechanism == DATA_QUALITY and i.metadata.get("check") == "band_unassessed"
        ]
        assert issues, "expected a band_unassessed data_quality Issue"
        return issues[0]

    def test_mechanism_is_exactly_data_quality(self, dq_issue):
        """test_data_quality_never_masquerades_as_a_verdict asserts this pairing."""
        assert dq_issue.mechanism == DATA_QUALITY

    def test_carries_a_check_key(self, dq_issue):
        assert dq_issue.metadata["check"] == "band_unassessed"

    def test_names_the_mechanism_that_did_not_run(self, dq_issue):
        assert dq_issue.metadata["mechanism_code"] in {m.code for m in MECHANISMS}

    def test_is_assigned_to_the_bim_coordinator(self, dq_issue):
        """It is a data fix, not an engineering decision."""
        assert dq_issue.assignee_role == "BIM coordinator"

    def test_points_at_the_element(self, dq_issue):
        assert dq_issue.element_id == "GUID-01"

    def test_the_gate_uses_a_different_check(self, galvanic_engine_fails):
        """A refused engine and a failed engine must not look alike.

        Both are data_quality and both are Low, so ``check`` is the only thing
        telling a reviewer whether the engine was never asked or was asked and
        came back empty.
        """
        result = run_corrosion_analysis(parsed_ifc(), include_low=False)
        checks = {
            i.metadata.get("check")
            for i in result["audit_issues"]
            if i.mechanism == DATA_QUALITY
        }
        assert "band_unassessed" in checks
        assert "hydraulics_unavailable" in checks

    def test_rule_id_marks_it_as_a_data_reference(self, dq_issue):
        assert dq_issue.rule_id.endswith(".DATA")

    def test_no_band_is_invented(self, dq_issue):
        """Step 1: the Issue exists *because* no band was produced."""
        assert dq_issue.metadata.get("reason")


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------


class TestFindings:
    @pytest.fixture
    def result(self):
        return run_corrosion_analysis(parsed_ifc(), include_low=True)

    def test_issues_are_produced(self, result):
        assert result["audit_issues"]

    def test_every_issue_references_the_element_guid(self, result):
        """Contract rule 1: guid is the join key."""
        assert all(i.element_id == "GUID-01" for i in result["audit_issues"])

    def test_bands_are_riskband_members(self, result):
        assert all(isinstance(i.band, RiskBand) for i in result["audit_issues"])

    def test_band_values_are_lowercase(self, result):
        """Title-case exists only inside the render call."""
        assert all(i.band.value.islower() for i in result["audit_issues"])

    def test_findings_carry_real_citations(self, result):
        """Unlike Path A, the engine references are still in hand here."""
        findings = [i for i in result["audit_issues"] if i.mechanism != DATA_QUALITY]
        assert findings
        for issue in findings:
            assert issue.citations, f"{issue.rule_id} cited nothing"
            assert all(c["standard"] for c in issue.citations)
            assert all(c["reason"] for c in issue.citations)

    def test_citations_name_recognised_standards(self, result):
        findings = [i for i in result["audit_issues"] if i.mechanism != DATA_QUALITY]
        named = {c["standard"] for i in findings for c in i.citations}
        assert any("NASA" in s or "ISO" in s or "ASTM" in s or "BIMGUARD" in s for s in named)

    def test_issue_ids_are_unique(self, result):
        ids = [i.id for i in result["audit_issues"]]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Statistics and ranking
# ---------------------------------------------------------------------------


class TestStats:
    def test_data_quality_is_not_counted_as_a_finding(self, all_engines_fail):
        """Folding it into `low` would report unassessed as assessed-and-safe."""
        issues = run_corrosion_analysis(parsed_ifc())["audit_issues"]
        stats = issue_stats(issues)
        assert stats["data_quality"] > 0
        assert stats["total"] == 0, "data_quality must not inflate the finding count"

    def test_stats_keys_are_stable(self):
        stats = issue_stats([])
        assert set(stats) == {"total", "critical", "high", "medium", "low", "data_quality"}

    def test_empty_input_is_all_zero(self):
        assert issue_stats([]) == {
            "total": 0,
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "data_quality": 0,
        }


class TestWorstBand:
    def test_band_rank_orders_by_severity_not_alphabet(self):
        """max() over raw values returns 'medium'; BAND_RANK returns critical."""
        assert BAND_RANK[RiskBand.CRITICAL] > BAND_RANK[RiskBand.HIGH]
        assert BAND_RANK[RiskBand.HIGH] > BAND_RANK[RiskBand.MEDIUM]
        assert BAND_RANK[RiskBand.MEDIUM] > BAND_RANK[RiskBand.LOW]

    def test_none_when_there_are_no_findings(self):
        assert worst_band([]) is None

    def test_data_quality_alone_yields_no_worst_band(self, all_engines_fail):
        issues = run_corrosion_analysis(parsed_ifc())["audit_issues"]
        assert all(i.mechanism == DATA_QUALITY for i in issues)
        assert worst_band(issues) is None


# ---------------------------------------------------------------------------
# AnalysisResult fragment
# ---------------------------------------------------------------------------


class TestResultShape:
    def test_keys_match_the_analysis_result_contract(self):
        result = run_corrosion_analysis(parsed_ifc())
        assert set(result) == {
            "audit_issues",
            "issue_stats",
            "cost_impact",
            "compliance_error",
            "compliance_is_demo",
        }

    def test_invalid_model_surfaces_as_compliance_error(self):
        """Errors are values across the boundary, not exceptions."""
        result = run_corrosion_analysis(parsed_ifc(valid=False))
        assert result["compliance_error"]
        assert result["audit_issues"] == []

    def test_valid_model_has_no_error(self):
        assert run_corrosion_analysis(parsed_ifc())["compliance_error"] is None

    def test_output_is_never_flagged_demo(self):
        """Real engines ran; labelling it demo would be false."""
        assert run_corrosion_analysis(parsed_ifc())["compliance_is_demo"] is False

    def test_cost_impact_is_none_not_invented(self):
        """No cost model exists; fabricating figures would corrupt a report."""
        assert run_corrosion_analysis(parsed_ifc())["cost_impact"] is None

    def test_empty_model_produces_no_issues(self):
        assert run_corrosion_analysis(parsed_ifc([]))["audit_issues"] == []


# ---------------------------------------------------------------------------
# The network mechanisms — MM-001 and XM-001
# ---------------------------------------------------------------------------


class TestNetworkMechanisms:
    """MM-001 and XM-001 run over the piping network, not over one element.

    The fixture network is the same one tests/test_material_media.py and
    tests/test_cross_material.py score directly. Using it here asserts the
    wiring, not the engines: that a corrosion run reaches both comparators,
    hands them a network, and folds what they return into ``audit_issues``.
    """

    @pytest.fixture(scope="class")
    def network(self):
        return piping_fixtures.generate_synthetic_piping_network()

    def test_all_five_mechanisms_are_declared(self):
        assert [spec.code for spec in MECHANISMS] == [
            "GC-001",
            "CC-001",
            "MC-001",
            "MM-001",
            "XM-001",
        ]

    def test_the_two_halves_partition_the_whole(self):
        """Every mechanism runs exactly once, on exactly one of the two paths."""
        assert ELEMENT_MECHANISMS + NETWORK_MECHANISMS == MECHANISMS
        codes = [spec.code for spec in MECHANISMS]
        assert len(set(codes)) == len(codes)

    def test_both_network_mechanisms_produce_findings(self, network):
        """The live path reaches MM-001 and XM-001 and keeps what they say."""
        issues = run_corrosion_analysis(
            parsed_ifc([], piping_elements=network), include_low=True
        )["audit_issues"]
        # The comparators version their rule ids ("MM-001.01", "MM-001.DQ"),
        # so the assertion is on the ruleset each finding cites, not on a bare
        # code no rule actually carries.
        rulesets = {i.rule_id.split(".")[0] for i in issues}
        assert "MM-001" in rulesets
        assert "XM-001" in rulesets

    def test_findings_are_real_verdicts_not_data_quality(self, network):
        """A wiring that only ever emits data_quality would look like success."""
        issues = run_corrosion_analysis(
            parsed_ifc([], piping_elements=network), include_low=True
        )["audit_issues"]
        verdicts = [i for i in issues if i.mechanism != DATA_QUALITY]
        assert any(i.mechanism.startswith("MM-001") for i in verdicts)
        assert any(i.mechanism.startswith("XM-001") for i in verdicts)

    def test_ids_do_not_collide_across_mechanisms(self, network):
        """One run, one allocator — the collision IssueIdAllocator exists for."""
        issues = run_corrosion_analysis(
            parsed_ifc(piping_elements=network), include_low=True
        )["audit_issues"]
        ids = [i.id for i in issues]
        assert len(set(ids)) == len(ids)

    def test_low_band_findings_obey_include_low(self, network):
        """XM-001 reports every couple; the run's own filter still applies."""
        strict = run_corrosion_analysis(
            parsed_ifc([], piping_elements=network), include_low=False
        )["audit_issues"]
        assert not [
            i for i in strict if i.band is RiskBand.LOW and i.mechanism != DATA_QUALITY
        ]

    def test_data_quality_survives_the_filter(self, network):
        """Step 4, on the network path: an unassessed element is still reported."""
        strict = run_corrosion_analysis(
            parsed_ifc([], piping_elements=network), include_low=False
        )["audit_issues"]
        assert [i for i in strict if i.mechanism == DATA_QUALITY]

    def test_absent_piping_view_is_not_a_finding(self):
        """A caller that did not ask for the network has found no defect."""
        assert run_corrosion_analysis(parsed_ifc([]))["audit_issues"] == []


class TestGalvanicSeriesJoin:
    """XM-001 reads GC-001's series, so the two taxonomies must actually meet."""

    def test_every_mapped_material_is_canonical(self):
        """A key no PipingElement can carry would never be looked up."""
        assert set(XM_MATERIAL_TO_SERIES_KEY) <= CANONICAL_MATERIALS

    def test_non_metallics_are_absent(self):
        """Plastics have no galvanic potential; giving them one would be false."""
        for material in ("PVC", "HDPE", "PEX", "PPR", "Unknown"):
            assert material not in XM_MATERIAL_TO_SERIES_KEY

    def test_galvanised_steel_is_not_carbon_steel(self):
        """The substring fallback in resolve_material() conflates these two.

        ``"steel"`` is tested before ``"galvanised"``, so GalvanisedSteel
        resolves to carbon_steel and a galvanised-to-carbon junction scores as
        no couple at all. This table is explicit precisely to avoid that.
        """
        assert XM_MATERIAL_TO_SERIES_KEY["GalvanisedSteel"] == "galv_steel"
        assert XM_MATERIAL_TO_SERIES_KEY["CarbonSteel"] == "carbon_steel"


# ---------------------------------------------------------------------------
# Engine gating — an unselected engine is not run, not run-and-filtered
# ---------------------------------------------------------------------------


class TestResolveMechanisms:
    """The selection is resolved once, before any element is assessed."""

    def test_no_selection_runs_every_mechanism(self):
        assert resolve_mechanisms(None) == MECHANISMS

    @pytest.mark.parametrize("spelling", ["GC", "gc", "GC-001", "gc-001", "GC-001.01"])
    def test_prefix_code_and_rule_id_all_name_the_same_engine(self, spelling):
        """The checkbox sends "GC"; the rules table stores "GC-001.01"."""
        assert resolve_mechanisms([spelling]) == (GALVANIC,)

    def test_selection_order_follows_declaration_not_the_caller(self):
        """Two spellings of one selection must run the same engines in one order."""
        assert resolve_mechanisms(["MC", "GC"]) == resolve_mechanisms(["GC", "MC"])

    def test_empty_selection_runs_nothing(self):
        """An empty list is a request for nothing, not a request for everything."""
        assert resolve_mechanisms([]) == ()

    def test_blank_entries_are_not_a_selection(self):
        """A query string carrying one empty value still means "none"."""
        assert resolve_mechanisms([""]) == ()

    def test_unknown_code_selects_no_engine(self):
        assert resolve_mechanisms(["ZZ-999"]) == ()

    def test_engine_codes_are_the_codes_that_would_run(self):
        assert resolve_engine_codes(["cc"]) == ("CC-001",)
        assert resolve_engine_codes(None) == tuple(m.code for m in MECHANISMS)


class TestEngineGating:
    """Only the selected engines execute."""

    @pytest.fixture(scope="class")
    def network(self):
        """Build the piping network MM-001 and XM-001 need to report anything."""
        return piping_fixtures.generate_synthetic_piping_network()

    def test_unselected_engine_produces_no_issues(self):
        issues = run_corrosion_analysis(
            parsed_ifc(), include_low=True, engines=["CC", "MC"]
        )["audit_issues"]
        assert issues, "the two selected engines should still report"
        assert not [i for i in issues if i.rule_id.startswith("GC")]

    def test_selected_engine_still_reports(self):
        issues = run_corrosion_analysis(
            parsed_ifc(), include_low=True, engines=["GC"]
        )["audit_issues"]
        assert [i for i in issues if i.rule_id.startswith("GC")]

    def test_unselected_engine_is_never_called(self, monkeypatch):
        """The point of the gate: skipped work, not filtered output.

        Filtering afterwards would produce the same Issue list at full cost, so
        the assertion is on the call, not on the findings.
        """
        calls: list[str] = []

        def spy(_element):
            calls.append("gc")
            raise AssertionError("GC-001 ran despite being unselected")

        monkeypatch.setattr(
            "app.modules.phase_6.phase_6c_corrosion_ui.assess_galvanic_risk", spy
        )
        run_corrosion_analysis(parsed_ifc(), include_low=True, engines=["CC"])
        assert calls == []

    def test_no_selection_runs_all_five(self, network):
        """The default is unchanged: omitting engines assesses everything."""
        issues = run_corrosion_analysis(
            parsed_ifc(piping_elements=network), include_low=True
        )["audit_issues"]
        codes = {i.rule_id.split(".")[0] for i in issues}
        assert codes == {m.code for m in MECHANISMS}

    def test_a_network_mechanism_can_be_selected_alone(self, network):
        """MM-001 and XM-001 gate on the same selection as GC/CC/MC."""
        issues = run_corrosion_analysis(
            parsed_ifc(piping_elements=network), include_low=True, engines=["MM"]
        )["audit_issues"]
        codes = {i.rule_id.split(".")[0] for i in issues}
        assert codes == {"MM-001"}

    def test_an_unselected_network_mechanism_does_not_run(self, network):
        """Selecting only the per-element engines leaves the comparators alone."""
        issues = run_corrosion_analysis(
            parsed_ifc(piping_elements=network), include_low=True, engines=["GC"]
        )["audit_issues"]
        codes = {i.rule_id.split(".")[0] for i in issues}
        assert codes == {"GC-001"}

    def test_an_unselected_network_mechanism_is_never_called(self, network, monkeypatch):
        """Skipped, not filtered: the comparator is not entered at all."""
        def spy(*_args, **_kwargs):
            raise AssertionError("XM-001 ran despite being unselected")

        monkeypatch.setattr(
            "app.modules.comparator.cross_material.compare", spy
        )
        run_corrosion_analysis(
            parsed_ifc(piping_elements=network), include_low=True, engines=["MM"]
        )

    def test_empty_selection_assesses_nothing(self):
        result = run_corrosion_analysis(parsed_ifc(), include_low=True, engines=[])
        assert result["audit_issues"] == []
        assert result["compliance_error"] is None

    def test_gating_does_not_suppress_data_quality_for_a_selected_engine(
        self, mic_engine_fails
    ):
        """Step 4 still holds inside a narrowed run."""
        issues = run_corrosion_analysis(
            parsed_ifc(), include_low=False, engines=["MC"]
        )["audit_issues"]
        assert [i for i in issues if i.mechanism == DATA_QUALITY]

    def test_an_unselected_engine_raises_no_data_quality_issue(self, mic_engine_fails):
        """Not assessed by choice is not the same as could not be assessed."""
        issues = run_corrosion_analysis(
            parsed_ifc(), include_low=False, engines=["GC"]
        )["audit_issues"]
        assert not [
            i for i in issues if i.metadata.get("mechanism_code") == MIC.code
        ]

    def test_invalid_model_still_reports_its_error_under_a_selection(self):
        """The model check precedes the gate; a narrowed run cannot hide it."""
        result = run_corrosion_analysis(parsed_ifc(valid=False), engines=["GC"])
        assert result["compliance_error"]
