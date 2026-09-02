from app.modules.module3_rule_builder.ids_exporter import (
    build_ids_document,
    export_ids_for_ruleset,
    filter_exportable_rules,
    import_ids_ruleset,
)


def test_filter_exportable_rules_only_keeps_property_checks_with_required_fields():
    rows = [
        {
            "rule_category": "property_check",
            "target_ifc_class": "IfcPipeSegment",
            "property_set": "Pset_PipeSegmentCommon",
            "property_name": "CorrosionAllowance",
            "operator": ">=",
            "check_value": 3,
            "unit": "mm",
            "rule_type": "numeric_comparison",
        },
        {
            "rule_category": "scoring_model",
            "target_ifc_class": "IfcPipeSegment",
            "property_set": "Pset_PipeSegmentCommon",
            "property_name": "CorrosionAllowance",
            "operator": ">=",
            "check_value": 3,
            "unit": "mm",
            "rule_type": "scoring_model",
        },
        {
            "rule_category": "property_check",
            "target_ifc_class": "",
            "property_set": "Pset_PipeSegmentCommon",
            "property_name": "CorrosionAllowance",
            "operator": ">=",
            "check_value": 3,
            "unit": "mm",
            "rule_type": "numeric_comparison",
        },
    ]

    exported = filter_exportable_rules(rows)

    assert len(exported) == 1
    assert exported[0]["target_ifc_class"] == "IfcPipeSegment"
    assert exported[0]["rule_category"] == "property_check"


def test_build_ids_document_bundles_exportable_checks_into_valid_xml():
    rows = [
        {
            "reference": "A1",
            "description": "Corrosion allowance shall be at least 3 mm.",
            "rule_category": "property_check",
            "target_ifc_class": "IfcPipeSegment",
            "property_set": "Pset_PipeSegmentCommon",
            "property_name": "CorrosionAllowance",
            "operator": ">=",
            "check_value": 3,
            "unit": "mm",
            "rule_type": "numeric_comparison",
            "severity": "mandatory",
            "source_text": "Corrosion allowance shall be at least 3 mm.",
        }
    ]

    xml = build_ids_document(rows, ifc_schema_version="IFC4")

    assert xml.startswith("<?xml")
    # ifctester.ids emits the IDS namespace as the default namespace
    # (<ids xmlns="...">) rather than a bound "ids:" prefix; both are
    # equally valid per XML namespaces, so assert on the namespace URI.
    assert "http://standards.buildingsmart.org/IDS" in xml
    assert "IfcPipeSegment" in xml
    assert "CorrosionAllowance" in xml
    assert "Pset_PipeSegmentCommon" in xml
    assert "IFC4" in xml


def test_filter_exportable_rules_allows_missing_property_set_for_real_db_rules():
    rows = [
        {
            "rule_category": "property_check",
            "target_ifc_class": "IfcStairFlight",
            "property_set": "",
            "property_name": "RiserHeight",
            "operator": "between",
            "value_min": 125,
            "value_max": 200,
            "rule_type": "range_check",
        },
        {
            "rule_category": "property_check",
            "target_ifc_class": "IfcDoor",
            "property_set": "",
            "property_name": "IsExternal",
            "operator": "exists",
            "check_value": None,
            "rule_type": "prohibition",
        },
    ]

    exported = filter_exportable_rules(rows)

    assert len(exported) == 2
    assert all(row["target_ifc_class"] for row in exported)
    assert all(row["property_name"] for row in exported)


def test_build_ids_document_handles_missing_property_set_and_range_checks():
    rows = [
        {
            "reference": "R-101",
            "description": "Riser height between 125 and 200 mm.",
            "rule_category": "property_check",
            "target_ifc_class": "IfcStairFlight",
            "property_set": "",
            "property_name": "RiserHeight",
            "operator": "between",
            "value_min": 125,
            "value_max": 200,
            "rule_type": "range_check",
        }
    ]

    xml = build_ids_document(rows, ifc_schema_version="IFC4")

    assert "IfcStairFlight" in xml
    assert "RiserHeight" in xml
    assert "125" in xml
    assert "200" in xml
    # Real IDS 1.0 names a property requirement's element <baseName>, not the
    # prior hand-rolled exporter's non-standard <name>.
    assert "<baseName>" in xml


def test_export_ids_for_ruleset_uses_ruleset_identifier_and_filters_scope():
    rows = [
        {
            "rule_category": "property_check",
            "target_ifc_class": "IfcDoor",
            "property_set": "Pset_DoorCommon",
            "property_name": "Width",
            "operator": ">=",
            "check_value": 900,
            "ruleset_id": "BUILDING-CODE-PART9",
        },
        {
            "rule_category": "threshold_band",
            "target_ifc_class": "IfcDoor",
            "property_set": "Pset_DoorCommon",
            "property_name": "Width",
            "operator": ">=",
            "check_value": 900,
            "ruleset_id": "BUILDING-CODE-PART9",
        },
    ]

    xml = export_ids_for_ruleset("BUILDING-CODE-PART9", rows)

    assert "BUILDING-CODE-PART9" in xml
    assert "IfcDoor" in xml
    assert "Width" in xml
    assert "threshold_band" not in xml.lower()


def test_import_ids_ruleset_parses_ids_xml_into_rule_rows():
    xml = '''<?xml version="1.0" encoding="UTF-8"?>
<ids:ids xmlns:ids="http://standards.buildingsmart.org/IDS" version="1.0" identifier="MY-IDS-SET">
  <ids:specifications>
    <ids:specification name="R-101">
      <ids:applicability>
        <ids:entity>
          <ids:name>IfcDoor</ids:name>
        </ids:entity>
      </ids:applicability>
      <ids:requirements>
        <ids:property>
          <ids:propertySet>Pset_DoorCommon</ids:propertySet>
          <ids:name>Width</ids:name>
          <ids:value>
            <ids:simpleValue>900</ids:simpleValue>
          </ids:value>
        </ids:property>
      </ids:requirements>
    </ids:specification>
  </ids:specifications>
</ids:ids>
'''

    rows = import_ids_ruleset(xml)

    assert len(rows) == 1
    assert rows[0]["ruleset_id"] == "MY-IDS-SET"
    assert rows[0]["target_ifc_class"] == "IfcDoor"
    assert rows[0]["property_set"] == "Pset_DoorCommon"
    assert rows[0]["property_name"] == "Width"
    assert rows[0]["rule_category"] == "property_check"
