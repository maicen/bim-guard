"""Local-file DuckDB storage for the bSDD ontology (classes/properties/edges).

Replaces the earlier flat-JSON reference/cache format with a single embedded
DuckDB database file -- still zero network, zero external database server
(consistent with app.services.bsdd_ontology_repository's "100%
database-independent" design), but with real column types, primary-key
upserts, and a far smaller on-disk footprint than repeating the same JSON
keys across 16k+ rows.

Shared between:
- app.services.bsdd_ontology_repository (runtime reads + live-lookup cache writes)
- scripts/crawl_bsdd_ontology.py and scripts/ingest_ifc_release.py (bulk rewrite
  of the curated reference database)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

_CLASSES_COLUMNS = (
    "uri",
    "code",
    "name",
    "dictionary_uri",
    "class_type",
    "parent_class_uri",
    "related_ifc_entities",
    "definition",
    "description",
)
_PROPERTIES_COLUMNS = ("uri", "code", "name", "data_type", "definition", "description", "units")
_EDGES_COLUMNS = ("class_uri", "property_uri", "property_set", "data_type", "units", "allowed_values")

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS classes (
    uri VARCHAR PRIMARY KEY,
    code VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    dictionary_uri VARCHAR NOT NULL,
    class_type VARCHAR NOT NULL,
    parent_class_uri VARCHAR,
    related_ifc_entities VARCHAR[] NOT NULL,
    definition VARCHAR,
    description VARCHAR
);
CREATE INDEX IF NOT EXISTS idx_classes_dictionary ON classes (dictionary_uri);
CREATE INDEX IF NOT EXISTS idx_classes_parent ON classes (parent_class_uri);

CREATE TABLE IF NOT EXISTS properties (
    uri VARCHAR PRIMARY KEY,
    code VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    data_type VARCHAR,
    definition VARCHAR,
    description VARCHAR,
    units VARCHAR[] NOT NULL
);

CREATE TABLE IF NOT EXISTS class_properties (
    class_uri VARCHAR NOT NULL,
    property_uri VARCHAR NOT NULL,
    property_set VARCHAR,
    data_type VARCHAR,
    units VARCHAR[] NOT NULL,
    allowed_values VARCHAR[] NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_edges_class ON class_properties (class_uri);
CREATE INDEX IF NOT EXISTS idx_edges_property ON class_properties (property_uri);
"""


def _ensure_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(_SCHEMA_SQL)


def _row_to_class_tuple(row: dict[str, Any]) -> tuple:
    return (
        row["uri"],
        row["code"],
        row["name"],
        row["dictionary_uri"],
        row.get("class_type") or "Class",
        row.get("parent_class_uri"),
        row.get("related_ifc_entities") or [],
        row.get("definition"),
        row.get("description"),
    )


def _row_to_property_tuple(row: dict[str, Any]) -> tuple:
    return (
        row["uri"],
        row.get("code") or row["uri"].rsplit("/", 1)[-1],
        row["name"],
        row.get("data_type"),
        row.get("definition"),
        row.get("description"),
        row.get("units") or [],
    )


def _row_to_edge_tuple(row: dict[str, Any]) -> tuple:
    return (
        row["class_uri"],
        row["property_uri"],
        row.get("property_set"),
        row.get("data_type"),
        row.get("units") or [],
        row.get("allowed_values") or [],
    )


