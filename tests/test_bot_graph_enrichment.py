"""Unit tests for app.modules.ifc_reader.bot_graph_enrichment."""

import networkx as nx
from rdflib import Literal
from rdflib.namespace import XSD

from app.modules.ifc_reader.bot_graph import BIMGUARD, build_bot_graph, element_uri
from app.modules.ifc_reader.bot_graph_enrichment import enrich_bot_graph_with_engine_outputs


def _sample_ifc_graph() -> nx.DiGraph:
    graph = nx.DiGraph()
    graph.add_node("SPACE-1", label="Corridor 101", ifc_type="IfcSpace", psets={})
    graph.add_node("DOOR-1", label="Door D1", ifc_type="IfcDoor", psets={})
    graph.add_edge("SPACE-1", "DOOR-1", rel_type="ContainedIn", color="#4CAF50")
    return graph


class _FakeDoor:
    def __init__(self, guid: str):
        self.GlobalId = guid


class _FakeIfcFile:
    def __init__(self, doors: list[_FakeDoor]):
        self._doors = doors

    def by_type(self, ifc_class: str):
        return self._doors if ifc_class == "IfcDoor" else []


class _FakeReader:
    """Stub standing in for `M2Reader` -- resolves one door's clear width."""

    def __init__(self, doors: list[_FakeDoor], clear_widths: dict[str, float]):
        self.ifc_file = _FakeIfcFile(doors)
        self._clear_widths = clear_widths

    def _door_clear_opening_width(self, door: _FakeDoor):
        width = self._clear_widths.get(door.GlobalId)
        if width is None:
            return None, {}
        return width, {}


def test_enrich_door_clear_widths_attaches_literal_from_reader():
    bot_graph = build_bot_graph(_sample_ifc_graph())
    reader = _FakeReader([_FakeDoor("DOOR-1")], {"DOOR-1": 849.0})

    enrich_bot_graph_with_engine_outputs(bot_graph, m2_reader=reader)

    value = bot_graph.value(element_uri("DOOR-1"), BIMGUARD.calculatedClearWidth)
    assert value == Literal(849.0, datatype=XSD.decimal)


def test_enrich_door_clear_widths_skips_when_reader_cannot_resolve():
    bot_graph = build_bot_graph(_sample_ifc_graph())
    reader = _FakeReader([_FakeDoor("DOOR-1")], {})

    enrich_bot_graph_with_engine_outputs(bot_graph, m2_reader=reader)

    assert bot_graph.value(element_uri("DOOR-1"), BIMGUARD.calculatedClearWidth) is None


def test_enrich_door_clear_widths_skips_without_a_reader():
    bot_graph = build_bot_graph(_sample_ifc_graph())

    # No m2_reader/ifc_file at all -- must not raise.
    enrich_bot_graph_with_engine_outputs(bot_graph, m2_reader=None)

    assert bot_graph.value(element_uri("DOOR-1"), BIMGUARD.calculatedClearWidth) is None


def test_enrich_door_clear_widths_skips_reader_that_raises():
    bot_graph = build_bot_graph(_sample_ifc_graph())

    class _RaisingReader:
        ifc_file = _FakeIfcFile([_FakeDoor("DOOR-1")])

        def _door_clear_opening_width(self, door):
            raise RuntimeError("no geometry")

    enrich_bot_graph_with_engine_outputs(bot_graph, m2_reader=_RaisingReader())

    assert bot_graph.value(element_uri("DOOR-1"), BIMGUARD.calculatedClearWidth) is None


def test_enrich_travel_distances_attaches_literal_per_space():
    bot_graph = build_bot_graph(_sample_ifc_graph())
    egress_checks = {
        "travel_distance": [
            {"space_guid": "SPACE-1", "travel_distance_m": 12.3},
            {"space_guid": "UNKNOWN-SPACE", "travel_distance_m": None},
        ]
    }

    enrich_bot_graph_with_engine_outputs(bot_graph, egress_checks=egress_checks)

    value = bot_graph.value(element_uri("SPACE-1"), BIMGUARD.travelDistanceM)
    assert value == Literal(12.3, datatype=XSD.decimal)
    assert bot_graph.value(element_uri("UNKNOWN-SPACE"), BIMGUARD.travelDistanceM) is None


def test_enrich_travel_distances_handles_missing_egress_checks():
    bot_graph = build_bot_graph(_sample_ifc_graph())

    # No egress_checks at all -- must not raise.
    enrich_bot_graph_with_engine_outputs(bot_graph, egress_checks=None)

    assert bot_graph.value(element_uri("SPACE-1"), BIMGUARD.travelDistanceM) is None
