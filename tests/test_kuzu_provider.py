"""Tests for the embedded KùzuDB graph provider and its GraphService wrapper."""

import pytest

from app.services.graph_database import GraphService
from app.services.kuzu_provider import KuzuDatabaseProvider


@pytest.fixture
def provider(tmp_path) -> KuzuDatabaseProvider:
    # Kùzu creates the database at this path itself -- it must not already
    # exist as a directory, so this only passes the (unused) parent to it.
    return KuzuDatabaseProvider(db_path=str(tmp_path / "graph"))


def test_add_node_creates_table_and_is_queryable(provider):
    provider.add_node("Rule", {"rule_id": "R1", "description": "Wall shall comply"})

    rows = provider.execute_query("MATCH (r:Rule) RETURN r.rule_id, r.description")

    assert rows == [{"r.rule_id": "R1", "r.description": "Wall shall comply"}]


def test_add_node_without_natural_key_generates_a_real_uuid_pk(provider):
    provider.add_node("Orphan", {"note": "no natural key"})

    rows = provider.execute_query("MATCH (o:Orphan) RETURN o.id, o.note")

    assert len(rows) == 1
    generated_id = rows[0]["o.id"]
    assert generated_id is not None
    # A real UUID4, not Python's object id()/memory address.
    assert len(generated_id) == 36
    assert generated_id.count("-") == 4


def test_add_node_evolves_schema_for_new_property_on_existing_table(provider):
    provider.add_node("Rule", {"rule_id": "R1", "description": "First"})
    provider.add_node("Rule", {"rule_id": "R2", "description": "Second", "severity": "mandatory"})

    rows = provider.execute_query("MATCH (r:Rule) RETURN r.rule_id, r.severity ORDER BY r.rule_id")

    assert rows == [
        {"r.rule_id": "R1", "r.severity": None},
        {"r.rule_id": "R2", "r.severity": "mandatory"},
    ]


def test_add_node_boolean_property_is_typed_boolean_not_int(provider):
    provider.add_node("Flag", {"id": "f1", "enabled": True})

    schema = provider.execute_query("CALL TABLE_INFO('Flag') RETURN *;")

    enabled_col = next(row for row in schema if row.get("name") == "enabled")
    assert enabled_col["type"] == "BOOL"


def test_add_node_dict_and_list_properties_round_trip_as_json(provider):
    provider.add_node("Doc", {"id": "d1", "metadata": {"page": 5}, "tags": ["a", "b"]})

    rows = provider.execute_query("MATCH (d:Doc) RETURN d.metadata, d.tags")

    assert rows[0]["d.metadata"] == '{"page": 5}'
    assert rows[0]["d.tags"] == '["a", "b"]'


def test_add_edge_with_explicit_labels_creates_a_real_traversable_edge(provider):
    provider.add_node("Rule", {"rule_id": "R1"})
    provider.add_node("IfcClass", {"id": "IfcWall"})

    provider.add_edge("R1", "IfcWall", "APPLIES_TO", from_label="Rule", to_label="IfcClass")

    rows = provider.execute_query(
        "MATCH (a:Rule)-[r:APPLIES_TO]->(b:IfcClass) RETURN a.rule_id, b.id"
    )
    assert rows == [{"a.rule_id": "R1", "b.id": "IfcWall"}]


def test_add_edge_resolves_labels_from_prior_add_node_calls_when_omitted(provider):
    provider.add_node("Rule", {"rule_id": "R1"})
    provider.add_node("IfcClass", {"id": "IfcWall"})

    provider.add_edge("R1", "IfcWall", "APPLIES_TO")  # no from_label/to_label

    rows = provider.execute_query("MATCH (:Rule)-[r:APPLIES_TO]->(:IfcClass) RETURN count(r) AS n")
    assert rows == [{"n": 1}]


def test_add_edge_with_unknown_endpoints_raises_instead_of_silently_doing_nothing(provider):
    with pytest.raises(ValueError, match="no known label"):
        provider.add_edge("unknown-source", "unknown-target", "SOME_REL")


