"""Tests for DocumentGraphService (Graph RAG and TOC Knowledge Graph Projection)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.modules.document_parsing.smart_toc_generator import build_smart_toc
from app.services.document_graph_service import DocumentGraphService
from app.services.graph_database import GraphService


class MockGraphDatabaseProvider:
    """Mock graph provider capturing Cypher queries and batch mutations."""

    def __init__(self):
        self.nodes: dict[str, list[dict[str, Any]]] = {}
        self.edges: dict[str, list[dict[str, Any]]] = {}
        self.executed_queries: list[tuple[str, dict[str, Any]]] = []

    def execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        self.executed_queries.append((query, parameters or {}))
        return [{"s": {"id": parameters.get("sec_id", "s1")}, "children": [], "citations": []}]

    def add_node(self, label: str, properties: Dict[str, Any]) -> None:
        self.nodes.setdefault(label, []).append(properties)

    def add_nodes_batch(self, label: str, nodes: List[Dict[str, Any]]) -> None:
        self.nodes.setdefault(label, []).extend(nodes)

    def add_edge(
        self,
        source_id: Any,
        target_id: Any,
        rel_type: str,
        properties: Optional[Dict[str, Any]] = None,
        *,
        from_label: Optional[str] = None,
        to_label: Optional[str] = None,
    ) -> None:
        self.edges.setdefault(rel_type, []).append({"source_id": source_id, "target_id": target_id})

    def add_edges_batch(
        self,
        rel_type: str,
        edges: List[Dict[str, Any]],
        *,
        from_label: Optional[str] = None,
        to_label: Optional[str] = None,
    ) -> None:
        self.edges.setdefault(rel_type, []).extend(edges)

    def clear(self) -> None:
        self.nodes.clear()
        self.edges.clear()

    def delete_by_project(self, project_id: Any) -> None:
        pass


def test_document_graph_service_availability():
    service_none = DocumentGraphService(None)
    assert not service_none.is_available()

    mock_provider = MockGraphDatabaseProvider()
    graph_service = GraphService(mock_provider)
    service_active = DocumentGraphService(graph_service)
    assert service_active.is_available()


def test_document_graph_service_ingest_tree():
    mock_provider = MockGraphDatabaseProvider()
    graph_service = GraphService(mock_provider)
    doc_graph_service = DocumentGraphService(graph_service)

    chunks = [
        {
            "section_number": "3",
            "section_name": "CHAPTER 3 - EGRESS",
            "text": "General egress provisions.",
            "char_count": 26,
            "page_number": 1,
        },
        {
            "section_number": "3.1",
            "section_name": "Corridor Doors",
            "text": "Corridor doors shall comply with Section 3.2 and swing clear.",
            "char_count": 60,
            "page_number": 2,
        },
        {
            "section_number": "3.2",
            "section_name": "Door Clearance",
            "text": "Clear width of exit doors must exceed 850 mm.",
            "char_count": 45,
            "page_number": 3,
        },
    ]

    tree, flat = build_smart_toc(chunks)
    counts = doc_graph_service.ingest_document_tree(101, tree, flat, document_title="Building Code 2026")

    assert counts["nodes"] > 0
    assert counts["edges"] > 0

    # Verify Document and DocumentSection nodes were added
    assert "Document" in mock_provider.nodes
    assert mock_provider.nodes["Document"][0]["document_id"] == 101

    assert "DocumentSection" in mock_provider.nodes
    assert len(mock_provider.nodes["DocumentSection"]) == 3

    # Verify IfcClass nodes for detected classes (IfcDoor, IfcSpace)
    assert "IfcClass" in mock_provider.nodes
    ifc_classes = [n["id"] for n in mock_provider.nodes["IfcClass"]]
    assert "IfcDoor" in ifc_classes

    # Verify PARENT_OF hierarchy edges exist
    assert "PARENT_OF" in mock_provider.edges
    parent_edges = mock_provider.edges["PARENT_OF"]
    assert any(e["source_id"] == "doc_101_s0" and e["target_id"] == "doc_101_s1" for e in parent_edges)

    # Verify CITES cross-reference edge exists from 3.1 -> 3.2
    assert "CITES" in mock_provider.edges
    cite_edges = mock_provider.edges["CITES"]
    assert any(e["source_id"] == "doc_101_s1" and e["target_id"] == "doc_101_s2" for e in cite_edges)

    # Verify APPLIES_TO edge to IfcClass
    assert "APPLIES_TO" in mock_provider.edges
    applies_edges = mock_provider.edges["APPLIES_TO"]
    assert any(e["target_id"] == "IfcDoor" for e in applies_edges)


def test_document_graph_service_get_subgraph():
    mock_provider = MockGraphDatabaseProvider()
    graph_service = GraphService(mock_provider)
    doc_graph_service = DocumentGraphService(graph_service)

    result = doc_graph_service.get_section_subgraph(101, "s1")
    assert "records" in result
    assert len(result["records"]) == 1
    assert len(mock_provider.executed_queries) == 1
    query, params = mock_provider.executed_queries[0]
    assert "MATCH (s:DocumentSection" in query
    assert params["sec_id"] == "doc_101_s1"
