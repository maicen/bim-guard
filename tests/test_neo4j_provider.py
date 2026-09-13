"""Tests for the Neo4j graph provider and its GraphService integration."""

from unittest.mock import patch

import pytest

from app.services.graph_database import GraphService
from app.services.neo4j_provider import Neo4jDatabaseProvider


class FakeRecord:
    """Mock record mimicking neo4j Record with a .data() method."""

    def __init__(self, data_dict):
        self._data = data_dict

    def data(self):
        return self._data


class FakeSession:
    """Mock session mimicking neo4j Session context manager."""

    def __init__(self, run_results=None):
        self.run_results = run_results or []
        self.queries_executed = []
        self.params_executed = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def run(self, query, parameters=None):
        self.queries_executed.append(query)
        self.params_executed.append(parameters or {})
        return self.run_results


class FakeDriver:
    """Mock driver mimicking neo4j Driver."""

    def __init__(self, session=None):
        self.session_instance = session or FakeSession()
        self.closed = False
        self.connectivity_verified = False

    def session(self, database=None):
        return self.session_instance

    def verify_connectivity(self):
        self.connectivity_verified = True

    def close(self):
        self.closed = True


@pytest.fixture
def mock_driver():
    return FakeDriver()


@pytest.fixture
def provider(mock_driver):
    return Neo4jDatabaseProvider(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="testpassword",
        database="neo4j",
        driver=mock_driver,
    )


def test_execute_query_runs_cypher_and_returns_dicts(provider, mock_driver):
    mock_driver.session_instance.run_results = [
        FakeRecord({"r.rule_id": "R1", "r.description": "Wall shall comply"})
    ]

    results = provider.execute_query(
        "MATCH (r:Rule) RETURN r.rule_id, r.description", {"param": 1}
    )

    assert results == [{"r.rule_id": "R1", "r.description": "Wall shall comply"}]
    assert len(mock_driver.session_instance.queries_executed) == 1
    assert "MATCH (r:Rule)" in mock_driver.session_instance.queries_executed[0]
    assert mock_driver.session_instance.params_executed[0] == {"param": 1}


def test_add_node_with_natural_primary_key(provider, mock_driver):
    provider.add_node("Rule", {"rule_id": "R1", "description": "Wall rule"})

    assert len(mock_driver.session_instance.queries_executed) == 1
    query = mock_driver.session_instance.queries_executed[0]
    params = mock_driver.session_instance.params_executed[0]

    assert "MERGE (n:Rule {rule_id: $pk_val})" in query
    assert "SET n += $props" in query
    assert params["pk_val"] == "R1"
    assert params["props"]["rule_id"] == "R1"
    assert params["props"]["description"] == "Wall rule"


def test_add_node_generates_uuid_pk_when_no_natural_key(provider, mock_driver):
    provider.add_node("Orphan", {"note": "no explicit id"})

    assert len(mock_driver.session_instance.queries_executed) == 1
    query = mock_driver.session_instance.queries_executed[0]
    params = mock_driver.session_instance.params_executed[0]

    assert "MERGE (n:Orphan {id: $pk_val})" in query
    gen_id = params["pk_val"]
    assert len(gen_id) == 36
    assert gen_id.count("-") == 4


def test_add_edge_with_explicit_labels(provider, mock_driver):
    provider.add_node("Rule", {"rule_id": "R1"})
    provider.add_node("IfcClass", {"id": "IfcWall"})

    provider.add_edge("R1", "IfcWall", "APPLIES_TO", {"confidence": 0.95}, from_label="Rule", to_label="IfcClass")

    edge_query = mock_driver.session_instance.queries_executed[-1]
    edge_params = mock_driver.session_instance.params_executed[-1]

    assert "MATCH (a:Rule {rule_id: $source_id})" in edge_query
    assert "(b:IfcClass {id: $target_id})" in edge_query
    assert "MERGE (a)-[r:APPLIES_TO]->(b)" in edge_query
    assert "SET r += $props" in edge_query
    assert edge_params["source_id"] == "R1"
    assert edge_params["target_id"] == "IfcWall"
    assert edge_params["props"] == {"confidence": 0.95}


