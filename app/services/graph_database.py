"""Provider-agnostic Graph Database infrastructure for BIM-Guard.

This module defines the abstract interface for graph database operations
to support GraphRAG (Rules Extraction) and topological rule evaluation.
Concrete implementations (e.g., KùzuDB, Neo4j, FalkorDB) can be injected
without changing domain logic.
"""

from typing import Any, Dict, List, Optional, Protocol

class GraphDatabaseProvider(Protocol):
    """Protocol defining standard graph database operations."""
    
    def execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return the results."""
        ...
        
    def add_node(self, label: str, properties: Dict[str, Any]) -> None:
        """Add a node to the graph."""
        ...
        
    def add_edge(self, source_id: Any, target_id: Any, rel_type: str, properties: Optional[Dict[str, Any]] = None) -> None:
        """Add an edge between two nodes."""
        ...
        
    def clear(self) -> None:
        """Clear all data from the graph."""
        ...


class GraphService:
    """Domain service wrapping the configured Graph Database provider."""
    
    def __init__(self, provider: Optional[GraphDatabaseProvider] = None):
        """Initialize with an optional graph provider.
        
        If no provider is injected, the service will no-op or raise
        NotImplementedError, allowing the rest of the application to function
        until a concrete graph DB is chosen and wired.
        """
        self.provider = provider
        
    def execute(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query."""
        if not self.provider:
            raise NotImplementedError("No Graph Database provider configured.")
        return self.provider.execute_query(query, parameters)
        
    def insert_document_node(self, node_id: str, text: str, metadata: Dict[str, Any]) -> None:
        """Helper to insert an extracted NLP document node for GraphRAG."""
        if not self.provider:
            return
        properties = {"node_id": node_id, "text": text, **metadata}
        self.provider.add_node("DocumentNode", properties)
        
    def link_rule_to_ifc(self, rule_id: str, ifc_class: str) -> None:
        """Helper to link an extracted rule to its target IFC class."""
        if not self.provider:
            return
        self.provider.add_edge(rule_id, ifc_class, "APPLIES_TO")
