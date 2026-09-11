"""Unit tests for app.engines.bimguard_shacl_engine.ShaclComplianceEngine."""

import networkx as nx
from rdflib import Literal
from rdflib.namespace import XSD

from app.engines.bimguard_shacl_engine import ShaclComplianceEngine
from app.modules.comparator.engine_registry import RuleEvaluationContext
from app.modules.comparator.issue_adapter import lift_shacl_report
from app.modules.ifc_reader.bot_graph import BIMGUARD, build_bot_graph, element_uri, enrich_literal
from app.modules.rule_builder.shacl_generator import compile_shapes


def _context(**metadata) -> RuleEvaluationContext:
    return RuleEvaluationContext(rule_type="CODE-SHACL", element=None, metadata=metadata)


def _door_graph(clear_width_mm: float):
    ifc_graph = nx.DiGraph()
    ifc_graph.add_node("DOOR-1", label="Door D1", ifc_type="IfcDoor", psets={})
    bot_graph = build_bot_graph(ifc_graph)
    enrich_literal(bot_graph, "DOOR-1", "calculatedClearWidth", clear_width_mm, datatype=XSD.decimal)
    return bot_graph


_DOOR_WIDTH_RULE = {
    "rule_id": "CODE-9.6.3.1",
    "description": "Door clear width shall be at least 900mm",
    "severity": "mandatory",
    "target_ifc_class": "IfcDoor",
    "property_name": "calculatedClearWidth",
    "operator": ">=",
    "check_value": "900",
    "unit": "mm",
}


def test_evaluate_not_assessed_without_shapes_or_ruleset():
    engine = ShaclComplianceEngine()

    result = engine.evaluate(_door_graph(900), context=None)

    assert result.status == "NOT_ASSESSED"


def test_evaluate_passes_when_door_meets_threshold():
    engine = ShaclComplianceEngine()
    shapes = compile_shapes([_DOOR_WIDTH_RULE])

    result = engine.evaluate(_door_graph(900), context=_context(shapes_graph=shapes))

    assert result.status == "PASS"
    assert result.details["conforms"] is True


def test_evaluate_fails_and_reports_narrow_door():
    engine = ShaclComplianceEngine()
    shapes = compile_shapes([_DOOR_WIDTH_RULE])

    result = engine.evaluate(_door_graph(700), context=_context(shapes_graph=shapes))

    assert result.status == "FAIL"
    assert result.details["conforms"] is False

    issues = lift_shacl_report(result.raw_result)
    assert len(issues) == 1
    assert issues[0].element_id == "DOOR-1"
    assert issues[0].rule_id == "CODE-9.6.3.1"
    assert "900mm" in issues[0].title


_UNIQUE_TAG_RULE = {
    "rule_id": "CODE-UNIQUE-TAG",
    "description": "Door tag codes shall be unique",
    "severity": "mandatory",
    "target_ifc_class": "IfcDoor",
    "property_name": "tagCode",
    "operator": "unique_within_scope",
    "uniqueness_scope": "building",
}


def _graph_with_elements(elements: list[tuple[str, str]], properties: dict[str, dict[str, str]]):
    """Build a BOT graph from `[(guid, ifc_type), ...]` plus `{guid: {predicate: value}}`."""
    ifc_graph = nx.DiGraph()
    for guid, ifc_type in elements:
        ifc_graph.add_node(guid, label=guid, ifc_type=ifc_type, psets={})
    bot_graph = build_bot_graph(ifc_graph)
    for guid, props in properties.items():
        for predicate, value in props.items():
            bot_graph.add((element_uri(guid), BIMGUARD[predicate], Literal(value)))
    return bot_graph


def test_unique_within_scope_flags_duplicate_doors():
    graph = _graph_with_elements(
        [("DOOR-1", "IfcDoor"), ("DOOR-2", "IfcDoor")],
        {"DOOR-1": {"tagCode": "D1"}, "DOOR-2": {"tagCode": "D1"}},
    )
    shapes = compile_shapes([_UNIQUE_TAG_RULE])

    result = ShaclComplianceEngine().evaluate(graph, context=_context(shapes_graph=shapes))

    assert result.status == "FAIL"
    issues = lift_shacl_report(result.raw_result, shapes_graph=shapes)
    assert {i.element_id for i in issues} == {"DOOR-1", "DOOR-2"}


def test_unique_within_scope_ignores_a_different_element_class():
    # DOOR-1's tag is unique among doors even though a window happens to
    # share the same value -- ?other must be restricted to the rule's own
    # target_ifc_class, not any element in the graph with the same predicate.
    graph = _graph_with_elements(
        [("DOOR-1", "IfcDoor"), ("WINDOW-1", "IfcWindow")],
        {"DOOR-1": {"tagCode": "X"}, "WINDOW-1": {"tagCode": "X"}},
    )
    shapes = compile_shapes([_UNIQUE_TAG_RULE])

    result = ShaclComplianceEngine().evaluate(graph, context=_context(shapes_graph=shapes))

    assert result.status == "PASS"


_TAG_CONSISTENCY_RULE = {
    "rule_id": "CODE-TAG-CONSISTENCY",
    "description": "Door tag prefix shall match its suffix field",
    "severity": "mandatory",
    "target_ifc_class": "IfcDoor",
    "property_name": "tagPrefix",
    "operator": "field_consistency",
    "compare_property": "tagSuffix",
}


def test_field_consistency_flags_mismatched_element():
    graph = _graph_with_elements(
        [("DOOR-1", "IfcDoor")],
        {"DOOR-1": {"tagPrefix": "B1", "tagSuffix": "B2"}},
    )
    shapes = compile_shapes([_TAG_CONSISTENCY_RULE])

    result = ShaclComplianceEngine().evaluate(graph, context=_context(shapes_graph=shapes))

    assert result.status == "FAIL"
    issues = lift_shacl_report(result.raw_result, shapes_graph=shapes)
    assert [i.element_id for i in issues] == ["DOOR-1"]


def test_field_consistency_ignores_other_elements_differing_values():
    # DOOR-1 is internally consistent (tagPrefix == tagSuffix); it must not
    # be flagged just because DOOR-2 happens to hold different values for
    # the same two properties -- field_consistency compares two properties
    # on the SAME element, never one element against another.
    graph = _graph_with_elements(
        [("DOOR-1", "IfcDoor"), ("DOOR-2", "IfcDoor")],
        {
            "DOOR-1": {"tagPrefix": "A1", "tagSuffix": "A1"},
            "DOOR-2": {"tagPrefix": "C1", "tagSuffix": "C1"},
        },
    )
    shapes = compile_shapes([_TAG_CONSISTENCY_RULE])

    result = ShaclComplianceEngine().evaluate(graph, context=_context(shapes_graph=shapes))

    assert result.status == "PASS"
