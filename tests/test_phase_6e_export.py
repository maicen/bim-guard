"""Tests for Session E's exporters.

The exporters consume ``AnalysisResult``, which is mechanism-agnostic, so these
tests use hand-built Issues carrying both a corrosion mechanism and a seismic
one. If a per-mechanism branch ever creeps in, the mixed-source tests fail.

The other thing under test is that ``data_quality`` entries survive the export
and stay distinguishable from verdicts — dropping them would restore the
invisibility §4.2 failure mode 5 describes.

Run: uv run pytest tests/test_phase_6e_export.py -v
"""

from __future__ import annotations

import csv
import io
import json
import zipfile

import pytest

from app.modules.comparator.issue_schema import RiskBand, make_issue
from app.modules.phase_6.phase_6e_export import (
    BAND_RANK,
    BAND_TO_BCF_PRIORITY,
    CSV_COLUMNS,
    DATA_QUALITY,
    export,
    sort_issues,
    to_bcf,
    to_csv,
    to_json,
)


def issue(
    id: str = "GC-0001",
    element_id: str = "GUID-01",
    mechanism: str = "GC-001 galvanic",
    band: RiskBand = RiskBand.HIGH,
    score: float = 0.71,
    metadata: dict | None = None,
    citations: list[dict] | None = None,
):
    """Build one Issue by hand."""
    return make_issue(
        id=id,
        element_id=element_id,
        rule_id="GC-001.01",
        title=f"{mechanism} on {element_id}",
        mechanism=mechanism,
        band=band,
        score=score,
        mitigation="Isolate dissimilar metals",
        assignee_role="Mechanical engineer",
        description="Assessed as high risk.",
        metadata=metadata if metadata is not None else {"ifc_type": "IfcPipeSegment"},
        citations=citations
        if citations is not None
        else [{"standard": "NASA-STD-6012", "clause": "Table 2", "reason": "threshold"}],
    )


def data_quality_issue(id: str = "MC-0009", element_id: str = "GUID-09"):
    """A non-verdict Issue, in the shape Sessions C and D emit."""
    return make_issue(
        id=id,
        element_id=element_id,
        rule_id="MC-001.DATA",
        title="MIC could not be evaluated",
        mechanism=DATA_QUALITY,
        band=RiskBand.LOW,
        score=0.10,
        mitigation="Review the IFC source.",
        assignee_role="BIM coordinator",
        metadata={"check": "band_unassessed", "mechanism_code": "MC-001"},
        citations=[],
    )


@pytest.fixture
def mixed_result() -> dict:
    """A result carrying corrosion findings, a seismic finding and data quality."""
    return {
        "audit_issues": [
            issue(id="GC-0001", band=RiskBand.MEDIUM),
            issue(id="CC-0002", mechanism="CC-001 crevice", band=RiskBand.CRITICAL),
            issue(id="SB-0003", mechanism="SB-001 seismic bracing", band=RiskBand.HIGH),
            data_quality_issue(),
        ],
        "issue_stats": {"total": 3, "critical": 1, "high": 1, "medium": 1, "low": 0, "data_quality": 1},
        "cost_impact": None,
        "compliance_error": None,
        "compliance_is_demo": False,
    }


@pytest.fixture
def empty_result() -> dict:
    return {
        "audit_issues": [],
        "issue_stats": {"total": 0, "critical": 0, "high": 0, "medium": 0, "low": 0, "data_quality": 0},
        "cost_impact": None,
        "compliance_error": None,
        "compliance_is_demo": False,
    }


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------


class TestSorting:
    def test_most_severe_first(self, mixed_result):
        ordered = sort_issues(mixed_result["audit_issues"])
        findings = [i for i in ordered if i.mechanism != DATA_QUALITY]
        assert [i.band for i in findings] == [RiskBand.CRITICAL, RiskBand.HIGH, RiskBand.MEDIUM]

    def test_data_quality_sorts_last(self, mixed_result):
        ordered = sort_issues(mixed_result["audit_issues"])
        assert ordered[-1].mechanism == DATA_QUALITY

    def test_rank_is_severity_not_alphabetical(self):
        assert BAND_RANK[RiskBand.CRITICAL] > BAND_RANK[RiskBand.HIGH] > BAND_RANK[RiskBand.MEDIUM] > BAND_RANK[RiskBand.LOW]

    def test_sorting_is_stable_for_equal_bands(self):
        issues = [issue(id="B", element_id="GUID-02"), issue(id="A", element_id="GUID-01")]
        assert [i.id for i in sort_issues(issues)] == ["A", "B"]


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


