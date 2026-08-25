"""Test BCF 2.1 exporter functionality."""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import xml.etree.ElementTree as ET
from datetime import datetime

from app.modules.module4_comparator.issue_schema import Issue, RiskBand
from app.services.bcf_exporter import BCFExporter


class TestBCFExporter:
    """Test BCF export functionality."""

    @staticmethod
    def create_test_issue(
        issue_id="BGR-0001",
        element_id="0FQ6pMwzXBJucYaRTqfuw2",
        band=RiskBand.CRITICAL,
        score=0.89,
    ):
        """Create a test issue."""
        return Issue(
            id=issue_id,
            element_id=element_id,
            rule_id="CC-001.03",
            title="SS316 flange crevice corrosion risk",
            description="Crevice corrosion mechanism detected",
            band=band,
            score=score,
            mechanism="CC-001 crevice corrosion",
            mitigation="Apply gasket material",
            assignee_role="Mechanical Engineer",
            status="open",
            created_at=datetime.now().isoformat() + "Z",
            updated_at=datetime.now().isoformat() + "Z",
            metadata={"joint_type": "JT-001", "pren": 42.5},
            citations=[{"standard": "NACE SP0169-2013", "clause": "Table 1"}],
        )

    def test_bcf_exporter_initialization(self):
        exporter = BCFExporter()
        assert exporter is not None
        print("✓ Initialization")

    def test_single_issue(self):
        exporter = BCFExporter()
        issue = self.create_test_issue()
        xml_string = exporter.generate_bcf_markup_xml([issue])
        assert "BGR-0001" in xml_string
        assert "SS316" in xml_string
        print("✓ Single issue")

    def test_multiple_issues(self):
        exporter = BCFExporter()
        issues = [
            self.create_test_issue("BGR-0001", band=RiskBand.CRITICAL, score=0.89),
            self.create_test_issue("BGR-0002", band=RiskBand.HIGH, score=0.73),
            self.create_test_issue("BGR-0003", band=RiskBand.MEDIUM, score=0.45),
        ]
        xml_string = exporter.generate_bcf_markup_xml(issues)
        assert "BGR-0001" in xml_string
        assert "BGR-0002" in xml_string
        assert "Critical" in xml_string
        assert "High" in xml_string
        print("✓ Multiple issues")

    def test_priority_mapping(self):
        exporter = BCFExporter()
        assert exporter._risk_band_to_bcf_priority(RiskBand.CRITICAL) == "Critical"
        assert exporter._risk_band_to_bcf_priority(RiskBand.HIGH) == "High"
        print("✓ Priority mapping")

    def test_metadata(self):
        exporter = BCFExporter()
        issue = self.create_test_issue()
        xml_string = exporter.generate_bcf_markup_xml([issue])
        assert "joint_type" in xml_string
        assert "JT-001" in xml_string
        print("✓ Metadata")

    def test_citations(self):
        exporter = BCFExporter()
        issue = self.create_test_issue()
        xml_string = exporter.generate_bcf_markup_xml([issue])
        assert "NACE" in xml_string
        print("✓ Citations")

    def test_namespace(self):
        exporter = BCFExporter()
        issue = self.create_test_issue()
        xml_string = exporter.generate_bcf_markup_xml([issue])
        assert "buildingsmart-tech.org" in xml_string
        print("✓ Namespace")

    def test_well_formed(self):
        exporter = BCFExporter()
        issue = self.create_test_issue()
        xml_string = exporter.generate_bcf_markup_xml([issue])
        root = ET.fromstring(xml_string)
        assert root is not None
        print("✓ Well-formed XML")


if __name__ == "__main__":
    print("Running BCF Exporter Tests...\n")
    test = TestBCFExporter()
    try:
        test.test_bcf_exporter_initialization()
        test.test_single_issue()
        test.test_multiple_issues()
        test.test_priority_mapping()
        test.test_metadata()
        test.test_citations()
        test.test_namespace()
        test.test_well_formed()
        print("\n✅ All BCF Exporter tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
