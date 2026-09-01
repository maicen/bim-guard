"""Tests for buildingSMART IDS (Information Delivery Specification) Expansion."""

from app.modules.module3_rule_builder.ids_exporter import (
    build_ids_document,
    import_ids_ruleset,
)
from app.modules.module4_comparator.compliance_runner import run_ids_loin_verification


def test_build_ids_document_with_tolerances_and_cardinality():
    rows = [
        {
            "reference": "PIPE-CORROSION-01",
            "description": "Corrosion allowance minimum thickness",
            "rule_category": "property_check",
            "target_ifc_class": "IfcPipeSegment",
            "property_set": "Pset_PipeSegmentCommon",
            "property_name": "CorrosionAllowance",
            "operator": ">=",
            "check_value": 3.0,
            "tolerance": 0.2,
            "cardinality": "required",
            "data_type": "IFCLENGTHMEASURE",
        }
    ]

    xml = build_ids_document(rows, ifc_schema_version="IFC4")
    assert "<ids:ids" in xml
    assert 'tolerance="0.2"' in xml
    assert 'cardinality="required"' in xml
    assert "Pset_PipeSegmentCommon" in xml
    assert "CorrosionAllowance" in xml


def test_import_ids_ruleset_with_facets_and_tolerances():
    ids_xml = """<?xml version="1.0" encoding="UTF-8"?>
<ids:ids xmlns:ids="http://standards.buildingsmart.org/IDS" version="1.0" identifier="TEST-SPEC">
  <ids:info>
    <ids:title>Test Specification</ids:title>
  </ids:info>
  <ids:specifications>
    <ids:specification ifcVersion="IFC4" name="MEP-Spec-01">
      <ids:applicability>
        <ids:entity>
          <ids:name>IfcPipeSegment</ids:name>
        </ids:entity>
      </ids:applicability>
      <ids:requirements>
        <ids:property dataType="IFCLENGTHMEASURE" tolerance="0.5">
          <ids:propertySet>Pset_PipeSegmentCommon</ids:propertySet>
          <ids:name>NominalDiameter</ids:name>
          <ids:value>
            <ids:simpleValue>100</ids:simpleValue>
          </ids:value>
        </ids:property>
        <ids:classification>
          <ids:system>Uniclass 2015</ids:system>
          <ids:value>Pr_65_52_63</ids:value>
        </ids:classification>
        <ids:material>
          <ids:value>Stainless Steel 316</ids:value>
        </ids:material>
      </ids:requirements>
    </ids:specification>
  </ids:specifications>
</ids:ids>
"""
    rules = import_ids_ruleset(ids_xml)
    assert len(rules) == 3

    prop_rule = next(r for r in rules if r["property_name"] == "NominalDiameter")
    assert prop_rule["target_ifc_class"] == "IfcPipeSegment"
    assert prop_rule["tolerance"] == 0.5
    assert prop_rule["check_value"] == 100

    cls_rule = next(r for r in rules if r["rule_type"] == "classification_check")
    assert cls_rule["check_value"] == "Pr_65_52_63"

    mat_rule = next(r for r in rules if r["rule_type"] == "material_check")
    assert mat_rule["check_value"] == "Stainless Steel 316"


def test_run_ids_loin_verification_with_tolerance_check():
    rules = [
        {
            "target_ifc_class": "IfcPipeSegment",
            "property_set": "Pset_PipeSegmentCommon",
            "property_name": "NominalDiameter",
            "operator": "=",
            "check_value": 100.0,
            "tolerance": 2.0,  # acceptable range: 98.0 to 102.0
            "reference": "IDS-TOL-01",
        }
    ]

    # Compliant element within tolerance (101.5 is within 100 +/- 2)
    compliant_element = {
        "GlobalId": "GUID-001",
        "element_type": "IfcPipeSegment",
        "NominalDiameter": 101.5,
    }
    report_pass = run_ids_loin_verification([compliant_element], rules)
    assert report_pass["passed"] is True
    assert report_pass["compliance_percent"] == 100.0

    # Non-compliant element outside tolerance (105.0 exceeds 100 +/- 2)
    failing_element = {
        "GlobalId": "GUID-002",
        "element_type": "IfcPipeSegment",
        "NominalDiameter": 105.0,
    }
    report_fail = run_ids_loin_verification([failing_element], rules)
    assert report_fail["passed"] is False
    assert report_fail["failed_checks"] == 1
    assert any("exceeds tolerance" in v["message"] for v in report_fail["violations"])
