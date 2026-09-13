"""Neo4j implementation of the GraphDatabaseProvider protocol.

Supports connecting to either hosted (Neo4j Aura, remote clusters) or local
Docker-launched Neo4j instances via Bolt or Neo4j routing protocols.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Dict, List, Optional

try:
    import neo4j
    from neo4j import Driver, GraphDatabase
except ImportError:
    neo4j = None
    Driver = None
    GraphDatabase = None

logger = logging.getLogger(__name__)

#: Neo4j label/property/relationship-type names are interpolated into Cypher
#: queries, so every identifier is validated against this pattern before use.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

#: Property keys checked, in order, as the primary key when a node's
#: properties don't declare one explicitly.
_PK_CANDIDATES = ("id", "guid", "node_id", "rule_id", "global_id")


class Neo4jDatabaseProvider:
    """Neo4j graph database provider implementing GraphDatabaseProvider."""

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        username: Optional[str] = "neo4j",
        password: Optional[str] = None,
        database: Optional[str] = "neo4j",
        *,
        driver: Optional[Any] = None,
        verify_connectivity: bool = False,
    ):
        """Initialize the Neo4j database driver connection.

        Args:
            uri: Connection URI (e.g. ``bolt://localhost:7687``,
                ``neo4j+s://<db-id>.databases.neo4j.io``).
            username: Username for basic auth (defaults to ``neo4j``).
            password: Password for basic auth. If empty or None, connects
                without authentication.
            database: Target database name (defaults to ``neo4j``).
            driver: Optional pre-configured Neo4j driver instance (useful for
                testing/mocking).
            verify_connectivity: Whether to verify connection immediately during
                initialization.

        Raises:
            ImportError: If the ``neo4j`` python package is not installed.
        """
        if driver is not None:
            self.driver = driver
        else:
            if GraphDatabase is None:
                raise ImportError(
                    "The `neo4j` package is not installed. Please install it with `uv add neo4j`."
                )

            auth = (username, password) if (username and password) else None
            self.driver = GraphDatabase.driver(uri, auth=auth)

        self.uri = uri
        self.username = username
        self.database = database
        self._node_label_by_id: Dict[Any, str] = {}
        self._node_pk_by_label: Dict[str, str] = {}

        if verify_connectivity and self.driver:
            self.verify_connectivity()

    @staticmethod
    def _validate_identifier(name: str) -> str:
        """Reject any label/rel-type/property name unsafe for Cypher clauses."""
        if not isinstance(name, str) or not _IDENTIFIER_RE.match(name):
            raise ValueError(
                f"Invalid Neo4j identifier {name!r}: must start with a letter or "
                "underscore and contain only letters, digits, and underscores."
            )
        return name

    def verify_connectivity(self) -> bool:
        """Verify driver connectivity to the Neo4j server."""
        try:
            if hasattr(self.driver, "verify_connectivity"):
                self.driver.verify_connectivity()
            return True
        except Exception as exc:
            logger.warning("Neo4j connectivity check failed: %s", exc)
            return False

    def execute_query(
        self, query: str, parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return the results as a list of dictionaries."""
        results: List[Dict[str, Any]] = []
        try:
            with self.driver.session(database=self.database) as session:
                records = session.run(query, parameters or {})
                for record in records:
                    if hasattr(record, "data"):
                        results.append(record.data())
                    else:
                        results.append(dict(record))
        except Exception as exc:
            logger.error("Neo4j query failed: %s -> %s", query, exc)
            raise
        return results

    def _pick_primary_key(self, properties: Dict[str, Any]) -> str:
        """Choose or generate a primary key property for a node."""
        for candidate in _PK_CANDIDATES:
            if candidate in properties:
                return candidate
        fallback_value = str(uuid.uuid4())
        properties["id"] = fallback_value
        return "id"

    def add_node(self, label: str, properties: Dict[str, Any]) -> None:
        """Add or update a node in the Neo4j graph."""
        self._validate_identifier(label)
        for key in properties:
            self._validate_identifier(key)

        props = dict(properties)
        pk = self._pick_primary_key(props)
        self._node_pk_by_label[label] = pk
        self._node_label_by_id[props[pk]] = label

        query = (
            f"MERGE (n:{label} {{{pk}: $pk_val}}) "
            f"SET n += $props"
        )
        self.execute_query(query, {"pk_val": props[pk], "props": props})

    def add_nodes_batch(self, label: str, nodes: List[Dict[str, Any]]) -> None:
        """Add or update multiple nodes in a single UNWIND batch query."""
        if not nodes:
            return
        self._validate_identifier(label)

        # Determine PK property key (from cache or first node)
        sample = dict(nodes[0])
        pk = self._node_pk_by_label.get(label) or self._pick_primary_key(sample)
        self._node_pk_by_label[label] = pk

        prepared_batch = []
        for node in nodes:
            props = dict(node)
            for key in props:
                self._validate_identifier(key)
            if pk not in props:
                props[pk] = str(uuid.uuid4())
            self._node_label_by_id[props[pk]] = label
            prepared_batch.append(props)

        query = (
            f"UNWIND $batch AS item "
            f"MERGE (n:{label} {{{pk}: item.{pk}}}) "
            f"SET n += item"
        )
        self.execute_query(query, {"batch": prepared_batch})

    def add_edge(
        self,
        source_id: Any,
        target_id: Any,
        rel_type: str,
        properties: Optional[Dict[str, Any]] = None,
        *,
        from_label: Optional[str] = None,
        to_label: Optional[str] = None,
        from_pk: Optional[str] = None,
        to_pk: Optional[str] = None,
    ) -> None:
        """Add or update a directed relationship between two nodes."""
        self._validate_identifier(rel_type)
        if from_label:
            self._validate_identifier(from_label)
        if to_label:
            self._validate_identifier(to_label)
        if from_pk:
            self._validate_identifier(from_pk)
        if to_pk:
            self._validate_identifier(to_pk)

        edge_props = properties or {}
        for key in edge_props:
            self._validate_identifier(key)

        resolved_from = from_label or self._node_label_by_id.get(source_id)
        resolved_to = to_label or self._node_label_by_id.get(target_id)

        from_clause = f":{resolved_from}" if resolved_from else ""
        to_clause = f":{resolved_to}" if resolved_to else ""

        pk_a = from_pk or (self._node_pk_by_label.get(resolved_from, "id") if resolved_from else "id")
        pk_b = to_pk or (self._node_pk_by_label.get(resolved_to, "id") if resolved_to else "id")

        query = (
            f"MATCH (a{from_clause} {{{pk_a}: $source_id}}), "
            f"(b{to_clause} {{{pk_b}: $target_id}}) "
            f"MERGE (a)-[r:{rel_type}]->(b) "
            f"SET r += $props"
        )
        self.execute_query(
            query,
            {
                "source_id": source_id,
                "target_id": target_id,
                "props": edge_props,
            },
        )

    def add_edges_batch(
        self,
        rel_type: str,
        edges: List[Dict[str, Any]],
        *,
        from_label: Optional[str] = None,
        to_label: Optional[str] = None,
        from_pk: Optional[str] = None,
        to_pk: Optional[str] = None,
    ) -> None:
        """Add or update multiple edges in a single UNWIND batch query."""
        if not edges:
            return
        self._validate_identifier(rel_type)
        if from_label:
            self._validate_identifier(from_label)
        if to_label:
            self._validate_identifier(to_label)
        if from_pk:
            self._validate_identifier(from_pk)
        if to_pk:
            self._validate_identifier(to_pk)

        first_source = edges[0].get("source_id")
        first_target = edges[0].get("target_id")
        resolved_from = from_label or self._node_label_by_id.get(first_source)
        resolved_to = to_label or self._node_label_by_id.get(first_target)

        from_clause = f":{resolved_from}" if resolved_from else ""
        to_clause = f":{resolved_to}" if resolved_to else ""

        pk_a = from_pk or (self._node_pk_by_label.get(resolved_from, "id") if resolved_from else "id")
        pk_b = to_pk or (self._node_pk_by_label.get(resolved_to, "id") if resolved_to else "id")

        prepared_edges = []
        for edge in edges:
            props = dict(edge.get("properties") or {})
            for key in props:
                self._validate_identifier(key)
            prepared_edges.append(
                {
                    "source_id": edge["source_id"],
                    "target_id": edge["target_id"],
                    "props": props,
                }
            )

        query = (
            f"UNWIND $batch AS edge "
            f"MATCH (a{from_clause} {{{pk_a}: edge.source_id}}), "
            f"(b{to_clause} {{{pk_b}: edge.target_id}}) "
            f"MERGE (a)-[r:{rel_type}]->(b) "
            f"SET r += edge.props"
        )
        self.execute_query(query, {"batch": prepared_edges})

    def ensure_index(self, label: str, property_name: str) -> None:
        """Create an index on a node property if it does not already exist."""
        self._validate_identifier(label)
        self._validate_identifier(property_name)
        index_name = f"idx_{label}_{property_name}".lower()
        query = f"CREATE INDEX {index_name} IF NOT EXISTS FOR (n:{label}) ON (n.{property_name})"
        self.execute_query(query)

    def clear(self) -> None:
        """Clear all nodes and relationships from the database."""
        self.execute_query("MATCH (n) DETACH DELETE n")
        self._node_label_by_id.clear()
        self._node_pk_by_label.clear()

    def close(self) -> None:
        """Close the underlying driver connection."""
        if self.driver is not None and hasattr(self.driver, "close"):
            self.driver.close()

    def __enter__(self) -> Neo4jDatabaseProvider:
        """Enter context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager and close driver."""
        self.close()
