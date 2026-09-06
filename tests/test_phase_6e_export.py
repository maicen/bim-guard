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
import re
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


class TestBCFTopicType:
    """A clash, a verdict and a data-quality note are different kinds of topic.

    Before this, all 4,321 topics in the demo archives were ``TopicType="Issue"``,
    so no coordination tool could filter the 2,937 seismic clashes apart from
    the corrosion verdicts, or either from the data-quality notes.
    """

    def test_seismic_finding_is_a_clash(self):
        seismic = issue(id="SB-0001", mechanism="SB-001 seismic bracing")
        seismic.rule_id = "SB-001.01"
        assert 'TopicType="Clash"' in _markup_for({"audit_issues": [seismic]}, "SB-0001")

    def test_data_quality_note_is_a_warning(self):
        markup = _markup_for({"audit_issues": [data_quality_issue()]}, "MC-0009")
        assert 'TopicType="Warning"' in markup

    def test_corrosion_verdict_stays_an_issue(self):
        assert 'TopicType="Issue"' in _markup_for({"audit_issues": [issue(id="GC-0001")]}, "GC-0001")

    def test_a_seismic_data_quality_note_is_a_warning_not_a_clash(self):
        """Data quality wins over the engine: nothing was measured to clash."""
        from app.modules.comparator.issue_schema import make_issue

        note = make_issue(
            id="SB-0009",
            element_id="GUID-09",
            rule_id="SB-001.DQ",
            title="Bracing could not be evaluated",
            mechanism=DATA_QUALITY,
            band=RiskBand.LOW,
            score=0.0,
            mitigation="Review the IFC source.",
            assignee_role="BIM coordinator",
            metadata={"check": "geometry_unavailable"},
            citations=[],
        )
        assert 'TopicType="Warning"' in _markup_for({"audit_issues": [note]}, "SB-0009")

    def test_every_emitted_type_is_declared_in_the_known_set(self):
        from app.modules.reporter.bcf_generator import TOPIC_TYPES

        seismic = issue(id="SB-0002", mechanism="SB-001 seismic bracing")
        seismic.rule_id = "SB-001.01"
        result = {"audit_issues": [issue(id="GC-0002"), seismic, data_quality_issue()]}
        with zipfile.ZipFile(io.BytesIO(to_bcf(result))) as zf:
            found = set()
            for name in zf.namelist():
                if name.endswith("markup.bcf"):
                    text = zf.read(name).decode("utf-8")
                    found.add(text.split('TopicType="', 1)[1].split('"', 1)[0])
        assert found == {"Issue", "Clash", "Warning"}
        assert found <= set(TOPIC_TYPES)


class TestBCFDueDateIsNotFabricated:
    """No source of truth carries a due date, so no topic may assert one.

    This previously emitted ``datetime.now()``, so all 4,321 topics in the demo
    archives claimed to be due on the day the archive was downloaded — a
    commitment a coordinator could schedule against, invented by the exporter.
    """

    def test_no_topic_carries_a_due_date(self, mixed_result):
        with zipfile.ZipFile(io.BytesIO(to_bcf(mixed_result))) as zf:
            for name in zf.namelist():
                if name.endswith("markup.bcf"):
                    assert "<DueDate>" not in zf.read(name).decode("utf-8")

    def test_the_topic_is_still_schema_valid_without_one(self):
        """DueDate is optional in markup.xsd; omitting it must not break order."""
        xmlschema = pytest.importorskip("xmlschema")
        from pathlib import Path

        schema = xmlschema.XMLSchema(
            Path(__file__).parent / "schemas" / "bcf21" / "markup.xsd"
        )
        markup = _markup_for({"audit_issues": [issue(id="GC-0001")]}, "GC-0001")
        assert not [str(e.reason or e) for e in schema.iter_errors(markup)]

    def test_assigned_to_survives_the_removal(self):
        """DueDate preceded AssignedTo in the sequence; AssignedTo must remain."""
        markup = _markup_for({"audit_issues": [issue(id="GC-0001")]}, "GC-0001")
        assert "<AssignedTo>Mechanical engineer</AssignedTo>" in markup


def _header(markup: str) -> str:
    """Return just the Markup/Header block.

    Scoped deliberately: ``<Date>`` also appears inside ``Comment``, so an
    assertion about the model's upload date has to look only at the Header.
    """
    return markup.split("<Header>", 1)[1].split("</Header>", 1)[0]


