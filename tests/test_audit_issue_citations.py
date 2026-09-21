"""Architectural findings carry their rule's source into BCF issues.

``AnalysisService.include_rule_results`` turns failing DB rules into
``AuditIssue`` records. Those used to carry no citations, so
``BCFExporter._format_issue_details`` never wrote the "Standards References"
block for them. The citation is built only from fields the rule itself stores;
a rule with nothing to cite yields none rather than an invented one.

Run: uv run pytest tests/test_audit_issue_citations.py -v
"""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
import zipfile
from typing import Any

import pytest

from app.modules.comparator import ComplianceComparator
from app.modules.comparator.issue_schema import Issue
from app.modules.reporter.bcf_generator import bcf_topic_guid
from app.services.analysis_runner import as_issue
from app.services.bcf_exporter import BCFExporter
from app.services.pipeline_services import AnalysisService

RUN_ID = "CITE-RUN"


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
        "source_text": "The clear width of a door shall be not less than 860 mm.",
        "source_document_id": 12,
        "source_page_number": 41,
        "failures": [{"guid": "DOOR-001", "reason": "Width below 860 mm"}],
    }
    result.update(overrides)
    return result


def merged_issues(*rules: dict[str, Any]) -> list[dict[str, Any]]:
    """Run rule results through include_rule_results and return the issue dicts."""
    service = AnalysisService()
    audit: dict[str, Any] = {"issues": [], "bcf_topics": []}
    return service.include_rule_results(audit, list(rules), run_id=RUN_ID)["issues"]


def comment_body(issue: Issue) -> str:
    """Export one issue to a BCF archive and return its topic comment text."""
    archive = zipfile.ZipFile(io.BytesIO(BCFExporter().build_archive([issue])))
    markup = archive.read(f"{bcf_topic_guid(issue.id)}/markup.bcf").decode()
    return ET.fromstring(markup).find("./Comment/Comment").text


class TestCitationBuiltFromTheRule:
    """The citation is the rule's own ruleset, reference and source text."""

    def test_citation_uses_the_rules_stored_fields(self):
        (issue,) = merged_issues(rule_result())

        assert issue["citations"] == [
            {
                "standard": "PART9-TEST",
                "clause": "9.8.2.1",
                "reason": "The clear width of a door shall be not less than 860 mm. (page 41)",
            }
        ]

    def test_every_failing_element_gets_the_citation(self):
        issues = merged_issues(
            rule_result(
                failures=[
                    {"guid": "DOOR-001", "reason": "too narrow"},
                    {"guid": "DOOR-002", "reason": "too narrow"},
                ]
            )
        )

        assert [i["element_id"] for i in issues] == ["DOOR-001", "DOOR-002"]
        assert all(len(i["citations"]) == 1 for i in issues)

    def test_reason_omits_the_page_when_none_is_stored(self):
        (issue,) = merged_issues(rule_result(source_page_number=None))

        assert issue["citations"][0]["reason"] == (
            "The clear width of a door shall be not less than 860 mm."
        )

    def test_source_text_whitespace_is_collapsed(self):
        (issue,) = merged_issues(
            rule_result(source_text="Door width\n  shall be\tnot less than 860 mm.", source_page_number=None)
        )

        assert issue["citations"][0]["reason"] == "Door width shall be not less than 860 mm."

    def test_standard_falls_back_to_the_source_document(self):
        (issue,) = merged_issues(rule_result(ruleset_id=None))

        assert issue["citations"][0]["standard"] == "Source document #12"

    def test_reference_alone_is_cited_without_inventing_a_reason(self):
        (issue,) = merged_issues(
            rule_result(source_text=None, source_page_number=None)
        )

        assert issue["citations"] == [
            {"standard": "PART9-TEST", "clause": "9.8.2.1", "reason": ""}
        ]

    def test_source_text_alone_is_cited_without_inventing_a_clause(self):
        (issue,) = merged_issues(rule_result(rule_ref=""))

        assert issue["citations"][0]["clause"] == ""
        assert "860 mm" in issue["citations"][0]["reason"]


class TestCitationOmittedWithoutASource:
    """No reference and no source text means no citation, not a made-up one."""

    @pytest.mark.parametrize("empty", [None, "", "   "])
    def test_rule_without_reference_or_source_text_has_no_citation(self, empty):
        (issue,) = merged_issues(
            rule_result(rule_ref=empty, source_text=empty)
        )

        assert issue["citations"] == []

    def test_a_ruleset_or_page_alone_is_not_enough_to_cite(self):
        (issue,) = merged_issues(
            rule_result(rule_ref="", source_text=None)
        )

        # ruleset_id, source_document_id and page 41 are all still on the rule.
        assert issue["citations"] == []

    def test_rule_missing_the_provenance_keys_entirely_has_no_citation(self):
        legacy = {
            "status": "FAIL",
            "rule_desc": "Door width must comply",
            "failures": [{"guid": "DOOR-001", "reason": "too narrow"}],
        }

        (issue,) = merged_issues(legacy)

        assert issue["citations"] == []

    def test_no_citation_leaves_the_rest_of_the_finding_unchanged(self):
        (issue,) = merged_issues(rule_result(rule_ref="", source_text=None))

        assert issue["rule_id"] == "DB-RULE"
        assert issue["band"] == "high"
        assert issue["description"] == "Width below 860 mm"


class TestBcfStandardsReferences:
    """The exporter writes the block from a citation-bearing finding."""

    def test_bcf_comment_contains_the_standards_references_block(self):
        (raw,) = merged_issues(rule_result())

        body = comment_body(as_issue(raw))

        assert "Standards References:" in body
        assert "- PART9-TEST Clause 9.8.2.1" in body
        assert "Reason: The clear width of a door shall be not less than 860 mm. (page 41)" in body

    def test_bcf_comment_has_no_block_when_the_rule_has_no_source(self):
        (raw,) = merged_issues(rule_result(rule_ref="", source_text=None))

        assert "Standards References" not in comment_body(as_issue(raw))


class TestEndToEndThroughTheComparator:
    """A rule's provenance survives the comparator on its way to the BCF."""

    def test_provenance_reaches_the_bcf_via_validate_metadata(self):
        extraction_item = {
            "rule_id": 7,
            "rule_ref": "9.8.2.1",
            "rule_desc": "Door width must comply",
            "target_ifc_class": "IfcDoor",
            "property_name": "OverallWidth",
            "operator": ">=",
            "check_value": 860,
            "unit": "mm",
            "severity": "mandatory",
            "ruleset_id": "PART9-TEST",
            "source_text": "Doors shall be at least 860 mm wide.",
            "source_document_id": 12,
            "source_page_number": 41,
            "elements": [{"name": "D1", "guid": "DOOR-001", "actual_value": 800}],
        }

        (result,) = ComplianceComparator().validate_metadata([extraction_item])
        assert result["status"] == "FAIL"

        (raw,) = merged_issues(result)
        body = comment_body(as_issue(raw))

        assert "- PART9-TEST Clause 9.8.2.1" in body
        assert "Reason: Doors shall be at least 860 mm wide. (page 41)" in body
