"""Unit tests for app.modules.rule_builder.shacl_generator."""

from rdflib.namespace import RDF, SH

from app.modules.rule_builder.shacl_generator import compile_shapes, rule_is_shacl_eligible


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
