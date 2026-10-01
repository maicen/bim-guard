"""Tests for the GraphRAG query console's server-scoped Cypher presets.

Runs against a real embedded KùzuDB (not mocked) -- these presets exist
specifically because free-form Cypher would leak across projects, so the
thing worth verifying is that the *preset* text is both syntactically valid
against a real backend and actually scopes to the given project_id, not
just that the Python around it behaves.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.services.graph_database import GraphService
from app.services.graph_query_presets import (
    GRAPH_QUERY_PRESETS,
    get_preset,
    run_preset,
)


class MockGraphProvider:
    """Mock graph provider simulating project-scoped Cypher queries for presets."""

    def __init__(self):
        self.nodes = []
        self.edges = []

    def add_node(self, label: str, properties: dict[str, Any]) -> None:
        self.nodes.append({"label": label, **properties})

    def add_nodes_batch(self, label: str, nodes: list[dict[str, Any]]) -> None:
        for node in nodes:
            self.add_node(label, node)

    def add_edge(
        self,
        source_id: Any,
        target_id: Any,
        rel_type: str,
        properties: dict[str, Any] | None = None,
        *,
        from_label: str | None = None,
        to_label: str | None = None,
    ) -> None:
        self.edges.append({"source_id": source_id, "target_id": target_id, "rel_type": rel_type, **(properties or {})})

    def add_edges_batch(
        self,
        rel_type: str,
        edges: list[dict[str, Any]],
        *,
        from_label: str | None = None,
        to_label: str | None = None,
    ) -> None:
        for edge in edges:
            self.add_edge(edge["source_id"], edge["target_id"], rel_type, edge.get("properties"), from_label=from_label, to_label=to_label)

    def execute_query(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        params = parameters or {}
        pid = str(params.get("project_id", ""))

        if "RETURN n.ifc_type AS type, count(n) AS count" in query:
            counts: dict[str, int] = {}
            for n in self.nodes:
                if str(n.get("project_id")) == pid:
                    t = n.get("ifc_type", n.get("label"))
                    counts[t] = counts.get(t, 0) + 1
            return [{"type": t, "count": c} for t, c in counts.items()]

        if "count(r) AS degree" in query or "RETURN n.name AS name" in query:
            results = []
            for n in self.nodes:
                if str(n.get("project_id")) == pid:
                    deg = sum(1 for e in self.edges if e["source_id"] == n.get("id") or e["target_id"] == n.get("id"))
                    results.append({"name": n.get("name"), "degree": deg})
            return sorted(results, key=lambda x: x.get("degree", 0), reverse=True)

        if "guid: $guid" in query or "n.guid = $guid" in query or "guid = $guid" in query:
            guid = str(params.get("guid", ""))
            src_node = next((n for n in self.nodes if n.get("guid") == guid and str(n.get("project_id")) == pid), None)
            if not src_node:
                return []
            src_id = src_node.get("id")
            neighbor_ids = {e["target_id"] for e in self.edges if e["source_id"] == src_id} | {e["source_id"] for e in self.edges if e["target_id"] == src_id}
            return [{"name": n.get("name"), "guid": n.get("guid"), "type": n.get("ifc_type")} for n in self.nodes if n.get("id") in neighbor_ids and str(n.get("project_id")) == pid]

        return []

    def clear(self) -> None:
        self.nodes.clear()
        self.edges.clear()


@pytest.fixture
def graph_service() -> GraphService:
    provider = MockGraphProvider()
    service = GraphService(provider=provider)

    # Two projects' worth of data, deliberately interleaved, so any preset
    # that forgot to filter by project_id would show up immediately.
    service.add_nodes_batch(
        "IfcWall",
        [
            {"id": "P1-W1", "guid": "W1", "name": "Wall 1", "ifc_type": "IfcWall", "project_id": "1"},
            {"id": "P2-W1", "guid": "W1", "name": "Other Wall", "ifc_type": "IfcWall", "project_id": "2"},
        ],
    )
    service.add_nodes_batch(
        "IfcDoor",
        [
            {"id": "P1-D1", "guid": "D1", "name": "Door 1", "ifc_type": "IfcDoor", "project_id": "1"},
            {"id": "P1-D2", "guid": "D2", "name": "Door 2", "ifc_type": "IfcDoor", "project_id": "1"},
        ],
    )
    service.add_edges_batch(
        "CONTAINS",
        [
            {"source_id": "P1-W1", "target_id": "P1-D1", "properties": {}},
            {"source_id": "P1-W1", "target_id": "P1-D2", "properties": {}},
        ],
        from_label="IfcWall",
        to_label="IfcDoor",
    )
    return service


def test_every_preset_is_registered_with_a_unique_key():
    keys = [preset.key for preset in GRAPH_QUERY_PRESETS]
    assert len(keys) == len(set(keys))
    assert len(keys) >= 1


def test_get_preset_returns_none_for_an_unknown_key():
    assert get_preset("not-a-real-preset") is None


def test_element_counts_by_type_is_scoped_to_the_given_project(graph_service):
    preset = get_preset("element-counts-by-type")

    rows = run_preset(graph_service, preset, project_id=1, params={})

    counts = {row["type"]: row["count"] for row in rows}
    assert counts == {"IfcWall": 1, "IfcDoor": 2}  # not project 2's wall


def test_most_connected_elements_is_scoped_to_the_given_project(graph_service):
    preset = get_preset("most-connected-elements")

    rows = run_preset(graph_service, preset, project_id=1, params={})

    names = {row["name"] for row in rows}
    assert names == {"Wall 1", "Door 1", "Door 2"}
    assert "Other Wall" not in names


def test_element_neighbors_requires_its_declared_guid_param(graph_service):
    preset = get_preset("element-neighbors")

    rows = run_preset(graph_service, preset, project_id=1, params={"guid": "W1"})

    names = {row["name"] for row in rows}
    assert names == {"Door 1", "Door 2"}


def test_run_preset_rejects_a_missing_required_param(graph_service):
    preset = get_preset("element-neighbors")

    with pytest.raises(ValueError, match="missing required params"):
        run_preset(graph_service, preset, project_id=1, params={})


def test_run_preset_rejects_an_undeclared_extra_param(graph_service):
    preset = get_preset("element-counts-by-type")

    with pytest.raises(ValueError, match="does not accept params"):
        run_preset(graph_service, preset, project_id=1, params={"guid": "W1"})


def test_run_preset_never_accepts_project_id_as_a_param(graph_service):
    """project_id is always the function's own keyword arg.

    A caller cannot smuggle a different one through `params` to read
    another project's data.
    """
    preset = get_preset("element-counts-by-type")

    with pytest.raises(ValueError, match="does not accept params"):
        run_preset(graph_service, preset, project_id=1, params={"project_id": "2"})
