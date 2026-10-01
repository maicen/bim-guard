"""Tests for GraphRagService and its API contracts."""

import asyncio
from unittest.mock import MagicMock

from app.modules.contracts.graph import (
    GraphRagCitation,
    GraphRagContextSummary,
    GraphRagQueryRequest,
    GraphRagQueryResponse,
    GraphRagStep,
    GraphRagToolCall,
)
from app.services.graph_rag_service import GraphRagService


def test_graph_rag_contracts_validation():
    """Verify serialization and validation of Graph-RAG contracts."""
    req = GraphRagQueryRequest(query="What is the fire rating of corridor doors?", scope="hybrid")
    assert req.scope == "hybrid"
    assert req.query == "What is the fire rating of corridor doors?"

    citation = GraphRagCitation(
        id="doc_1005",
        source_type="document",
        title="Section 1005: Means of Egress Sizing",
        reference="Section 1005",
        snippet="Corridors shall have a minimum fire resistance rating of 1 hour.",
        page_number=45,
    )
    assert citation.source_type == "document"
    assert citation.page_number == 45

    step = GraphRagStep(
        step_index=0,
        title="Entity Extraction",
        description="Found IfcDoor",
        status="done",
    )
    assert step.step_index == 0

    tool_call = GraphRagToolCall(
        tool_name="query_ifc_model_graph",
        arguments={"project_id": 1, "primary_class": "IfcDoor"},
        output_summary="Retrieved 5 doors",
        cypher_query="MATCH (d:IfcDoor) RETURN d",
        status="success",
    )
    assert tool_call.status == "success"

    resp = GraphRagQueryResponse(
        project_id=1,
        scope="hybrid",
        answer="Doors comply with Section 1005 [Doc: Section 1005, p. 45].",
        citations=[citation],
        tool_calls=[tool_call],
        reasoning_steps=[step],
        cypher_queries=["MATCH (d:IfcDoor) RETURN d"],
        suggested_followups=["Check door widths"],
        subgraph_data={},
    )
    assert resp.project_id == 1
    assert len(resp.citations) == 1
    assert len(resp.tool_calls) == 1


def test_graph_rag_service_hybrid_query():
    """Verify GraphRagService executes both document and model queries with simulated graph records."""
    mock_graph = MagicMock()
    mock_graph.provider = MagicMock()

    # Mock execute for document search and model search
    def mock_execute(cypher: str, params: dict):
        if "DocumentSection" in cypher:
            return [
                {
                    "id": "doc_1_s1",
                    "title": "Corridor Fire Doors",
                    "sec_num": "716.2",
                    "summary": "Corridor doors require 60-minute fire resistance rating.",
                    "page": 12,
                    "target_classes": ["IfcDoor"],
                }
            ]
        elif "IfcDoor" in cypher or "IfcProduct" in cypher:
            return [
                {
                    "guid": "2O2$4Drb52xP2wt",
                    "name": "Single-Flush Door 01",
                    "ifc_type": "IfcDoor",
                    "fire_rating": "60 min",
                    "space_name": "Corridor 101",
                    "storey_name": "Level 1",
                }
            ]
        elif "ifc_classes" in cypher or "count(n)" in cypher:
            return [{"class_name": "IfcDoor", "element_count": 12}]
        return []

    mock_graph.execute.side_effect = mock_execute

    service = GraphRagService(graph_service=mock_graph)

    # 1. Test context summary
    context = service.get_project_context_summary(project_id=42)
    assert isinstance(context, GraphRagContextSummary)
    assert context.project_id == 42
    assert context.total_models == 0
    assert context.is_graph_ready is True
    assert context.has_ifc_model is True
    assert context.total_elements == 12

    # 2. Test hybrid query
    req = GraphRagQueryRequest(
        query="Do our corridor doors meet the 60-minute fire rating in the specification?",
        scope="hybrid",
    )
    response = asyncio.run(service.query(project_id=42, request=req))

    assert isinstance(response, GraphRagQueryResponse)
    assert response.project_id == 42
    assert response.scope == "hybrid"
    assert len(response.citations) >= 2
    assert any(c.source_type == "document" for c in response.citations)
    assert any(c.source_type == "model" for c in response.citations)
    assert len(response.reasoning_steps) >= 3
    assert len(response.tool_calls) >= 2
    assert len(response.suggested_followups) > 0


def test_graph_rag_service_streaming():
    """Verify GraphRagService streams SSE packets properly."""
    mock_graph = MagicMock()
    mock_graph.provider = MagicMock()
    mock_graph.execute.return_value = [
        {
            "id": "doc_1_s1",
            "title": "Egress Doors",
            "sec_num": "1005.1",
            "summary": "Minimum width 900mm.",
            "page": 5,
            "target_classes": ["IfcDoor"],
        }
    ]

    service = GraphRagService(graph_service=mock_graph)
    req = GraphRagQueryRequest(query="What is the minimum door width?", scope="document")

    async def _collect():
        events = []
        async for packet in service.stream_query(project_id=1, request=req):
            events.append(packet)
        return events

    events = asyncio.run(_collect())

    assert len(events) > 0
    # Verify SSE format
    assert any("event: step" in e for e in events)
    assert any("event: tool_call" in e for e in events)
    assert any("event: citation" in e for e in events)
    assert any("event: done" in e for e in events)