def test_add_edge_with_properties_stores_them_on_the_relationship(provider):
    provider.add_node("Rule", {"rule_id": "R1"})
    provider.add_node("IfcClass", {"id": "IfcWall"})

    provider.add_edge(
        "R1", "IfcWall", "APPLIES_TO", {"confidence": 0.9}, from_label="Rule", to_label="IfcClass"
    )

    rows = provider.execute_query("MATCH (:Rule)-[r:APPLIES_TO]->(:IfcClass) RETURN r.confidence")
    assert rows == [{"r.confidence": 0.9}]


@pytest.mark.parametrize(
    "bad_label",
    ["Bad Label", "1StartsWithDigit", "Has-Dash", "Has;Semicolon", "DROP TABLE Rule"],
)
def test_add_node_rejects_unsafe_label_identifiers(provider, bad_label):
    with pytest.raises(ValueError, match="Invalid Kuzu identifier"):
        provider.add_node(bad_label, {"id": "x"})


def test_add_node_rejects_unsafe_property_key_identifiers(provider):
    with pytest.raises(ValueError, match="Invalid Kuzu identifier"):
        provider.add_node("Rule", {"id": "x", "bad key; DROP TABLE Rule": "y"})


def test_reopening_an_existing_kuzu_db_loads_its_catalog(tmp_path):
    db_path = str(tmp_path / "graph")
    first = KuzuDatabaseProvider(db_path=db_path)
    first.add_node("Rule", {"rule_id": "R1"})
    first.close()  # Kuzu is single-writer per path -- release the lock first.

    # A fresh provider instance against the same path must recognize the
    # table already exists (not attempt CREATE NODE TABLE again) and must
    # be able to evolve/query it.
    second = KuzuDatabaseProvider(db_path=db_path)
    second.add_node("Rule", {"rule_id": "R2", "severity": "mandatory"})

    rows = second.execute_query("MATCH (r:Rule) RETURN r.rule_id ORDER BY r.rule_id")
    assert rows == [{"r.rule_id": "R1"}, {"r.rule_id": "R2"}]
    second.close()


def test_clear_drops_every_table(provider):
    provider.add_node("Rule", {"rule_id": "R1"})
    provider.add_node("IfcClass", {"id": "IfcWall"})
    provider.add_edge("R1", "IfcWall", "APPLIES_TO", from_label="Rule", to_label="IfcClass")

    provider.clear()

    rows = provider.execute_query("CALL show_tables() RETURN *;")
    assert rows == []


class TestGraphServiceWithRealProvider:
    """GraphService's helper methods, against the real embedded provider."""

    def test_insert_document_node(self, provider):
        service = GraphService(provider=provider)

        service.insert_document_node("n1", "Every stair shall have a minimum width.", {"page": 5})

        rows = provider.execute_query("MATCH (n:DocumentNode) RETURN n.node_id, n.text, n.page")
        assert rows == [
            {"n.node_id": "n1", "n.text": "Every stair shall have a minimum width.", "n.page": 5}
        ]

    def test_link_rule_to_ifc_creates_both_endpoint_nodes_and_a_real_edge(self, provider):
        service = GraphService(provider=provider)

        service.link_rule_to_ifc("REQ-1", "IfcDoor")

        rows = provider.execute_query(
            "MATCH (a:Rule)-[:APPLIES_TO]->(b:IfcClass) RETURN a.rule_id, b.class_name"
        )
        assert rows == [{"a.rule_id": "REQ-1", "b.class_name": "IfcDoor"}]


def test_graph_service_without_provider_no_ops_on_writes_and_raises_on_execute():
    service = GraphService()

    service.insert_document_node("n1", "text", {})  # must not raise
    service.link_rule_to_ifc("R1", "IfcWall")  # must not raise

    with pytest.raises(NotImplementedError):
        service.execute("MATCH (n) RETURN n")
