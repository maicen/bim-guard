"""KùzuDB implementation of the GraphDatabaseProvider protocol."""

import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import kuzu
except ImportError:
    kuzu = None

logger = logging.getLogger(__name__)

#: Kuzu table/column/rel-type names are interpolated directly into DDL/Cypher
#: strings (Kuzu's parameterized queries only bind property *values*, not
#: identifiers), so every identifier that reaches a query is checked against
#: this before use -- rejecting anything with a quote, semicolon, or other
#: character that could break out of the intended clause.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

#: Property keys checked, in order, as the primary key when a node's
#: properties don't declare one explicitly.
_PK_CANDIDATES = ("id", "guid", "node_id", "rule_id", "global_id")


class KuzuDatabaseProvider:
    """Embedded KùzuDB graph database provider.

    Kùzu requires strongly-typed node/rel tables (unlike a loose property
    graph), so this provider inspects the properties passed to add_node() and
    auto-generates (and evolves) the schema: CREATE NODE TABLE on first use
    of a label, then ALTER TABLE ADD for any new property key seen on a later
    call with that label.
    """

    def __init__(self, db_path: str = ".kuzu"):
        """Initialize the Kùzu database and connection."""
        if kuzu is None:
            raise ImportError("KuzuDB is not installed. Please install it with `uv add kuzu`.")

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = kuzu.Database(str(self.db_path))
        self.conn = kuzu.Connection(self.db)

        # Track catalog state to avoid querying it on every insert.
        self._node_tables: set = set()
        self._rel_tables: set = set()
        self._node_pk_by_label: Dict[str, str] = {}
        self._node_columns: Dict[str, set] = {}
        self._rel_table_pairs: Dict[str, Tuple[str, str]] = {}
        self._rel_columns: Dict[str, set] = {}
        # Best-effort id -> label lookup so add_edge(source_id, target_id, rel_type)
        # can still resolve endpoints when the caller doesn't pass
        # from_label/to_label explicitly. Ambiguous if the same id value is
        # reused across different labels -- callers that care should pass
        # from_label/to_label.
        self._node_label_by_id: Dict[Any, str] = {}

        self._init_catalog()

    def _init_catalog(self) -> None:
        """Load existing tables (and rel FROM/TO pairs) from the catalog."""
        try:
            results = self.conn.execute("CALL show_tables() RETURN *;")
            while results.has_next():
                # show_tables() columns: [id, name, type, database name, comment]
                _table_id, name, table_type, *_rest = results.get_next()
                if table_type == "NODE":
                    self._node_tables.add(name)
                elif table_type == "REL":
                    self._rel_tables.add(name)
        except Exception as e:
            logger.warning(f"Failed to initialize catalog: {e}")
            return

        for rel_name in self._rel_tables:
            try:
                conn_res = self.conn.execute(f"CALL SHOW_CONNECTION('{rel_name}') RETURN *;")
                if conn_res.has_next():
                    src_table, dst_table, *_rest = conn_res.get_next()
                    self._rel_table_pairs[rel_name] = (src_table, dst_table)
            except Exception as e:
                logger.warning(f"Failed to load FROM/TO pair for rel table {rel_name}: {e}")

    @staticmethod
    def _validate_identifier(name: str) -> str:
        """Reject any label/column/rel-type name unsafe to interpolate into DDL/Cypher."""
        if not isinstance(name, str) or not _IDENTIFIER_RE.match(name):
            raise ValueError(
                f"Invalid Kuzu identifier {name!r}: must start with a letter or "
                "underscore and contain only letters, digits, and underscores."
            )
        return name

    def _python_to_kuzu_type(self, val: Any) -> str:
        """Map Python types to Kuzu types."""
        # bool is a subclass of int in Python, so this check must come first
        # or every boolean property would be typed INT64 instead of BOOLEAN.
        if isinstance(val, bool):
            return "BOOLEAN"
        if isinstance(val, int):
            return "INT64"
        if isinstance(val, float):
            return "DOUBLE"
        return "STRING"

    def _fetch_existing_columns(self, label: str) -> set:
        """Introspect an already-existing table's columns via TABLE_INFO."""
        try:
            res = self.conn.execute(f"CALL TABLE_INFO('{label}') RETURN *;")
            columns = set()
            while res.has_next():
                # TABLE_INFO columns: [property id, name, type, default expression, primary key]
                _prop_id, col_name, *_rest = res.get_next()
                columns.add(col_name)
            return columns
        except Exception as e:
            logger.warning(f"Failed to introspect columns for table {label}: {e}")
            return set()

    def _fetch_primary_key(self, label: str) -> Optional[str]:
        """Introspect an already-existing table's primary-key column via TABLE_INFO."""
        try:
            res = self.conn.execute(f"CALL TABLE_INFO('{label}') RETURN *;")
            while res.has_next():
                _prop_id, col_name, _type, _default, is_pk = res.get_next()
                if is_pk:
                    return col_name
        except Exception as e:
            logger.warning(f"Failed to introspect primary key for table {label}: {e}")
        return None

    def _pick_primary_key(self, label: str, properties: Dict[str, Any]) -> str:
        """Choose (or, failing that, generate) a primary key for a new node table."""
        for candidate in _PK_CANDIDATES:
            if candidate in properties:
                return candidate

        fallback_value = str(uuid.uuid4())
        properties["id"] = fallback_value
        logger.warning(
            "No natural id-like key (%s) found in properties for node label=%s; "
            "generated a random UUID primary key (id=%s). Pass one of those "
            "keys explicitly for stable upserts/lookups.",
            ", ".join(_PK_CANDIDATES),
            label,
            fallback_value,
        )
        return "id"

    def _ensure_node_table(self, label: str, properties: Dict[str, Any]) -> str:
        """Create (or evolve) the node table for `label` so `properties` fits it.

        Returns the primary-key column name for `label`.
        """
        self._validate_identifier(label)
        for key in properties:
            self._validate_identifier(key)

        if label not in self._node_tables:
            pk = self._pick_primary_key(label, properties)
            columns = [f"{k} {self._python_to_kuzu_type(v)}" for k, v in properties.items()]
            schema_query = f"CREATE NODE TABLE {label} ({', '.join(columns)}, PRIMARY KEY({pk}));"
            logger.info(f"Creating Kuzu node table: {schema_query}")
            self.conn.execute(schema_query)
            self._node_tables.add(label)
            self._node_pk_by_label[label] = pk
            self._node_columns[label] = set(properties.keys())
            return pk

        # Table already exists -- either created earlier this session, or
        # loaded from an existing .kuzu_db at startup. Evolve its schema for
        # any new property key instead of failing the CREATE with an opaque
        # "unknown property" error from Kuzu.
        if label not in self._node_columns:
            self._node_columns[label] = self._fetch_existing_columns(label)
        if label not in self._node_pk_by_label:
            self._node_pk_by_label[label] = self._fetch_primary_key(label) or "id"

        missing = set(properties.keys()) - self._node_columns[label]
        for col in missing:
            kuzu_type = self._python_to_kuzu_type(properties[col])
            alter_query = f"ALTER TABLE {label} ADD {col} {kuzu_type};"
            logger.info(f"Evolving Kuzu node table: {alter_query}")
            self.conn.execute(alter_query)
            self._node_columns[label].add(col)

        return self._node_pk_by_label[label]

    def _ensure_rel_table(
        self, rel_type: str, from_label: str, to_label: str, properties: Dict[str, Any]
    ) -> None:
        """Create (or evolve) the REL table for `rel_type` so `properties` fits it.

        Kuzu requires a fixed FROM/TO node-table pair per REL table, and --
        like node tables -- its edge properties are also a fixed schema, not
        a loose per-edge bag: creating an edge with a property the REL table
        was never given a column for fails with a Binder exception, so this
        mirrors _ensure_node_table's create-then-evolve approach for edges.
        """
        self._validate_identifier(rel_type)
        self._validate_identifier(from_label)
        self._validate_identifier(to_label)
        for key in properties:
            self._validate_identifier(key)

        if rel_type not in self._rel_tables:
            columns = [f"{k} {self._python_to_kuzu_type(v)}" for k, v in properties.items()]
            column_clause = f", {', '.join(columns)}" if columns else ""
            query = f"CREATE REL TABLE {rel_type} (FROM {from_label} TO {to_label}{column_clause});"
            logger.info(f"Creating Kuzu rel table: {query}")
            self.conn.execute(query)
            self._rel_tables.add(rel_type)
            self._rel_table_pairs[rel_type] = (from_label, to_label)
            self._rel_columns[rel_type] = set(properties.keys())
            return

        recorded = self._rel_table_pairs.get(rel_type)
        if recorded is not None and recorded != (from_label, to_label):
            raise ValueError(
                f"REL table {rel_type!r} already exists for "
                f"{recorded[0]}->{recorded[1]}; this provider creates one "
                f"FROM/TO pair per rel_type and {from_label}->{to_label} "
                "doesn't match. Use a differently named rel_type for this pair."
            )

        if rel_type not in self._rel_columns:
            self._rel_columns[rel_type] = self._fetch_existing_columns(rel_type)

        missing = set(properties.keys()) - self._rel_columns[rel_type]
        for col in missing:
            kuzu_type = self._python_to_kuzu_type(properties[col])
            alter_query = f"ALTER TABLE {rel_type} ADD {col} {kuzu_type};"
            logger.info(f"Evolving Kuzu rel table: {alter_query}")
            self.conn.execute(alter_query)
            self._rel_columns[rel_type].add(col)

    def execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return the results."""
        results = []
        try:
            res = self.conn.execute(query, parameters or {})
            if res.has_next():
                columns = res.get_column_names()
                while res.has_next():
                    row = res.get_next()
                    results.append(dict(zip(columns, row)))
        except Exception as e:
            logger.error(f"Kuzu query failed: {query} -> {e}")
            raise
        return results

    def add_node(self, label: str, properties: Dict[str, Any]) -> None:
        """Add a node to the graph, auto-creating/evolving its table as needed."""
        # Copy so a generated fallback primary key doesn't mutate the caller's dict.
        properties = dict(properties)
        pk = self._ensure_node_table(label, properties)

        keys = list(properties.keys())
        cypher_props = ", ".join(f"{k}: ${k}" for k in keys)
        query = f"CREATE (n:{label} {{{cypher_props}}})"

        safe_params = {
            k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in properties.items()
        }
        self.execute_query(query, safe_params)

        self._node_label_by_id[properties[pk]] = label

    def add_edge(
        self,
        source_id: Any,
        target_id: Any,
        rel_type: str,
        properties: Optional[Dict[str, Any]] = None,
        *,
        from_label: Optional[str] = None,
        to_label: Optional[str] = None,
    ) -> None:
        """Add an edge between two existing nodes.

        Kuzu's REL tables are strictly typed to one FROM/TO node-table pair,
        so unlike add_node this can't infer a schema purely from the id
        arguments. Pass from_label/to_label explicitly when known (preferred
        -- unambiguous and works even if the endpoint was never added via
        add_node()); otherwise this falls back to whatever label the most
        recent add_node() call recorded for that id, and raises a clear
        ValueError if either endpoint's label can't be resolved, rather than
        silently doing nothing.
        """
        resolved_from = from_label or self._node_label_by_id.get(source_id)
        resolved_to = to_label or self._node_label_by_id.get(target_id)
        if not resolved_from or not resolved_to:
            unresolved = []
            if not resolved_from:
                unresolved.append(f"source_id={source_id!r}")
            if not resolved_to:
                unresolved.append(f"target_id={target_id!r}")
            raise ValueError(
                f"Cannot add {rel_type!r} edge: no known label for "
                f"{' and '.join(unresolved)}. Pass from_label/to_label "
                "explicitly, or add_node() the endpoints first."
            )

        properties = properties or {}
        self._ensure_rel_table(rel_type, resolved_from, resolved_to, properties)

        pk_a = self._node_pk_by_label.get(resolved_from, "id")
        pk_b = self._node_pk_by_label.get(resolved_to, "id")

        edge_props = ""
        if properties:
            prop_clause = ", ".join(f"{k}: ${k}" for k in properties)
            edge_props = f" {{{prop_clause}}}"

        query = (
            f"MATCH (a:{resolved_from} {{{pk_a}: $__source_id}}), "
            f"(b:{resolved_to} {{{pk_b}: $__target_id}}) "
            f"CREATE (a)-[:{rel_type}{edge_props}]->(b)"
        )
        safe_params = {
            k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in properties.items()
        }
        safe_params["__source_id"] = source_id
        safe_params["__target_id"] = target_id
        self.execute_query(query, safe_params)

    def clear(self) -> None:
        """Clear all data from the graph by dropping every table (rels first, then nodes)."""
        for t in self._rel_tables:
            self.execute_query(f"DROP TABLE {t}")
        for t in self._node_tables:
            self.execute_query(f"DROP TABLE {t}")
        self._node_tables.clear()
        self._rel_tables.clear()
        self._node_pk_by_label.clear()
        self._node_columns.clear()
        self._rel_table_pairs.clear()
        self._rel_columns.clear()
        self._node_label_by_id.clear()

    def close(self) -> None:
        """Release the connection/database handles (and the on-disk lock file).

        Kuzu is single-writer per path: another Database() against the same
        db_path fails with "Could not set lock on file" until this is
        called, so anything that opens more than one provider for the same
        path in a process (tests included) needs this.
        """
        self.conn.close()
        self.db.close()
