"""Local-first lookup layer over the crawled bSDD ontology tables.

Sits in front of BSDDClient: a class or property already crawled into
public.bsdd_classes / bsdd_properties / bsdd_class_properties (see
scripts/crawl_bsdd_ontology.py) resolves entirely from the database -- no
external bSDD API round trip, no rate limit, no per-hover network latency.
Anything not found locally falls back to a live bSDD lookup via the caller's
BSDDClient, and the result is written back into these tables afterwards --
so a live miss today is a local hit tomorrow, and the ontology grows from
actual usage, not just the seeded crawl.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from app.logging_config import get_logger
from app.modules.contracts import BSDDClassItem, BSDDPropertyItem
from app.services.bsdd_client import BSDDClient
from app.services.persistence import PersistenceService

logger = get_logger(__name__)

_CLASS_SCHEMA = {
    "uri": str,
    "code": str,
    "name": str,
    "dictionary_uri": str,
    "class_type": str,
    "parent_class_uri": str,
    "related_ifc_entities": str,  # jsonb
    "definition": str,
    "description": str,
}
_PROPERTY_SCHEMA = {
    "uri": str,
    "code": str,
    "name": str,
    "data_type": str,
    "definition": str,
    "description": str,
    "units": str,  # jsonb
}
_EDGE_SCHEMA = {
    "class_uri": str,
    "property_uri": str,
    "property_set": str,
    "data_type": str,
    "units": str,  # jsonb
    "allowed_values": str,  # jsonb
}

SECONDS_PER_HOUR = 3600
# The crawl is a manual, occasional operation (scripts/crawl_bsdd_ontology.py)
# and writes go through persist_class(), which patches this snapshot directly
# -- so a full reload is only needed to pick up an external change (a rerun
# of the crawler, a manual DB edit), not to stay current with this process's
# own writes. Refreshing hourly instead of every few minutes avoids paying
# the ~20s paginated reload cost on an otherwise-idle server.
_REFRESH_SECONDS = 4 * SECONDS_PER_HOUR


class BSDDOntologyRepository:
    """Reads and opportunistically writes the local bSDD ontology cache."""

    def __init__(self, db=None):
        self._db = db or PersistenceService.get_db()
        self._classes = PersistenceService.get_table("bsdd_classes", _CLASS_SCHEMA, pk="uri", db=None)
        self._properties = PersistenceService.get_table("bsdd_properties", _PROPERTY_SCHEMA, pk="uri", db=None)
        self._edges = PersistenceService.get_table("bsdd_class_properties", _EDGE_SCHEMA, pk="id", db=None)

        self._classes_by_uri: dict[str, dict] = {}
        self._properties_by_uri: dict[str, dict] = {}
        self._edges_by_class: dict[str, list[dict]] = {}
        self._cached_at = 0.0

    # ── Read path (local ontology, refreshed periodically) ─────────────────

    def _refresh_if_stale(self) -> None:
        if self._classes_by_uri and (time.time() - self._cached_at) < _REFRESH_SECONDS:
            return
        try:
            self._classes_by_uri = {row["uri"]: row for row in self._classes.rows}
            self._properties_by_uri = {row["uri"]: row for row in self._properties.rows}
            edges_by_class: dict[str, list[dict]] = {}
            for row in self._edges.rows:
                edges_by_class.setdefault(row["class_uri"], []).append(row)
            self._edges_by_class = edges_by_class
            self._cached_at = time.time()
        except Exception:
            logger.exception("Failed to load local bSDD ontology; falling back to live lookups only")

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
        """Best-effort upsert of a live-fetched class into the local ontology.

        Never raises: a caching failure must not break the live lookup that
        triggered it. Called after any get_class() falls through to a live
        BSDDClient fetch, so the next lookup for the same class is local.
        """
        try:
            self._db.table("bsdd_classes").upsert(
                {
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
                },
                on_conflict="uri",
            ).execute()

            if item.properties:
                prop_rows = [
                    {
                        "uri": p.uri,
                        "code": p.uri.rsplit("/", 1)[-1],
                        "name": p.name,
                        "data_type": p.data_type,
                        "definition": p.definition,
                        "description": p.description,
                        "units": [p.units] if p.units else [],
                    }
                    for p in item.properties
                    if p.uri
                ]
                self._db.table("bsdd_properties").upsert(prop_rows, on_conflict="uri").execute()

                edge_rows = [
                    {
                        "class_uri": item.uri,
                        "property_uri": p.uri,
                        "property_set": p.property_set,
                        "data_type": p.data_type,
                        "units": [p.units] if p.units else [],
                        "allowed_values": p.allowed_values,
                    }
                    for p in item.properties
                    if p.uri
                ]
                self._db.table("bsdd_class_properties").upsert(
                    edge_rows, on_conflict="class_uri,property_uri,property_set"
                ).execute()

            # Patch the in-memory snapshot directly rather than invalidating
            # it -- a full reload is the expensive part (a paginated re-read
            # of every row in all three tables), and the whole point of this
            # cache is to not pay that cost on every write either.
            self._classes_by_uri[item.uri] = {
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
            edges = []
            for p in item.properties:
                if not p.uri:
                    continue
                self._properties_by_uri[p.uri] = {
                    "uri": p.uri,
                    "code": p.uri.rsplit("/", 1)[-1],
                    "name": p.name,
                    "data_type": p.data_type,
                    "definition": p.definition,
                    "description": p.description,
                    "units": [p.units] if p.units else [],
                }
                edges.append(
                    {
                        "class_uri": item.uri,
                        "property_uri": p.uri,
                        "property_set": p.property_set,
                        "data_type": p.data_type,
                        "units": [p.units] if p.units else [],
                        "allowed_values": p.allowed_values,
                    }
                )
            self._edges_by_class[item.uri] = edges
        except Exception:
            logger.exception("Failed to cache bSDD class %s locally (non-fatal)", item.uri)

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