class TestBCFHeaderNamesTheRealModel:
    """Header/File must name the model the finding came from.

    Every topic in every archive previously named ``BIMGUARD_AI_Model.ifc``,
    a file that does not exist, while project 1542's 886 cross-model clashes
    already recorded both real filenames in their metadata.
    """

    def _seismic(self, source: str, clashing: str):
        from app.modules.comparator.issue_schema import make_issue

        return make_issue(
            id="SB-0001",
            element_id="GUID-01",
            rule_id="SB-001.01",
            title="Bracing clearance clash",
            mechanism="SB-001 seismic bracing",
            band=RiskBand.CRITICAL,
            score=0.9,
            mitigation="Relocate.",
            assignee_role="Mechanical engineer",
            metadata={"source_model": source, "clashing_source_model": clashing},
            citations=[],
        )

    def test_cross_model_clash_names_both_files(self):
        result = {
            "audit_issues": [self._seismic("plumb.ifc", "str.ifc")],
            "source_files": [
                {"filename": "plumb.ifc", "date": "2026-09-05T20:03:55+00:00"},
                {"filename": "str.ifc", "date": "2026-09-05T20:04:54+00:00"},
            ],
        }
        markup = _markup_for(result, "SB-0001")
        assert _header(markup).count("<Filename>") == 2
        assert "<Filename>plumb.ifc</Filename>" in markup
        assert "<Filename>str.ifc</Filename>" in markup
        assert "BIMGUARD_AI_Model.ifc" not in markup

    def test_intra_model_clash_names_one_file_not_two(self):
        result = {
            "audit_issues": [self._seismic("plumb.ifc", "plumb.ifc")],
            "source_files": [{"filename": "plumb.ifc", "date": "2026-09-05T20:03:55+00:00"}],
        }
        markup = _markup_for(result, "SB-0001")
        assert _header(markup).count("<Filename>") == 1

    def test_corrosion_finding_takes_the_projects_model(self):
        result = {
            "audit_issues": [issue(id="GC-0001")],
            "source_files": [
                {"filename": "test_hospital_mep_demo.ifc", "date": "2026-09-06T08:06:16+00:00"}
            ],
        }
        markup = _markup_for(result, "GC-0001")
        assert "<Filename>test_hospital_mep_demo.ifc</Filename>" in markup
        assert "<Date>2026-09-06T08:06:16+00:00</Date>" in markup

    def test_upload_date_is_omitted_when_unknown_rather_than_invented(self):
        result = {
            "audit_issues": [issue(id="GC-0001")],
            "source_files": [{"filename": "model.ifc", "date": ""}],
        }
        markup = _markup_for(result, "GC-0001")
        assert "<Filename>model.ifc</Filename>" in markup
        assert "<Date>" not in _header(markup)

    def test_multi_file_header_is_schema_valid(self):
        xmlschema = pytest.importorskip("xmlschema")
        from pathlib import Path

        schema = xmlschema.XMLSchema(
            Path(__file__).parent / "schemas" / "bcf21" / "markup.xsd"
        )
        result = {
            "audit_issues": [self._seismic("plumb.ifc", "str.ifc")],
            "source_files": [
                {"filename": "plumb.ifc", "date": "2026-09-05T20:03:55+00:00"},
                {"filename": "str.ifc", "date": "2026-09-05T20:04:54+00:00"},
            ],
        }
        markup = _markup_for(result, "SB-0001")
        assert not [str(e.reason or e) for e in schema.iter_errors(markup)]

    def test_caller_supplying_no_models_still_exports(self):
        """Harness scripts and pre-existing cached results omit source_files."""
        markup = _markup_for({"audit_issues": [issue(id="GC-0001")]}, "GC-0001")
        assert "<Filename>BIMGUARD_AI_Model.ifc</Filename>" in markup


def _description(markup: str) -> str:
    """Return the topic's Description, XML entities resolved."""
    raw = markup.split("<Description>", 1)[1].split("</Description>", 1)[0]
    return (
        raw.replace("&#10;", "\n")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&amp;", "&")
    )


