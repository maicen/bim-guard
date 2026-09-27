"""Tests for ModelHealthService and data-quality checks inspired by ifc-to-graph-assignment."""

from __future__ import annotations

from typing import Any

from app.services.graph_database import GraphService
from app.services.model_health_service import ModelHealthService


class FakeGraphProvider:
    """In-memory fake provider returning configured mock Cypher query results."""

    def __init__(self, query_responses: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self.query_responses = query_responses or {}
        self.executed_queries: list[str] = []

    def execute_query(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        self.executed_queries.append(query)
        for key, rows in self.query_responses.items():
            if key in query:
                return rows
        return []

    def add_node(self, label: str, properties: dict[str, Any]) -> None:
        pass

    def add_nodes_batch(self, label: str, nodes: list[dict[str, Any]]) -> None:
        pass

    def add_edge(self, source_id: Any, target_id: Any, rel_type: str, properties: dict[str, Any] | None = None, **kwargs) -> None:
        pass

    def add_edges_batch(self, rel_type: str, edges: list[dict[str, Any]], **kwargs) -> None:
        pass

    def clear(self) -> None:
        pass

    def delete_by_project(self, project_id: Any) -> None:
        pass


def test_model_health_service_perfect_model():
    """Verify that a model with 0 violations scores 100.0 and receives Grade A."""
    provider = FakeGraphProvider(query_responses={})
    graph_service = GraphService(provider)
    service = ModelHealthService(graph_service)

    report = service.audit_project(project_id=1, total_elements=150)

    assert report.project_id == 1
    assert report.health_score == 100.0
    assert report.grade == "A"
    assert report.total_elements_audited == 150
    assert report.total_violations == 0
    assert len(report.checks) == 8
    assert all(check.passed for check in report.checks)


def test_model_health_service_with_violations():
    """Verify that models with missing fire ratings and unassigned storeys receive deductions."""
    responses = {
        "fire_rating IS NULL": [
            {"guid": "door-1", "name": "Door 101", "type": "IfcDoor"},
            {"guid": "door-2", "name": "Door 102", "type": "IfcDoor"},
        ],
        "WHERE storeys = 0": [
            {"guid": "wall-1", "name": "Wall 1", "type": "IfcWall"},
        ],
        "s.ifc_type = 'IfcSpace'": [
            {"guid": "space-1", "name": "", "type": "IfcSpace"},
        ],
    }
    provider = FakeGraphProvider(query_responses=responses)
    graph_service = GraphService(provider)
    service = ModelHealthService(graph_service)

    report = service.audit_project(project_id=42, total_elements=80)

    assert report.project_id == 42
    assert report.health_score < 100.0
    assert report.total_violations == 4

    checks_by_key = {c.key: c for c in report.checks}
    assert checks_by_key["doors-missing-fire-rating"].passed is False
    assert checks_by_key["doors-missing-fire-rating"].violation_count == 2
    assert "Pset_DoorCommon" in checks_by_key["doors-missing-fire-rating"].recommendation

    assert checks_by_key["unassigned-storeys"].passed is False
    assert checks_by_key["unassigned-storeys"].violation_count == 1

    assert checks_by_key["spaces-missing-attributes"].passed is False
    assert checks_by_key["spaces-missing-attributes"].violation_count == 1
