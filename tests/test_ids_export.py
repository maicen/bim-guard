"""IDS export/import round-trip via ifctester.ids (buildingSMART IDS 1.0)."""

import tempfile
from pathlib import Path

import ifctester.ids as ifctester_ids

from app.modules.contracts import RuleCreateRequest, RuleExtractionDraft
from app.modules.module3_rule_builder.ids_exporter import (
    build_ids_document,
    filter_exportable_rules,
    import_ids_ruleset,
    translate_rule_drafts_to_ids,
)

RANGE_ROW = {
    "reference": "REQ-1",
    "rule_category": "property_check",
    "target_ifc_class": "IfcDoor",
    "property_set": "Pset_DoorCommon",
    "property_name": "ClearWidth",
    "operator": "between",
    "value_min": "810",
    "value_max": "900",
}

MIN_ROW = {
    "reference": "REQ-2",
    "rule_category": "property_check",
    "target_ifc_class": "IfcStairFlight",
    "property_set": "Pset_StairFlightCommon",
    "property_name": "TreadLength",
    "operator": ">=",
    "check_value": "900",
}

EXISTS_ROW = {
    "reference": "REQ-3",
    "rule_category": "property_check",
    "target_ifc_class": "IfcWall",
    "property_set": "Pset_WallCommon",
    "property_name": "FireRating",
    "operator": "exists",
}

NON_EXPORTABLE_ROW = {
    "reference": "REQ-4",
    "rule_category": "geometry_check",  # not IDS-exportable
    "target_ifc_class": "IfcWall",
    "property_set": "",
    "property_name": "",
}


def _validate_against_schema(xml_text: str) -> None:
    """Assert xml_text validates against the vendored buildingSMART IDS 1.0 XSD."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ids", encoding="utf-8", delete=False) as tmp:
        tmp.write(xml_text)
        tmp_path = tmp.name
    try:
        ifctester_ids.get_schema().validate(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_filter_exportable_rules_excludes_non_property_checks():
    filtered = filter_exportable_rules([RANGE_ROW, NON_EXPORTABLE_ROW])
    assert filtered == [RANGE_ROW]


def test_build_ids_document_is_schema_valid():
    xml_text = build_ids_document([RANGE_ROW, MIN_ROW, EXISTS_ROW])
    _validate_against_schema(xml_text)  # raises XMLSchemaValidationError on failure


def test_round_trip_range_operator():
    xml_text = build_ids_document([RANGE_ROW])
    imported = import_ids_ruleset(xml_text)

    assert len(imported) == 1
    row = imported[0]
    assert row["target_ifc_class"] == "IfcDoor"
    assert row["property_name"] == "ClearWidth"
    assert row["operator"] == "between"
    assert row["value_min"] == 810
    assert row["value_max"] == 900


def test_round_trip_min_operator():
    xml_text = build_ids_document([MIN_ROW])
    imported = import_ids_ruleset(xml_text)

    assert len(imported) == 1
    row = imported[0]
    assert row["operator"] == ">="
    assert row["check_value"] == 900


def test_round_trip_exists_operator():
    xml_text = build_ids_document([EXISTS_ROW])
    imported = import_ids_ruleset(xml_text)

    assert len(imported) == 1
    assert imported[0]["property_name"] == "FireRating"


def test_import_malformed_xml_raises_value_error():
    try:
        import_ids_ruleset("<ids><specification>unclosed")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for malformed XML")


def test_import_well_formed_but_non_ids_xml_returns_empty_list():
    """Neither parser finds IDS specifications in unrelated-but-valid XML."""
    assert import_ids_ruleset("<not-ids>not valid</not-ids>") == []


def test_import_empty_text_returns_empty_list():
    assert import_ids_ruleset("") == []
    assert import_ids_ruleset("   ") == []


def test_translate_rule_drafts_to_ids_raises_when_none_have_a_target():
    draft = RuleExtractionDraft(
        source_document_id=1,
        proposed_rule=RuleCreateRequest(
            rule_id="REQ-1",
            property_set="Pset_DoorCommon",
            property_name="ClearWidth",
            operator=">=",
            check_value="900",
        ),
    )
    # RuleCreateRequest carries no target-IFC-class field (a pre-existing
    # contract gap), so every draft is filtered out and IDS 1.0 requires at
    # least one specification -- this documents that gap rather than
    # papering over it with an invalid empty document.
    try:
        translate_rule_drafts_to_ids([draft])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError when no draft has a target IFC class")


def test_build_ids_document_raises_when_nothing_exportable():
    try:
        build_ids_document([NON_EXPORTABLE_ROW])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for an all-non-exportable row set")
