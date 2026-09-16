"""Crawl a curated branch of the bSDD IFC 4.3 hierarchy into the local reference DuckDB.

Outputs a single bundled DuckDB file at data/reference/bsdd/bsdd_ontology.duckdb
(see app.services.bsdd_duckdb_store) directly from the live buildingSMART Data
Dictionary API -- an embedded, zero-server database file, not a database to run
or connect to.

The IFC *entity* hierarchy (classType=Class) is deliberately curated, not a
full-dictionary crawl: starting from a set of seed classes, it walks each seed's
full DESCENDANT subtree (children, recursively) plus its ANCESTOR chain up to
IfcRoot -- but does NOT expand an ancestor's other children.

Usage:
    uv run python scripts/crawl_bsdd_ontology.py --curated
    uv run python scripts/crawl_bsdd_ontology.py --roots IfcDoor IfcWindow
    uv run python scripts/crawl_bsdd_ontology.py --max-classes 50 --dry-run

Per-class fetches (the GroupOfProperties/domain-class N+1 fan-out, and each
BFS level of the IFC entity walk) run concurrently via a thread pool, bounded
by --workers (default: BSDD_MAX_CONCURRENT_REQUESTS in app/services/
bsdd_client.py -- see that constant's comment for how the safe concurrency
ceiling was measured against the live, undocumented bSDD throttle). The
shared httpx.Client there also reuses connections (keep-alive) instead of
opening a fresh TLS handshake per request.
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.modules.contracts import BSDDClassItem  # noqa: E402
from app.services import bsdd_duckdb_store  # noqa: E402
from app.services.bsdd_client import (  # noqa: E402
    BSDD_MAX_CONCURRENT_REQUESTS,
    CURATED_DICTIONARY_METADATA,
    BSDDClient,
)

IFC43_DICTIONARY_URI = "https://identifier.buildingsmart.org/uri/buildingsmart/ifc/4.3"
DEFAULT_REFERENCE_DIR = Path(__file__).resolve().parent.parent / "data" / "reference" / "bsdd"

CURATED_BSDD_DICTIONARIES = [
    "https://identifier.buildingsmart.org/uri/buildingsmart/ifc/4.3",
    "https://identifier.buildingsmart.org/uri/accord/ACCORD/1.0",
    "https://identifier.buildingsmart.org/uri/bsird/rir/1.0",
    "https://identifier.buildingsmart.org/uri/bs-energy/subsea-flexible-pipes/2.1",
    "https://identifier.buildingsmart.org/uri/nbs/uniclass2015/1",
]

DEFAULT_CORE_SEED_CLASSES = [
    "IfcWall",
    "IfcBeam",
    "IfcColumn",
    "IfcSlab",
    "IfcDoor",
    "IfcWindow",
    "IfcCovering",
    "IfcPlate",
    "IfcMember",
    "IfcRailing",
    "IfcStair",
    "IfcPipeSegment",
    "IfcPipeFitting",
    "IfcValve",
    "IfcPump",
    "IfcDuctSegment",
    "IfcDuctFitting",
    "IfcAirTerminal",
    "IfcSpace",
    "IfcBuildingElementProxy",
]


def default_seed_roots() -> list[str]:
    """Return default seed classes covering all major building and MEP elements."""
    return list(DEFAULT_CORE_SEED_CLASSES)


def load_existing_reference_data(output_dir: Path) -> tuple[dict[str, dict], dict[str, dict], list[dict]]:
    """Load existing bundled reference rows from the local DuckDB file if present."""
    try:
        return bsdd_duckdb_store.read_ontology_tables(output_dir / "bsdd_ontology.duckdb")
    except Exception:
        return {}, {}, []


class Crawler:
    def __init__(
        self,
        client: BSDDClient,
        dictionary_uri: str,
        max_classes: int | None,
        existing_classes: set[str] | None = None,
        workers: int = BSDD_MAX_CONCURRENT_REQUESTS,
    ):
        self.client = client
        self.dictionary_uri = dictionary_uri
        self.max_classes = max_classes
        self.existing_classes = existing_classes or set()
        self.workers = workers
        self.visited: dict[str, BSDDClassItem] = {}

    def _class_uri(self, code: str) -> str:
        return f"{self.dictionary_uri}/class/{code}"

    def _fetch_one(self, code: str) -> BSDDClassItem | None:
        """Fetch a single class.

        Safe to call from any thread -- the client itself caps real network
        concurrency against bSDD and already retries 429s (honoring
        `Retry-After`) inside get_class()/_http_get(). Retrying again here on
        top of that would multiply requests during exactly the situation
        (sustained throttling) where the API most needs fewer, not more.
        """
        return self.client.get_class(self.dictionary_uri, code)

    def _walk_ancestors(self, item: BSDDClassItem) -> None:
        """Fetch (but never expand) a class's parent chain up to IfcRoot."""
        code = item.parent_class_code
        while code:
            uri = self._class_uri(code)
            if uri in self.visited:
                code = self.visited[uri].parent_class_code
                continue
            if uri in self.existing_classes:
                break
            parent = self._fetch_one(code)
            if parent is None:
                print(f"  ! {code} -- not found after retries")
                break
            self.visited[uri] = parent
            print(f"  [{len(self.visited)}] {code}  (ancestor)")
            code = parent.parent_class_code

    def crawl(self, roots: list[str]) -> None:
        """Level-order BFS over the descendant tree.

        Each round's queued codes are fetched concurrently (bounded by
        self.workers) before their children are enqueued for the next round.
        Ancestor walks stay sequential per item -- chains are short and
        heavily cache-deduped across siblings that share ancestors.
        """
        queue: list[str] = list(dict.fromkeys(roots))
        enqueued: set[str] = {self._class_uri(c) for c in queue}

        while queue:
            if self.max_classes is not None:
                remaining = self.max_classes - len(self.visited)
                if remaining <= 0:
                    break
                queue = queue[:remaining]

            batch = [c for c in queue if self._class_uri(c) not in self.visited and self._class_uri(c) not in self.existing_classes]
            queue = []
            if not batch:
                continue

            with ThreadPoolExecutor(max_workers=min(self.workers, len(batch))) as pool:
                fetched = list(pool.map(self._fetch_one, batch))

            next_round: list[str] = []
            for code, item in zip(batch, fetched):
                uri = self._class_uri(code)
                if item is None:
                    print(f"  ! {code} -- not found after retries")
                    continue
                self.visited[uri] = item
                print(f"  [{len(self.visited)}] {code}" + ("" if item.definition else "  (no definition)"))
                self._walk_ancestors(item)
                for child_code in item.child_class_codes:
                    child_uri = self._class_uri(child_code)
                    if child_uri not in self.visited and child_uri not in enqueued:
                        next_round.append(child_code)
                        enqueued.add(child_uri)

            queue = next_round


