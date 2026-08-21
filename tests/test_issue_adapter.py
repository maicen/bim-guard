"""
Tests for the Path A <-> Issue adapter (F4).

The adapter is the only module that knows both Module4 shapes, so F6's
orchestrator wiring leans on it entirely. These tests pin the contract
described in docs/integration_plan_mm_xm.md section 9 (assertions A1-A7)
before anything downstream depends on it.

Path A dicts here are built by the `path_a_row()` helper rather than by
running the engines, so a band under test is the band asserted. The key set
mirrors run_compliance_checks() exactly; if that function grows or renames a
key, `test_helper_matches_runner_contract` is the test that should fail first.

Run: uv run pytest tests/test_issue_adapter.py -v
"""

import pytest

from app.modules.module4_comparator.issue_adapter import (
    IssueIdAllocator,
    issues_from_path_a,
    path_a_view,
)
from app.modules.module4_comparator.issue_schema import Issue, RiskBand, make_issue

# Every key the adapter reads from a Path A dict, by mechanism. Kept here so a
# drift in run_compliance_checks() surfaces as one failing assertion rather
# than as silently absent metadata.
GALVANIC_KEYS = (
    "voltage_gap_V",
    "voltage_threshold",
    "pren_fail",
    "anodic_material",
    "material_a",
    "material_b",
)
CREVICE_KEYS = ("crevice_geometry", "cct_adequate", "joint_type")
MIC_KEYS = ("mic_flow_class", "mic_temperature_class", "mic_dead_leg_class")


def path_a_row(
    guid: str = "GUID-01",
    name: str = "Pipe-01",
    galvanic: str = "LOW",
    crevice: str = "LOW",
    mic: str = "LOW",
    **overrides,
) -> dict:
    """Build a dict shaped like one run_compliance_checks() result.

    Scores are fixed and distinct per mechanism so a projected score can be
    traced back to the mechanism it came from.
    """
    row = {
        # Identity
        "guid": guid,
        "name": name,
        "ifc_type": "IfcPipeSegment",
        "description": "",
        "floor": "L01",
        "system": "DOMESTICCOLDWATER",
        "position": (0.0, 0.0, 0.0),
        "length_m": 2.5,
        # Materials
        "material_a": "SS316",
        "material_b": "GalvanisedSteel",
        "anodic_material": "galv_steel",
        "environment": "internal_dry",
        "joint_type": "JT-004",
        # Galvanic
        "galvanic_score": 0.71,
        "galvanic_band": galvanic,
        "voltage_gap_V": 0.74,
        "voltage_threshold": 0.15,
        "pren_fail": True,
        # Crevice
        "crevice_score": 0.82,
        "crevice_band": crevice,
        "crevice_geometry": "tight",
        "cct_adequate": True,
        # MIC
        "mic_score": 0.23,
        "mic_band": mic,
        "mic_flow_class": "stagnant",
        "mic_temperature_class": "optimal",
        "mic_dead_leg_class": "none",
        # Overall
        "overall_score": 0.82,
        "overall_band": "HIGH",
        "dominant_mechanism": "crevice",
        "action": "BLOCK — BCF issued; lead engineer to confirm resolution",
        "mitigation": "Specify PTFE isolation sleeve + neoprene washer",
    }
    row.update(overrides)
    return row


@pytest.fixture
def allocator() -> IssueIdAllocator:
    """A fresh run-scoped id allocator."""
    return IssueIdAllocator("test-run")


def path_b_issue(
    element_id: str,
    rule_id: str,
    band: RiskBand,
    score: float,
    issue_id: str = "MM-0001",
) -> Issue:
    """Build an Issue of the shape MM-001 / XM-001 emit."""
    prefix = rule_id.split(".")[0]
    return make_issue(
        id=issue_id,
        element_id=element_id,
        rule_id=rule_id,
        title=f"{prefix} on {element_id}",
        mechanism=f"{prefix} path-b",
        band=band,
        score=score,
        mitigation="Substitute material or isolate.",
    )


def test_helper_matches_runner_contract():
    """path_a_row() carries every key the adapter's mechanism specs read.

    Guards the fixture itself: a test built on a dict missing the keys under
    test would pass by skipping the code path rather than by exercising it.
    """
    row = path_a_row()
    required = {
        "guid",
        "name",
        "mitigation",
        "action",
        "dominant_mechanism",
        "galvanic_band",
        "galvanic_score",
        "crevice_band",
        "crevice_score",
        "mic_band",
        "mic_score",
        *GALVANIC_KEYS,
        *CREVICE_KEYS,
        *MIC_KEYS,
    }
    assert required <= set(row), f"helper is missing {sorted(required - set(row))}"


