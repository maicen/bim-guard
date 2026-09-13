"""Unit tests for graph routes, centrality metrics, and on-call API endpoints."""

from __future__ import annotations

from unittest.mock import patch

import networkx as nx
from fastapi.testclient import TestClient

from app.api.projects import get_project_access_checker
from app.main import app
from app.modules.ifc_reader.ifc_graph import (
    compute_graph_centrality,
    get_centrality_consequence_multiplier,
)


def test_compute_graph_centrality():
    graph = nx.DiGraph()
    # Star graph topology around a central hub
    graph.add_node("HUB", ifc_type="IfcBuildingStorey")
    for i in range(1, 6):
        node = f"NODE_{i}"
        graph.add_node(node, ifc_type="IfcWall")
        graph.add_edge("HUB", node, rel_type="Contains")

    centralities = compute_graph_centrality(graph)
    assert len(centralities) == 6
    assert centralities["HUB"]["degree"] == 1.0
    assert centralities["HUB"]["closeness"] == 1.0

    # Test multiplier
    hub_mult = get_centrality_consequence_multiplier("HUB", centralities)
    leaf_mult = get_centrality_consequence_multiplier("NODE_1", centralities)

    assert hub_mult > leaf_mult
    assert 1.0 <= leaf_mult <= 1.5
    assert 1.0 < hub_mult <= 1.5


def test_graph_routes_endpoints():
    client = TestClient(app)

    # Bypass project access checker for test
    app.dependency_overrides[get_project_access_checker] = lambda: lambda pid: None

    try:
        # Test proof graph endpoint
        res = client.get("/api/graph/101/proof/ISSUE-99")
        assert res.status_code == 200
        data = res.json()
        assert data["issue_id"] == "ISSUE-99"
        assert "nodes" in data
        assert "edges" in data
        assert "explanation" in data

        # Test status endpoint with no file (graceful fallback)
        with patch("app.services.models_service.ModelsService.resolve_primary_path", return_value=None):
            res = client.get("/api/graph/101/status")
            assert res.status_code == 200
            status_data = res.json()
            assert status_data["project_id"] == 101
            assert status_data["node_count"] == 0

    finally:
        app.dependency_overrides.pop(get_project_access_checker, None)
