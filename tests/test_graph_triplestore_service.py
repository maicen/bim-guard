"""Tests for the GraphTriplestoreService and its pyoxigraph wrapper."""

import rdflib

from app.services.graph_triplestore_service import GraphTriplestoreService


def test_triplestore_service_load_and_query():
    """Test loading rdflib graphs and querying with SPARQL."""
    svc = GraphTriplestoreService()
    
    # Create an rdflib graph for project 1
    g1 = rdflib.Graph()
    g1.add((rdflib.URIRef("http://example.org/project/1"), rdflib.URIRef("http://example.org/hasName"), rdflib.Literal("Project One")))
    
    # Create an rdflib graph for project 2
    g2 = rdflib.Graph()
    g2.add((rdflib.URIRef("http://example.org/project/2"), rdflib.URIRef("http://example.org/hasName"), rdflib.Literal("Project Two")))
    
    svc.load_graph(1, g1)
    svc.load_graph(2, g2)
    
    # Query project 1
    res1 = svc.query(1, "SELECT ?name WHERE { ?s <http://example.org/hasName> ?name }")
    bindings1 = res1.get("results", {}).get("bindings", [])
    assert len(bindings1) == 1
    assert bindings1[0]["name"]["value"] == "Project One"
    
    # Query project 2
    res2 = svc.query(2, "SELECT ?name WHERE { ?s <http://example.org/hasName> ?name }")
    bindings2 = res2.get("results", {}).get("bindings", [])
    assert len(bindings2) == 1
    assert bindings2[0]["name"]["value"] == "Project Two"

def test_triplestore_service_ask_query():
    """Test ASK queries."""
    svc = GraphTriplestoreService()
    g = rdflib.Graph()
    g.add((rdflib.URIRef("http://example.org/a"), rdflib.URIRef("http://example.org/b"), rdflib.Literal("c")))
    svc.load_graph(1, g)
    
    res = svc.query(1, "ASK { ?s ?p ?o }")
    assert res.get("boolean") is True

def test_triplestore_service_rejects_cross_tenant_graph_clause():
    """A query for project 1 must not be able to read project 2's graph.

    Only `default_graph` scoping (which a crafted query with an explicit
    GRAPH clause can route around) is not enough for tenant isolation.
    """
    svc = GraphTriplestoreService()

    g1 = rdflib.Graph()
    g1.add((rdflib.URIRef("http://example.org/s1"), rdflib.URIRef("http://example.org/p"), rdflib.Literal("project one secret")))
    g2 = rdflib.Graph()
    g2.add((rdflib.URIRef("http://example.org/s2"), rdflib.URIRef("http://example.org/p"), rdflib.Literal("project two secret")))
    svc.load_graph(1, g1)
    svc.load_graph(2, g2)

    query = "SELECT ?v WHERE { GRAPH <https://bimguard.io/graphs/2> { ?s ?p ?v } }"
    result = svc.query(1, query)

    # named_graphs restricts which graphs a GRAPH clause may address, so the
    # pattern simply matches nothing rather than raising -- either way,
    # project 2's data must never come back from a query scoped to project 1.
    bindings = result.get("results", {}).get("bindings", [])
    assert bindings == []


def test_triplestore_service_construct_query():
    """Test CONSTRUCT queries which return triples."""
    svc = GraphTriplestoreService()
    g = rdflib.Graph()
    g.add((rdflib.URIRef("http://example.org/s"), rdflib.URIRef("http://example.org/p"), rdflib.URIRef("http://example.org/o")))
    svc.load_graph(1, g)
    
    res = svc.query(1, "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }")
    triples = res.get("triples", [])
    assert len(triples) == 1
    assert triples[0]["subject"]["value"] == "http://example.org/s"
    assert triples[0]["predicate"]["value"] == "http://example.org/p"
    assert triples[0]["object"]["value"] == "http://example.org/o"