# ---------------------------------------------------------------------------
# A1-A4 — issues_from_path_a()
# ---------------------------------------------------------------------------


class TestIssuesFromPathA:
    """One Issue per element per mechanism, not one per element."""

    def test_a1_two_mechanisms_yield_two_issues(self, allocator):
        """A1: galvanic MEDIUM + crevice HIGH is two findings, not one."""
        results = [path_a_row(galvanic="MEDIUM", crevice="HIGH", mic="LOW")]

        issues = issues_from_path_a(results, id_allocator=allocator)

        assert len(issues) == 2
        # Mechanism order is fixed: galvanic, crevice, MIC.
        assert [i.rule_id for i in issues] == ["GC-001.01", "CC-001.01"]
        assert [i.band for i in issues] == [RiskBand.MEDIUM, RiskBand.HIGH]
        # Both describe the same element; they must not have collapsed.
        assert {i.element_id for i in issues} == {"GUID-01"}
        assert issues[0].score == 0.71
        assert issues[1].score == 0.82

    def test_a1_issues_are_returned_in_input_order(self, allocator):
        """Element order is preserved across a multi-element run."""
        results = [
            path_a_row(guid="G-A", name="Pipe-A", galvanic="HIGH"),
            path_a_row(guid="G-B", name="Pipe-B", crevice="HIGH"),
        ]

        issues = issues_from_path_a(results, id_allocator=allocator)

        assert [i.element_id for i in issues] == ["G-A", "G-B"]

    def test_a2_all_low_yields_nothing_by_default(self, allocator):
        """A2: a compliant element produces no Issue, matching Path B."""
        results = [path_a_row(galvanic="LOW", crevice="LOW", mic="LOW")]

        assert issues_from_path_a(results, id_allocator=allocator) == []

    def test_a2_include_low_yields_all_three(self, allocator):
        """A2: include_low=True emits every mechanism that ran."""
        results = [path_a_row(galvanic="LOW", crevice="LOW", mic="LOW")]

        issues = issues_from_path_a(results, id_allocator=allocator, include_low=True)

        assert len(issues) == 3
        assert [i.rule_id for i in issues] == ["GC-001.01", "CC-001.01", "MC-001.01"]
        assert all(i.band is RiskBand.LOW for i in issues)

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("CRITICAL", RiskBand.CRITICAL),
            ("HIGH", RiskBand.HIGH),
            ("MEDIUM", RiskBand.MEDIUM),
            ("LOW", RiskBand.LOW),
        ],
    )
    def test_a3_band_round_trip(self, allocator, raw, expected):
        """A3: the runner's uppercase band coerces to RiskBand and back."""
        results = [path_a_row(galvanic=raw)]

        issue = issues_from_path_a(results, id_allocator=allocator, include_low=True)[0]

        assert issue.band is expected
        assert issue.band.value == raw.lower()

    def test_a3_unknown_band_raises_naming_the_element(self, allocator):
        """An unrecognised band is a loud failure, not a silent LOW."""
        results = [path_a_row(name="Pipe-99", galvanic="SEVERE")]

        with pytest.raises(ValueError) as exc:
            issues_from_path_a(results, id_allocator=allocator)

        message = str(exc.value)
        assert "SEVERE" in message
        assert "Pipe-99" in message
        assert "GC-001" in message

    def test_a4_citations_are_empty_with_an_explicit_marker(self, allocator):
        """A4: Path A has no citation data, so it claims none.

        Pins the honesty rule in integration_plan_mm_xm.md section 4.1 against
        a future 'helpful' hardcode of the sort compliance_orchestrator.py
        already carries.
        """
        results = [path_a_row(galvanic="HIGH", crevice="HIGH", mic="HIGH")]

        issues = issues_from_path_a(results, id_allocator=allocator)

        assert len(issues) == 3
        for issue in issues:
            assert issue.citations == []
            assert (
                issue.metadata["citations_unavailable"]
                == "path_a_runner_discards_engine_citations"
            )

    def test_a4_metadata_records_the_keys_consumed(self, allocator):
        """Every projected value is traceable to the key it came from."""
        results = [path_a_row(galvanic="HIGH", crevice="HIGH", mic="HIGH")]

        galvanic, crevice, mic = issues_from_path_a(results, id_allocator=allocator)

        assert galvanic.metadata["path"] == "A"
        assert set(GALVANIC_KEYS) <= set(galvanic.metadata["source_dict_keys"])
        assert set(CREVICE_KEYS) <= set(crevice.metadata["source_dict_keys"])
        assert set(MIC_KEYS) <= set(mic.metadata["source_dict_keys"])
        # The band and score keys are consumed too, and named as such.
        assert "galvanic_band" in galvanic.metadata["source_dict_keys"]
        assert "galvanic_score" in galvanic.metadata["source_dict_keys"]

    def test_a4_mechanism_metadata_is_lifted_verbatim(self, allocator):
        """Lifted values keep both their key and their sense.

        cct_adequate is True when cct_adequacy_score < 0.6 — the engine scores
        CCT as risk, so a low score means adequate. Copying the value under an
        inverted name would flip the meaning of every crevice finding.
        """
        results = [path_a_row(crevice="HIGH", cct_adequate=True)]

        issue = issues_from_path_a(results, id_allocator=allocator)[0]

        assert issue.metadata["cct_adequate"] is True
        assert "cct_inadequate" not in issue.metadata
        assert issue.metadata["crevice_geometry"] == "tight"
        assert issue.metadata["joint_type"] == "JT-004"

    def test_absent_mechanism_is_skipped(self, allocator):
        """A dict with no mic_band means MIC did not run for that element."""
        row = path_a_row(galvanic="HIGH", crevice="HIGH", mic="HIGH")
        del row["mic_band"]

        issues = issues_from_path_a([row], id_allocator=allocator)

        assert [i.rule_id for i in issues] == ["GC-001.01", "CC-001.01"]

    def test_common_fields_come_from_the_source_dict(self, allocator):
        """title, mitigation and description track the runner's own text."""
        results = [path_a_row(name="Riser-07", galvanic="HIGH")]

        issue = issues_from_path_a(results, id_allocator=allocator)[0]

        assert issue.title == "GC-001 on Riser-07"
        assert issue.mitigation == "Specify PTFE isolation sleeve + neoprene washer"
        assert issue.description.startswith("BLOCK")
        assert issue.element_id == "GUID-01"


