"""Build IFC relationship graphs and render them as PyVis HTML."""

from html import escape
from pathlib import Path

import networkx as nx
from pyvis.network import Network

try:
    import ifcopenshell
    import ifcopenshell.util.element

    _IFCOPENSHELL_AVAILABLE = True
except ImportError:
    _IFCOPENSHELL_AVAILABLE = False


_SPATIAL_TYPES = {"IfcProject", "IfcSite", "IfcBuilding", "IfcBuildingStorey", "IfcSpace"}
_EDGE_PRIORITY = {"ContainedIn": 0, "Aggregates": 1, "Connects": 2}


def _safe_label(entity) -> str:
    name = getattr(entity, "Name", None)
    return name or entity.is_a()


def _node_title(guid: str, label: str, ifc_type: str, psets: dict) -> str:
    pset_names = list(psets.keys())[:6]
    pset_suffix = ""
    if pset_names:
        joined = ", ".join(escape(name) for name in pset_names)
        extra = len(psets) - len(pset_names)
        more = f" (+{extra} more)" if extra > 0 else ""
        pset_suffix = f"<br/><b>Psets:</b> {joined}{more}"
    return (
        f"<b>{escape(label)}</b>"
        f"<br/><b>Type:</b> {escape(ifc_type)}"
        f"<br/><b>GUID:</b> {escape(guid)}"
        f"{pset_suffix}"
    )


def build_ifc_graph(model) -> nx.DiGraph:
    """Build a directed IFC relationship graph from products and key relations."""
    graph = nx.DiGraph()

    for product in model.by_type("IfcProduct"):
        guid = getattr(product, "GlobalId", None)
        if not guid:
            continue
        try:
            psets = ifcopenshell.util.element.get_psets(product)
        except Exception:
            psets = {}
        graph.add_node(
            guid,
            label=_safe_label(product),
            ifc_type=product.is_a(),
            psets=psets,
        )

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

    return graph


def _select_nodes(graph: nx.DiGraph, max_nodes: int) -> set[str]:
    if graph.number_of_nodes() <= max_nodes:
        return set(graph.nodes())

    ranked = sorted(
        graph.nodes(),
        key=lambda node_id: (
            graph.nodes[node_id].get("ifc_type") in _SPATIAL_TYPES,
            graph.degree(node_id),
            graph.in_degree(node_id),
        ),
        reverse=True,
    )
    return set(ranked[:max_nodes])


def build_pyvis_graph(
    graph: nx.DiGraph, violations: list[dict], max_nodes: int = 220, max_edges: int = 600
):
    """Render a PyVis HTML graph from the IFC relationship graph."""
    violation_ids = {
        entry.get("element")
        for entry in violations
        if isinstance(entry, dict) and entry.get("element")
    }

    selected_nodes = _select_nodes(graph, max_nodes)
    selected_graph = graph.subgraph(selected_nodes).copy()

    edge_rows = sorted(
        selected_graph.edges(data=True),
        key=lambda edge: (
            _EDGE_PRIORITY.get(edge[2].get("rel_type", "Connects"), 99),
            edge[0],
            edge[1],
        ),
    )
    limited_edges = edge_rows[:max_edges]

    net = Network(
        height="700px",
        width="100%",
        directed=True,
        bgcolor="#0f172a",
        font_color="#e5e7eb",
        select_menu=True,
        filter_menu=True,
    )
    net.barnes_hut(
        gravity=-18000,
        central_gravity=0.16,
        spring_length=150,
        spring_strength=0.04,
        damping=0.1,
    )

    for node_id, attrs in selected_graph.nodes(data=True):
        ifc_type = attrs.get("ifc_type", "IfcProduct")
        label = attrs.get("label", ifc_type)
        highlighted = node_id in violation_ids
        is_spatial = ifc_type in _SPATIAL_TYPES
        color = "#ef4444" if highlighted else "#22c55e" if is_spatial else "#60a5fa"
        size = 24 if highlighted else 20 if is_spatial else 14
        net.add_node(
            node_id,
            label=label[:36],
            title=_node_title(node_id, label, ifc_type, attrs.get("psets", {})),
            color=color,
            shape="dot",
            size=size,
            group=ifc_type,
        )

    for source, target, attrs in limited_edges:
        net.add_edge(
            source,
            target,
            color=attrs.get("color", "#94a3b8"),
            title=attrs.get("rel_type", "Relation"),
            arrows="to",
        )

    net.set_options(
        """
        const options = {
          "interaction": {"hover": true, "navigationButtons": true, "keyboard": true},
          "nodes": {"borderWidth": 1, "borderWidthSelected": 2, "font": {"size": 14}},
          "edges": {"smooth": {"type": "dynamic"}, "width": 2},
          "physics": {
            "barnesHut": {
              "gravitationalConstant": -18000,
              "centralGravity": 0.16,
              "springLength": 150,
              "springConstant": 0.04,
              "damping": 0.1
            },
            "minVelocity": 0.75
          }
        }
        """
    )

    relationship_counts = {
        "ContainedIn": 0,
        "Aggregates": 0,
        "Connects": 0,
    }
    for _, _, attrs in graph.edges(data=True):
        rel_type = attrs.get("rel_type")
        if rel_type in relationship_counts:
            relationship_counts[rel_type] += 1

    return {
        "html": net.generate_html(notebook=False),
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "displayed_node_count": selected_graph.number_of_nodes(),
        "displayed_edge_count": len(limited_edges),
        "truncated": selected_graph.number_of_nodes() < graph.number_of_nodes()
        or len(limited_edges) < graph.number_of_edges(),
        "violation_count": len(violation_ids & set(graph.nodes())),
        "relationship_counts": relationship_counts,
    }


def render_ifc_graph(ifc_path: Path | str, violations: list[dict] | None = None):
    """Open an IFC file, build its relationship graph, and return rendered HTML metadata."""
    if not _IFCOPENSHELL_AVAILABLE:
        raise ImportError("ifcopenshell is not installed.")

    model = ifcopenshell.open(str(ifc_path))
    graph = build_ifc_graph(model)
    return build_pyvis_graph(graph, violations or [])
