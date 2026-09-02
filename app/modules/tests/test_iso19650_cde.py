"""
Unit and Integration Tests for ISO 19650 Compliance & CDE State Machine Workflow.
"""

import pytest
from app.modules.contracts import CDEState
from app.modules.module1_doc_parser.iso_validator import ISO19650Validator, ISOValidationResult
from app.modules.module2_ifc_read.ifc_parser import extract_ifc_header_iso_metadata
from app.modules.module3_rule_builder.ids_exporter import build_ids_document, filter_exportable_rules
from app.modules.module4_comparator.compliance_runner import run_ids_loin_verification
from app.modules.module5_reporter.bcf_generator import BCFIssue, generate_bcf, _markup_xml
from app.modules.phase_6.phase_6e_export import export, to_ids
from app.services.cde_state_machine import CDEStateMachine, TransitionResult
from app.services.bcf_exporter import BCFExporter
from app.modules.module4_comparator.issue_schema import Issue, RiskBand


# ---------------------------------------------------------------------------
# ISO 19650 Validator Tests
# ---------------------------------------------------------------------------

def test_iso_validator_valid_filename():
    filename = "PRJ1-BIMG-01-00-M3-A-0001_S1_P01.01.ifc"
    res = ISO19650Validator.validate_filename(filename)
    assert res.is_valid is True
    assert res.fields["project_code"] == "PRJ1"
    assert res.fields["originator"] == "BIMG"
    assert res.fields["volume_system"] == "01"
    assert res.fields["level"] == "00"
    assert res.fields["type"] == "M3"
    assert res.fields["role"] == "A"
    assert res.fields["number"] == "0001"
    assert res.fields["suitability_code"] == "S1"
    assert res.fields["revision_code"] == "P01.01"


def test_iso_validator_invalid_filename():
    filename = "random_model_file.ifc"
    res = ISO19650Validator.validate_filename(filename)
    assert res.is_valid is False
    assert len(res.errors) > 0


def test_iso_validator_suitability_and_revision():
    assert ISO19650Validator.validate_suitability_code("S1") is True
    assert ISO19650Validator.validate_suitability_code("A4") is True
    assert ISO19650Validator.validate_suitability_code("INVALID") is False

    assert ISO19650Validator.validate_revision_code("P01.01") is True
    assert ISO19650Validator.validate_revision_code("C01") is True


# ---------------------------------------------------------------------------
# CDE State Machine Tests
# ---------------------------------------------------------------------------

def test_cde_state_machine_wip_to_shared_success():
    res = CDEStateMachine.evaluate_transition(
        current_state="WIP",
        target_state="SHARED",
        filename="PRJ1-BIMG-01-00-M3-A-0001.ifc",
        critical_issues_count=0,
        ids_check_passed=True,
    )
    assert res.allowed is True
    assert res.target_state == CDEState.SHARED


def test_cde_state_machine_wip_to_shared_blocked_on_invalid_naming():
    res = CDEStateMachine.evaluate_transition(
        current_state="WIP",
        target_state="SHARED",
        filename="invalid_name.ifc",
        critical_issues_count=0,
        ids_check_passed=True,
    )
    assert res.allowed is False
    assert "container naming validation failed" in res.reason


def test_cde_state_machine_wip_to_shared_blocked_on_critical_issues():
    res = CDEStateMachine.evaluate_transition(
        current_state="WIP",
        target_state="SHARED",
        filename="PRJ1-BIMG-01-00-M3-A-0001.ifc",
        critical_issues_count=3,
        ids_check_passed=True,
    )
    assert res.allowed is False
    assert "critical compliance issues" in res.reason


def test_cde_state_machine_shared_to_published_requires_approval():
    # Without approval
    res_blocked = CDEStateMachine.evaluate_transition(
        current_state="SHARED",
        target_state="PUBLISHED",
        is_approved=False,
        approved_by="",
    )
    assert res_blocked.allowed is False
    assert "approval is required" in res_blocked.reason

    # With approval
    res_allowed = CDEStateMachine.evaluate_transition(
        current_state="SHARED",
        target_state="PUBLISHED",
        is_approved=True,
        approved_by="Lead Architect John Doe",
    )
    assert res_allowed.allowed is True
    assert res_allowed.target_state == CDEState.PUBLISHED


