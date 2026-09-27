"""Tests for RegulatoryGraphService inspired by kg-lite-builder GraphRAG concepts."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.modules.contracts.rules import RuleResponse
from app.services.regulatory_graph_service import RegulatoryGraphService


@pytest.fixture
def mock_rules_service():
    service = MagicMock()
    service.list_rules.return_value = [
        RuleResponse(
            id=1,
            rule_id="IBC-1017.2",
            ruleset_id="IBC 2024",
            reference="IBC 2024 Section 1017.2",
            description="The exit access travel distance shall not exceed the distance specified in Section 1017.2. Cross-reference Section 1006.",
            target_ifc_class="IfcSpace,IfcDoor",
            property_name="travel_distance",
            operator="<=",
            check_value="61.0",
            unit="m",
            severity="critical",
            category="Arch",
        ),
        RuleResponse(
            id=2,
            rule_id="IBC-716.2.2.1",
            ruleset_id="IBC 2024",
            reference="IBC 2024 Section 716.2.2.1",
            description="Fire-rated door assemblies shall have a minimum fire protection rating per Table 716.1(2).",
            target_ifc_class="IfcDoor",
            property_name="fire_rating",
            operator=">=",
            check_value="60",
            unit="min",
            severity="critical",
            category="Arch",
        ),
        RuleResponse(
            id=3,
            rule_id="ADA-404.2.3",
            ruleset_id="ADA 2010",
            reference="ADA 2010 Section 404.2.3",
            description="Door openings shall provide a clear width of 32 inches minimum.",
            target_ifc_class="IfcDoor",
            property_name="clear_width",
            operator=">=",
            check_value="0.813",
            unit="m",
            severity="warning",
            category="Arch",
        ),
    ]
    return service


def test_get_governing_requirements_by_ifc(mock_rules_service):
    """Verify that querying IfcDoor retrieves requirements across all applicable standards."""
    reg_service = RegulatoryGraphService(rules_service=mock_rules_service)

    res = reg_service.get_governing_requirements("IfcDoor")

    assert res.ifc_type == "IfcDoor"
    assert res.total_requirements == 3
    assert set(res.standards_covered) == {"IBC 2024", "ADA 2010"}

    params = {req.parameter for req in res.requirements}
    assert "travel_distance" in params
    assert "fire_rating" in params
    assert "clear_width" in params


def test_get_clause_context(mock_rules_service):
    """Verify retrieving contextual knowledge graph neighborhood for a clause."""
    reg_service = RegulatoryGraphService(rules_service=mock_rules_service)

    res = reg_service.get_clause_context("1017.2")

    assert "1017.2" in res.clause.clause_id
    assert res.clause.standard == "IBC 2024"
    assert "1017" in res.clause.section
    assert "IfcDoor" in res.clause.target_ifc_types
    assert "IfcSpace" in res.clause.target_ifc_types

    # Verify cross-reference extraction
    assert "1006" in res.clause.cross_references
    assert len(res.cross_referenced_clauses) > 0
    assert any(c.clause_id == "1006" for c in res.cross_referenced_clauses)


def test_ingest_regulatory_graph(mock_rules_service):
    """Verify batch ingestion of regulatory standards into the graph database."""
    fake_graph = MagicMock()
    fake_graph.provider = MagicMock()

    reg_service = RegulatoryGraphService(rules_service=mock_rules_service, graph_service=fake_graph)

    stats = reg_service.ingest_regulatory_graph()

    assert stats["status"] == "success"
    assert stats["rules_count"] == 3
    assert stats["nodes"] > 0
    assert stats["edges"] > 0

    assert fake_graph.add_nodes_batch.call_count >= 5  # Standard, Section, Clause, Requirement, IfcClass
    assert fake_graph.add_edges_batch.call_count >= 4  # HAS_SECTION, CONTAINS_CLAUSE, MANDATES, APPLIES_TO
