"""Unit tests for graph routes, centrality metrics, and on-call API endpoints."""

from __future__ import annotations

from unittest.mock import patch

import networkx as nx
from fastapi.testclient import TestClient

from app.api.projects import get_project_access_checker
from app.main import app
from app.modules.ifc_reader.ifc_graph import (
    build_spatial_tree,
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


def test_build_spatial_tree_rolls_aggregates_and_contained_in_into_one_tree():
    graph = nx.DiGraph()
    graph.add_node("PROJ", ifc_type="IfcProject", label="Project")
    graph.add_node("BLDG", ifc_type="IfcBuilding", label="Building")
    graph.add_node("STOREY", ifc_type="IfcBuildingStorey", label="Level 1")
    graph.add_node("WALL", ifc_type="IfcWall", label="Wall 1")
    graph.add_edge("PROJ", "BLDG", rel_type="Aggregates")
    graph.add_edge("BLDG", "STOREY", rel_type="Aggregates")
    graph.add_edge("STOREY", "WALL", rel_type="ContainedIn")

    tree = build_spatial_tree(graph)

    assert tree["guid"] == "PROJ"
    assert tree["children"][0]["guid"] == "BLDG"
    assert tree["children"][0]["children"][0]["guid"] == "STOREY"
    assert tree["children"][0]["children"][0]["children"][0]["guid"] == "WALL"


def test_build_spatial_tree_ignores_non_spatial_edges():
    graph = nx.DiGraph()
    graph.add_node("PROJ", ifc_type="IfcProject", label="Project")
    graph.add_node("MAT", ifc_type="IfcMaterial", label="Steel")
    graph.add_edge("PROJ", "MAT", rel_type="HasMaterial")

    tree = build_spatial_tree(graph)

    assert tree["children"] == []


def test_build_spatial_tree_returns_none_without_an_ifcproject_node():
    graph = nx.DiGraph()
    graph.add_node("WALL", ifc_type="IfcWall", label="Wall 1")

    assert build_spatial_tree(graph) is None


def test_build_spatial_tree_caps_children_and_reports_truncation():
    graph = nx.DiGraph()
    graph.add_node("PROJ", ifc_type="IfcProject", label="Project")
    for i in range(5):
        node = f"WALL_{i}"
        graph.add_node(node, ifc_type="IfcWall", label=node)
        graph.add_edge("PROJ", node, rel_type="ContainedIn")

    tree = build_spatial_tree(graph, max_children_per_node=2)

    assert len(tree["children"]) == 2
    assert tree["truncated_count"] == 3


def test_graph_routes_endpoints():
    client = TestClient(app)

    # Bypass project access checker for test
    app.dependency_overrides[get_project_access_checker] = lambda: lambda pid: None

    try:
        # Proof graph endpoint: no analysis has ever run for this project, so
        # no slug's cached result contains ISSUE-99 -- 404, not a fabricated stand-in.
        res = client.get("/api/graph/101/proof/ISSUE-99")
        assert res.status_code == 404

        # Test status endpoint with no file (graceful fallback)
        with patch("app.services.models_service.ModelsService.resolve_primary_path", return_value=None):
            res = client.get("/api/graph/101/status")
            assert res.status_code == 200
            status_data = res.json()
            assert status_data["project_id"] == 101
            assert status_data["node_count"] == 0

        # Test spatial-tree endpoint with no file (graceful fallback)
        with patch("app.services.models_service.ModelsService.resolve_primary_path", return_value=None):
            res = client.get("/api/graph/101/spatial-tree")
            assert res.status_code == 200
            tree_data = res.json()
            assert tree_data["project_id"] == 101
            assert tree_data["root"] is None

        # Test element relationships endpoint with no file (graceful fallback)
        with patch("app.services.models_service.ModelsService.resolve_primary_path", return_value=None):
            res = client.get("/api/graph/101/element/SOME-GUID/relationships")
            assert res.status_code == 200
            rel_data = res.json()
            assert rel_data["project_id"] == 101
            assert rel_data["guid"] == "SOME-GUID"
            assert rel_data["exists"] is False

    finally:
        app.dependency_overrides.pop(get_project_access_checker, None)


def test_get_issue_proof_uses_the_real_stored_issue_not_a_dummy():
    from app.modules.comparator.issue_schema import Issue, RiskBand

    real_issue = Issue(
        id="GC-001-WALL-GUID-1",
        element_id="WALL-GUID-1",
        rule_id="GC-001",
        title="Galvanic corrosion risk between dissimilar metals",
        band=RiskBand.HIGH,
        score=0.82,
        mechanism="GC-001",
        mitigation="Insert a dielectric isolator between the two metals.",
    )

    client = TestClient(app)
    app.dependency_overrides[get_project_access_checker] = lambda: lambda pid: None

    def fake_run_analysis(slug, project_id, **kwargs):
        if slug == "corrosion":
            return {"audit_issues": [real_issue]}
        return {"audit_issues": []}

    try:
        with patch("app.services.analysis_runner.run_analysis", side_effect=fake_run_analysis):
            res = client.get("/api/graph/202/proof/GC-001-WALL-GUID-1")
            assert res.status_code == 200
            data = res.json()
            assert data["issue_id"] == "GC-001-WALL-GUID-1"
            assert data["rule_id"] == "GC-001"
            assert data["element_id"] == "WALL-GUID-1"
            # Not the old hardcoded dummy's fixed values
            assert data["element_id"] != "2O2Fr$t4X7Zf8NOew3FL9r"
    finally:
        app.dependency_overrides.pop(get_project_access_checker, None)
