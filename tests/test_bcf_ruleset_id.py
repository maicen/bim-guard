"""Rule-backed findings name their ruleset in BCF issues.

``AnalysisService.include_rule_results`` turns failing DB rules into findings.
The ruleset each rule belongs to is stored on the rule itself, so it is carried
into the finding's details and written by both BCF writers -- the persisted
report artifact (``bcf_generator``) and the services-layer ``BCFExporter`` --
as a ``Ruleset:`` line in the topic description and a ``Ruleset:<id>`` label.
A rule with no ruleset gets neither, rather than a blank line.

Run: uv run pytest tests/test_bcf_ruleset_id.py -v
"""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
import zipfile
from typing import Any

from app.modules.comparator.issue_schema import Issue
from app.modules.reporter.bcf_generator import bcf_topic_guid, generate_bcf
from app.services.analysis_runner import as_issue
from app.services.bcf_exporter import BCFExporter
from app.services.pipeline_services import AnalysisService
from app.services.report_artifacts import ReportArtifactService

RUN_ID = "RULESET-RUN"


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
        "failures": [{"guid": "DOOR-001", "reason": "Width below 860 mm"}],
    }
    result.update(overrides)
    return result


def merged(rule: dict[str, Any]) -> dict[str, Any]:
    """Run one rule result through include_rule_results and return the audit result."""
    service = AnalysisService()
    audit: dict[str, Any] = {"issues": [], "bcf_topics": []}
    return service.include_rule_results(audit, [rule], run_id=RUN_ID)


def archive_topics(content: bytes) -> list[ET.Element]:
    """Return every ``Topic`` element from a BCF archive's markup files."""
    archive = zipfile.ZipFile(io.BytesIO(content))
    return [
        ET.fromstring(archive.read(name)).find("Topic")
        for name in archive.namelist()
        if name.endswith("markup.bcf")
    ]


def labels_of(topic: ET.Element) -> list[str]:
    """Return a topic's label texts."""
    return [label.text for label in topic.findall("Labels")]


class TestFindingCarriesTheRulesetItsRuleStores:
    """include_rule_results reads the ruleset from the rule, never from code."""

    def test_ruleset_lands_in_details_and_topic_payload(self):
        result = merged(rule_result())

        (issue,) = result["issues"]
        (topic,) = result["bcf_topics"]
        assert issue["details"]["ruleset_id"] == "PART9-TEST"
        assert topic["ruleset_id"] == "PART9-TEST"
        assert "Ruleset: PART9-TEST" in topic["description"]

    def test_rule_without_a_ruleset_gets_no_line_or_key(self):
        result = merged(rule_result(ruleset_id=None))

        (topic,) = result["bcf_topics"]
        assert "ruleset_id" not in topic
        assert "Ruleset" not in topic["description"]

    def test_blank_ruleset_is_treated_as_absent(self):
        result = merged(rule_result(ruleset_id="   "))

        (topic,) = result["bcf_topics"]
        assert "ruleset_id" not in topic
        assert "Ruleset" not in topic["description"]


class TestPersistedArtifactWritesTheRuleset:
    """The bcf_generator path names the ruleset in the description and a label."""

    def test_label_and_description_reach_the_archive(self):
        (topic,) = merged(rule_result())["bcf_topics"]

        content = generate_bcf([ReportArtifactService._topic_to_issue(topic)])
        (bcf_topic,) = archive_topics(content)

        assert "Ruleset:PART9-TEST" in labels_of(bcf_topic)
        assert "Ruleset: PART9-TEST" in bcf_topic.find("Description").text

    def test_no_ruleset_means_no_ruleset_label(self):
        (topic,) = merged(rule_result(ruleset_id=None))["bcf_topics"]

        content = generate_bcf([ReportArtifactService._topic_to_issue(topic)])
        (bcf_topic,) = archive_topics(content)

        assert not any(label.startswith("Ruleset:") for label in labels_of(bcf_topic))
        assert "Ruleset" not in bcf_topic.find("Description").text


class TestExporterWritesTheRuleset:
    """The services-layer BCFExporter reads it from Issue.metadata."""

    @staticmethod
    def exported_topic(issue: Issue) -> ET.Element:
        archive = zipfile.ZipFile(io.BytesIO(BCFExporter().build_archive([issue])))
        markup = archive.read(f"{bcf_topic_guid(issue.id)}/markup.bcf").decode()
        return ET.fromstring(markup).find("Topic")

    def test_ruleset_is_described_and_labelled(self):
        (issue_dict,) = merged(rule_result())["issues"]

        topic = self.exported_topic(as_issue(issue_dict))

        assert "Ruleset: PART9-TEST" in topic.find("Description").text
        assert "Ruleset:PART9-TEST" in labels_of(topic)

    def test_finding_from_an_engine_without_a_rule_record_has_none(self):
        (issue_dict,) = merged(rule_result(ruleset_id=None))["issues"]

        topic = self.exported_topic(as_issue(issue_dict))

        assert "Ruleset" not in topic.find("Description").text
        assert not any(label.startswith("Ruleset:") for label in labels_of(topic))