class TestBCFStructuredDescription:
    """The Description is the only text a coordinator sees in Revit or Solibri.

    It previously read, in full, "MC-001 assessed this element as medium." — no
    element, no input, no threshold, no standard — so a topic could not be
    acted on without going back to the web UI.
    """

    def test_description_names_the_element_and_its_context(self):
        finding = issue(
            id="GC-0001",
            metadata={"ifc_type": "IfcValve", "system": "LTHW Heating", "floor": "Level 00"},
        )
        text = _description(_markup_for({"audit_issues": [finding]}, "GC-0001"))
        assert "ELEMENT" in text
        assert "Type: IfcValve" in text
        assert "GUID: GUID-01" in text
        assert "System: LTHW Heating" in text
        assert "Floor: Level 00" in text

    def test_description_carries_input_provenance(self):
        finding = issue(
            id="GC-0002",
            metadata={
                "material_source": "ifc_metadata",
                "material_confidence": "high",
                "environment_source": "inferred from spatial names",
                "galvanic_couple": "bimetallic_pair_from_model",
            },
        )
        text = _description(_markup_for({"audit_issues": [finding]}, "GC-0002"))
        assert "Material source: ifc_metadata" in text
        assert "Material confidence: high" in text
        assert "Environment source: inferred from spatial names" in text
        assert "Galvanic couple basis: bimetallic_pair_from_model" in text

    def test_description_states_band_score_and_ruleset(self):
        finding = issue(id="CC-0003", metadata={"ruleset_version": "BIMGUARD-CC-001 v1.0.0"})
        text = _description(_markup_for({"audit_issues": [finding]}, "CC-0003"))
        assert "Band: high" in text
        assert "Score: 0.71" in text
        assert "Ruleset: BIMGUARD-CC-001 v1.0.0" in text

    def test_description_traces_each_standard_to_its_clause(self):
        finding = issue(
            id="GC-0004",
            citations=[
                {"standard": "NASA-STD-6012", "clause": "Table 2", "reason": "gap 0.27V"},
                {"standard": "EN ISO 15329", "clause": "T1", "reason": "severity 0.2"},
            ],
        )
        text = _description(_markup_for({"audit_issues": [finding]}, "GC-0004"))
        assert "STANDARDS" in text
        assert "NASA-STD-6012 — Table 2: gap 0.27V" in text
        assert "EN ISO 15329 — T1: severity 0.2" in text

    def test_seismic_description_carries_the_clash_geometry_and_both_models(self):
        from app.modules.comparator.issue_schema import make_issue

        clash = make_issue(
            id="SB-0001",
            element_id="GUID-A",
            rule_id="SB-001.01",
            title="Bracing clearance clash",
            mechanism="SB-001 seismic bracing",
            band=RiskBand.CRITICAL,
            score=0.9,
            mitigation="Relocate.",
            assignee_role="Mechanical engineer",
            metadata={
                "clashing_element_id": "GUID-B",
                "clashing_element_class": "IfcBeam",
                "overlap_volume_mm3": 131822370.75,
                "clearance_mm": 200.0,
                "source_model": "plumb.ifc",
                "clashing_source_model": "str.ifc",
                "jurisdiction": "EN 1998-1:2020 + DIN 4149:2022",
            },
            citations=[],
        )
        text = _description(_markup_for({"audit_issues": [clash]}, "SB-0001"))
        assert "CLASH GEOMETRY" in text
        assert "Clashing element: GUID-B" in text
        assert "Overlap volume: 131,822,370.8 mm" in text
        assert "Required clearance: 200 mm" in text
        assert "Source model: plumb.ifc" in text
        assert "Clashing source model: str.ifc" in text
        assert "Jurisdiction: EN 1998-1:2020 + DIN 4149:2022" in text

    def test_absent_values_produce_no_line_rather_than_an_empty_one(self):
        """An empty 'Material: ' asserts an empty material; silence asserts nothing."""
        finding = issue(id="GC-0005", metadata={"ifc_type": "IfcPipeSegment"})
        text = _description(_markup_for({"audit_issues": [finding]}, "GC-0005"))
        assert "Material source:" not in text
        assert "System:" not in text
        assert "Floor:" not in text
        assert "CLASH GEOMETRY" not in text

    def test_corrosion_finding_has_no_clash_section(self):
        text = _description(_markup_for({"audit_issues": [issue(id="GC-0006")]}, "GC-0006"))
        assert "CLASH GEOMETRY" not in text

    def test_data_quality_note_states_the_failed_check(self):
        text = _description(_markup_for({"audit_issues": [data_quality_issue()]}, "MC-0009"))
        assert "Check: band_unassessed" in text

    def test_description_stays_schema_valid(self):
        xmlschema = pytest.importorskip("xmlschema")
        from pathlib import Path

        schema = xmlschema.XMLSchema(
            Path(__file__).parent / "schemas" / "bcf21" / "markup.xsd"
        )
        markup = _markup_for({"audit_issues": [issue(id="GC-0001")]}, "GC-0001")
        assert not [str(e.reason or e) for e in schema.iter_errors(markup)]


