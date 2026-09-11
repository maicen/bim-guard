"""Service for persistent RDF graph storage and SPARQL querying."""

from __future__ import annotations

import json
from typing import Any

import pyoxigraph
import rdflib

from app.logging_config import get_logger

logger = get_logger(__name__)


class GraphTriplestoreService:
    """Provides triplestore persistence and SPARQL querying via pyoxigraph.

    Unlike the ephemeral rdflib.Graph used for in-memory SHACL validation,
    this service maintains a pyoxigraph.Store (either in-memory or on-disk)
    that isolates project data using named graphs.
    """

    def __init__(self, store_path: str | None = None) -> None:
        """Initialize the triplestore.

        Args:
            store_path: Optional path to persist the store on disk. If None,
                the store is kept in-memory.
        """
        if store_path:
            self.store = pyoxigraph.Store(store_path)
            logger.info("Initialized pyoxigraph store at %s", store_path)
        else:
            self.store = pyoxigraph.Store()
            logger.info("Initialized in-memory pyoxigraph store")

    def _graph_name_for(self, project_id: int) -> pyoxigraph.NamedNode:
        """Return the named graph URI for a given project."""
        return pyoxigraph.NamedNode(f"https://bimguard.io/graphs/{project_id}")

    def load_graph(self, project_id: int, graph: rdflib.Graph) -> None:
        """Replace the project's named graph with the given rdflib graph.

        Args:
            project_id: The project this graph belongs to.
            graph: The rdflib.Graph containing the triples to store.
        """
        graph_name = self._graph_name_for(project_id)
        
        # Clear existing graph for this project to ensure we don't leak stale triples
        self.store.clear_graph(graph_name)
        
        count = 0
        for s, p, o in graph:
            # Convert rdflib terms to pyoxigraph terms via N-Triples serialization parsing
            # Alternatively, we can construct pyoxigraph terms directly, but rdflib serialization
            # and pyoxigraph parsing is very robust. For performance, we'll build them directly.
            
            subject = self._convert_term(s)
            predicate = self._convert_term(p)
            object_ = self._convert_term(o)
            
            if subject and predicate and object_:
                self.store.add(pyoxigraph.Quad(subject, predicate, object_, graph_name))
                count += 1
                
        logger.info("Loaded %d triples into graph %s", count, graph_name.value)

    def query(self, project_id: int, sparql_query: str) -> dict[str, Any]:
        """Execute a SPARQL query against a project's named graph.

        Args:
            project_id: The project whose named graph should be queried.
            sparql_query: The SPARQL SELECT, ASK, or CONSTRUCT query to run.

        Returns:
            The SPARQL JSON results format representation of the query results.
        """
        graph_name = self._graph_name_for(project_id)
        
        try:
            # We use use_default_graph_as_union=False and default_graph=graph_name
            # so the query only sees the project's data.
            # wait, pyoxigraph's query method has `default_graph` param?
            # Actually, `query` signature: query(query: str, *, default_graph: Union[NamedNode, BlankNode, DefaultGraph, None] = None, named_graphs: Optional[Iterable[Union[NamedNode, BlankNode]]] = None, use_default_graph_as_union: bool = False, base_iri: Optional[str] = None)
            
            results = self.store.query(
                sparql_query,
                default_graph=graph_name,
                use_default_graph_as_union=False,
            )
            
            return self._format_results(results)
        except Exception as exc:
            logger.error("SPARQL query failed project_id=%d error=%s", project_id, exc)
            raise

    def _convert_term(self, term: rdflib.term.Identifier) -> Any:
        """Convert an rdflib term to a pyoxigraph term."""
        if isinstance(term, rdflib.URIRef):
            return pyoxigraph.NamedNode(str(term))
        elif isinstance(term, rdflib.BNode):
            return pyoxigraph.BlankNode(str(term))
        elif isinstance(term, rdflib.Literal):
            if term.language:
                return pyoxigraph.Literal(str(term), language=term.language)
            elif term.datatype:
                return pyoxigraph.Literal(str(term), datatype=pyoxigraph.NamedNode(str(term.datatype)))
            else:
                return pyoxigraph.Literal(str(term))
        return None

    def _format_results(self, results: Any) -> dict[str, Any]:
        """Format pyoxigraph query results into SPARQL JSON results format."""
        if isinstance(results, bool) or type(results).__name__ == "QueryBoolean":
            # ASK query
            return {"head": {}, "boolean": bool(results)}
        
        # SELECT query (pyoxigraph.QuerySolutions)
        try:
            variables = results.variables
            bindings = []
            
            for solution in results:
                binding = {}
                for var in variables:
                    val = solution[var]
                    if val is not None:
                        binding[var.value] = self._format_term(val)
                bindings.append(binding)
                
            return {
                "head": {"vars": [v.value for v in variables]},
                "results": {"bindings": bindings}
            }
        except AttributeError:
            # CONSTRUCT or DESCRIBE query which returns an iterator of Quad
            # We can't format this as standard SELECT json, but we can return triples.
            triples = []
            for triple in results:
                triples.append({
                    "subject": self._format_term(triple.subject),
                    "predicate": self._format_term(triple.predicate),
                    "object": self._format_term(triple.object)
                })
            return {"triples": triples}

    def _format_term(self, term: Any) -> dict[str, str]:
        """Format a pyoxigraph term into the SPARQL JSON format dictionary."""
        if isinstance(term, pyoxigraph.NamedNode):
            return {"type": "uri", "value": term.value}
        elif isinstance(term, pyoxigraph.BlankNode):
            return {"type": "bnode", "value": term.value}
        elif isinstance(term, pyoxigraph.Literal):
            res = {"type": "literal", "value": term.value}
            if term.language:
                res["xml:lang"] = term.language
            elif term.datatype and term.datatype.value != "http://www.w3.org/2001/XMLSchema#string":
                res["datatype"] = term.datatype.value
            return res
        return {"type": "unknown", "value": str(term)}