def crawl_classes_by_type(
    client: BSDDClient,
    dictionary_uri: str,
    class_type: str = "class",
    max_items: int | None = None,
    fetch_properties: bool = True,
    existing_classes: set[str] | None = None,
    workers: int = BSDD_MAX_CONCURRENT_REQUESTS,
) -> dict[str, BSDDClassItem]:
    """Fetch classes of a given classType directly from a dictionary listing.

    Used for GroupOfProperties in IFC (Pset_/Qto_ definitions) as well as
    curated domain dictionaries (ACCORD, RIR, Subsea pipes) that do not use
    an IfcRoot ancestor inheritance tree. For classification systems without
    properties (such as Uniclass), fetch_properties=False enables fast batch paging.
    Skips any entity already stored in existing_classes.

    Each page's per-class get_class() calls (the N+1 fan-out for Psets/Qtos
    and domain classes) run concurrently, bounded by `workers` -- the client's
    own semaphore additionally caps real network concurrency against bSDD.
    get_class()/_http_get() already retries 429s internally (honoring
    `Retry-After`), so this doesn't retry again on top of that -- stacking
    retries here would multiply outbound requests during exactly the moment
    (sustained throttling) where fewer requests, not more, are needed.
    """
    visited: dict[str, BSDDClassItem] = {}
    offset = 0
    limit = 1000 if not fetch_properties else 100
    total: int | None = None
    skipped_count = 0

    while total is None or offset < total:
        summaries, total = client.list_classes_by_type(dictionary_uri, class_type, offset, limit)
        if not summaries:
            break

        pending: list[tuple[str, str]] = []  # (code, uri)
        for summary in summaries:
            code = summary.get("code")
            if not code:
                continue
            uri = summary.get("uri") or f"{dictionary_uri}/class/{code}"
            if existing_classes and uri in existing_classes:
                skipped_count += 1
                continue

            if max_items is not None and len(visited) + len(pending) >= max_items:
                break

            if not fetch_properties:
                item = BSDDClassItem(
                    uri=uri,
                    code=code,
                    name=summary.get("name") or code,
                    dictionary_uri=dictionary_uri,
                    class_type=summary.get("classType") or "Class",
                    description=summary.get("descriptionPart"),
                    properties=[],
                )
                visited[item.uri] = item
            else:
                pending.append((code, uri))

        if pending:
            codes = [code for code, _ in pending]
            with ThreadPoolExecutor(max_workers=min(workers, len(codes))) as pool:
                fetched = list(pool.map(lambda c: client.get_class(dictionary_uri, c), codes))
            for (code, _uri), item in zip(pending, fetched):
                if item is not None:
                    visited[item.uri] = item
                    print(f"  [{class_type} {len(visited)}/{total}] {code}")
                else:
                    print(f"  ! {code} -- not found after retries")

        if not fetch_properties:
            print(f"  [{class_type} {len(visited)}/{total or '?'}] (paged {len(summaries)}, skipped {skipped_count} existing)")

        if max_items is not None and len(visited) >= max_items:
            break

        offset += limit
    if skipped_count:
        print(f"  Skipped {skipped_count} classes already stored in the local reference DuckDB.")
    return visited


