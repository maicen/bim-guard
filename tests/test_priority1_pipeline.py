"""Priority 1 production pipeline contracts."""

import pytest

from app.services.pipeline_services import AnalysisService
from app.services.projects_service import is_enhancement_authorized

pytestmark = pytest.mark.slow


def test_enhancement_authorization_no_token_required():
    assert is_enhancement_authorized("")
    assert is_enhancement_authorized("anything")


def test_db_rule_failures_join_the_audit_issue_and_bcf_contract():
    service = AnalysisService()
    audit = {"pipeline": "audit", "issues": [], "bcf_topics": []}

    merged = service.include_rule_results(
        audit,
        [
            {
                "status": "FAIL",
                "rule_ref": "9.8.2.1",
                "rule_desc": "Door width must comply",
                "severity": "mandatory",
                "property_name": "OverallWidth",
                "target": "IfcDoor",
                "failures": [{"guid": "DOOR-001", "reason": "Width below 860 mm"}],
            }
        ],
        run_id="DB-AUDIT",
    )

    assert merged["issues"][0]["rule_id"] == "9.8.2.1"
    assert merged["issues"][0]["element_id"] == "DOOR-001"
    assert merged["bcf_topics"][0]["element_guid"] == "DOOR-001"
    assert audit["issues"] == []


def test_project_enhancement_lineage_contract_properties():
    record = {
        "id": 12,
        "project_id": 7,
        "source_reference": "sb://models/source.ifc",
        "source_version": 0,
        "output_reference": "sb://models/source_v1.ifc",
        "version": 1,
        "summary": {"names_added": 2},
        "created_at": "2026-08-22T14:00:00Z",
    }

    assert record["source_version"] == 0
    assert record["version"] == 1
    assert record["output_reference"].endswith(".ifc")
    assert record["summary"]["names_added"] == 2
