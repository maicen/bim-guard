"""Build IFC relationship graphs and ingest them into GraphService (Neo4j / KùzuDB).

Provides:
- `build_ifc_graph(model) -> nx.DiGraph`: Builds a NetworkX directed relationship graph.
- `ingest_ifc_to_graph(...) -> dict[str, int]`: Streamlines IFC entities and relationships
  directly into a GraphService backend using batch Cypher / provider operations.
- `build_ifc_graph_summary(...) -> dict`: Returns structured metadata and statistics.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

import networkx as nx

if TYPE_CHECKING:
    from app.services.graph_database import GraphService

try:
    import ifcopenshell
    import ifcopenshell.util.element

    _IFCOPENSHELL_AVAILABLE = True
except ImportError:
    ifcopenshell = None
    _IFCOPENSHELL_AVAILABLE = False

logger = logging.getLogger(__name__)

_SPATIAL_TYPES = {"IfcProject", "IfcSite", "IfcBuilding", "IfcBuildingStorey", "IfcSpace"}
_EDGE_PRIORITY = {"ContainedIn": 0, "Aggregates": 1, "Connects": 2, "HasMaterial": 3}


def _safe_label(entity: Any) -> str:
    name = getattr(entity, "Name", None)
    return name or entity.is_a()


def build_ifc_graph(model: Any) -> nx.DiGraph:
    """Build a directed IFC relationship graph from products, spaces, and relations."""
    graph = nx.DiGraph()

    # IfcProject is an IfcContext, so add it explicitly as the root zone
    for project in model.by_type("IfcProject"):
        guid = getattr(project, "GlobalId", None)
        if not guid:
            continue
        graph.add_node(
            guid,
            label=_safe_label(project),
            ifc_type=project.is_a(),
            psets={},
        )

    # Physical products and spatial structures
    for product in model.by_type("IfcProduct"):
        guid = getattr(product, "GlobalId", None)
        if not guid:
            continue
        try:
            psets = ifcopenshell.util.element.get_psets(product) if ifcopenshell else {}
        except Exception:
            psets = {}
        graph.add_node(
            guid,
            label=_safe_label(product),
            ifc_type=product.is_a(),
            psets=psets,
        )

    # Spatial containment: (:Structure)-[:ContainedIn]->(:Element)
    for rel in model.by_type("IfcRelContainedInSpatialStructure"):
        container = getattr(rel, "RelatingStructure", None)
        container_guid = getattr(container, "GlobalId", None)
        if not container_guid:
            continue
        for element in getattr(rel, "RelatedElements", []):
            element_guid = getattr(element, "GlobalId", None)
            if container_guid in graph and element_guid in graph:
                graph.add_edge(
                    container_guid,
                    element_guid,
                    rel_type="ContainedIn",
                    color="#4CAF50",
                )

    # Spatial aggregation: (:Whole)-[:Aggregates]->(:Part)
    for rel in model.by_type("IfcRelAggregates"):
        whole = getattr(rel, "RelatingObject", None)
        whole_guid = getattr(whole, "GlobalId", None)
        if not whole_guid:
            continue
        for part in getattr(rel, "RelatedObjects", []):
            part_guid = getattr(part, "GlobalId", None)
            if whole_guid in graph and part_guid in graph:
                graph.add_edge(
                    whole_guid,
                    part_guid,
                    rel_type="Aggregates",
                    color="#2196F3",
                )

    # Physical connection: (:Element)-[:Connects]->(:Element)
    for rel in model.by_type("IfcRelConnectsElements"):
        source = getattr(rel, "RelatingElement", None)
        target = getattr(rel, "RelatedElement", None)
        source_guid = getattr(source, "GlobalId", None)
        target_guid = getattr(target, "GlobalId", None)
        if source_guid in graph and target_guid in graph:
            graph.add_edge(
                source_guid,
                target_guid,
                rel_type="Connects",
                color="#FF9800",
            )

    # Material association: (:Element)-[:HasMaterial]->(:Material)
    for rel in model.by_type("IfcRelAssociatesMaterial"):
        material_select = getattr(rel, "RelatingMaterial", None)
        if not material_select:
            continue
        material_name = (
            getattr(material_select, "Name", None)
            or getattr(material_select, "Material", None)
            or material_select.is_a()
        )
        if not isinstance(material_name, str):
            material_name = str(material_name)
        material_id = f"Material_{material_name}"
        if material_id not in graph:
            graph.add_node(
                material_id,
                label=material_name,
                ifc_type="IfcMaterial",
                psets={},
            )
        for element in getattr(rel, "RelatedObjects", []):
            element_guid = getattr(element, "GlobalId", None)
            if element_guid and element_guid in graph:
                graph.add_edge(
                    element_guid,
                    material_id,
                    rel_type="HasMaterial",
                    color="#9C27B0",
                )

    return graph


def compute_graph_centrality(graph: nx.DiGraph) -> dict[str, dict[str, float]]:
    """Compute closeness, degree, and betweenness centralities on an IFC relationship graph.

    Inspired by TopologicPy network centrality analytics for BIM graphs:
    identifies central structural conduits, key spatial hubs, and critical circulation nodes.
    """
    if len(graph) == 0:
        return {}

    # Convert to undirected graph for structural reachability
    undirected = graph.to_undirected()

    try:
        closeness = nx.closeness_centrality(undirected)
    except Exception:
        closeness = {}

    try:
        degree = nx.degree_centrality(undirected)
    except Exception:
        degree = {}

    # Betweenness is computationally heavier; cap at moderate sized graphs for interactive response
    betweenness = {}
    if len(graph) <= 1000:
        try:
            betweenness = nx.betweenness_centrality(undirected)
        except Exception:
            betweenness = {}

    results: dict[str, dict[str, float]] = {}
    for node in graph.nodes():
        node_str = str(node)
        results[node_str] = {
            "closeness": round(float(closeness.get(node, 0.0)), 4),
            "degree": round(float(degree.get(node, 0.0)), 4),
            "betweenness": round(float(betweenness.get(node, 0.0)), 4) if betweenness else 0.0,
        }
    return results


def find_orphan_elements(graph: nx.DiGraph) -> list[dict[str, Any]]:
    """Return graph nodes with no containment, connection, or material relationship.

    Excludes spatial root types (``IfcProject``/``IfcSite``/``IfcBuilding``/
    ``IfcBuildingStorey``/``IfcSpace``), which legitimately sit at the top of
    the containment tree and can have zero inbound edges, and synthetic
    ``IfcMaterial`` nodes, which are graph bookkeeping rather than model
    elements. Used by ``GraphTopologyEngine`` (GRAPH-TOPOLOGY-001) to flag
    elements disconnected from the rest of the model.
    """
    orphans: list[dict[str, Any]] = []
    for node, attrs in graph.nodes(data=True):
        ifc_type = attrs.get("ifc_type", "Unknown")
        if ifc_type in _SPATIAL_TYPES or ifc_type == "IfcMaterial":
            continue
        if graph.in_degree(node) + graph.out_degree(node) == 0:
            orphans.append(
                {
                    "guid": node,
                    "label": attrs.get("label", node),
                    "ifc_type": ifc_type,
                    "degree": 0,
                }
            )
    return orphans


def get_centrality_consequence_multiplier(
    guid: str,
    centralities: dict[str, dict[str, float]],
    base_multiplier: float = 1.0,
    max_multiplier: float = 1.5,
) -> float:
    """Calculate a consequence multiplier (1.0 to 1.5x) based on element network centrality."""
    metrics = centralities.get(guid)
    if not metrics:
        return base_multiplier

    score = float(metrics.get("degree", 0.0))
    boost = score * (max_multiplier - base_multiplier)
    return round(base_multiplier + boost, 3)


def build_ifc_graph_summary(
    graph: nx.DiGraph,
    violations: list[dict[str, Any]] | None = None,
    include_centrality: bool = True,
) -> dict[str, Any]:
    """Generate structured summary metadata and centrality analytics for an IFC relationship graph."""
    violation_ids = {
        entry.get("element")
        for entry in (violations or [])
        if isinstance(entry, dict) and entry.get("element")
    }

    relationship_counts: dict[str, int] = defaultdict(int)
    for _, _, attrs in graph.edges(data=True):
        rel_type = attrs.get("rel_type", "Other")
        relationship_counts[rel_type] += 1

    type_counts: dict[str, int] = defaultdict(int)
    for _, attrs in graph.nodes(data=True):
        ifc_type = attrs.get("ifc_type", "Unknown")
        type_counts[ifc_type] += 1

    centrality_summary: dict[str, Any] = {}
    top_central_elements: list[dict[str, Any]] = []

    if include_centrality and len(graph) > 0:
        centralities = compute_graph_centrality(graph)
        sorted_nodes = sorted(
            centralities.items(),
            key=lambda item: max(item[1].get("degree", 0.0), item[1].get("closeness", 0.0)),
            reverse=True,
        )
        for guid, metrics in sorted_nodes[:5]:
            node_attrs = graph.nodes.get(guid, {})
            top_central_elements.append(
                {
                    "guid": guid,
                    "label": node_attrs.get("label", guid),
                    "ifc_type": node_attrs.get("ifc_type", "Unknown"),
                    "degree": metrics.get("degree", 0.0),
                    "closeness": metrics.get("closeness", 0.0),
                }
            )
        centrality_summary = {
            "evaluated_nodes": len(centralities),
            "max_degree": max((m.get("degree", 0.0) for m in centralities.values()), default=0.0),
            "max_closeness": max((m.get("closeness", 0.0) for m in centralities.values()), default=0.0),
        }

    return {
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "violation_count": len(violation_ids & set(graph.nodes())),
        "relationship_counts": dict(relationship_counts),
        "type_counts": dict(type_counts),
        "centrality_summary": centrality_summary,
        "top_central_elements": top_central_elements,
    }


def ingest_ifc_to_graph(
    model_or_path: Any,
    graph_service: GraphService,
    *,
    project_id: str | None = None,
    include_psets: bool = False,
    graph: nx.DiGraph | None = None,
) -> dict[str, int]:
    """Extract IFC entities and relationships and ingest them in batch into GraphService.

    Args:
        model_or_path: An open ifcopenshell.file or a Path/str to an IFC file.
        graph_service: An active GraphService instance connected to Neo4j or KùzuDB.
        project_id: Optional project identifier to associate with all ingested nodes.
        include_psets: Whether to flatten and attach property set values to element nodes.
        graph: An already-built graph for ``model_or_path`` (from
            ``build_ifc_graph``), reused instead of building a second one --
            for a caller (e.g. the orchestrator's graph intelligence
            side-channel) that already built the graph for its own summary or
            engine pass over the same model.

    Returns:
        Dict with total counts of ingested nodes and relationships.
    """
    if graph is None:
        if not _IFCOPENSHELL_AVAILABLE:
            raise ImportError("ifcopenshell is not installed.")

        if isinstance(model_or_path, (str, Path)):
            model = ifcopenshell.open(str(model_or_path))
        else:
            model = model_or_path

        graph = build_ifc_graph(model)

    # Group nodes by label (ifc_type)
    nodes_by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node_id, attrs in graph.nodes(data=True):
        ifc_type = attrs.get("ifc_type", "IfcProduct")
        node_props: dict[str, Any] = {
            "id": node_id,
            "guid": node_id,
            "name": attrs.get("label", node_id),
            "ifc_type": ifc_type,
        }
        if project_id:
            node_props["project_id"] = project_id

        if include_psets and attrs.get("psets"):
            # Flatten top property set keys if requested
            for pset_name, pset_vals in attrs["psets"].items():
                if isinstance(pset_vals, dict):
                    for k, v in list(pset_vals.items())[:10]:
                        safe_key = f"pset_{pset_name}_{k}".replace(" ", "_")
                        if isinstance(v, (str, int, float, bool)):
                            node_props[safe_key[:40]] = v

        nodes_by_label[ifc_type].append(node_props)

    total_nodes = 0
    for label, nodes in nodes_by_label.items():
        graph_service.add_nodes_batch(label, nodes)
        total_nodes += len(nodes)

    # Group edges by rel_type
    edges_by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source_id, target_id, attrs in graph.edges(data=True):
        rel_type = attrs.get("rel_type", "CONNECTS").upper()
        # Normalise relationship names to standard Cypher convention
        if rel_type == "CONTAINEDIN":
            rel_type = "CONTAINS"
        edges_by_type[rel_type].append(
            {
                "source_id": source_id,
                "target_id": target_id,
                "properties": {"project_id": project_id} if project_id else {},
            }
        )

    total_edges = 0
    for rel_type, edges in edges_by_type.items():
        graph_service.add_edges_batch(rel_type, edges)
        total_edges += len(edges)

    logger.info(
        "Ingested IFC model to graph: %d nodes across %d labels, %d edges across %d types",
        total_nodes,
        len(nodes_by_label),
        total_edges,
        len(edges_by_type),
    )

    return {
        "nodes": total_nodes,
        "edges": total_edges,
        "labels": len(nodes_by_label),
        "rel_types": len(edges_by_type),
    }


def render_ifc_graph(
    ifc_path: Path | str, violations: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Open an IFC file and return structured graph summary metrics without PyVis."""
    if not _IFCOPENSHELL_AVAILABLE:
        raise ImportError("ifcopenshell is not installed.")

    model = ifcopenshell.open(str(ifc_path))
    graph = build_ifc_graph(model)
    return build_ifc_graph_summary(graph, violations or [])