def crawl_group_of_properties(
    client: BSDDClient,
    dictionary_uri: str,
    max_items: int | None,
    existing_classes: set[str] | None = None,
    workers: int = BSDD_MAX_CONCURRENT_REQUESTS,
) -> dict[str, BSDDClassItem]:
    """Fetch every GroupOfProperties class (Pset_/Qto_ definition) in a dictionary."""
    return crawl_classes_by_type(
        client,
        dictionary_uri,
        "groupofproperties",
        max_items,
        existing_classes=existing_classes,
        workers=workers,
    )


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
                "class_type": item.class_type,
                "parent_class_uri": f"{item.dictionary_uri}/class/{item.parent_class_code}"
                if item.parent_class_code
                else None,
                "related_ifc_entities": item.related_ifc_entities,
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


def save_local_reference_data(
    output_dir: Path,
    class_rows: list[dict],
    property_rows: list[dict],
    edge_rows: list[dict],
) -> None:
    """Save crawled ontology rows to the bundled local reference DuckDB file."""
    db_path = output_dir / "bsdd_ontology.duckdb"
    bsdd_duckdb_store.write_ontology_tables(db_path, class_rows, property_rows, edge_rows)
    print(f"Saved local reference DuckDB to {db_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--roots", nargs="*", default=None, help="Seed IFC class codes (default: core building elements)")
    parser.add_argument("--dictionary-uri", default=IFC43_DICTIONARY_URI)
    parser.add_argument(
        "--curated",
        action="store_true",
        help="Crawl all curated BIM-Guard compliance, regulatory, and corrosion dictionaries (IFC 4.3, ACCORD, RIR, Subsea, Uniclass 2015)",
    )
    parser.add_argument("--rebuild-ifc", action="store_true", help="Re-crawl IFC 4.3 entity hierarchy even if the reference DuckDB already has it")
    parser.add_argument("--max-classes", type=int, default=None, help="Safety cap on entity/domain classes visited")
    parser.add_argument(
        "--workers",
        type=int,
        default=BSDD_MAX_CONCURRENT_REQUESTS,
        help=f"Max concurrent bSDD requests (default: {BSDD_MAX_CONCURRENT_REQUESTS}, the empirically "
        "safe margin below bSDD's undocumented throttle -- see app/services/bsdd_client.py)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Crawl and print counts without writing to disk")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_REFERENCE_DIR,
        help="Local directory to store the crawled reference DuckDB file (default: data/reference/bsdd)",
    )
    parser.add_argument(
        "--skip-group-of-properties",
        action="store_true",
        help="Skip the exhaustive Pset_/Qto_ (GroupOfProperties) crawl and only walk the IFC entity hierarchy",
    )
    parser.add_argument(
        "--max-group-of-properties",
        type=int,
        default=None,
        help="Safety cap on GroupOfProperties classes visited (default: all of them)",
    )
    args = parser.parse_args()

    bsdd_client = BSDDClient(timeout_seconds=20.0)
    all_visited: dict[str, BSDDClassItem] = {}

    # Load existing reference data to merge against and skip already crawled classes
    existing_classes, existing_props, existing_edges = load_existing_reference_data(args.output_dir)
    existing_class_uris = set(existing_classes.keys())

    target_dictionaries: list[str] = []
    if args.curated:
        target_dictionaries = list(CURATED_BSDD_DICTIONARIES)
    else:
        target_dictionaries = [args.dictionary_uri]

    for dict_uri in target_dictionaries:
        dict_meta = CURATED_DICTIONARY_METADATA.get(dict_uri, {})
        dict_name = dict_meta.get("name", dict_uri)
        print("\n=======================================================")
        print(f"Target Dictionary: {dict_name}")
        print(f"URI: {dict_uri}")
        print("=======================================================")

        if "ifc" in dict_uri.lower():
            if existing_classes and not args.rebuild_ifc and not args.roots:
                print(f"Using existing cached IFC 4.3 reference classes ({len(existing_classes)} classes on disk).")
                continue

            roots = args.roots or default_seed_roots()
            if not roots:
                print("! No seed roots found -- skipping entity tree crawl for IFC.")
            else:
                print(f"Seed roots ({len(roots)}): {', '.join(roots)}")
                crawler = Crawler(
                    bsdd_client, dict_uri, args.max_classes, existing_classes=existing_class_uris, workers=args.workers
                )
                crawler.crawl(roots)
                print(f"Crawled {len(crawler.visited)} IFC entity classes.")
                all_visited.update(crawler.visited)

            if not args.skip_group_of_properties:
                print("\nCrawling GroupOfProperties classes (every Pset_/Qto_ definition)...")
                gop_visited = crawl_group_of_properties(
                    bsdd_client,
                    dict_uri,
                    args.max_group_of_properties,
                    existing_classes=existing_class_uris,
                    workers=args.workers,
                )
                print(f"Crawled {len(gop_visited)} GroupOfProperties classes.")
                all_visited.update(gop_visited)
        elif "uniclass" in dict_uri.lower():
            print("\nCrawling Uniclass 2015 classification taxonomy...")
            uniclass_visited = crawl_classes_by_type(
                bsdd_client,
                dict_uri,
                "class",
                args.max_classes,
                fetch_properties=False,
                existing_classes=existing_class_uris,
                workers=args.workers,
            )
            print(f"Crawled {len(uniclass_visited)} Uniclass classes.")
            all_visited.update(uniclass_visited)
        else:
            print(f"\nCrawling domain classes for {dict_name}...")
            domain_visited = crawl_classes_by_type(
                bsdd_client,
                dict_uri,
                "class",
                args.max_classes,
                fetch_properties=True,
                existing_classes=existing_class_uris,
                workers=args.workers,
            )
            print(f"Crawled {len(domain_visited)} domain classes.")
            all_visited.update(domain_visited)

    crawled_classes, crawled_props, crawled_edges = build_rows(all_visited)

    # Merge crawled rows with existing on-disk data
    merged_classes = dict(existing_classes)
    for row in crawled_classes:
        merged_classes[row["uri"]] = row

    merged_props = dict(existing_props)
    for row in crawled_props:
        merged_props[row["uri"]] = row

    seen_edge_keys = {(e["class_uri"], e["property_uri"], e.get("property_set")) for e in existing_edges}
    merged_edges = list(existing_edges)
    for e in crawled_edges:
        key = (e["class_uri"], e["property_uri"], e.get("property_set"))
        if key not in seen_edge_keys:
            seen_edge_keys.add(key)
            merged_edges.append(e)

    print(
        f"\nFinal Combined Ontology across schemas: {len(merged_classes)} classes, {len(merged_props)} unique properties, "
        f"{len(merged_edges)} class-property edges."
    )

    if args.dry_run:
        print("Dry run -- not writing to disk.")
        return

    if args.output_dir:
        save_local_reference_data(
            args.output_dir,
            list(merged_classes.values()),
            list(merged_props.values()),
            merged_edges,
        )
    print("Done.")


if __name__ == "__main__":
    main()