# ---------------------------------------------------------------------------
# A7 — IssueIdAllocator
# ---------------------------------------------------------------------------


class TestIssueIdAllocator:
    """Ids must be unique per run: BCF keys one topic per id."""

    def test_a7_no_duplicates_across_mechanisms(self):
        """A7: MM and XM findings in one run never collide.

        The failure this replaces: material_media, cross_material and
        ComplianceOrchestrator each mint 'BGR-%04d' from a counter starting at
        zero, so any run combining two of them emits two BGR-0001.
        """
        allocator = IssueIdAllocator("run-1")

        ids = [allocator.next("MM") for _ in range(3)]
        ids += [allocator.next("XM") for _ in range(3)]
        ids += [allocator.next("GC") for _ in range(3)]

        assert len(set(ids)) == len(ids)
        assert ids[:3] == ["MM-0001", "MM-0002", "MM-0003"]
        assert ids[3:6] == ["XM-0001", "XM-0002", "XM-0003"]

    def test_a7_path_a_run_emits_unique_ids(self):
        """A whole Path A run is collision-free across elements."""
        allocator = IssueIdAllocator("run-2")
        results = [
            path_a_row(guid=f"G-{n}", name=f"Pipe-{n}", galvanic="HIGH", crevice="HIGH")
            for n in range(5)
        ]

        issues = issues_from_path_a(results, id_allocator=allocator)

        ids = [i.id for i in issues]
        assert len(ids) == 10
        assert len(set(ids)) == 10

    def test_id_format_is_prefix_and_four_digits(self):
        """Ids read 'GC-0001', not 'GC-001-0001'."""
        allocator = IssueIdAllocator("run-3")
        results = [path_a_row(galvanic="HIGH", crevice="HIGH", mic="HIGH")]

        issues = issues_from_path_a(results, id_allocator=allocator)

        assert [i.id for i in issues] == ["GC-0001", "CC-0001", "MC-0001"]

    def test_counters_are_independent_per_prefix(self):
        """Interleaving prefixes does not skip numbers in either sequence."""
        allocator = IssueIdAllocator("run-4")

        assert allocator.next("MM") == "MM-0001"
        assert allocator.next("XM") == "XM-0001"
        assert allocator.next("MM") == "MM-0002"
        assert allocator.next("XM") == "XM-0002"

    def test_run_id_is_retained(self):
        """The allocator carries the run it belongs to."""
        assert IssueIdAllocator("run-5").run_id == "run-5"


# ---------------------------------------------------------------------------
# A5-A6 — path_a_view()
# ---------------------------------------------------------------------------


