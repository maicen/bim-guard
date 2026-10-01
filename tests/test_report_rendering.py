"""Tests for report_rendering (ReportLab PDF generation and Jinja2 HTML rendering)."""

from app.modules.contracts.compliance import (
    ReportCoverContract,
    ReportExecutiveSummaryContract,
    ReportFindingRowContract,
    ReportModel,
    ReportPriorityFindingContract,
    ReportRuleRegisterRowContract,
    ReportRulesetResultContract,
    ReportScopeContract,
    ReportTopFailedRuleContract,
    ReportUnverifiedRowContract,
)
from app.services.report_rendering import render_report_html, render_report_pdf


def _mock_report_model(
    *,
    has_rules: bool = True,
    has_findings: bool = True,
) -> ReportModel:
    cover = ReportCoverContract(
        project_name="Test Office Tower",
        project_code="PRJ-2026-001",
        model_file_name="Architectural_Model_v2.ifc",
        report_id="BGR-1-20261002010000",
        analysis_date="2026-10-02T01:00:00Z",
        discipline="Architecture",
        ifc_schema="IFC4",
        suitability_code="S3",
        revision_code="P02",
        cde_state="SHARED",
        document_id="BG-ARC-ZZ-M3-A-0001",
    )
    exec_summary = ReportExecutiveSummaryContract(
        narrative="Model meets 92.5% of verified compliance checks across evaluated egress and spatial rules.",
        elements_evaluated=450,
        unique_elements_evaluated=380,
        rules_executed=15 if has_rules else 0,
        checks_run=120 if has_rules else 0,
        passed=111 if has_rules else 0,
        failed=9 if has_findings else 0,
        unable_to_verify=3 if has_rules else 0,
        pass_rate=92.5 if has_rules else 0.0,
        mandatory_failed=2 if has_findings else 0,
        top_failed_rules=[
            ReportTopFailedRuleContract(
                rule_reference="ARCH-EGRESS-001",
                rule_description="Clear corridor width must be at least 1200mm",
                fail_count=5,
            ),
            ReportTopFailedRuleContract(
                rule_reference="ARCH-SPATIAL-002",
                rule_description="Minimum ceiling height for habitable spaces",
                fail_count=4,
            ),
        ]
        if has_findings
        else [],
    )
    scope = ReportScopeContract(
        model_file_name="Architectural_Model_v2.ifc",
        ifc_schema="IFC4",
        element_count=450,
        storey_count=5,
        ruleset_names=["Building Code Egress", "Accessibility Guidelines"] if has_rules else [],
        model_hash="sha256-abc123456789",
        rule_database_version="v2.4.0",
        engine_version="1.0.0",
        generated_at="2026-10-02T01:00:00Z",
        generated_by="BIM Guard Automated Compliance Pipeline",
    )
    results_by_ruleset = (
        [
            ReportRulesetResultContract(
                ruleset_id="RS-EGRESS",
                ruleset_name="Building Code Egress",
                source_citation="IBC 2024 Chapter 10",
                rule_count=8,
                passed=7,
                failed=1,
                unable_to_verify=0,
                pass_rate=87.5,
            ),
            ReportRulesetResultContract(
                ruleset_id="RS-SPATIAL",
                ruleset_name="Accessibility Guidelines",
                source_citation="ADA Standards 2010",
                rule_count=7,
                passed=5,
                failed=1,
                unable_to_verify=1,
                pass_rate=83.3,
            ),
        ]
        if has_rules
        else []
    )
    priority_findings = (
        [
            ReportPriorityFindingContract(
                rule_reference="ARCH-EGRESS-001",
                rule_description="Clear corridor width must be at least 1200mm",
                ruleset_id="RS-EGRESS",
                ruleset_name="Building Code Egress",
                element_name="Corridor 102",
                element_guid="1a2b3c4d-0001",
                storey="Level 1",
                measured="1050 mm",
                required="1200 mm",
                difference="-150 mm",
                citation="IBC 2024 Section 1020.2",
                ifc_property="NominalWidth",
                reliability="high",
                reliability_reason="Direct IFC schema property",
                action_required="Widen corridor boundary walls to achieve min 1200mm clear width",
                assignee_role="Lead Architect",
                severity="mandatory",
            )
        ]
        if has_findings
        else []
    )
    findings_register = (
        [
            ReportFindingRowContract(
                element_name="Corridor 102",
                element_guid="1a2b3c4d-0001",
                storey="Level 1",
                rule_reference="ARCH-EGRESS-001",
                measured="1050 mm",
                required="1200 mm",
                difference="-150 mm",
                severity="mandatory",
            ),
            ReportFindingRowContract(
                element_name="Office 204",
                element_guid="1a2b3c4d-0002",
                storey="Level 2",
                rule_reference="ARCH-SPATIAL-002",
                measured="2300 mm",
                required="2400 mm",
                difference="-100 mm",
                severity="recommended",
            ),
        ]
        if has_findings
        else []
    )
    unable_to_verify = (
        [
            ReportUnverifiedRowContract(
                rule_reference="ARCH-FIRE-003",
                rule_description="Fire rating on non-standard assemblies",
                reason="Pset_FireRating not present on model instances",
                affected_count=12,
            )
        ]
        if has_rules
        else []
    )
    rule_register = (
        [
            ReportRuleRegisterRowContract(
                rule_reference="ARCH-EGRESS-001",
                rule_description="Clear corridor width",
                ruleset_id="RS-EGRESS",
                ruleset_name="Building Code Egress",
                citation="IBC 2024 1020.2",
                ifc_property="NominalWidth",
                reliability="high",
                status="FAIL",
                fail_count=1,
                total_count=10,
            ),
            ReportRuleRegisterRowContract(
                rule_reference="ARCH-SPATIAL-001",
                rule_description="Minimum door clear opening width",
                ruleset_id="RS-SPATIAL",
                ruleset_name="Accessibility Guidelines",
                citation="ADA 404.2.3",
                ifc_property="OverallWidth",
                reliability="high",
                status="PASS",
                fail_count=0,
                total_count=35,
            ),
        ]
        if has_rules
        else []
    )

    return ReportModel(
        cover=cover,
        executive_summary=exec_summary,
        scope=scope,
        results_by_ruleset=results_by_ruleset,
        priority_findings=priority_findings,
        findings_register=findings_register,
        findings_register_total=len(findings_register),
        findings_register_truncated=False,
        unable_to_verify=unable_to_verify,
        rule_register=rule_register,
        element_type_sheets=[],
    )


def test_render_report_pdf_returns_valid_pdf_bytes():
    model = _mock_report_model()
    pdf_bytes = render_report_pdf(model)

    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 2000


def test_render_report_pdf_empty_model_is_valid():
    model = _mock_report_model(has_rules=False, has_findings=False)
    pdf_bytes = render_report_pdf(model)

    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 1000


def test_render_report_html_returns_valid_html():
    model = _mock_report_model()
    html_str = render_report_html(model, render_target="full")

    assert "<!DOCTYPE html>" in html_str
    assert "Test Office Tower" in html_str
    assert "ARCH-EGRESS-001" in html_str