def test_graph_rag_floors_query():
    """Verify GraphRagService identifies 'floors' as IfcBuildingStorey and returns storey details."""
    mock_graph = MagicMock()
    mock_graph.provider = MagicMock()

    executed_queries = []

    def mock_execute(cypher: str, params: dict):
        executed_queries.append(cypher)
        if "IfcBuildingStorey" in cypher:
            return [
                {
                    "guid": "storey_guid_1",
                    "name": "Level 0 - Ground Floor",
                    "ifc_type": "IfcBuildingStorey",
                    "element_count": 85,
                    "element_types": ["IfcWall", "IfcDoor", "IfcSlab"],
                },
                {
                    "guid": "storey_guid_2",
                    "name": "Level 1 - First Floor",
                    "ifc_type": "IfcBuildingStorey",
                    "element_count": 112,
                    "element_types": ["IfcWall", "IfcDoor", "IfcWindow"],
                },
            ]
        return []

    mock_graph.execute.side_effect = mock_execute

    service = GraphRagService(graph_service=mock_graph)
    req = GraphRagQueryRequest(
        query="How many floors in this model?",
        scope="model",
    )

    response = asyncio.run(service.query(project_id=8, request=req))

    assert response.project_id == 8
    assert response.scope == "model"
    # Verify tool call targets storeys query
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].tool_name == "query_building_storeys"
    assert response.tool_calls[0].arguments.get("primary_class") == "IfcBuildingStorey"

    # Verify citations created for the floors
    assert len(response.citations) == 2
    assert response.citations[0].ifc_type == "IfcBuildingStorey"
    assert "Level 0 - Ground Floor" in response.citations[0].title
    assert "Level 1 - First Floor" in response.citations[1].title

    # Verify answer contains verified facts
    assert ("Level 0" in response.answer and "Ground Floor" in response.answer) or "Total Building Storeys" in response.answer


def test_graph_rag_model_inventory_query():
    """Verify GraphRagService directly handles 'How many models in this project?' and gates irrelevant doc search."""
    mock_graph = MagicMock()
    mock_graph.provider = MagicMock()
    mock_graph.execute.return_value = []

    mock_models_service = MagicMock()
    mock_models_service.list_models.return_value = [
        {
            "id": 101,
            "file_name": "Hospital_Architectural.ifc",
            "role": "primary",
            "is_primary": True,
            "cde_state": "WIP",
            "revision_code": "P01.01",
            "uploaded_at": "2026-09-01T00:00:00Z",
        },
        {
            "id": 102,
            "file_name": "Hospital_Structural.ifc",
            "role": "secondary",
            "is_primary": False,
            "cde_state": "SHARED",
            "revision_code": "P01.02",
            "uploaded_at": "2026-09-02T00:00:00Z",
        },
    ]

    service = GraphRagService(
        graph_service=mock_graph,
        models_service=mock_models_service,
    )

    req = GraphRagQueryRequest(
        query="How many models in this project?",
        scope="hybrid",
    )

    response = asyncio.run(service.query(project_id=5006, request=req))

    assert response.project_id == 5006
    # Tool call must identify model inventory
    tool_names = [t.tool_name for t in response.tool_calls]
    assert "query_model_inventory" in tool_names
    # Document search should be bypassed or produce 0 irrelevant doc citations
    assert all(c.source_type == "model" for c in response.citations)
    assert len(response.citations) == 2
    assert "Hospital_Architectural.ifc" in response.citations[0].title
    assert "Hospital_Structural.ifc" in response.citations[1].title

    # Verify context summary distinguishes attached models from ingested graph
    summary = service.get_project_context_summary(project_id=5006)
    assert summary.total_models == 2
    assert summary.has_ifc_model is True
    assert summary.is_graph_ready is False
    assert summary.total_elements == 0


def test_graph_rag_project_metadata_query():
    """Verify GraphRagService answers project overview queries directly with project metadata."""
    mock_graph = MagicMock()
    mock_graph.provider = MagicMock()

    mock_projects_service = MagicMock()
    mock_projects_service.get_project.return_value = {
        "id": 42,
        "name": "Metro Transit Hub",
        "client_name": "Metropolitan Transit Authority",
        "project_code": "MTH-2026",
        "status": "active",
        "description": "Central intermodal transit terminal.",
    }
    mock_projects_service.get_client_documents_by_project.return_value = []

    mock_models_service = MagicMock()
    mock_models_service.list_models.return_value = []

    service = GraphRagService(
        graph_service=mock_graph,
        models_service=mock_models_service,
        projects_service=mock_projects_service,
    )

    req = GraphRagQueryRequest(
        query="Tell me about this project and who the client is",
        scope="hybrid",
    )

    response = asyncio.run(service.query(project_id=42, request=req))

    assert response.project_id == 42
    tool_names = [t.tool_name for t in response.tool_calls]
    assert "query_project_metadata" in tool_names
    assert len(response.citations) >= 1
    assert "Metro Transit Hub" in response.citations[0].snippet

