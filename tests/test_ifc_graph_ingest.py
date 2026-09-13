"""Unit tests for IFC graph extraction and graph database ingestion without PyVis."""

from unittest.mock import MagicMock

from app.modules.ifc_reader.ifc_graph import (
    build_ifc_graph,
    build_ifc_graph_summary,
    ingest_ifc_to_graph,
    render_ifc_graph,
)
from app.services.graph_database import GraphService


class MockEntity:
    def __init__(self, guid: str, name: str, ifc_class: str):
        self.GlobalId = guid
        self.Name = name
        self._ifc_class = ifc_class

    def is_a(self, class_name: str | None = None) -> str | bool:
        if class_name is None:
            return self._ifc_class
        return self._ifc_class == class_name


class MockRelContained:
    def __init__(self, container, elements):
        self.RelatingStructure = container
        self.RelatedElements = elements


class MockRelAggregates:
    def __init__(self, whole, parts):
        self.RelatingObject = whole
        self.RelatedObjects = parts


class MockRelConnects:
    def __init__(self, source, target):
        self.RelatingElement = source
        self.RelatedElement = target


class MockRelMaterial:
    def __init__(self, material, elements):
        self.RelatingMaterial = material
        self.RelatedObjects = elements


class MockIfcModel:
    def __init__(self):
        self.projects = [MockEntity("proj-1", "Hospital Project", "IfcProject")]
        self.sites = [MockEntity("site-1", "Main Site", "IfcSite")]
        self.storeys = [MockEntity("storey-1", "Level 1", "IfcBuildingStorey")]
        self.walls = [
            MockEntity("wall-1", "North Wall", "IfcWall"),
            MockEntity("wall-2", "East Wall", "IfcWall"),
        ]
        self.pipes = [MockEntity("pipe-1", "Hot Water Pipe", "IfcPipeSegment")]
        self.materials = [MockEntity("mat-1", "Copper", "IfcMaterial")]

        self.contained = [
            MockRelContained(self.storeys[0], self.walls + self.pipes)
        ]
        self.aggregates = [
            MockRelAggregates(self.projects[0], self.sites),
            MockRelAggregates(self.sites[0], self.storeys),
        ]
        self.connects = [MockRelConnects(self.walls[0], self.walls[1])]
        self.rel_materials = [MockRelMaterial(self.materials[0], self.pipes)]

    def by_type(self, type_name: str):
        if type_name == "IfcProject":
            return self.projects
        elif type_name == "IfcProduct":
            return self.sites + self.storeys + self.walls + self.pipes
        elif type_name == "IfcRelContainedInSpatialStructure":
            return self.contained
        elif type_name == "IfcRelAggregates":
            return self.aggregates
        elif type_name == "IfcRelConnectsElements":
            return self.connects
        elif type_name == "IfcRelAssociatesMaterial":
            return self.rel_materials
        return []


class InMemoryGraphProvider:
    """In-memory GraphDatabaseProvider for unit testing."""

    def __init__(self):
        self.nodes_by_label = {}
        self.edges_by_type = {}
        self.queries_run = []

    def execute_query(self, query: str, parameters=None):
        self.queries_run.append((query, parameters))
        return []

    def add_node(self, label: str, properties: dict):
        self.nodes_by_label.setdefault(label, []).append(properties)

    def add_nodes_batch(self, label: str, nodes: list):
        self.nodes_by_label.setdefault(label, []).extend(nodes)

    def add_edge(self, source_id, target_id, rel_type: str, properties=None, **kwargs):
        self.edges_by_type.setdefault(rel_type, []).append(
            {"source_id": source_id, "target_id": target_id, "properties": properties or {}}
        )

    def add_edges_batch(self, rel_type: str, edges: list, **kwargs):
        self.edges_by_type.setdefault(rel_type, []).extend(edges)

    def clear(self):
        self.nodes_by_label.clear()
        self.edges_by_type.clear()


def test_build_ifc_graph_structure():
    model = MockIfcModel()
    graph = build_ifc_graph(model)

    assert "proj-1" in graph
    assert "wall-1" in graph
    assert "pipe-1" in graph
    assert "Material_Copper" in graph

    # Check edges
    edges = list(graph.edges(data=True))
    assert any(e[2]["rel_type"] == "Aggregates" and e[0] == "proj-1" for e in edges)
    assert any(e[2]["rel_type"] == "ContainedIn" and e[0] == "storey-1" for e in edges)
    assert any(e[2]["rel_type"] == "Connects" and e[0] == "wall-1" and e[1] == "wall-2" for e in edges)
    assert any(e[2]["rel_type"] == "HasMaterial" and e[0] == "pipe-1" for e in edges)


def test_build_ifc_graph_summary():
    model = MockIfcModel()
    graph = build_ifc_graph(model)
    summary = build_ifc_graph_summary(graph, violations=[{"element": "wall-1"}])

    assert summary["node_count"] == graph.number_of_nodes()
    assert summary["edge_count"] == graph.number_of_edges()
    assert summary["violation_count"] == 1
    assert "ContainedIn" in summary["relationship_counts"]
    assert "IfcWall" in summary["type_counts"]


def test_ingest_ifc_to_graph_batches():
    model = MockIfcModel()
    provider = InMemoryGraphProvider()
    service = GraphService(provider=provider)

    stats = ingest_ifc_to_graph(model, service, project_id="P123")

    assert stats["nodes"] == 7  # proj, site, storey, 2 walls, pipe, material
    assert stats["edges"] == 7  # 2 aggregates, 3 contained (storey -> 2 walls, 1 pipe), 1 connects, 1 hasmaterial

    # Verify nodes in provider
    assert "IfcWall" in provider.nodes_by_label
    assert len(provider.nodes_by_label["IfcWall"]) == 2
    assert provider.nodes_by_label["IfcWall"][0]["project_id"] == "P123"

    # Verify edges in provider
    assert "CONTAINS" in provider.edges_by_type
    assert "CONNECTS" in provider.edges_by_type
    assert "AGGREGATES" in provider.edges_by_type
    assert "HASMATERIAL" in provider.edges_by_type


def test_render_ifc_graph_returns_summary(monkeypatch):
    mock_open = MagicMock(return_value=MockIfcModel())
    monkeypatch.setattr("ifcopenshell.open", mock_open)
    monkeypatch.setattr("app.modules.ifc_reader.ifc_graph._IFCOPENSHELL_AVAILABLE", True)

    result = render_ifc_graph("fake_model.ifc")

    assert "node_count" in result
    assert "edge_count" in result
    assert "html" not in result  # PyVis HTML is gone!