def read_ontology_tables(db_path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Read the whole database into the same (classes, properties, edges) shape the old JSON loader returned.

    classes/properties come back keyed by uri; edges as a flat list of dicts.
    Returns empty structures (not an error) if `db_path` doesn't exist yet.
    """
    if not db_path.exists():
        return {}, {}, []

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        classes = {
            row[0]: dict(zip(_CLASSES_COLUMNS, row))
            for row in con.execute(f"SELECT {', '.join(_CLASSES_COLUMNS)} FROM classes").fetchall()
        }
        properties = {
            row[0]: dict(zip(_PROPERTIES_COLUMNS, row))
            for row in con.execute(f"SELECT {', '.join(_PROPERTIES_COLUMNS)} FROM properties").fetchall()
        }
        edges = [
            dict(zip(_EDGES_COLUMNS, row))
            for row in con.execute(f"SELECT {', '.join(_EDGES_COLUMNS)} FROM class_properties").fetchall()
        ]
        return classes, properties, edges
    finally:
        con.close()


def write_ontology_tables(
    db_path: Path,
    class_rows: list[dict[str, Any]],
    property_rows: list[dict[str, Any]],
    edge_rows: list[dict[str, Any]],
) -> None:
    """Bulk-overwrite the whole database from fully-merged rows (the crawler/ingest scripts' write path).

    Mirrors the old save_local_reference_json's "write the merged snapshot"
    semantics: callers merge against read_ontology_tables()'s output in
    Python first, then pass the complete result here to replace the tables
    atomically (DuckDB DDL inside a connection is transactional).
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    try:
        con.execute("BEGIN TRANSACTION")
        con.execute("DROP TABLE IF EXISTS classes")
        con.execute("DROP TABLE IF EXISTS properties")
        con.execute("DROP TABLE IF EXISTS class_properties")
        _ensure_schema(con)
        con.executemany(
            f"INSERT INTO classes ({', '.join(_CLASSES_COLUMNS)}) VALUES ({', '.join('?' * len(_CLASSES_COLUMNS))})",
            [_row_to_class_tuple(r) for r in class_rows],
        )
        con.executemany(
            f"INSERT INTO properties ({', '.join(_PROPERTIES_COLUMNS)}) VALUES ({', '.join('?' * len(_PROPERTIES_COLUMNS))})",
            [_row_to_property_tuple(r) for r in property_rows],
        )
        con.executemany(
            f"INSERT INTO class_properties ({', '.join(_EDGES_COLUMNS)}) VALUES ({', '.join('?' * len(_EDGES_COLUMNS))})",
            [_row_to_edge_tuple(r) for r in edge_rows],
        )
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()


def upsert_class(
    db_path: Path,
    class_row: dict[str, Any],
    property_rows: list[dict[str, Any]],
    edge_rows: list[dict[str, Any]],
) -> None:
    """Persist one live-fetched class (the runtime cache write path -- app.services.bsdd_ontology_repository).

    Class/property rows upsert by primary key (uri); a class's edges are
    replaced wholesale (delete-then-insert), matching the prior in-memory
    `self._edges_by_class[item.uri] = edge_rows` full-replace semantics.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    try:
        _ensure_schema(con)
        con.execute("BEGIN TRANSACTION")
        con.execute(
            f"""
            INSERT INTO classes ({', '.join(_CLASSES_COLUMNS)}) VALUES ({', '.join('?' * len(_CLASSES_COLUMNS))})
            ON CONFLICT (uri) DO UPDATE SET
                code = excluded.code,
                name = excluded.name,
                dictionary_uri = excluded.dictionary_uri,
                class_type = excluded.class_type,
                parent_class_uri = excluded.parent_class_uri,
                related_ifc_entities = excluded.related_ifc_entities,
                definition = excluded.definition,
                description = excluded.description
            """,
            _row_to_class_tuple(class_row),
        )
        if property_rows:
            con.executemany(
                f"""
                INSERT INTO properties ({', '.join(_PROPERTIES_COLUMNS)}) VALUES ({', '.join('?' * len(_PROPERTIES_COLUMNS))})
                ON CONFLICT (uri) DO UPDATE SET
                    code = excluded.code,
                    name = excluded.name,
                    data_type = excluded.data_type,
                    definition = excluded.definition,
                    description = excluded.description,
                    units = excluded.units
                """,
                [_row_to_property_tuple(r) for r in property_rows],
            )
        con.execute("DELETE FROM class_properties WHERE class_uri = ?", [class_row["uri"]])
        if edge_rows:
            con.executemany(
                f"INSERT INTO class_properties ({', '.join(_EDGES_COLUMNS)}) VALUES ({', '.join('?' * len(_EDGES_COLUMNS))})",
                [_row_to_edge_tuple(r) for r in edge_rows],
            )
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()


__all__ = ["read_ontology_tables", "write_ontology_tables", "upsert_class"]