class TestBCFDocumentReferences:
    """Each standard the finding was assessed against becomes a structured reference.

    Before this, the standards appeared only inside prose, so no tool could
    filter or list the normative references behind a topic.
    """

    def test_one_reference_per_cited_standard(self):
        finding = issue(
            id="GC-0001",
            citations=[
                {"standard": "NASA-STD-6012", "clause": "Table 2", "reason": "gap"},
                {"standard": "EN ISO 15329", "clause": "T1", "reason": "severity"},
            ],
        )
        markup = _markup_for({"audit_issues": [finding]}, "GC-0001")
        assert markup.count("<DocumentReference ") == 2

    def test_reference_names_the_standard_and_the_clause_applied(self):
        finding = issue(
            id="GC-0002",
            citations=[{"standard": "NASA-STD-6012", "clause": "Table 2", "reason": "gap"}],
        )
        markup = _markup_for({"audit_issues": [finding]}, "GC-0002")
        assert "<Description>NASA-STD-6012 — Table 2</Description>" in markup

    def test_standard_is_named_as_the_constants_catalogue_spells_it(self):
        """Citations say 'EN ISO 15329'; NOTEBOOK_STANDARDS says 'EN ISO 15329:2007'."""
        finding = issue(
            id="CC-0003",
            citations=[{"standard": "EN ISO 15329", "clause": "T2", "reason": "wetting"}],
        )
        markup = _markup_for({"audit_issues": [finding]}, "CC-0003")
        assert "<Description>EN ISO 15329:2007 — T2</Description>" in markup

    def test_no_referenced_document_is_invented(self):
        """No URL or DOI exists for these standards, so none may be emitted."""
        finding = issue(
            id="GC-0004",
            citations=[{"standard": "NASA-STD-6012", "clause": "Table 2", "reason": "gap"}],
        )
        markup = _markup_for({"audit_issues": [finding]}, "GC-0004")
        assert "<ReferencedDocument>" not in markup
        assert 'isExternal="false"' in markup

    def test_duplicate_citations_collapse_to_one_reference(self):
        finding = issue(
            id="SB-0005",
            citations=[
                {"standard": "EN 1998-1", "clause": "bracing clearance", "reason": "200mm"},
                {"standard": "EN 1998-1", "clause": "bracing clearance", "reason": "200mm"},
            ],
        )
        markup = _markup_for({"audit_issues": [finding]}, "SB-0005")
        assert markup.count("<DocumentReference ") == 1

    def test_finding_without_citations_emits_no_reference(self):
        finding = issue(id="GC-0006", citations=[])
        markup = _markup_for({"audit_issues": [finding]}, "GC-0006")
        assert "<DocumentReference" not in markup

    def test_reference_guid_is_stable_across_exports(self):
        finding = issue(
            id="GC-0007",
            citations=[{"standard": "NASA-STD-6012", "clause": "Table 2", "reason": "gap"}],
        )
        first = _markup_for({"audit_issues": [finding]}, "GC-0007")
        second = _markup_for({"audit_issues": [finding]}, "GC-0007")
        guid_of = lambda m: m.split('<DocumentReference Guid="', 1)[1].split('"', 1)[0]
        assert guid_of(first) == guid_of(second)

    def test_document_references_are_schema_valid(self):
        xmlschema = pytest.importorskip("xmlschema")
        from pathlib import Path

        schema = xmlschema.XMLSchema(
            Path(__file__).parent / "schemas" / "bcf21" / "markup.xsd"
        )
        finding = issue(
            id="GC-0008",
            citations=[
                {"standard": "NASA-STD-6012", "clause": "Table 2", "reason": "gap"},
                {"standard": "EN ISO 15329", "clause": "T1", "reason": "severity"},
            ],
        )
        markup = _markup_for({"audit_issues": [finding]}, "GC-0008")
        assert not [str(e.reason or e) for e in schema.iter_errors(markup)]


