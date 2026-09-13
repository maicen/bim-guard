"""Tests for the theme-agnostic graph topology engine.

Covers ``find_orphan_elements`` (app.modules.ifc_reader.ifc_graph) and
``GraphTopologyEngine`` (app.engines.bimguard_graph_engine) directly, plus the
orchestrator's ``_run_graph_intelligence`` wiring that turns orphan records
into ``AuditIssue`` dicts through the same ``RuleEvaluator``/``lift_engine_result``
path ``_run_arch_engine_compliance`` uses for the ARCH engines.

Run: uv run pytest tests/test_graph_engine.py -v
"""

from __future__ import annotations

import networkx as nx
import pytest

from app.engines.bimguard_graph_engine import GraphTopologyEngine
from app.modules.ifc_reader.ifc_graph import find_orphan_elements
from app.services import pipeline_tracker as pt

# ---------------------------------------------------------------------------
# find_orphan_elements
# ---------------------------------------------------------------------------


def _graph_with(nodes: list[tuple[str, dict]], edges: list[tuple[str, str]]) -> nx.DiGraph:
    graph = nx.DiGraph()
    for node_id, attrs in nodes:
        graph.add_node(node_id, **attrs)
    for source, target in edges:
        graph.add_edge(source, target, rel_type="Connects")
    return graph


def test_disconnected_product_is_flagged_orphan():
    graph = _graph_with(
        nodes=[("wall-1", {"ifc_type": "IfcWall", "label": "Wall 1"})],
        edges=[],
    )

    orphans = find_orphan_elements(graph)

    assert orphans == [{"guid": "wall-1", "label": "Wall 1", "ifc_type": "IfcWall", "degree": 0}]


def test_connected_product_is_not_flagged():
    graph = _graph_with(
        nodes=[
            ("storey-1", {"ifc_type": "IfcBuildingStorey", "label": "Level 1"}),
            ("wall-1", {"ifc_type": "IfcWall", "label": "Wall 1"}),
        ],
        edges=[("storey-1", "wall-1")],
    )

    assert find_orphan_elements(graph) == []


def test_spatial_root_types_are_never_flagged_even_with_zero_degree():
    graph = _graph_with(
        nodes=[
            ("project-1", {"ifc_type": "IfcProject", "label": "Project"}),
            ("site-1", {"ifc_type": "IfcSite", "label": "Site"}),
        ],
        edges=[],
    )

    assert find_orphan_elements(graph) == []


def test_material_nodes_are_never_flagged():
    graph = _graph_with(
        nodes=[("Material_Steel", {"ifc_type": "IfcMaterial", "label": "Steel"})],
        edges=[],
    )

    assert find_orphan_elements(graph) == []


# ---------------------------------------------------------------------------
# GraphTopologyEngine
# ---------------------------------------------------------------------------


def test_engine_fails_an_orphan_record():
    engine = GraphTopologyEngine()

    result = engine.evaluate(
        {"guid": "wall-1", "label": "Wall 1", "ifc_type": "IfcWall", "degree": 0}
    )

    assert result.rule_type == "GRAPH-TOPOLOGY-001"
    assert result.status == "FAIL"
    assert result.element_id == "wall-1"
    assert result.details["passes"] is False


def test_engine_passes_a_connected_record():
    engine = GraphTopologyEngine()

    result = engine.evaluate(
        {"guid": "wall-1", "label": "Wall 1", "ifc_type": "IfcWall", "degree": 2}
    )

    assert result.status == "PASS"
    assert result.details["passes"] is True


def test_engine_never_fails_a_spatial_root_regardless_of_degree():
    engine = GraphTopologyEngine()

    result = engine.evaluate(
        {"guid": "project-1", "label": "Project", "ifc_type": "IfcProject", "degree": 0}
    )

    assert result.status == "PASS"


# ---------------------------------------------------------------------------
# Orchestrator wiring: _run_graph_intelligence
# ---------------------------------------------------------------------------


class _FakeReader:
    def __init__(self, ifc_file):
        self.ifc_file = ifc_file


@pytest.fixture(autouse=True)
def _clear_trackers():
    pt.TRACKERS.clear()
    yield
    pt.TRACKERS.clear()


