"""Unit tests for app.engines.bimguard_shacl_engine.ShaclComplianceEngine."""

import networkx as nx
from rdflib.namespace import XSD

from app.engines.bimguard_shacl_engine import ShaclComplianceEngine
from app.modules.comparator.engine_registry import RuleEvaluationContext
from app.modules.comparator.issue_adapter import lift_shacl_report
from app.modules.ifc_reader.bot_graph import build_bot_graph, enrich_literal
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