class TestCsv:
    def test_header_is_the_declared_column_order(self, mixed_result):
        first = to_csv(mixed_result).splitlines()[0]
        assert first.split(",") == list(CSV_COLUMNS)

    def test_empty_result_still_emits_a_header(self, empty_result):
        """So a consumer can tell 'no findings' from 'export failed'."""
        text = to_csv(empty_result)
        assert text.strip().splitlines() == [",".join(CSV_COLUMNS)]

    def test_one_row_per_issue(self, mixed_result):
        rows = list(csv.DictReader(io.StringIO(to_csv(mixed_result))))
        assert len(rows) == len(mixed_result["audit_issues"])

    def test_bands_are_lowercase_values(self, mixed_result):
        rows = list(csv.DictReader(io.StringIO(to_csv(mixed_result))))
        assert all(r["band"] == r["band"].lower() for r in rows)
        assert {r["band"] for r in rows} <= {"critical", "high", "medium", "low"}

    def test_data_quality_is_flagged_in_its_own_column(self, mixed_result):
        rows = list(csv.DictReader(io.StringIO(to_csv(mixed_result))))
        flagged = [r for r in rows if r["is_data_quality"] == "yes"]
        assert len(flagged) == 1
        assert flagged[0]["check"] == "band_unassessed"

    def test_standards_are_carried(self, mixed_result):
        rows = list(csv.DictReader(io.StringIO(to_csv(mixed_result))))
        findings = [r for r in rows if r["is_data_quality"] == "no"]
        assert all("NASA-STD-6012" in r["standards"] for r in findings)

    def test_seismic_and_corrosion_export_identically(self, mixed_result):
        """One exporter, no per-mechanism branch."""
        rows = list(csv.DictReader(io.StringIO(to_csv(mixed_result))))
        mechanisms = {r["mechanism"] for r in rows}
        assert any("GC-001" in m for m in mechanisms)
        assert any("SB-001" in m for m in mechanisms)

    def test_a_seismic_row_carries_the_clash_geometry(self):
        """The measurement a reviewer wants from an SB-001 row: by how much?"""
        seismic = issue(
            id="SB-0001",
            mechanism="SB-001 seismic bracing",
            metadata={"overlap_volume_mm3": 41250.0, "clearance_mm": 300.0},
        )
        rows = list(csv.DictReader(io.StringIO(to_csv({"audit_issues": [seismic]}))))
        assert rows[0]["overlap_volume_mm3"] == "41250.0"
        assert rows[0]["clearance_mm"] == "300.0"

    def test_a_corrosion_row_leaves_the_clash_columns_blank(self):
        """Blank, not 0: GC-001 did not measure an overlap of nothing."""
        rows = list(csv.DictReader(io.StringIO(to_csv({"audit_issues": [issue()]}))))
        assert rows[0]["overlap_volume_mm3"] == ""
        assert rows[0]["clearance_mm"] == ""

    def test_commas_in_text_do_not_break_columns(self):
        result = {"audit_issues": [issue(id="GC-0001")], "issue_stats": {}}
        result["audit_issues"][0].description = "One, two, three"
        rows = list(csv.DictReader(io.StringIO(to_csv(result))))
        assert rows[0]["description"] == "One, two, three"


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------