class TestPathAView:
    """The dict spine survives the round trip intact."""

    def test_a5_every_input_key_is_preserved(self):
        """A5: the projection adds keys and removes none."""
        base = [path_a_row(guid="G-1"), path_a_row(guid="G-2", name="Pipe-02")]
        before = [set(row) for row in base]

        view = path_a_view([], base)

        for original_keys, row in zip(before, view):
            assert original_keys <= set(row), f"lost {sorted(original_keys - set(row))}"

    def test_a5_values_are_preserved_not_just_keys(self):
        """Existing values pass through untouched."""
        base = [path_a_row(guid="G-1", name="Pipe-01")]

        row = path_a_view([], base)[0]

        for key, value in base[0].items():
            assert row[key] == value

    def test_a5_base_results_are_not_mutated(self):
        """The caller's dicts are never written to."""
        base = [path_a_row(guid="G-1")]
        snapshot = dict(base[0])

        path_a_view([path_b_issue("G-1", "MM-001.SS316.chlorinated", RiskBand.HIGH, 0.7)], base)

        assert base[0] == snapshot
        assert "path_b_issues" not in base[0]

    def test_a6_row_count_never_shrinks(self):
        """A6: the spine is one row per element, findings or not."""
        base = [path_a_row(guid=f"G-{n}") for n in range(4)]

        view = path_a_view([], base)

        assert len(view) >= len(base)
        assert len(view) == 4

    def test_a6_compliant_elements_survive_the_merge(self):
        """A6: an element with no Issue keeps its row and reads as clean.

        This is the denominator: building the table from Issues alone would
        make 'no elements flagged' indistinguishable from 'nothing ran'.
        """
        base = [path_a_row(guid="G-FLAGGED"), path_a_row(guid="G-CLEAN")]
        issues = [path_b_issue("G-FLAGGED", "MM-001.SS316.chlorinated", RiskBand.HIGH, 0.7)]

        view = path_a_view(issues, base)

        clean = next(row for row in view if row["guid"] == "G-CLEAN")
        assert clean["path_b_issues"] == []
        assert clean["path_b_count"] == 0
        assert clean["path_b_band"] is None

    def test_path_b_fields_are_initialised_on_every_row(self):
        """The UI can read the new keys without guarding for absence."""
        view = path_a_view([], [path_a_row()])

        row = view[0]
        assert row["path_b_issues"] == []
        assert row["path_b_band"] is None
        assert row["path_b_count"] == 0
        assert row["mm_band"] is None
        assert row["mm_score"] == 0.0
        assert row["xm_band"] is None
        assert row["xm_score"] == 0.0

    def test_issues_merge_onto_the_matching_guid(self):
        """Findings land on their own element's row and nowhere else."""
        base = [path_a_row(guid="G-1"), path_a_row(guid="G-2")]
        issues = [
            path_b_issue("G-1", "MM-001.SS316.chlorinated", RiskBand.HIGH, 0.7, "MM-0001"),
            path_b_issue("G-1", "XM-001.galv.SS316", RiskBand.MEDIUM, 0.5, "XM-0001"),
            path_b_issue("G-2", "MM-001.CarbonSteel.potable", RiskBand.LOW, 0.2, "MM-0002"),
        ]

        view = path_a_view(issues, base)

        first = next(row for row in view if row["guid"] == "G-1")
        second = next(row for row in view if row["guid"] == "G-2")
        assert first["path_b_count"] == 2
        assert second["path_b_count"] == 1
        assert [i["id"] for i in first["path_b_issues"]] == ["MM-0001", "XM-0001"]

    def test_worst_band_wins_by_severity_not_alphabetically(self):
        """path_b_band is the worst band present.

        RiskBand values are lowercase strings, so a direct string comparison
        orders them critical < high < low < medium and would let a MEDIUM
        finding outrank a CRITICAL one.
        """
        base = [path_a_row(guid="G-1")]
        issues = [
            path_b_issue("G-1", "MM-001.a.b", RiskBand.MEDIUM, 0.5, "MM-0001"),
            path_b_issue("G-1", "XM-001.a.b", RiskBand.CRITICAL, 0.9, "XM-0001"),
            path_b_issue("G-1", "MM-001.c.d", RiskBand.LOW, 0.1, "MM-0002"),
        ]

        row = path_a_view(issues, base)[0]

        assert row["path_b_band"] == "critical"

    def test_mm_and_xm_are_tracked_separately(self):
        """Each pack reports its own worst finding."""
        base = [path_a_row(guid="G-1")]
        issues = [
            path_b_issue("G-1", "MM-001.a.b", RiskBand.HIGH, 0.7, "MM-0001"),
            path_b_issue("G-1", "MM-001.c.d", RiskBand.MEDIUM, 0.4, "MM-0002"),
            path_b_issue("G-1", "XM-001.a.b", RiskBand.CRITICAL, 0.9, "XM-0001"),
        ]

        row = path_a_view(issues, base)[0]

        assert (row["mm_band"], row["mm_score"]) == ("high", 0.7)
        assert (row["xm_band"], row["xm_score"]) == ("critical", 0.9)

    def test_data_quality_rule_ids_still_attribute_to_their_pack(self):
        """MM-001.DATA is an MM finding despite having no material segment."""
        base = [path_a_row(guid="G-1")]
        issues = [path_b_issue("G-1", "MM-001.DATA", RiskBand.MEDIUM, 0.5)]

        row = path_a_view(issues, base)[0]

        assert row["mm_band"] == "medium"
        assert row["xm_band"] is None

    def test_issues_are_projected_as_plain_dicts(self):
        """The UI receives serialisable rows, not dataclass instances."""
        base = [path_a_row(guid="G-1")]
        issues = [path_b_issue("G-1", "MM-001.a.b", RiskBand.HIGH, 0.7, "MM-0001")]

        projected = path_a_view(issues, base)[0]["path_b_issues"][0]

        assert isinstance(projected, dict)
        assert projected["id"] == "MM-0001"
        assert projected["band"] == "high"
        assert projected["element_id"] == "G-1"


