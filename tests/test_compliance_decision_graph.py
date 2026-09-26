"""Tests for causal compliance decision lineage and W3C PROV-O audit graph."""

from __future__ import annotations

from typing import Any

import rdflib

from app.services.compliance_decision_graph import (
    analyze_rule_impact,
    export_w3c_prov_rdf,
    ingest_compliance_verdicts,
    trace_decision_causal_chain,
)
from app.services.graph_database import GraphService


class FakeGraphProvider:
    """In-memory mock graph provider for testing Cypher execution and batch operations."""

    def __init__(self):
        self.nodes: dict[str, list[dict[str, Any]]] = {}
        self.edges: dict[str, list[dict[str, Any]]] = {}
        self.executed_queries: list[tuple[str, dict[str, Any]]] = []

    def execute_query(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        self.executed_queries.append((query, parameters or {}))
        # Mock trace response when queried
        if "MATCH (v:ComplianceVerdict" in query and "issue_id" in str(parameters):
            return [
                {
                    "v": {
                        "id": "verdict_ISSUE-101",
                        "verdict_id": "verdict_ISSUE-101",
                        "issue_id": "ISSUE-101",
                        "project_id": "1",
                        "element_id": "3Kf7q8XzR1pP2mN4gV8xQ",
                        "rule_id": "ARCH-EGRESS-001",
                        "outcome": "FAIL",
                        "risk_band": "critical",
                        "score": 0.89,
                        "mechanism": "ARCH-EGRESS-001",
                    },
                    "r": {
                        "id": "rule_ARCH-EGRESS-001",
                        "rule_id": "ARCH-EGRESS-001",
                        "standard": "IBC 2024",
                        "clause": "1005.1",
                    },
                    "e": {
                        "guid": "3Kf7q8XzR1pP2mN4gV8xQ",
                        "name": "Single Door 900x2100",
                        "ifc_type": "IfcDoor",
                    },
                    "parents": [
                        {"id": "storey_1", "guid": "storey_1", "name": "Level 1", "ifc_type": "IfcBuildingStorey"}
                    ],
                }
            ]
        elif "MATCH (v:ComplianceVerdict" in query and "rule_id" in str(parameters):
            return [
                {
                    "v": {
                        "id": "verdict_ISSUE-101",
                        "issue_id": "ISSUE-101",
                        "outcome": "FAIL",
                        "risk_band": "critical",
                        "score": 0.89,
                        "title": "Clear width below minimum",
                    },
                    "e": {
                        "guid": "3Kf7q8XzR1pP2mN4gV8xQ",
                        "name": "Single Door 900x2100",
                        "ifc_type": "IfcDoor",
                    },
                }
            ]
        return []

    def add_node(self, label: str, properties: dict[str, Any]) -> None:
        self.nodes.setdefault(label, []).append(properties)

    def add_nodes_batch(self, label: str, nodes: list[dict[str, Any]]) -> None:
        self.nodes.setdefault(label, []).extend(nodes)

    def add_edge(self, source_id: Any, target_id: Any, rel_type: str, properties: dict[str, Any] | None = None, **kwargs) -> None:
        self.edges.setdefault(rel_type, []).append({"source_id": source_id, "target_id": target_id, "properties": properties or {}})

    def add_edges_batch(self, rel_type: str, edges: list[dict[str, Any]], **kwargs) -> None:
        self.edges.setdefault(rel_type, []).extend(edges)

    def clear(self) -> None:
        self.nodes.clear()
        self.edges.clear()

    def delete_by_project(self, project_id: Any) -> None:
        pass


def _sample_issues() -> list[dict[str, Any]]:
    return [
        {
            "id": "ISSUE-101",
            "rule_id": "ARCH-EGRESS-001",
            "element_id": "3Kf7q8XzR1pP2mN4gV8xQ",
            "title": "Door clear width below minimum egress requirement",
            "band": "critical",
            "score": 0.89,
            "mechanism": "ARCH-EGRESS-001",
            "mitigation": "Widen door clear width to >= 900mm",
            "citations": [{"standard": "IBC 2024", "clause": "1005.1"}],
        },
        {
            "id": "ISSUE-102",
            "rule_id": "ARCH-SPATIAL-001",
            "element_id": "4Lg8r9YaS2qQ3nO5hW9yR",
            "title": "Corridor width restriction",
            "band": "medium",
            "score": 0.65,
            "mechanism": "ARCH-SPATIAL-001",
            "citations": [{"standard": "IBC 2024", "clause": "1020.2"}],
        },
    ]


def test_ingest_compliance_verdicts():
    provider = FakeGraphProvider()
    graph_service = GraphService(provider)

    stats = ingest_compliance_verdicts(graph_service, "1", _sample_issues())

    assert stats["verdicts"] == 2
    assert stats["rules"] == 2
    assert "ComplianceVerdict" in provider.nodes
    assert len(provider.nodes["ComplianceVerdict"]) == 2
    assert provider.nodes["ComplianceVerdict"][0]["outcome"] == "FAIL"
    assert provider.nodes["ComplianceVerdict"][0]["element_id"] == "3Kf7q8XzR1pP2mN4gV8xQ"
    assert len(provider.executed_queries) == 1  # Link query was executed


def test_trace_decision_causal_chain():
    provider = FakeGraphProvider()
    graph_service = GraphService(provider)

    chain = trace_decision_causal_chain(graph_service, "1", "ISSUE-101")

    assert chain["issue_id"] == "ISSUE-101"
    assert chain["verdict"]["outcome"] == "FAIL"
    assert chain["rule"]["standard"] == "IBC 2024"
    assert chain["element"]["ifc_type"] == "IfcDoor"
    assert len(chain["lineage_nodes"]) == 4  # Verdict, Rule, Element, Storey
    assert len(chain["lineage_edges"]) == 3  # TRIGGERED_BY, EVALUATED_ELEMENT, CONTAINS
    assert "evaluated by ARCH-EGRESS-001 against IBC 2024 §1005.1" in chain["prov_summary"]


def test_analyze_rule_impact():
    provider = FakeGraphProvider()
    graph_service = GraphService(provider)

    impact = analyze_rule_impact(graph_service, "1", "ARCH-EGRESS-001")

    assert impact["rule_id"] == "ARCH-EGRESS-001"
    assert impact["total_findings"] == 1
    assert impact["total_elements_evaluated"] == 1
    assert impact["impacted_elements"][0]["element_id"] == "3Kf7q8XzR1pP2mN4gV8xQ"


def test_export_w3c_prov_rdf():
    turtle_output = export_w3c_prov_rdf("1", _sample_issues())

    assert turtle_output is not None
    assert "@prefix prov: <http://www.w3.org/ns/prov#> ." in turtle_output

    # Parse with rdflib to prove valid Turtle format
    g = rdflib.Graph()
    g.parse(data=turtle_output, format="turtle")

    PROV = rdflib.Namespace("http://www.w3.org/ns/prov#")
    BIMGUARD = rdflib.Namespace("https://bim-guard.xyz/prov/")

    # Verify Activity exists
    activities = list(g.subjects(rdflib.RDF.type, PROV.Activity))
    assert len(activities) == 1
    assert activities[0] == BIMGUARD["activity/pipeline_run_1"]

    # Verify Verdict Entities exist
    entities = list(g.subjects(rdflib.RDF.type, PROV.Entity))
    assert len(entities) >= 4  # 2 verdicts + 2 rules + 2 elements
