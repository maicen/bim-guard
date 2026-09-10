"""Unit tests for app.modules.ifc_reader.bot_graph."""

import networkx as nx
from rdflib import RDF, Literal
from rdflib.namespace import XSD

from app.modules.ifc_reader.bot_graph import (
    BIMGUARD,
    BOT,
    build_bot_graph,
    element_uri,
    enrich_literal,
)


def _sample_ifc_graph() -> nx.DiGraph:
    """Build a tiny Storey -> Space -> Door containment graph.

    Shaped like `app.modules.ifc_reader.ifc_graph.build_ifc_graph()`'s output.
    """
    graph = nx.DiGraph()
    graph.add_node("STOREY-1", label="Level 1", ifc_type="IfcBuildingStorey", psets={})
    graph.add_node("SPACE-1", label="Corridor 101", ifc_type="IfcSpace", psets={})
    graph.add_node("DOOR-1", label="Door D1", ifc_type="IfcDoor", psets={})
    graph.add_edge("STOREY-1", "SPACE-1", rel_type="ContainedIn", color="#4CAF50")
    graph.add_edge("SPACE-1", "DOOR-1", rel_type="ContainedIn", color="#4CAF50")
    return graph


def test_build_bot_graph_emits_bot_classes():
    bot_graph = build_bot_graph(_sample_ifc_graph())

    assert (element_uri("STOREY-1"), RDF.type, BOT.Storey) in bot_graph
    assert (element_uri("SPACE-1"), RDF.type, BOT.Space) in bot_graph
    assert (element_uri("DOOR-1"), RDF.type, BOT.Element) in bot_graph
    assert (element_uri("DOOR-1"), RDF.type, BIMGUARD.IfcDoor) in bot_graph


def test_build_bot_graph_emits_hasspace_containment():
    bot_graph = build_bot_graph(_sample_ifc_graph())

    assert (element_uri("STOREY-1"), BOT.hasSpace, element_uri("SPACE-1")) in bot_graph
    # Space -> Door is not a spatial-to-spatial containment pair, so it falls
    # back to the generic bot:containsElement predicate.
    assert (element_uri("SPACE-1"), BOT.containsElement, element_uri("DOOR-1")) in bot_graph


def test_enrich_literal_attaches_computed_value():
    bot_graph = build_bot_graph(_sample_ifc_graph())

    enrich_literal(bot_graph, "DOOR-1", "calculatedClearWidth", 880.0)

    value = bot_graph.value(element_uri("DOOR-1"), BIMGUARD.calculatedClearWidth)
    assert value == Literal(880.0, datatype=XSD.decimal)


def test_enrich_literal_replaces_previous_value():
    bot_graph = build_bot_graph(_sample_ifc_graph())

    enrich_literal(bot_graph, "DOOR-1", "calculatedClearWidth", 700.0)
    enrich_literal(bot_graph, "DOOR-1", "calculatedClearWidth", 880.0)

    values = list(bot_graph.objects(element_uri("DOOR-1"), BIMGUARD.calculatedClearWidth))
    assert values == [Literal(880.0, datatype=XSD.decimal)]