def test_add_edge_infers_labels_from_prior_add_node(provider, mock_driver):
    provider.add_node("Rule", {"rule_id": "R1"})
    provider.add_node("IfcClass", {"id": "IfcDoor"})

    provider.add_edge("R1", "IfcDoor", "APPLIES_TO")

    edge_query = mock_driver.session_instance.queries_executed[-1]
    edge_params = mock_driver.session_instance.params_executed[-1]

    assert "MATCH (a:Rule {rule_id: $source_id})" in edge_query
    assert "(b:IfcClass {id: $target_id})" in edge_query
    assert "MERGE (a)-[r:APPLIES_TO]->(b)" in edge_query
    assert edge_params["source_id"] == "R1"
    assert edge_params["target_id"] == "IfcDoor"


def test_clear_executes_detach_delete(provider, mock_driver):
    provider.add_node("Rule", {"rule_id": "R1"})
    provider.clear()

    last_query = mock_driver.session_instance.queries_executed[-1]
    assert last_query == "MATCH (n) DETACH DELETE n"
    assert provider._node_label_by_id == {}


def test_close_closes_driver(provider, mock_driver):
    provider.close()
    assert mock_driver.closed is True


def test_context_manager(mock_driver):
    with Neo4jDatabaseProvider(driver=mock_driver) as p:
        assert p is not None
    assert mock_driver.closed is True


def test_verify_connectivity(mock_driver):
    provider = Neo4jDatabaseProvider(driver=mock_driver, verify_connectivity=True)
    assert mock_driver.connectivity_verified is True
    assert provider.verify_connectivity() is True


@pytest.mark.parametrize(
    "bad_identifier",
    ["Bad Label", "1StartsWithDigit", "Has-Dash", "Has;Semicolon", "DROP TABLE Rule", "a'b"],
)
def test_rejects_unsafe_identifiers(provider, bad_identifier):
    with pytest.raises(ValueError, match="Invalid Neo4j identifier"):
        provider.add_node(bad_identifier, {"id": "1"})

    with pytest.raises(ValueError, match="Invalid Neo4j identifier"):
        provider.add_node("SafeLabel", {bad_identifier: "val"})

    with pytest.raises(ValueError, match="Invalid Neo4j identifier"):
        provider.add_edge("1", "2", bad_identifier)


def test_import_error_raised_when_neo4j_missing():
    with patch("app.services.neo4j_provider.GraphDatabase", None):
        with pytest.raises(ImportError, match="The `neo4j` package is not installed"):
            Neo4jDatabaseProvider(driver=None)


class TestGraphServiceWithNeo4j:
    """GraphService domain methods with Neo4jDatabaseProvider."""

    def test_insert_document_node(self, provider, mock_driver):
        service = GraphService(provider=provider)
        service.insert_document_node("doc-1", "Stair text content", {"page": 3})

        query = mock_driver.session_instance.queries_executed[-1]
        params = mock_driver.session_instance.params_executed[-1]

        assert "MERGE (n:DocumentNode {node_id: $pk_val})" in query
        assert params["props"]["node_id"] == "doc-1"
        assert params["props"]["text"] == "Stair text content"
        assert params["props"]["page"] == 3

    def test_link_rule_to_ifc(self, provider, mock_driver):
        service = GraphService(provider=provider)
        service.link_rule_to_ifc("RULE-99", "IfcBeam")

        # Must have added Rule node, IfcClass node, and the APPLIES_TO relationship
        queries = mock_driver.session_instance.queries_executed
        assert any("MERGE (n:Rule" in q for q in queries)
        assert any("MERGE (n:IfcClass" in q for q in queries)
        assert any("MERGE (a)-[r:APPLIES_TO]->(b)" in q for q in queries)
