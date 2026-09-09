"""KùzuDB implementation of the GraphDatabaseProvider protocol."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging

try:
    import kuzu
except ImportError:
    kuzu = None

logger = logging.getLogger(__name__)

class KuzuDatabaseProvider:
    """Embedded KùzuDB graph database provider."""

    def __init__(self, db_path: str = ".kuzu"):
        """Initialize the Kùzu database and connection."""
        if kuzu is None:
            raise ImportError("KuzuDB is not installed. Please install it with `uv add kuzu`.")
        
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.db = kuzu.Database(str(self.db_path))
        self.conn = kuzu.Connection(self.db)
        
        # Track tables to avoid querying catalog for every insert
        self._node_tables = set()
        self._rel_tables = set()
        self._init_catalog()

    def _init_catalog(self):
        """Load existing tables from catalog."""
        try:
            results = self.conn.execute("CALL show_tables() RETURN *;")
            while results.has_next():
                row = results.get_next()
                if row[1] == "NODE":
                    self._node_tables.add(row[0])
                elif row[1] == "REL":
                    self._rel_tables.add(row[0])
        except Exception as e:
            logger.warning(f"Failed to initialize catalog: {e}")

    def _python_to_kuzu_type(self, val: Any) -> str:
        """Map Python types to Kuzu types."""
        if isinstance(val, int):
            return "INT64"
        if isinstance(val, float):
            return "DOUBLE"
        if isinstance(val, bool):
            return "BOOLEAN"
        return "STRING"

    def _ensure_node_table(self, label: str, properties: Dict[str, Any]):
        """Dynamically create a node table if it doesn't exist."""
        if label in self._node_tables:
            return
            
        # By convention, the first key is assumed to be the primary key
        # or we look for 'id', 'guid', 'node_id'
        pk = "id"
        for candidate in ["id", "guid", "node_id", "rule_id", "global_id"]:
            if candidate in properties:
                pk = candidate
                break
        
        if pk not in properties:
            properties[pk] = str(id(properties)) # fallback pk

        columns = []
        for k, v in properties.items():
            kuzu_type = self._python_to_kuzu_type(v)
            columns.append(f"{k} {kuzu_type}")
            
        schema_query = f"CREATE NODE TABLE {label} ({', '.join(columns)}, PRIMARY KEY({pk}));"
        logger.info(f"Creating Kuzu Node Table: {schema_query}")
        self.conn.execute(schema_query)
        self._node_tables.add(label)

    def _ensure_rel_table(self, rel_type: str):
        """Dynamically create a rel table if it doesn't exist.
        For simplicity, this allows ANY to ANY, which Kuzu handles using multiple table creation
        or we assume a generic rel table. In Kùzu, rel tables strictly define FROM and TO tables.
        For this generic MVP, we will create a generic rel table between ANY node tables, but Kuzu requires specific FROM/TO.
        Since we don't know the FROM/TO tables at this layer easily without looking up IDs, 
        we will rely on specific Cypher CREATE statements or just log a warning.
        """
        if rel_type in self._rel_tables:
            return
            
        # In Kùzu, creating a REL table requires specifying FROM and TO node tables.
        # Since this generic method doesn't know the tables, we skip auto-creation 
        # and assume the user has pre-created it via Cypher, or we log a warning.
        logger.warning(
            f"Kùzu requires specifying FROM and TO tables for REL {rel_type}. "
            f"Please pre-create it with: CREATE REL TABLE {rel_type} (FROM NodeA TO NodeB)"
        )

    def execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return the results."""
        results = []
        try:
            res = self.conn.execute(query, parameters or {})
            if res.has_next():
                # For simplicity, convert the Kuzu result set into a list of dicts
                # Note: Kuzu's result set API returns rows. We need column names.
                columns = [col for col in res.get_column_names()]
                while res.has_next():
                    row = res.get_next()
                    results.append(dict(zip(columns, row)))
        except Exception as e:
            logger.error(f"Kuzu query failed: {query} -> {e}")
            raise
        return results

    def add_node(self, label: str, properties: Dict[str, Any]) -> None:
        """Add a node to the graph."""
        self._ensure_node_table(label, properties)
        
        # Build Cypher CREATE query
        keys = list(properties.keys())
        cypher_props = ", ".join([f"{k}: ${k}" for k in keys])
        query = f"CREATE (n:{label} {{{cypher_props}}})"
        
        # Sanitize parameters (convert dicts/lists to JSON strings for Kuzu STRING cols)
        safe_params = {}
        for k, v in properties.items():
            if isinstance(v, (dict, list)):
                safe_params[k] = json.dumps(v)
            else:
                safe_params[k] = v
                
        self.execute_query(query, safe_params)

    def add_edge(self, source_id: Any, target_id: Any, rel_type: str, properties: Optional[Dict[str, Any]] = None) -> None:
        """Add an edge between two nodes. (Assumes nodes have an 'id' or 'node_id' or 'guid' property)."""
        self._ensure_rel_table(rel_type)
        
        properties = properties or {}
        cypher_props = ""
        if properties:
            keys = list(properties.keys())
            cypher_props = ", ".join([f"{k}: ${k}" for k in keys])
            cypher_props = f" {{{cypher_props}}}"
            
        # Generic match across all nodes in Kuzu isn't supported without labels.
        # But wait, Kuzu requires node labels in MATCH.
        # So a completely generic add_edge is tricky in strictly typed Kùzu.
        # We will log an error guiding the user to use execute_query instead for Kuzu.
        logger.warning(
            "Generic add_edge is not fully supported in Kùzu due to strict typing. "
            "Please use execute_query(MATCH (a:Type1), (b:Type2) CREATE (a)-[:REL]->(b)) instead."
        )

    def clear(self) -> None:
        """Clear all data from the graph by destroying the database."""
        # Kuzu doesn't have a simple DROP ALL. We'd have to drop all tables.
        for t in self._rel_tables:
            self.execute_query(f"DROP TABLE {t}")
        for t in self._node_tables:
            self.execute_query(f"DROP TABLE {t}")
        self._node_tables.clear()
        self._rel_tables.clear()