class TestOrphanIssues:
    """An Issue whose element is absent from the spine still gets seen."""

    def test_orphan_is_appended_as_its_own_row(self):
        """An XM couple whose anode is not in base_results is not dropped."""
        base = [path_a_row(guid="G-1")]
        issues = [path_b_issue("GHOST", "XM-001.a.b", RiskBand.HIGH, 0.7, "XM-0001")]

        view = path_a_view(issues, base)

        assert len(view) == 2
        orphan = next(row for row in view if row["guid"] == "GHOST")
        assert orphan["path_b_only"] is True
        assert orphan["path_b_count"] == 1

    def test_orphan_row_carries_the_spine_keys_blanked(self):
        """The row is renderable: same keys as any other, values empty."""
        base = [path_a_row(guid="G-1")]
        issues = [path_b_issue("GHOST", "XM-001.a.b", RiskBand.HIGH, 0.7)]

        view = path_a_view(issues, base)

        orphan = next(row for row in view if row["guid"] == "GHOST")
        assert set(base[0]) <= set(orphan)
        assert orphan["name"] is None
        assert orphan["overall_band"] is None

    def test_multiple_orphans_for_one_element_share_a_row(self):
        """Two findings on the same absent element make one row, not two."""
        base = [path_a_row(guid="G-1")]
        issues = [
            path_b_issue("GHOST", "XM-001.a.b", RiskBand.MEDIUM, 0.5, "XM-0001"),
            path_b_issue("GHOST", "XM-001.c.d", RiskBand.HIGH, 0.6, "XM-0002"),
        ]

        view = path_a_view(issues, base)

        ghosts = [row for row in view if row["guid"] == "GHOST"]
        assert len(ghosts) == 1
        assert ghosts[0]["path_b_count"] == 2
        assert ghosts[0]["path_b_band"] == "high"

    def test_empty_spine_still_projects_orphans(self):
        """A run with no Path A results does not crash the projection."""
        issues = [path_b_issue("GHOST", "XM-001.a.b", RiskBand.HIGH, 0.7)]

        view = path_a_view(issues, [])

        assert len(view) == 1
        assert view[0]["guid"] == "GHOST"
        assert view[0]["path_b_only"] is True

    def test_no_issues_and_no_base_gives_no_rows(self):
        """The empty run is empty, not an error."""
        assert path_a_view([], []) == []


# ---------------------------------------------------------------------------
# Round trip
# ---------------------------------------------------------------------------


def test_path_a_issues_survive_projection_back_onto_their_own_spine():
    """Lifting Path A to Issues and projecting back keeps element identity.

    Path A Issues are not Path B findings, so they do not populate mm_/xm_;
    what this pins is that the guid join holds in both directions.
    """
    allocator = IssueIdAllocator("round-trip")
    base = [
        path_a_row(guid="G-1", name="Pipe-01", galvanic="HIGH"),
        path_a_row(guid="G-2", name="Pipe-02"),
    ]

    issues = issues_from_path_a(base, id_allocator=allocator)
    view = path_a_view(issues, base)

    assert len(view) == len(base)
    flagged = next(row for row in view if row["guid"] == "G-1")
    clean = next(row for row in view if row["guid"] == "G-2")
    assert flagged["path_b_count"] == 1
    assert flagged["path_b_band"] == "high"
    assert clean["path_b_count"] == 0
    assert flagged["mm_band"] is None
    assert flagged["xm_band"] is None