class TestJson:
    def test_is_valid_json(self, mixed_result):
        json.loads(to_json(mixed_result))

    def test_findings_and_data_quality_are_separate(self, mixed_result):
        payload = json.loads(to_json(mixed_result))
        assert len(payload["findings"]) == 3
        assert len(payload["data_quality"]) == 1

    def test_data_quality_never_appears_among_findings(self, mixed_result):
        payload = json.loads(to_json(mixed_result))
        assert all(f["mechanism"] != DATA_QUALITY for f in payload["findings"])

    def test_carries_stats_and_error_state(self, mixed_result):
        payload = json.loads(to_json(mixed_result))
        assert payload["issue_stats"]["critical"] == 1
        assert payload["compliance_error"] is None
        assert payload["compliance_is_demo"] is False

    def test_error_state_survives_export(self):
        """'No findings' and 'the analysis did not run' must stay distinct."""
        payload = json.loads(
            to_json({"audit_issues": [], "compliance_error": "IFC unreadable"})
        )
        assert payload["compliance_error"] == "IFC unreadable"
        assert payload["findings"] == []

    def test_bands_serialise_as_lowercase_strings(self, mixed_result):
        payload = json.loads(to_json(mixed_result))
        assert all(isinstance(f["band"], str) and f["band"].islower() for f in payload["findings"])

    def test_citations_are_carried(self, mixed_result):
        payload = json.loads(to_json(mixed_result))
        assert all(f["citations"] for f in payload["findings"])

    def test_empty_result_is_still_well_formed(self, empty_result):
        payload = json.loads(to_json(empty_result))
        assert payload["findings"] == []
        assert payload["data_quality"] == []


# ---------------------------------------------------------------------------
# BCF 2.1
# ---------------------------------------------------------------------------


class TestBcf:
    def test_output_is_a_zip(self, mixed_result):
        assert zipfile.is_zipfile(io.BytesIO(to_bcf(mixed_result)))

    def test_archive_declares_bcf_version(self, mixed_result):
        with zipfile.ZipFile(io.BytesIO(to_bcf(mixed_result))) as zf:
            assert "bcf.version" in zf.namelist()

    def test_one_markup_per_issue(self, mixed_result):
        with zipfile.ZipFile(io.BytesIO(to_bcf(mixed_result))) as zf:
            markups = [n for n in zf.namelist() if n.endswith("markup.bcf")]
        assert len(markups) == len(mixed_result["audit_issues"])

    def test_data_quality_is_included_by_default(self, mixed_result):
        """Excluding it would hide unassessed elements from coordination."""
        with zipfile.ZipFile(io.BytesIO(to_bcf(mixed_result))) as zf:
            blob = "".join(zf.read(n).decode("utf-8", "replace") for n in zf.namelist() if n.endswith("markup.bcf"))
        assert "data-quality" in blob

    def test_data_quality_can_be_excluded_explicitly(self, mixed_result):
        with zipfile.ZipFile(io.BytesIO(to_bcf(mixed_result, include_data_quality=False))) as zf:
            markups = [n for n in zf.namelist() if n.endswith("markup.bcf")]
        assert len(markups) == 3

    def test_priority_maps_from_band(self):
        assert BAND_TO_BCF_PRIORITY[RiskBand.CRITICAL] == "Critical"
        assert BAND_TO_BCF_PRIORITY[RiskBand.HIGH] == "Major"
        assert BAND_TO_BCF_PRIORITY[RiskBand.MEDIUM] == "Normal"
        assert BAND_TO_BCF_PRIORITY[RiskBand.LOW] == "Minor"

    def test_every_band_has_a_priority(self):
        assert set(BAND_TO_BCF_PRIORITY) == set(RiskBand)

    def test_data_quality_is_assigned_to_the_bim_coordinator(self, mixed_result):
        with zipfile.ZipFile(io.BytesIO(to_bcf(mixed_result))) as zf:
            blob = "".join(zf.read(n).decode("utf-8", "replace") for n in zf.namelist() if n.endswith("markup.bcf"))
        assert "BIM coordinator" in blob

    def test_empty_result_still_produces_a_valid_archive(self, empty_result):
        with zipfile.ZipFile(io.BytesIO(to_bcf(empty_result))) as zf:
            assert "bcf.version" in zf.namelist()


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


class TestExportDispatch:
    @pytest.mark.parametrize("fmt,extension", [("csv", "csv"), ("json", "json"), ("bcf", "bcf")])
    def test_supported_formats_render(self, mixed_result, fmt, extension):
        content, media_type, ext = export(mixed_result, fmt)
        assert isinstance(content, bytes) and content
        assert media_type
        assert ext == extension

    def test_format_is_case_insensitive(self, mixed_result):
        assert export(mixed_result, "CSV")[2] == "csv"

    @pytest.mark.parametrize("fmt", ["pdf", "", "xlsx", None])
    def test_unsupported_format_raises(self, mixed_result, fmt):
        with pytest.raises(ValueError):
            export(mixed_result, fmt)

    def test_error_names_the_supported_formats(self, mixed_result):
        with pytest.raises(ValueError) as excinfo:
            export(mixed_result, "pdf")
        assert "csv" in str(excinfo.value)