class TestBCFBimSnippet:
    """The machine-readable finding travels inside the topic folder."""

    def _archive(self, result):
        return zipfile.ZipFile(io.BytesIO(to_bcf(result)))

    def test_topic_folder_carries_the_finding_as_json(self):
        from app.modules.reporter.bcf_generator import bcf_topic_guid

        folder = bcf_topic_guid("GC-0001")
        with self._archive({"audit_issues": [issue(id="GC-0001")]}) as z:
            payload = json.loads(z.read(f"{folder}/finding.json").decode("utf-8"))
        assert payload["id"] == "GC-0001"
        assert payload["element_id"] == "GUID-01"
        assert payload["rule_id"] == "GC-001.01"
        assert payload["band"] == "high"

    def test_snippet_is_declared_on_the_topic(self):
        markup = _markup_for({"audit_issues": [issue(id="GC-0001")]}, "GC-0001")
        assert '<BimSnippet SnippetType="JSON" isExternal="false">' in markup
        assert "<Reference>finding.json</Reference>" in markup

    def test_snippet_precedes_document_references_in_the_sequence(self):
        """markup.xsd orders Topic as ... Description, BimSnippet, DocumentReference."""
        markup = _markup_for({"audit_issues": [issue(id="GC-0001")]}, "GC-0001")
        assert markup.index("<BimSnippet") < markup.index("<DocumentReference")

    def test_snippet_matches_the_json_export_for_the_same_finding(self):
        """One record, two containers: the archive must not carry a different truth."""
        from app.modules.reporter.bcf_generator import bcf_topic_guid

        result = {"audit_issues": [issue(id="GC-0001")]}
        exported = json.loads(to_json(result))["findings"][0]
        with self._archive(result) as z:
            snippet = json.loads(
                z.read(f"{bcf_topic_guid('GC-0001')}/finding.json").decode("utf-8")
            )
        assert snippet == exported

    def test_archive_stays_schema_valid_with_a_snippet(self):
        xmlschema = pytest.importorskip("xmlschema")
        from pathlib import Path

        schema = xmlschema.XMLSchema(
            Path(__file__).parent / "schemas" / "bcf21" / "markup.xsd"
        )
        markup = _markup_for({"audit_issues": [issue(id="GC-0001")]}, "GC-0001")
        assert not [str(e.reason or e) for e in schema.iter_errors(markup)]


