"""Building Topology Ontology (BOT) graph construction.

Translates the containment/adjacency structures BIM-Guard already derives
from an IFC model -- `build_ifc_graph()`'s networkx.DiGraph
(`app.modules.ifc_reader.ifc_graph`) and `IFCSpatialAdjacency`'s
space-boundary map (`app.modules.ifc_reader.ifc_spatial`) -- into an RDF
graph using the standard BOT vocabulary (https://w3id.org/bot#), plus a
BIM-Guard namespace for engine-computed literals (clear widths, travel
distances, clearance volumes) that pure BOT/IFC has no predicate for.

This module does not re-derive spatial relationships itself: it is a thin
adapter over the existing extraction so the SHACL engine
(`app.engines.bimguard_shacl_engine`) has one RDF graph to validate against.
"""

from __future__ import annotations

from typing import Any

import networkx as nx
from rdflib import RDF, RDFS, Graph, Literal, Namespace, URIRef
from rdflib.namespace import XSD

BOT = Namespace("https://w3id.org/bot#")
BIMGUARD = Namespace("https://bimguard.ai/onto#")
S4BLDG = Namespace("https://saref.etsi.org/saref4bldg/")

#: IFC spatial-structure types mapped onto their BOT class. `IfcProject` maps
#: to `bot:Zone` (the SRS's root spatial container) rather than a dedicated
#: BOT class of its own -- BOT has no `Project` class, and `bot:Zone` is the
#: vocabulary's generic spatial-region superclass.
_SPATIAL_TYPE_TO_BOT = {
    "IfcProject": BOT.Zone,
    "IfcSite": BOT.Site,
    "IfcBuilding": BOT.Building,
    "IfcBuildingStorey": BOT.Storey,
    "IfcSpace": BOT.Space,
}

#: IFC distribution/MEP element types mapped onto their SAREF4BLDG class,
#: emitted as an *additional* `rdf:type` alongside the generic `bot:Element`
#: typing every non-spatial element already gets -- see the SRS's Building
#: Geometry and Spatial Topology Integration table.
_DISTRIBUTION_TYPE_TO_S4BLDG = {
    "IfcDistributionElement": S4BLDG.DistributionDevice,
    "IfcFlowController": S4BLDG.FlowController,
    "IfcEnergyConversionDevice": S4BLDG.EnergyConversionDevice,
    "IfcSensor": S4BLDG.Sensor,
    "IfcAlarm": S4BLDG.Alarm,
}

#: `ifc_graph.build_ifc_graph()` edge `rel_type` -> BOT containment predicate,
#: keyed by (container BOT class, member BOT class); falls back to
#: `bot:containsElement`/`bot:hasElement` for anything not spatial-to-spatial.
#: `(Zone, Site)` is here because `IfcProject`-to-`IfcSite` is only ever
#: expressed via `IfcRelAggregates` ("Aggregates"), never
#: `IfcRelContainedInSpatialStructure` ("ContainedIn").
_CONTAINMENT_PREDICATE = {
    (BOT.Zone, BOT.Site): BOT.containsZone,
    (BOT.Site, BOT.Building): BOT.hasBuilding,
    (BOT.Building, BOT.Storey): BOT.hasStorey,
    (BOT.Storey, BOT.Space): BOT.hasSpace,
}

#: Edge `rel_type` values (from `build_ifc_graph()`) treated as containment
#: for BOT-graph purposes.
_CONTAINMENT_REL_TYPES = {"ContainedIn", "Aggregates"}


def element_uri(guid: str) -> URIRef:
    """Return the stable BIM-Guard URI for an IFC GlobalId."""
    return BIMGUARD[f"element/{guid}"]


def build_bot_graph(ifc_graph: nx.DiGraph, adjacency: Any | None = None) -> Graph:
    """Build a BOT-vocabulary RDF graph from an existing IFC relationship graph.

    Args:
        ifc_graph: the output of `app.modules.ifc_reader.ifc_graph.build_ifc_graph()`.
        adjacency: an optional, already-built `IFCSpatialAdjacency` instance
            (`app.modules.ifc_reader.ifc_spatial`) used to add
            `bot:adjacentElement` edges between elements bounding the same
            space and `bot:hasSpace` links for door/space connectivity. Skipped
            when not supplied or when it has no boundary data.
    """
    graph = Graph()
    graph.bind("bot", BOT)
    graph.bind("bimguard", BIMGUARD)
    graph.bind("s4bldg", S4BLDG)

    for guid, data in ifc_graph.nodes(data=True):
        subject = element_uri(guid)
        ifc_type = data.get("ifc_type", "")
        bot_class = _SPATIAL_TYPE_TO_BOT.get(ifc_type, BOT.Element)
        graph.add((subject, RDF.type, bot_class))
        graph.add((subject, RDF.type, BIMGUARD[ifc_type or "UnknownIfcType"]))
        s4bldg_class = _DISTRIBUTION_TYPE_TO_S4BLDG.get(ifc_type)
        if s4bldg_class is not None:
            graph.add((subject, RDF.type, s4bldg_class))
        label = data.get("label")
        if label:
            graph.add((subject, RDFS.label, Literal(str(label))))
        graph.add((subject, BIMGUARD.globalId, Literal(guid, datatype=XSD.string)))

    for container_guid, member_guid, edge in ifc_graph.edges(data=True):
        if edge.get("rel_type") not in _CONTAINMENT_REL_TYPES:
            continue
        container = element_uri(container_guid)
        member = element_uri(member_guid)
        container_class = next(graph.objects(container, RDF.type), None)
        member_class = next(graph.objects(member, RDF.type), None)
        predicate = _CONTAINMENT_PREDICATE.get((container_class, member_class))
        if predicate is not None:
            graph.add((container, predicate, member))
        else:
            # No specific spatial predicate for this pair: emit both the
            # existing generic BOT predicate (kept for backward
            # compatibility with earlier graphs/shapes) and `bot:hasElement`
            # (the SRS's preferred generic containment predicate).
            graph.add((container, BOT.containsElement, member))
            graph.add((container, BOT.hasElement, member))

    if adjacency is not None and getattr(adjacency, "has_boundaries", False):
        _add_adjacency_triples(graph, adjacency)

    return graph


def _add_adjacency_triples(graph: Graph, adjacency: Any) -> None:
    """Add `bot:hasSpace` (door/space) and `bot:adjacentElement` (party-wall) triples."""
    for door_guid, space_guids in adjacency.get_door_to_spaces().items():
        door = element_uri(door_guid)
        for space_guid in space_guids:
            graph.add((element_uri(space_guid), BOT.hasSpace, door))

    for party_wall in adjacency.get_party_walls():
        wall = element_uri(party_wall["wall_guid"])
        for space_guid in party_wall["space_guids"]:
            graph.add((wall, BOT.adjacentElement, element_uri(space_guid)))


def enrich_literal(
    graph: Graph,
    guid: str,
    predicate: str,
    value: float | int | str | bool,
    *,
    datatype: URIRef = XSD.decimal,
) -> None:
    """Attach one engine-computed value to an element node as an RDF literal.

    Used to write geometry-engine outputs (`ifc_geometry.py`, `ifc_egress.py`,
    `ifc_stair.py`, `blue_halo/`) back onto the BOT graph so SHACL shapes can
    constrain them -- e.g. `enrich_literal(graph, door_guid,
    "calculatedClearWidth", 880.0)`.
    """
    graph.set((element_uri(guid), BIMGUARD[predicate], Literal(value, datatype=datatype)))
