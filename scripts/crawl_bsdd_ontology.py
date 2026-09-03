"""Crawl a curated branch of the bSDD IFC 4.3 hierarchy into local tables.

Populates public.bsdd_classes / bsdd_properties / bsdd_class_properties (see
supabase/migrations/20260903213309_create_bsdd_ontology.sql) from the live
buildingSMART Data Dictionary API, so the app can look up class/property
definitions, hierarchy, and relationships without a live bSDD round trip.

Scope is deliberately curated, not a full-dictionary crawl: starting from a
set of seed classes (by default, every distinct target_ifc_class already
used in public.rules), it walks each seed's full DESCENDANT subtree
(children, recursively) plus its ANCESTOR chain up to IfcRoot -- but does
NOT expand an ancestor's other children, which is what would otherwise
explode this into most of the IFC entity hierarchy. A door's cousins (other
built elements) stay out unless they're a seed or a descendant of one.

Usage:
    uv run python scripts/crawl_bsdd_ontology.py
    uv run python scripts/crawl_bsdd_ontology.py --roots IfcDoor IfcWindow
    uv run python scripts/crawl_bsdd_ontology.py --max-classes 50 --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.environment import load_env_file  # noqa: E402
from app.modules.contracts import BSDDClassItem  # noqa: E402
from app.services.bsdd_client import BSDDClient  # noqa: E402
from supabase import Client, create_client  # noqa: E402

IFC43_DICTIONARY_URI = "https://identifier.buildingsmart.org/uri/buildingsmart/ifc/4.3"
BATCH_SIZE = 500


def _build_client() -> Client:
    """Create a Supabase client from server-side credentials.

    Fails loudly rather than silently falling back to the in-memory stub,
    since a crawl that doesn't persist is just a slow way to warm bSDD's
    own cache.
    """
    load_env_file()
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip() or os.getenv("SUPABASE_KEY", "").strip()
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required to persist the crawl.")
    return create_client(url, key)


def default_seed_roots(db: Client) -> list[str]:
    """Distinct target_ifc_class values already used by this app's rules."""
    seen: list[str] = []
    offset = 0
    page_size = 1000
    while True:
        resp = (
            db.table("rules")
            .select("target_ifc_class")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = resp.data or []
        for row in rows:
            cls = (row.get("target_ifc_class") or "").strip()
            if cls and cls not in seen:
                seen.append(cls)
        if len(rows) < page_size:
            break
        offset += page_size
    return seen


class Crawler:
    def __init__(self, client: BSDDClient, dictionary_uri: str, max_classes: int | None, delay: float):
        self.client = client
        self.dictionary_uri = dictionary_uri
        self.max_classes = max_classes
        self.delay = delay
        self.visited: dict[str, BSDDClassItem] = {}

    def _class_uri(self, code: str) -> str:
        return f"{self.dictionary_uri}/class/{code}"

    def _fetch(self, code: str) -> BSDDClassItem | None:
        uri = self._class_uri(code)
        if uri in self.visited:
            return self.visited[uri]
        if self.max_classes is not None and len(self.visited) >= self.max_classes:
            return None

        # BSDDClient._http_get swallows the exception on a failed request
        # (including a 429) and just returns None, indistinguishable from a
        # genuine 404 -- so a rate limit would otherwise silently truncate
        # the crawl. Back off and retry a few times before accepting that as
        # a real miss.
        item = None
        for attempt in range(4):
            item = self.client.get_class(self.dictionary_uri, code)
            if item is not None:
                break
            time.sleep(self.delay * (3**attempt) + 1.0)
        time.sleep(self.delay)

        if item is not None:
            self.visited[uri] = item
            print(f"  [{len(self.visited)}] {code}" + ("" if item.definition else "  (no definition)"))
        else:
            print(f"  ! {code} -- not found after retries")
        return item

    def _walk_ancestors(self, item: BSDDClassItem) -> None:
        """Fetch (but never expand) a class's parent chain up to IfcRoot."""
        code = item.parent_class_code
        while code:
            parent = self._fetch(code)
            if parent is None:
                break
            code = parent.parent_class_code

    def crawl(self, roots: list[str]) -> None:
        queue = list(roots)
        while queue:
            code = queue.pop(0)
            if self._class_uri(code) in self.visited:
                continue
            item = self._fetch(code)
            if item is None:
                continue
            self._walk_ancestors(item)
            for child_code in item.child_class_codes:
                if self._class_uri(child_code) not in self.visited:
                    queue.append(child_code)


def build_rows(visited: dict[str, BSDDClassItem]) -> tuple[list[dict], list[dict], list[dict]]:
    class_rows: list[dict] = []
    property_rows: dict[str, dict] = {}
    edge_rows: list[dict] = []

    for uri, item in visited.items():
        class_rows.append(
            {
                "uri": item.uri,
                "code": item.code,
                "name": item.name,
                "dictionary_uri": item.dictionary_uri,
                "class_type": "Class",
                "parent_class_uri": f"{item.dictionary_uri}/class/{item.parent_class_code}"
                if item.parent_class_code
                else None,
                "definition": item.definition,
                "description": item.description,
            }
        )
        for prop in item.properties:
            if not prop.uri:
                continue
            property_rows.setdefault(
                prop.uri,
                {
                    "uri": prop.uri,
                    "code": prop.uri.rsplit("/", 1)[-1],
                    "name": prop.name,
                    "data_type": prop.data_type,
                    "definition": prop.definition,
                    "description": prop.description,
                    "units": [prop.units] if prop.units else [],
                },
            )
            edge_rows.append(
                {
                    "class_uri": item.uri,
                    "property_uri": prop.uri,
                    "property_set": prop.property_set,
                    "data_type": prop.data_type,
                    "units": [prop.units] if prop.units else [],
                    "allowed_values": prop.allowed_values,
                }
            )

    return class_rows, list(property_rows.values()), edge_rows


def upsert_batches(db: Client, table: str, rows: list[dict], on_conflict: str) -> None:
    for start in range(0, len(rows), BATCH_SIZE):
        chunk = rows[start : start + BATCH_SIZE]
        db.table(table).upsert(chunk, on_conflict=on_conflict).execute()
        print(f"  upserted {table} {start + len(chunk)}/{len(rows)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--roots", nargs="*", default=None, help="Seed IFC class codes (default: distinct target_ifc_class from public.rules)")
    parser.add_argument("--dictionary-uri", default=IFC43_DICTIONARY_URI)
    parser.add_argument("--max-classes", type=int, default=600, help="Safety cap on total classes visited")
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds between bSDD requests")
    parser.add_argument("--dry-run", action="store_true", help="Crawl and print counts without writing to the database")
    args = parser.parse_args()

    db = _build_client()
    roots = args.roots or default_seed_roots(db)
    if not roots:
        raise SystemExit("No seed roots found (public.rules has no target_ifc_class values) -- pass --roots explicitly.")

    print(f"Seed roots ({len(roots)}): {', '.join(roots)}")

    # The default 3s client timeout is tuned for small interactive lookups;
    # a class with 200+ properties (e.g. IfcDoor) can take longer to fetch.
    bsdd_client = BSDDClient(timeout_seconds=20.0)
    crawler = Crawler(bsdd_client, args.dictionary_uri, args.max_classes, args.delay)
    crawler.crawl(roots)

    class_rows, property_rows, edge_rows = build_rows(crawler.visited)
    print(
        f"\nCrawled {len(class_rows)} classes, {len(property_rows)} unique properties, "
        f"{len(edge_rows)} class-property edges."
    )

    if args.dry_run:
        print("Dry run -- not writing to the database.")
        return

    upsert_batches(db, "bsdd_classes", class_rows, on_conflict="uri")
    upsert_batches(db, "bsdd_properties", property_rows, on_conflict="uri")
    upsert_batches(db, "bsdd_class_properties", edge_rows, on_conflict="class_uri,property_uri,property_set")
    print("Done.")


if __name__ == "__main__":
    main()