# ---------------------------------------------------------------------------
# LOIN & buildingSMART IDS Tests
# ---------------------------------------------------------------------------

def test_ids_exporter_xml_generation():
    rules = [
        {
            "id": 1,
            "ruleset_id": "RS-01",
            "rule_category": "property_check",
            "target_ifc_class": "IfcPipeSegment",
            "property_set": "Pset_PipeSegmentCommon",
            "property_name": "NominalDiameter",
            "operator": ">=",
            "check_value": "0.1",
            "reference": "REQ-PIPE-01",
        }
    ]
    ids_xml = build_ids_document(rules)
    assert '<?xml version="1.0" encoding="UTF-8"?>' in ids_xml
    assert 'xmlns:ids="http://standards.buildingsmart.org/IDS"' in ids_xml
    assert "<ids:name>IfcPipeSegment</ids:name>" in ids_xml
    assert "<ids:name>NominalDiameter</ids:name>" in ids_xml


def test_run_ids_loin_verification():
    elements = [
        {
            "is_a": lambda: "IfcPipeSegment",
            "GlobalId": "12345",
            "get_info": lambda: {"psets": {"Pset_PipeSegmentCommon": {"NominalDiameter": 0.15}}, "material": "Carbon Steel"},
        }
    ]
    rules = [
        {
            "id": 1,
            "target_ifc_class": "IfcPipeSegment",
            "property_set": "Pset_PipeSegmentCommon",
            "property_name": "NominalDiameter",
            "reference": "LOIN-01",
        },
        {
            "id": 2,
            "target_ifc_class": "IfcPipeSegment",
            "property_set": "",
            "property_name": "material",
            "reference": "LOIN-02",
        },
    ]

    res = run_ids_loin_verification(elements, rules)
    assert res["passed"] is True
    assert res["compliance_percent"] == 100.0
    assert res["total_checks"] == 2
    assert res["passed_checks"] == 2


# ---------------------------------------------------------------------------
# BCF ISO 19650 Reporting Tests
# ---------------------------------------------------------------------------

def test_bcf_markup_iso_metadata_injection():
    issue = BCFIssue(
        guid="TEST-GUID-123",
        title="Corrosion Risk Detected",
        description="Galvanic corrosion between carbon steel and stainless steel",
        priority="Critical",
        status="Open",
        assigned_to="MEP Engineer",
        due_date="2026-10-01",
        labels=["galvanic"],
        component_guid="COMP-001",
        component_name="Pipe Fitting",
        service_type="Chilled Water",
        floor="L01",
        risk_band="CRITICAL",
        mechanism="galvanic",
        risk_score=95.0,
        mitigation="Install dielectric isolation flange",
        project_code="PRJ1",
        originator="BIMG",
        suitability_code="S1",
        revision_code="P01.01",
        cde_state="WIP",
    )

    markup = _markup_xml(issue, 1, "7A0E74E1-3CC3-46E8-B94E-516D2A12AD47")
    assert "<Labels>Suitability:S1</Labels>" in markup
    assert "<Labels>Originator:BIMG</Labels>" in markup
    assert "<Labels>CDE:WIP</Labels>" in markup
    # Header/File/@IfcProject is typed IfcGuid (22-char GlobalId) in BCF 2.1,
    # so a project *code* must not be written there; it travels in the comment.
    assert "IfcProject=" not in markup
    assert "ISO 19650 Container: PRJ1-BIMG" in markup

    issue.project_code = "0YvctVUKr0kugbFTf53O9L"  # a real IfcProject GlobalId
    markup = _markup_xml(issue, 1, "7A0E74E1-3CC3-46E8-B94E-516D2A12AD47")
    assert 'IfcProject="0YvctVUKr0kugbFTf53O9L"' in markup


def test_phase_6_ids_export_format():
    result = {
        "rules": [
            {
                "id": 10,
                "rule_category": "property_check",
                "target_ifc_class": "IfcWall",
                "property_name": "FireRating",
                "reference": "FIRE-01",
            }
        ]
    }
    content, media_type, ext = export(result, "ids")
    assert media_type == "application/xml"
    assert ext == "ids"
    assert b"IfcWall" in content
    assert b"FireRating" in content