class TestBCFExtensionsSchema:
    """project.bcfp has always declared extensions.xsd; it was never written."""

    def test_extensions_xsd_is_present_in_the_archive(self, mixed_result):
        with zipfile.ZipFile(io.BytesIO(to_bcf(mixed_result))) as z:
            assert "extensions.xsd" in z.namelist()

    def test_declared_schema_name_matches_the_file_written(self, mixed_result):
        with zipfile.ZipFile(io.BytesIO(to_bcf(mixed_result))) as z:
            bcfp = z.read("project.bcfp").decode("utf-8")
            declared = bcfp.split("<ExtensionSchema>", 1)[1].split("</ExtensionSchema>", 1)[0]
            assert declared in z.namelist()

    def test_extensions_is_well_formed_xml_schema(self, mixed_result):
        xmlschema = pytest.importorskip("xmlschema")
        with zipfile.ZipFile(io.BytesIO(to_bcf(mixed_result))) as z:
            text = z.read("extensions.xsd").decode("utf-8")
        xmlschema.XMLSchema(io.StringIO(text))  # raises if the schema is invalid

    def test_it_enumerates_exactly_the_topic_types_emitted(self, mixed_result):
        with zipfile.ZipFile(io.BytesIO(to_bcf(mixed_result))) as z:
            text = z.read("extensions.xsd").decode("utf-8")
            emitted = set()
            for name in z.namelist():
                if name.endswith("markup.bcf"):
                    markup = z.read(name).decode("utf-8")
                    emitted.add(markup.split('TopicType="', 1)[1].split('"', 1)[0])
        block = text.split('name="TopicType"', 1)[1].split("</xs:simpleType>", 1)[0]
        declared = set(re.findall(r'<xs:enumeration value="([^"]*)"/>', block))
        assert declared == emitted

    def test_it_declares_the_snippet_type_actually_used(self, mixed_result):
        with zipfile.ZipFile(io.BytesIO(to_bcf(mixed_result))) as z:
            text = z.read("extensions.xsd").decode("utf-8")
        block = text.split('name="SnippetType"', 1)[1].split("</xs:simpleType>", 1)[0]
        assert '<xs:enumeration value="JSON"/>' in block

    def test_stage_is_declared_with_no_values_because_none_are_published(self, mixed_result):
        with zipfile.ZipFile(io.BytesIO(to_bcf(mixed_result))) as z:
            text = z.read("extensions.xsd").decode("utf-8")
        block = text.split('name="Stage"', 1)[1].split("</xs:simpleType>", 1)[0]
        assert "<xs:enumeration" not in block

    def test_every_emitted_label_is_declared(self, mixed_result):
        with zipfile.ZipFile(io.BytesIO(to_bcf(mixed_result))) as z:
            text = z.read("extensions.xsd").decode("utf-8")
            emitted = set()
            for name in z.namelist():
                if name.endswith("markup.bcf"):
                    emitted.update(
                        re.findall(r"<Labels>([^<]*)</Labels>", z.read(name).decode("utf-8"))
                    )
        block = text.split('name="TopicLabel"', 1)[1].split("</xs:simpleType>", 1)[0]
        declared = set(re.findall(r'<xs:enumeration value="([^"]*)"/>', block))
        assert emitted <= declared


class TestBCFTitleConvention:
    """Titles follow {DOMAIN}-{ENGINE}-{FLOOR}-{seq} so an archive sorts usefully.

    Seismic titles previously read "Seismic bracing clearance clash on 19FnYm9E"
    — one element, GUID truncated to eight characters — so the topic did not
    say what clashed with what.
    """

    def _title(self, markup: str) -> str:
        return markup.split("<Title>", 1)[1].split("</Title>", 1)[0]

    def test_corrosion_title_carries_domain_engine_floor_and_sequence(self):
        finding = issue(id="GC-0001", metadata={"floor": "Level 03 Roof"})
        title = self._title(_markup_for({"audit_issues": [finding]}, "GC-0001"))
        assert title.startswith("PIP-GC-L03-0001 ")

    def test_basement_level_is_numbered_not_named(self):
        finding = issue(id="MC-0001", metadata={"floor": "Level 00 Basement"})
        finding.rule_id = "MC-001.01"
        title = self._title(_markup_for({"audit_issues": [finding]}, "MC-0001"))
        assert title.startswith("PIP-MC-L00-0001 ")

    def test_seismic_title_uses_the_seismic_domain_and_names_both_elements(self):
        from app.modules.comparator.issue_schema import make_issue

        clash = make_issue(
            id="SB-0001",
            element_id="GUID-A",
            rule_id="SB-001.01",
            title="Seismic bracing clearance clash on GUID-A",
            mechanism="SB-001 seismic bracing",
            band=RiskBand.CRITICAL,
            score=0.9,
            mitigation="Relocate.",
            assignee_role="Mechanical engineer",
            metadata={"clashing_element_id": "GUID-B"},
            citations=[],
        )
        title = self._title(_markup_for({"audit_issues": [clash]}, "SB-0001"))
        assert title == "SEI-SB-NA-0001 Bracing clearance clash GUID-A vs GUID-B"

    def test_absent_floor_is_marked_not_invented(self):
        """Every SB-001 finding on 1542 has an empty floor; L00 would be a guess."""
        finding = issue(id="XM-0001", metadata={})
        finding.rule_id = "XM-001.01"
        title = self._title(_markup_for({"audit_issues": [finding]}, "XM-0001"))
        assert title.startswith("PIP-XM-NA-0001 ")

    def test_floor_without_a_level_number_uses_its_name(self):
        finding = issue(id="GC-0002", metadata={"floor": "Roof"})
        title = self._title(_markup_for({"audit_issues": [finding]}, "GC-0002"))
        assert title.startswith("PIP-GC-ROOF-0001 ")

    def test_sequence_is_stable_across_two_exports_of_one_result(self):
        result = {
            "audit_issues": [
                issue(id="GC-0001", band=RiskBand.MEDIUM),
                issue(id="CC-0002", mechanism="CC-001 crevice", band=RiskBand.CRITICAL),
            ]
        }
        first = self._title(_markup_for(result, "GC-0001"))
        second = self._title(_markup_for(result, "GC-0001"))
        assert first == second

    def test_sequence_is_unique_within_an_archive(self, mixed_result):
        with zipfile.ZipFile(io.BytesIO(to_bcf(mixed_result))) as z:
            seqs = []
            for name in z.namelist():
                if name.endswith("markup.bcf"):
                    title = z.read(name).decode("utf-8").split("<Title>", 1)[1]
                    seqs.append(title.split(" ", 1)[0].rsplit("-", 1)[-1])
        assert len(seqs) == len(set(seqs))

    def test_unrecognisable_engine_keeps_its_own_title(self):
        odd = issue(id="ZZ-0001")
        odd.rule_id = "not-a-rule-id"
        title = self._title(_markup_for({"audit_issues": [odd]}, "ZZ-0001"))
        assert title == odd.title


