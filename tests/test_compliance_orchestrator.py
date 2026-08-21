"""Test ComplianceOrchestrator - full compliance pipeline."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.modules.module4_comparator.compliance_orchestrator import ComplianceOrchestrator
from app.modules.module4_comparator.issue_schema import Issue, RiskBand


class TestComplianceOrchestrator:
    """Test the compliance orchestration pipeline."""

    def test_orchestrator_initialization(self):
        """Test orchestrator initializes."""
        orchestrator = ComplianceOrchestrator()
        assert orchestrator is not None
        print("✓ Initialization")

    def test_results_to_issues_conversion(self):
        """Test conversion of raw compliance results to Issue objects."""
        orchestrator = ComplianceOrchestrator()

        raw_results = [
            {
                "guid": "0FQ6pMwzXBJucYaRTqfuw2",
                "name": "SS316 Flanged Joint",
                "description": "Crevice corrosion risk identified",
                "overall_band": "CRITICAL",
                "overall_score": 0.89,
                "dominant_mechanism": "Crevice",
                "galvanic_score": 0.15,
                "galvanic_band": "LOW",
                "crevice_score": 0.89,
                "crevice_band": "CRITICAL",
                "mic_score": 0.0,
                "mic_band": "LOW",
                "joint_type": "JT-001",
                "environment": "swimming_pool",
                "voltage_gap_V": 0.05,
                "crevice_geometry": "tight",
                "mitigation": "Specify gasket",
            }
        ]

        issues = orchestrator._results_to_issues(raw_results, "Test Run")

        assert len(issues) == 1
        issue = issues[0]
        assert issue.id == "BGR-0001"
        assert issue.element_id == "0FQ6pMwzXBJucYaRTqfuw2"
        assert issue.band == RiskBand.CRITICAL
        assert issue.score == 0.89
        assert "CC-001" in issue.rule_id
        assert "crevice" in issue.mechanism.lower()
        assert len(issue.citations) > 0
        print("✓ Results to Issues conversion")

    def test_issue_summary_generation(self):
        """Test issue summary statistics generation."""
        orchestrator = ComplianceOrchestrator()

        issues = [
            Issue(
                id="BGR-0001",
                element_id="elem-001",
                rule_id="CC-001.01",
                title="Test",
                band=RiskBand.CRITICAL,
                score=0.89,
                mechanism="CC-001",
            ),
            Issue(
                id="BGR-0002",
                element_id="elem-002",
                rule_id="GC-001.01",
                title="Test",
                band=RiskBand.HIGH,
                score=0.73,
                mechanism="GC-001",
            ),
            Issue(
                id="BGR-0003",
                element_id="elem-003",
                rule_id="GC-001.01",
                title="Test",
                band=RiskBand.MEDIUM,
                score=0.45,
                mechanism="GC-001",
            ),
            Issue(
                id="BGR-0004",
                element_id="elem-004",
                rule_id="MC-001.01",
                title="Test",
                band=RiskBand.LOW,
                score=0.15,
                mechanism="MC-001",
            ),
        ]

        summary = orchestrator._summarize_issues(issues)

        assert summary["total"] == 4
        assert summary["critical"] == 1
        assert summary["high"] == 1
        assert summary["medium"] == 1
        assert summary["low"] == 1
        print("✓ Issue summary generation")

    def test_infer_assignee_role(self):
        """Test assignee role inference."""
        orchestrator = ComplianceOrchestrator()

        assert orchestrator._infer_assignee_role("GC-001") == "Materials Engineer"
        assert orchestrator._infer_assignee_role("CC-001") == "Mechanical Engineer"
        assert orchestrator._infer_assignee_role("MC-001") == "Process Engineer"
        print("✓ Assignee role inference")

    def test_full_pipeline_dry_run(self):
        """Test full pipeline logic."""
        orchestrator = ComplianceOrchestrator()

        raw_results = [
            {
                "guid": "elem-001",
                "name": "SS316 Pipe Main",
                "description": "Critical service",
                "overall_band": "CRITICAL",
                "overall_score": 0.89,
                "dominant_mechanism": "Crevice",
                "galvanic_score": 0.0,
                "galvanic_band": "LOW",
                "crevice_score": 0.89,
                "crevice_band": "CRITICAL",
                "mic_score": 0.0,
                "mic_band": "LOW",
                "joint_type": "JT-001",
                "environment": "swimming_pool",
                "voltage_gap_V": 0.0,
                "crevice_geometry": "tight",
                "mitigation": "Gasket replacement",
            }
        ]

        issues = orchestrator._results_to_issues(raw_results, "Test Run")
        summary = orchestrator._summarize_issues(issues)

        assert len(issues) == 1
        assert summary["total"] == 1
        assert summary["critical"] == 1
        assert issues[0].band == RiskBand.CRITICAL
        print("✓ Full pipeline dry run")


if __name__ == "__main__":
    print("Running ComplianceOrchestrator Tests...\n")
    test = TestComplianceOrchestrator()
    try:
        test.test_orchestrator_initialization()
        test.test_results_to_issues_conversion()
        test.test_issue_summary_generation()
        test.test_infer_assignee_role()
        test.test_full_pipeline_dry_run()
        print("\n✅ All ComplianceOrchestrator tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
