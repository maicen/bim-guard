"""The persisted BCF report carries each finding's own fix and source clause.

``AnalysisService`` hands the report a compact topic payload, and
``ReportArtifactService._topic_to_issue`` adapts it for ``bcf_generator``. That
adapter used to write one generic mitigation for every finding and dropped the
citations, so the persisted report said less than the export archive. It now
writes the finding's mitigation into the topic comment and each citation as a
``Topic/DocumentReference``. A finding with neither falls back to the generic
mitigation and no reference, rather than an invented one.

Run: uv run pytest tests/test_persisted_bcf_mitigation_citations.py -v
"""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

import pytest

from app.modules.reporter.bcf_generator import generate_bcf
from app.services.pipeline_services import AnalysisService
from app.services.report_artifacts import DEFAULT_MITIGATION, ReportArtifactService

RUN_ID = "PERSIST-RUN"
SCHEMA_DIR = Path(__file__).parent / "schemas" / "bcf21"
CITED_TEXT = "The clear width of a door shall be not less than 860 mm."


def rule_result(**overrides: Any) -> dict[str, Any]:
    """Build a failing comparator-shaped rule result with one failing element."""
    result: dict[str, Any] = {
        "status": "FAIL",
        "rule_ref": "9.8.2.1",
        "rule_desc": "Door width must comply",
        "severity": "mandatory",
        "property_name": "OverallWidth",
        "target": "IfcDoor",
        "ruleset_id": "PART9-TEST",
        "source_text": CITED_TEXT,
        "source_document_id": 12,
        "source_page_number": 41,
        "failures": [{"guid": "DOOR-001", "reason": "Width below 860 mm"}],
    }
    result.update(overrides)
    return result


def topic_for(rule: dict[str, Any]) -> dict[str, Any]:
    """Run one rule result through include_rule_results and return its topic payload."""
    service = AnalysisService()
    audit: dict[str, Any] = {"issues": [], "bcf_topics": []}
    (topic,) = service.include_rule_results(audit, [rule], run_id=RUN_ID)["bcf_topics"]
    return topic


def persisted_markup(topic: dict[str, Any]) -> str:
    """Build the persisted BCF archive for *topic* and return its markup.bcf text."""
    content = generate_bcf([ReportArtifactService._topic_to_issue(topic)])
    archive = zipfile.ZipFile(io.BytesIO(content))
    (name,) = [n for n in archive.namelist() if n.endswith("markup.bcf")]
    return archive.read(name).decode()


def comment_text(markup: str) -> str:
    """Return the topic comment body from a markup.bcf document."""
    return ET.fromstring(markup).find("./Comment/Comment").text


def reference_descriptions(markup: str) -> list[str]:
    """Return every ``DocumentReference`` description in a markup.bcf document."""
    return [
        ref.find("Description").text
        for ref in ET.fromstring(markup).findall("./Topic/DocumentReference")
    ]


class TestTopicPayloadCarriesTheFinding:
    """include_rule_results puts the finding's own fix and citation on the topic."""

    def test_mitigation_and_citations_are_on_the_topic(self):
        topic = topic_for(rule_result())

        assert topic["mitigation"] == "Correct the IFC property and re-run the audit."
        assert topic["citations"] == [
            {
                "standard": "PART9-TEST",
                "clause": "9.8.2.1",
                "reason": f"{CITED_TEXT} (page 41)",
            }
        ]

    def test_rule_with_nothing_to_cite_has_no_citations_key(self):
        topic = topic_for(rule_result(rule_ref="", source_text=""))

        assert "citations" not in topic
        assert "mitigation" in topic


class TestPersistedReportWritesThem:
    """The persisted archive says what the export archive says."""

    def test_comment_carries_the_findings_mitigation_not_the_generic_one(self):
        markup = persisted_markup(topic_for(rule_result()))

        body = comment_text(markup)
        assert "Mitigation: Correct the IFC property and re-run the audit." in body
        assert DEFAULT_MITIGATION not in body

    def test_citation_becomes_a_document_reference(self):
        markup = persisted_markup(topic_for(rule_result()))

        assert reference_descriptions(markup) == [
            f"PART9-TEST Clause 9.8.2.1: {CITED_TEXT} (page 41)"
        ]

    def test_no_citation_means_no_document_reference(self):
        markup = persisted_markup(topic_for(rule_result(rule_ref="", source_text="")))

        assert reference_descriptions(markup) == []

    def test_topic_without_a_mitigation_keeps_the_generic_one(self):
        topic = topic_for(rule_result())
        del topic["mitigation"]

        assert f"Mitigation: {DEFAULT_MITIGATION}" in comment_text(persisted_markup(topic))


class TestCitationDescription:
    """Missing parts of a citation are left out, never filled in."""

    @pytest.mark.parametrize(
        ("citation", "expected"),
        [
            ({"standard": "S", "clause": "1.2", "reason": "why"}, "S Clause 1.2: why"),
            ({"standard": "", "clause": "1.2", "reason": "why"}, "Clause 1.2: why"),
            ({"standard": "S", "clause": "", "reason": "why"}, "S: why"),
            ({"standard": "", "clause": "", "reason": "why"}, "why"),
            ({"standard": "S", "clause": "1.2", "reason": ""}, "S Clause 1.2"),
            ({"standard": "", "clause": "", "reason": ""}, ""),
        ],
    )
    def test_formats_only_what_the_citation_has(self, citation, expected):
        assert ReportArtifactService._citation_description(citation) == expected


def test_persisted_markup_is_xsd_valid_with_a_document_reference():
    """The DocumentReference sits where markup.xsd requires it."""
    xmlschema = pytest.importorskip(
        "xmlschema", reason="xmlschema is required for BCF schema validation (dev dependency group)"
    )
    schema = xmlschema.XMLSchema(SCHEMA_DIR / "markup.xsd")

    markup = persisted_markup(topic_for(rule_result()))

    errors = [str(error) for error in schema.iter_errors(markup)]
    assert not errors, "markup.bcf schema violations:\n  " + "\n  ".join(errors)
