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
from rdflib import RDF, RDFS, BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import XSD

from app.services.qudt_normalizer import normalize_to_qudt

BOT = Namespace("https://w3id.org/bot#")
BIMGUARD = Namespace("https://bimguard.ai/onto#")
S4BLDG = Namespace("https://saref.etsi.org/saref4bldg/")
QUDT = Namespace("http://qudt.org/schema/qudt/")
UNIT = Namespace("http://qudt.org/vocab/unit/")

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
    graph.bind("qudt", QUDT)
    graph.bind("unit", UNIT)

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
    """Add door/space, party-wall, and space/space adjacency triples.

    `bot:hasSpace` (door/space), `bot:adjacentElement` (party-wall), and
    `bot:adjacentZone` (space/space, symmetric).
    """
    for door_guid, space_guids in adjacency.get_door_to_spaces().items():
        door = element_uri(door_guid)
        for space_guid in space_guids:
            graph.add((element_uri(space_guid), BOT.hasSpace, door))

    for party_wall in adjacency.get_party_walls():
        wall = element_uri(party_wall["wall_guid"])
        space_guids = party_wall["space_guids"]
        for space_guid in space_guids:
            graph.add((wall, BOT.adjacentElement, element_uri(space_guid)))

        # Every pair of spaces sharing this wall is a pair of adjacent zones
        # -- emitted in both directions, since "adjacent to" is inherently
        # symmetric for two spaces (unlike bot:adjacentElement above, which
        # is deliberately one-directional: the wall bounds the space, not
        # the reverse).
        for i, guid_a in enumerate(space_guids):
            for guid_b in space_guids[i + 1 :]:
                zone_a, zone_b = element_uri(guid_a), element_uri(guid_b)
                graph.add((zone_a, BOT.adjacentZone, zone_b))
                graph.add((zone_b, BOT.adjacentZone, zone_a))


def get_element_relationships(bot_graph: Graph, guid: str) -> dict[str, Any]:
    """Return one element's BOT/SAREF4BLDG classification and relationships.

    Reads an already-built `build_bot_graph()` output rather than a separate
    persisted triplestore, so the Knowledge Graph-Enriched 3D Viewport works
    the same way `graph_routes.py`'s `/status`/`/spatial-tree` endpoints do --
    on demand from the primary model file, regardless of whether this project
    has ever had `enable_shacl=True` persist a graph.

    Relationships are limited to BOT/SAREF4BLDG predicates (containment,
    `bot:adjacentElement`, `bot:adjacentZone`, `bot:hasSpace`) -- not the
    `bimguard:` engine-literal enrichments (`enrich_literal`), which are
    per-rule computed values, not graph structure.
    """
    subject = element_uri(guid)
    has_outgoing = any(bot_graph.triples((subject, None, None)))
    has_incoming = any(bot_graph.triples((None, None, subject)))
    if not has_outgoing and not has_incoming:
        return {
            "exists": False,
            "ifc_type": None,
            "label": None,
            "bot_classes": [],
            "s4bldg_classes": [],
            "outgoing": [],
            "incoming": [],
        }

    ifc_type: str | None = None
    bot_classes: list[str] = []
    s4bldg_classes: list[str] = []
    for rdf_class in bot_graph.objects(subject, RDF.type):
        class_str = str(rdf_class)
        if class_str.startswith(str(BOT)):
            bot_classes.append(class_str[len(str(BOT)) :])
        elif class_str.startswith(str(S4BLDG)):
            s4bldg_classes.append(class_str[len(str(S4BLDG)) :])
        elif class_str.startswith(str(BIMGUARD)) and class_str[len(str(BIMGUARD)) :].startswith("Ifc"):
            ifc_type = class_str[len(str(BIMGUARD)) :]

    label = next(bot_graph.objects(subject, RDFS.label), None)

    def _local_name(uri: URIRef) -> str:
        text = str(uri)
        return text.rsplit("#", 1)[-1].rsplit("/", 1)[-1]

    def _node_label(node: URIRef) -> str:
        found = next(bot_graph.objects(node, RDFS.label), None)
        return str(found) if found else _local_name(node)

    outgoing: list[dict[str, str]] = []
    for predicate, obj in bot_graph.predicate_objects(subject):
        pred_str = str(predicate)
        if isinstance(obj, Literal) or not (pred_str.startswith(str(BOT)) or pred_str.startswith(str(S4BLDG))):
            continue
        outgoing.append(
            {
                "predicate": _local_name(predicate),
                "guid": _local_name(obj),
                "label": _node_label(obj),
            }
        )

    incoming: list[dict[str, str]] = []
    for subj, predicate in bot_graph.subject_predicates(subject):
        pred_str = str(predicate)
        if not (pred_str.startswith(str(BOT)) or pred_str.startswith(str(S4BLDG))):
            continue
        incoming.append(
            {
                "predicate": _local_name(predicate),
                "guid": _local_name(subj),
                "label": _node_label(subj),
            }
        )

    return {
        "exists": True,
        "ifc_type": ifc_type,
        "label": str(label) if label else None,
        "bot_classes": bot_classes,
        "s4bldg_classes": s4bldg_classes,
        "outgoing": outgoing,
        "incoming": incoming,
    }


def enrich_literal(
    graph: Graph,
    guid: str,
    predicate: str,
    value: float | int | str | bool,
    *,
    datatype: URIRef = XSD.decimal,
    unit: str | None = None,
) -> None:
    """Attach one engine-computed value to an element node as an RDF literal.

    Used to write geometry-engine outputs (`ifc_geometry.py`, `ifc_egress.py`,
    `ifc_stair.py`, `blue_halo/`) back onto the BOT graph so SHACL shapes can
    constrain them -- e.g. `enrich_literal(graph, door_guid,
    "calculatedClearWidth", 880.0)`.

    `value` is always stored raw/as given under `predicate` -- SHACL shapes
    (`app.modules.rule_builder.shacl_generator`) compare against this literal
    in whatever unit it was written in. When `unit` is also given, an
    ADDITIONAL, SI-converted `qudt:numericValue`/`qudt:hasUnit` quantity node
    is attached under `{predicate}Qudt` purely for interoperability/export --
    it is never what a SHACL constraint reads, so it does not need to agree
    with `datatype`/`value`'s own unit.
    """
    subject = element_uri(guid)
    graph.set((subject, BIMGUARD[predicate], Literal(value, datatype=datatype)))
    
    if unit is not None and isinstance(value, (int, float)):
        si_value, qudt_uri = normalize_to_qudt(float(value), unit)
        if qudt_uri:
            # Create an additive QUDT blank node for this quantity
            quantity_node = BNode()
            graph.add((subject, BIMGUARD[f"{predicate}Qudt"], quantity_node))
            graph.add((quantity_node, QUDT.numericValue, Literal(si_value, datatype=XSD.decimal)))
            graph.add((quantity_node, QUDT.hasUnit, URIRef(qudt_uri)))