def _viewpoint_for(result: dict, finding_id: str) -> str:
    """Return the viewpoint.bcfv text of the topic exported from ``finding_id``."""
    from app.modules.reporter.bcf_generator import bcf_topic_guid

    folder = bcf_topic_guid(finding_id)
    with zipfile.ZipFile(io.BytesIO(to_bcf(result))) as zf:
        return zf.read(f"{folder}/viewpoint.bcfv").decode("utf-8")


class TestBCFViewpointTruthfulness:
    """The viewpoint must colour by band and must not invent a camera."""

    def test_band_colour_is_applied_not_the_grey_fallback(self):
        """Regression: the colour table was keyed upper-case, Issue.band is lower.

        Every lookup missed, so all 4,321 topics across the 1917 and 1542
        archives were coloured FF888888.
        """
        for band, colour in (
            (RiskBand.CRITICAL, "FFC00000"),
            (RiskBand.HIGH, "FFC05000"),
            (RiskBand.MEDIUM, "FFFF8C00"),
            (RiskBand.LOW, "FF107C10"),
        ):
            finding = issue(id=f"GC-{band.value}", band=band)
            viewpoint = _viewpoint_for({"audit_issues": [finding]}, f"GC-{band.value}")
            assert f'<Color Color="{colour}">' in viewpoint, band

    def test_no_topic_is_coloured_the_unknown_fallback(self, mixed_result):
        with zipfile.ZipFile(io.BytesIO(to_bcf(mixed_result))) as z:
            for name in z.namelist():
                if name.endswith("viewpoint.bcfv"):
                    assert "FF888888" not in z.read(name).decode("utf-8")

    def test_no_camera_is_written_when_no_position_is_known(self):
        """A constant camera on every topic is a fabricated viewpoint."""
        viewpoint = _viewpoint_for({"audit_issues": [issue(id="GC-0001")]}, "GC-0001")
        assert "<PerspectiveCamera>" not in viewpoint

    def test_a_caller_supplying_real_coordinates_still_gets_a_camera(self):
        from app.modules.reporter.bcf_generator import generate_bcf

        from tests.test_bcf_generator import create_test_bcf_issue

        archive = generate_bcf([create_test_bcf_issue()])
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            name = [n for n in z.namelist() if n.endswith("viewpoint.bcfv")][0]
            assert "<PerspectiveCamera>" in z.read(name).decode("utf-8")

    def test_spaces_are_hidden_by_a_view_setup_hint(self):
        viewpoint = _viewpoint_for({"audit_issues": [issue(id="GC-0001")]}, "GC-0001")
        assert '<ViewSetupHints SpacesVisible="false"/>' in viewpoint

    def test_viewpoint_without_a_camera_is_schema_valid(self):
        xmlschema = pytest.importorskip("xmlschema")
        from pathlib import Path

        schema = xmlschema.XMLSchema(
            Path(__file__).parent / "schemas" / "bcf21" / "visinfo.xsd"
        )
        viewpoint = _viewpoint_for({"audit_issues": [issue(id="GC-0001")]}, "GC-0001")
        assert not [str(e.reason or e) for e in schema.iter_errors(viewpoint)]