def test_run_graph_intelligence_lifts_orphans_into_issues(monkeypatch):
    from app.modules.orchestrator import BIMGuard_App

    graph = _graph_with(
        nodes=[("wall-1", {"ifc_type": "IfcWall", "label": "Wall 1"})],
        edges=[],
    )
    monkeypatch.setattr(
        "app.modules.ifc_reader.ifc_graph.build_ifc_graph", lambda model: graph
    )

    reader = _FakeReader(ifc_file=object())
    summary, issues, error = BIMGuard_App._run_graph_intelligence(reader, project_id=999)

    assert error is None
    assert summary["node_count"] == 1
    assert len(issues) == 1
    assert issues[0]["element_id"] == "wall-1"
    assert issues[0]["mechanism"] == "GRAPH-TOPOLOGY-001"


def test_run_graph_intelligence_reports_progress_under_its_own_run_key(monkeypatch):
    from app.modules.orchestrator import BIMGuard_App

    graph = _graph_with(nodes=[], edges=[])
    monkeypatch.setattr(
        "app.modules.ifc_reader.ifc_graph.build_ifc_graph", lambda model: graph
    )

    reader = _FakeReader(ifc_file=object())
    BIMGuard_App._run_graph_intelligence(reader, project_id=999)

    graph_snapshot = pt.snapshot(999, run_key="graph")
    assert graph_snapshot["engines"]["GRAPH-001"]["status"] == "complete"

    # The default run_key for the same project is untouched -- a concurrent
    # corrosion run for project 999 would not see this reset its progress.
    default_snapshot = pt.snapshot(999)
    assert default_snapshot["engines"]["GRAPH-001"] == {"status": "pending"}


def test_run_graph_intelligence_returns_nothing_without_a_reader():
    from app.modules.orchestrator import BIMGuard_App

    summary, issues, error = BIMGuard_App._run_graph_intelligence(None, project_id=1)

    assert (summary, issues, error) == (None, [], None)


# ---------------------------------------------------------------------------
# Orchestrator wiring: graph_service persistence
# ---------------------------------------------------------------------------


class _FakeGraphService:
    """Records ingest_ifc_to_graph's batch calls instead of touching a real DB."""

    def __init__(self):
        self.node_batches: list[tuple[str, list[dict]]] = []
        self.edge_batches: list[tuple[str, list[dict]]] = []

    def add_nodes_batch(self, label, nodes):
        self.node_batches.append((label, list(nodes)))

    def add_edges_batch(self, rel_type, edges, *, from_label=None, to_label=None):
        self.edge_batches.append((rel_type, list(edges)))


def test_run_graph_intelligence_persists_into_the_injected_graph_service(monkeypatch):
    from app.modules.orchestrator import BIMGuard_App

    graph = _graph_with(
        nodes=[
            ("storey-1", {"ifc_type": "IfcBuildingStorey", "label": "Level 1"}),
            ("wall-1", {"ifc_type": "IfcWall", "label": "Wall 1"}),
        ],
        edges=[("storey-1", "wall-1")],
    )
    monkeypatch.setattr(
        "app.modules.ifc_reader.ifc_graph.build_ifc_graph", lambda model: graph
    )

    reader = _FakeReader(ifc_file=object())
    fake_service = _FakeGraphService()

    summary, issues, error = BIMGuard_App._run_graph_intelligence(
        reader, project_id=999, graph_service=fake_service
    )

    assert error is None
    assert issues == []  # the wall is connected -- no orphan finding
    assert sum(len(nodes) for _, nodes in fake_service.node_batches) == 2
    assert sum(len(edges) for _, edges in fake_service.edge_batches) == 1


def test_graph_persistence_failure_does_not_break_orphan_findings(monkeypatch):
    from app.modules.orchestrator import BIMGuard_App

    graph = _graph_with(
        nodes=[("wall-1", {"ifc_type": "IfcWall", "label": "Wall 1"})],
        edges=[],
    )
    monkeypatch.setattr(
        "app.modules.ifc_reader.ifc_graph.build_ifc_graph", lambda model: graph
    )

    class _BrokenGraphService:
        def add_nodes_batch(self, label, nodes):
            raise ConnectionError("Neo4j is unreachable")

    reader = _FakeReader(ifc_file=object())
    summary, issues, error = BIMGuard_App._run_graph_intelligence(
        reader, project_id=999, graph_service=_BrokenGraphService()
    )

    assert error is None
    assert len(issues) == 1
    assert issues[0]["element_id"] == "wall-1"