# ---------------------------------------------------------------------------
# BCF provenance — CreationAuthor and ruleset labels (god-mode audit, step 1)
# ---------------------------------------------------------------------------


def _markup_for(result: dict, finding_id: str) -> str:
    """Return the markup.bcf text of the topic exported from ``finding_id``."""
    from app.modules.reporter.bcf_generator import bcf_topic_guid

    folder = bcf_topic_guid(finding_id)
    with zipfile.ZipFile(io.BytesIO(to_bcf(result))) as zf:
        return zf.read(f"{folder}/markup.bcf").decode("utf-8")


class TestBCFCreationAuthor:
    """Every topic must name the engine that raised it, not a fixed string.

    Before this, all 4,321 topics across the 1917 and 1542 demo archives —
    seismic clashes included — claimed ``BIMGUARD AI - GC-001/CC-001 v1.0.0``.
    """

    def test_author_names_the_engine_and_its_ruleset_revision(self):
        result = {
            "audit_issues": [
                issue(id="MC-0001", metadata={"ruleset_version": "BIMGUARD-MC-001 v1.0.0"})
            ]
        }
        result["audit_issues"][0].rule_id = "MC-001.01"
        markup = _markup_for(result, "MC-0001")
        assert "<CreationAuthor>BIMGUARD AI MC-001 v1.0.0</CreationAuthor>" in markup

    def test_engine_without_a_ruleset_version_omits_the_revision(self):
        """XM-001 and SB-001 record no ruleset_version; inventing one is fabrication."""
        seismic = issue(id="SB-0001", mechanism="SB-001 seismic bracing", metadata={})
        seismic.rule_id = "SB-001.01"
        markup = _markup_for({"audit_issues": [seismic]}, "SB-0001")
        assert "<CreationAuthor>BIMGUARD AI SB-001</CreationAuthor>" in markup
        assert "GC-001/CC-001" not in markup

    def test_no_topic_claims_gc_cc_authorship_for_another_engine(self):
        mic = issue(id="MC-0002", mechanism="MC-001 microbiological", metadata={})
        mic.rule_id = "MC-001.01"
        markup = _markup_for({"audit_issues": [mic]}, "MC-0002")
        assert "GC-001" not in markup and "CC-001" not in markup

    def test_unshaped_rule_id_falls_back_to_the_generic_author(self):
        odd = issue(id="ZZ-0001")
        odd.rule_id = "not-a-rule-id"
        markup = _markup_for({"audit_issues": [odd]}, "ZZ-0001")
        assert "<CreationAuthor>BIMGUARD AI</CreationAuthor>" in markup


class TestBCFRulesetLabels:
    def test_engine_and_ruleset_are_labels_on_the_topic(self):
        result = {
            "audit_issues": [
                issue(id="GC-0007", metadata={"ruleset_version": "BIMGUARD-GC-001 v1.0.0"})
            ]
        }
        markup = _markup_for(result, "GC-0007")
        assert "<Labels>GC-001</Labels>" in markup
        assert "<Labels>ruleset:BIMGUARD-GC-001 v1.0.0</Labels>" in markup

    def test_data_quality_check_is_labelled_with_its_prefix(self):
        markup = _markup_for({"audit_issues": [data_quality_issue()]}, "MC-0009")
        assert "<Labels>check:band_unassessed</Labels>" in markup
        assert "<Labels>data-quality</Labels>" in markup

    def test_no_ruleset_label_when_the_finding_records_no_version(self):
        bare = issue(id="XM-0001", mechanism="XM-001 cross-material", metadata={})
        bare.rule_id = "XM-001.01"
        markup = _markup_for({"audit_issues": [bare]}, "XM-0001")
        assert "ruleset:" not in markup
        assert "<Labels>XM-001</Labels>" in markup
