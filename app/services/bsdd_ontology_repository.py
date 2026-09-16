"""Local-first and 100% database-independent lookup layer for the bSDD ontology.

Sits in front of BSDDClient: the curated reference ontology is bundled locally
as a single DuckDB file (data/reference/bsdd/bsdd_ontology.duckdb, built by
scripts/crawl_bsdd_ontology.py / scripts/ingest_ifc_release.py), and dynamic
live lookups persist to a local DuckDB runtime cache in
data/cache/bsdd/bsdd_runtime.duckdb (see app.services.bsdd_duckdb_store).
Both are loaded into plain Python dicts on startup, so lookups resolve
entirely in-process (< 50ms cold start, < 1ms memory lookup) with zero
database *server*, zero network latency, and zero remote database reliance --
DuckDB here is just an embedded file format, not a service to run or connect to.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

from app.logging_config import get_logger
from app.modules.contracts import BSDDClassItem, BSDDPropertyItem
from app.services import bsdd_duckdb_store
from app.services.bsdd_client import BSDDClient

logger = get_logger(__name__)

SECONDS_PER_HOUR = 3600
# Reference ontologies are static bundled files; refreshing hourly ensures
# any background crawler or runtime updates to disk cache are picked up.
_REFRESH_SECONDS = 4 * SECONDS_PER_HOUR


class BSDDOntologyRepository:
    """In-memory, local-file-backed bSDD ontology repository with zero database reliance."""

    def __init__(self, db: Any = None) -> None:
        # db accepted for backward compatibility with legacy test callers, but unused.
        self._reference_dir = Path(__file__).resolve().parent.parent.parent / "data" / "reference" / "bsdd"
        self._cache_dir = Path(__file__).resolve().parent.parent.parent / "data" / "cache" / "bsdd"

        self._classes_by_uri: dict[str, dict[str, Any]] = {}
        self._properties_by_uri: dict[str, dict[str, Any]] = {}
        self._edges_by_class: dict[str, list[dict[str, Any]]] = {}
        self._cached_at: float = 0.0

    # ── Read path (local ontology, refreshed periodically) ─────────────────

    def _load_from_local_reference(self) -> bool:
        """Load curated bSDD baseline and dynamic runtime cache synchronously (< 50ms)."""
        reference_db = self._reference_dir / "bsdd_ontology.duckdb"
        if not reference_db.exists():
            return False

        try:
            classes_by_uri, properties_by_uri, edge_rows = bsdd_duckdb_store.read_ontology_tables(reference_db)
            if not classes_by_uri:
                return False

            self._classes_by_uri = classes_by_uri
            self._properties_by_uri = properties_by_uri
            edges_by_class: dict[str, list[dict[str, Any]]] = {}
            for row in edge_rows:
                edges_by_class.setdefault(row["class_uri"], []).append(row)
            self._edges_by_class = edges_by_class

            # Merge dynamic runtime cache (live-fetched classes, cached opportunistically) if present.
            runtime_db = self._cache_dir / "bsdd_runtime.duckdb"
            rt_classes, rt_properties, rt_edges = bsdd_duckdb_store.read_ontology_tables(runtime_db)
            self._classes_by_uri.update(rt_classes)
            self._properties_by_uri.update(rt_properties)
            for row in rt_edges:
                self._edges_by_class.setdefault(row["class_uri"], []).append(row)

            self._cached_at = time.time()
            logger.debug(
                "Loaded local bSDD reference DuckDB (%d classes, %d properties, %d classes with edges) in <50ms",
                len(self._classes_by_uri),
                len(self._properties_by_uri),
                len(self._edges_by_class),
            )
            return True
        except Exception:
            logger.exception("Failed to load local bSDD reference DuckDB")
            return False

    def _refresh_if_stale(self) -> None:
        if self._classes_by_uri and (time.time() - self._cached_at) < _REFRESH_SECONDS:
            return
        self._load_from_local_reference()

    def _class_item(self, uri: str) -> Optional[BSDDClassItem]:
        row = self._classes_by_uri.get(uri)
        if row is None:
            return None
        props: list[BSDDPropertyItem] = []
        for edge in self._edges_by_class.get(uri, []):
            prop_row = self._properties_by_uri.get(edge["property_uri"])
            if not prop_row:
                continue
            units = edge.get("units") or prop_row.get("units") or []
            props.append(
                BSDDPropertyItem(
                    uri=prop_row["uri"],
                    name=prop_row["name"],
                    property_set=edge.get("property_set"),
                    data_type=edge.get("data_type") or prop_row.get("data_type"),
                    units=units[0] if units else None,
                    allowed_values=edge.get("allowed_values") or [],
                    definition=prop_row.get("definition"),
                    description=prop_row.get("description"),
                )
            )
        parent_uri = row.get("parent_class_uri")
        child_codes = [
            r["code"] for r in self._classes_by_uri.values() if r.get("parent_class_uri") == uri
        ]
        return BSDDClassItem(
            uri=row["uri"],
            code=row["code"],
            name=row["name"],
            dictionary_uri=row["dictionary_uri"],
            class_type=row.get("class_type") or "Class",
            parent_class_code=(parent_uri or "").rsplit("/", 1)[-1] or None,
            child_class_codes=sorted(child_codes),
            related_ifc_entities=row.get("related_ifc_entities") or [],
            properties=props,
            definition=row.get("definition"),
            description=row.get("description"),
        )

    def get_class(self, dictionary_uri: str, code: str) -> Optional[BSDDClassItem]:
        """Look up a class by dictionary + code, local ontology only."""
        self._refresh_if_stale()
        return self._class_item(f"{dictionary_uri}/class/{code}")

    def get_class_by_uri(self, uri: str) -> Optional[BSDDClassItem]:
        self._refresh_if_stale()
        return self._class_item(uri)

    def search_classes(self, query: str, limit: int = 10) -> list[BSDDClassItem]:
        self._refresh_if_stale()
        lowered = query.strip().lower()
        if not lowered:
            return []
        # Name/code matches only, exact-name first -- ranking by relevance
        # the same way the live bSDD search does (see BSDDClient.search_properties'
        # docstring): a query matching only a class's long-form definition is
        # a much weaker signal than matching its actual name or code, and
        # mixing the two drowns real matches in noise.
        hits = sorted(
            (
                row
                for row in self._classes_by_uri.values()
                if lowered in row["name"].lower() or lowered in row["code"].lower()
            ),
            key=lambda row: row["name"].lower() != lowered,
        )
        items = [self._class_item(row["uri"]) for row in hits[:limit]]
        return [item for item in items if item is not None]

    def search_properties(self, query: str, limit: int = 8) -> list[BSDDPropertyItem]:
        self._refresh_if_stale()
        lowered = query.strip().lower()
        if not lowered:
            return []
        # Name matches first, ranked exact-first; only fall back to matching
        # the (much longer, noisier) definition text when nothing matched by
        # name at all -- see search_classes' comment above.
        by_name = sorted(
            (row for row in self._properties_by_uri.values() if lowered in row["name"].lower()),
            key=lambda row: row["name"].lower() != lowered,
        )
        hits = by_name[:limit]
        if not hits:
            hits = [
                row
                for row in self._properties_by_uri.values()
                if lowered in (row.get("definition") or "").lower()
            ][:limit]
        return [
            BSDDPropertyItem(
                uri=row["uri"],
                name=row["name"],
                data_type=row.get("data_type"),
                units=(row.get("units") or [None])[0],
                allowed_values=[],
                definition=row.get("definition"),
                description=row.get("description"),
            )
            for row in hits
        ]

    def list_classes(self) -> list[dict[str, Any]]:
        """Lightweight rows (uri/code/name/parent) for browsing -- e.g. a wiki tree."""
        self._refresh_if_stale()
        return [
            {
                "uri": row["uri"],
                "code": row["code"],
                "name": row["name"],
                "class_type": row.get("class_type") or "Class",
                "parent_class_uri": row.get("parent_class_uri"),
                "dictionary_uri": row.get("dictionary_uri"),
            }
            for row in self._classes_by_uri.values()
        ]

    def get_property_by_uri(self, uri: str) -> Optional[dict[str, Any]]:
        self._refresh_if_stale()
        row = self._properties_by_uri.get(uri)
        if row is None:
            return None
        return {
            "uri": row["uri"],
            "code": row["code"],
            "name": row["name"],
            "data_type": row.get("data_type"),
            "units": row.get("units") or [],
            "definition": row.get("definition"),
            "description": row.get("description"),
            "used_by_classes": self.classes_using_property(uri),
        }

    def classes_using_property(self, property_uri: str) -> list[dict[str, Any]]:
        """Which locally-known classes carry a given property -- the reverse edge."""
        self._refresh_if_stale()
        out = []
        for class_uri, edges in self._edges_by_class.items():
            for edge in edges:
                if edge["property_uri"] == property_uri:
                    row = self._classes_by_uri.get(class_uri)
                    if row:
                        out.append({"uri": row["uri"], "code": row["code"], "name": row["name"]})
                    break
        return out

    # ── Write path: opportunistic caching of a live bSDD lookup ────────────

    def persist_class(self, item: BSDDClassItem) -> None:
        """Persist a live-fetched class into in-memory ontology and the local DuckDB runtime cache.

        Never raises: a caching failure must not break the live lookup that
        triggered it. Persists to data/cache/bsdd/bsdd_runtime.duckdb so the
        next lookup or server restart resolves it locally without repeating
        network calls.
        """
        try:
            class_row = {
                "uri": item.uri,
                "code": item.code,
                "name": item.name,
                "dictionary_uri": item.dictionary_uri,
                "class_type": item.class_type,
                "parent_class_uri": f"{item.dictionary_uri}/class/{item.parent_class_code}"
                if item.parent_class_code
                else None,
                "related_ifc_entities": item.related_ifc_entities,
                "definition": item.definition,
                "description": item.description,
            }
            self._classes_by_uri[item.uri] = class_row

            prop_rows = []
            edge_rows = []
            for p in item.properties:
                if not p.uri:
                    continue
                p_row = {
                    "uri": p.uri,
                    "code": p.uri.rsplit("/", 1)[-1],
                    "name": p.name,
                    "data_type": p.data_type,
                    "definition": p.definition,
                    "description": p.description,
                    "units": [p.units] if p.units else [],
                }
                self._properties_by_uri[p.uri] = p_row
                prop_rows.append(p_row)

                e_row = {
                    "class_uri": item.uri,
                    "property_uri": p.uri,
                    "property_set": p.property_set,
                    "data_type": p.data_type,
                    "units": [p.units] if p.units else [],
                    "allowed_values": p.allowed_values,
                }
                edge_rows.append(e_row)

            self._edges_by_class[item.uri] = edge_rows

            self._persist_to_local_cache(class_row, prop_rows, edge_rows)
        except Exception:
            logger.exception("Failed to cache bSDD class %s locally (non-fatal)", item.uri)

    def _persist_to_local_cache(
        self, class_row: dict[str, Any], prop_rows: list[dict[str, Any]], edge_rows: list[dict[str, Any]]
    ) -> None:
        """Persist dynamic runtime records to data/cache/bsdd/bsdd_runtime.duckdb."""
        runtime_db = self._cache_dir / "bsdd_runtime.duckdb"
        bsdd_duckdb_store.upsert_class(runtime_db, class_row, prop_rows, edge_rows)

    # ── Local-first orchestration ───────────────────────────────────────────

    def get_class_cached(self, client: BSDDClient, dictionary_uri: str, code: str) -> Optional[BSDDClassItem]:
        """Local ontology first; on a miss, fetch live and persist for next time."""
        local = self.get_class(dictionary_uri, code)
        if local is not None:
            return local
        live = client.get_class(dictionary_uri, code)
        if live is not None:
            self.persist_class(live)
        return live


_REPOSITORY: BSDDOntologyRepository | None = None


def get_bsdd_ontology_repository() -> BSDDOntologyRepository:
    """Process-wide singleton, matching DEFAULT_BSDD_CLIENT's lifecycle."""
    global _REPOSITORY
    if _REPOSITORY is None:
        _REPOSITORY = BSDDOntologyRepository()
    return _REPOSITORY
