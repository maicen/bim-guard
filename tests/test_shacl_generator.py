"""Unit tests for app.modules.rule_builder.shacl_generator."""

from rdflib.namespace import RDF, SH

from app.modules.rule_builder.shacl_generator import (
    compile_shapes,
    rule_is_shacl_eligible,
    rule_row_to_shacl_input,
)


def _door_width_rule(**overrides) -> dict:
    rule = {
        "rule_id": "CODE-9.6.3.1",
        "description": "Door clear width shall be at least 900mm",
        "mechanism": "CODE",
        "severity": "mandatory",
        "target_ifc_class": "IfcDoor",
        "property_name": "calculatedClearWidth",
        "operator": ">=",
        "check_value": "900",
        "unit": "mm",
        "applies_when": None,
    }
    rule.update(overrides)
    return rule


def test_rule_is_shacl_eligible_for_numeric_operator():
    assert rule_is_shacl_eligible(_door_width_rule()) is True


def test_rule_is_not_eligible_without_target_class_or_property():
    assert rule_is_shacl_eligible(_door_width_rule(target_ifc_class=None)) is False
    assert rule_is_shacl_eligible(_door_width_rule(property_name=None)) is False


def test_rule_is_not_eligible_for_unsupported_operator():
    assert rule_is_shacl_eligible(_door_width_rule(operator="some_unsupported_op")) is False


def test_field_consistency_eligible_only_without_name_pattern():
    rule = _door_width_rule(operator="field_consistency", compare_property="tag_id")
    assert rule_is_shacl_eligible(rule) is True
    assert rule_is_shacl_eligible({**rule, "name_pattern": r"(\d+)$"}) is False
    assert rule_is_shacl_eligible({**rule, "compare_property": None}) is False


def test_unique_within_scope_eligible_only_for_building_scope():
    rule = _door_width_rule(operator="unique_within_scope")
    assert rule_is_shacl_eligible(rule) is True
    assert rule_is_shacl_eligible({**rule, "uniqueness_scope": "building"}) is True
    assert rule_is_shacl_eligible({**rule, "uniqueness_scope": "storey"}) is False
    assert rule_is_shacl_eligible({**rule, "uniqueness_scope": "space"}) is False


def test_compile_shapes_emits_node_shape_with_min_inclusive():
    shapes = compile_shapes([_door_width_rule()])

    node_shapes = list(shapes.subjects(RDF.type, SH.NodeShape))
    assert len(node_shapes) == 1

    prop_shapes = list(shapes.objects(node_shapes[0], SH.property))
    assert len(prop_shapes) == 1
    assert shapes.value(prop_shapes[0], SH.minInclusive) is not None
    assert float(shapes.value(prop_shapes[0], SH.minInclusive)) == 900.0
    assert shapes.value(prop_shapes[0], SH.severity) == SH.Violation


def test_compile_shapes_skips_ineligible_rules():
    shapes = compile_shapes([_door_width_rule(operator="some_unsupported_op")])

    assert len(list(shapes.subjects(RDF.type, SH.NodeShape))) == 0


# ---------------------------------------------------------------------------
# rule_row_to_shacl_input: decoding a raw rules-table row
# ---------------------------------------------------------------------------


def test_rule_row_to_shacl_input_decodes_json_encoded_columns():
    """A raw DB row (RuleService._build_rule_row's own encoding) round-trips.

    check_value/value_min/value_max/applies_when/exceptions are stored
    JSON-encoded as TEXT; a row read straight from the table carries them as
    strings, not the Python values compile_shapes/_add_shape operate on.
    """
    raw_row = {
        "reference": "CODE-9.6.3.1",
        "target_ifc_class": "IfcDoor",
        "property_name": "calculatedClearWidth",
        "operator": ">=",
        "check_value": "900.0",
        "value_min": "null",
        "value_max": "null",
        "applies_when": '{"material_any_of": ["gypsum"]}',
        "exceptions": "[]",
    }

    rule = rule_row_to_shacl_input(raw_row)

    assert rule["rule_id"] == "CODE-9.6.3.1"
    assert rule["check_value"] == 900.0
    assert rule["value_min"] is None
    assert rule["applies_when"] == {"material_any_of": ["gypsum"]}
    assert rule["exceptions"] == []


def test_rule_row_to_shacl_input_passes_through_already_decoded_values():
    """A row that already carries native Python values (not from the DB) is untouched."""
    row = {
        "rule_id": "CODE-1",
        "check_value": 900.0,
        "applies_when": {"material_any_of": ["gypsum"]},
    }

    rule = rule_row_to_shacl_input(row)

    assert rule["check_value"] == 900.0
    assert rule["applies_when"] == {"material_any_of": ["gypsum"]}


def test_rule_row_to_shacl_input_compiles_into_a_valid_shape():
    """A raw row, once decoded, compiles the same as an already-decoded rule dict."""
    raw_row = {
        "reference": "CODE-9.6.3.1",
        "description": "Door clear width shall be at least 900mm",
        "target_ifc_class": "IfcDoor",
        "property_name": "calculatedClearWidth",
        "operator": ">=",
        "check_value": "900.0",
        "unit": "mm",
        "severity": "mandatory",
    }

    shapes = compile_shapes([rule_row_to_shacl_input(raw_row)])

    node_shapes = list(shapes.subjects(RDF.type, SH.NodeShape))
    assert len(node_shapes) == 1
    prop_shapes = list(shapes.objects(node_shapes[0], SH.property))
    assert float(shapes.value(prop_shapes[0], SH.minInclusive)) == 900.0


def test_compile_shapes_plain_target_class_when_scope_unresolvable():
    # "occupancy_any_of" has no known graph predicate mapping (yet), so the
    # shape must fall back to a plain sh:targetClass rather than silently
    # narrowing to nothing.
    shapes = compile_shapes([_door_width_rule(applies_when={"occupancy_any_of": ["assembly"]})])

    node_shape = next(shapes.subjects(RDF.type, SH.NodeShape))
    assert shapes.value(node_shape, SH.targetClass) is not None
    assert shapes.value(node_shape, SH.target) is None


def test_compile_shapes_sparql_target_for_material_scope():
    shapes = compile_shapes([_door_width_rule(applies_when={"material_any_of": ["steel"]})])

    node_shape = next(shapes.subjects(RDF.type, SH.NodeShape))
    assert shapes.value(node_shape, SH.targetClass) is None
    assert shapes.value(node_shape, SH.target) is not None
