"""Crawl a curated branch of the bSDD IFC 4.3 hierarchy into local reference JSON.

Outputs bundled JSON files under data/reference/bsdd/ (bsdd_classes.json,
bsdd_properties.json, bsdd_class_properties.json) directly from the live
buildingSMART Data Dictionary API, completely eliminating database dependencies.

The IFC *entity* hierarchy (classType=Class) is deliberately curated, not a
full-dictionary crawl: starting from a set of seed classes, it walks each seed's
full DESCENDANT subtree (children, recursively) plus its ANCESTOR chain up to
IfcRoot -- but does NOT expand an ancestor's other children.

Usage:
    uv run python scripts/crawl_bsdd_ontology.py --curated
    uv run python scripts/crawl_bsdd_ontology.py --roots IfcDoor IfcWindow
    uv run python scripts/crawl_bsdd_ontology.py --max-classes 50 --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.modules.contracts import BSDDClassItem  # noqa: E402
from app.services.bsdd_client import CURATED_DICTIONARY_METADATA, BSDDClient  # noqa: E402

IFC43_DICTIONARY_URI = "https://identifier.buildingsmart.org/uri/buildingsmart/ifc/4.3"
DEFAULT_REFERENCE_DIR = Path(__file__).resolve().parent.parent / "data" / "reference" / "bsdd"

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


def crawl_classes_by_type(
    client: BSDDClient,
    dictionary_uri: str,
    class_type: str = "class",
    delay: float = 0.5,
    max_items: int | None = None,
) -> dict[str, BSDDClassItem]:
    """Fetch classes of a given classType directly from a dictionary listing.

    Used for GroupOfProperties in IFC (Pset_/Qto_ definitions) as well as
    curated domain dictionaries (ACCORD, RIR, Subsea pipes) that do not use
    an IfcRoot ancestor inheritance tree.
    """
    visited: dict[str, BSDDClassItem] = {}
    offset = 0
    limit = 100
    total: int | None = None
    while total is None or offset < total:
        summaries, total = client.list_classes_by_type(dictionary_uri, class_type, offset, limit)
        if not summaries:
            break
        for summary in summaries:
            code = summary.get("code")
            if not code:
                continue
            if max_items is not None and len(visited) >= max_items:
                return visited

            item = None
            for attempt in range(5):
                item = client.get_class(dictionary_uri, code)
                if item is not None:
                    break
                backoff = delay * (2**attempt) + 1.5
                time.sleep(backoff)
            time.sleep(delay)

            if item is not None:
                visited[item.uri] = item
                print(f"  [{class_type} {len(visited)}/{total}] {code}")
            else:
                print(f"  ! {code} -- not found after retries")
        offset += limit
    return visited


def crawl_group_of_properties(
    client: BSDDClient, dictionary_uri: str, delay: float, max_items: int | None
) -> dict[str, BSDDClassItem]:
    """Fetch every GroupOfProperties class (Pset_/Qto_ definition) in a dictionary.

    Paged straight from the dictionary's class listing rather than walked
    from seeds -- see the module docstring for why these need a different
    strategy than the IFC entity hierarchy.
    """
    return crawl_classes_by_type(client, dictionary_uri, "groupofproperties", delay, max_items)


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


def save_local_reference_json(
    output_dir: Path,
    class_rows: list[dict],
    property_rows: list[dict],
    edge_rows: list[dict],
) -> None:
    """Save crawled ontology rows directly to bundled local reference JSON files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "bsdd_classes.json").write_text(json.dumps(class_rows, indent=2), encoding="utf-8")
    (output_dir / "bsdd_properties.json").write_text(json.dumps(property_rows, indent=2), encoding="utf-8")
    (output_dir / "bsdd_class_properties.json").write_text(json.dumps(edge_rows, indent=2), encoding="utf-8")
    print(f"Saved local reference JSON to {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--roots", nargs="*", default=None, help="Seed IFC class codes (default: core building elements)")
    parser.add_argument("--dictionary-uri", default=IFC43_DICTIONARY_URI)
    parser.add_argument(
        "--curated",
        action="store_true",
        help="Crawl all curated BIM-Guard compliance, regulatory, and corrosion dictionaries (IFC 4.3, ACCORD, RIR, Subsea)",
    )
    parser.add_argument("--max-classes", type=int, default=600, help="Safety cap on entity/domain classes visited")
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds between bSDD requests")
    parser.add_argument("--dry-run", action="store_true", help="Crawl and print counts without writing to disk")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_REFERENCE_DIR,
        help="Local directory to store the crawled reference JSON files (default: data/reference/bsdd)",
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

    target_dictionaries: list[str] = []
    if args.curated:
        # Standard curated suite for automated compliance, corrosion, and statutory checking
        target_dictionaries = [
            IFC43_DICTIONARY_URI,
            "https://identifier.buildingsmart.org/uri/accord/ACCORD/1.0",
            "https://identifier.buildingsmart.org/uri/bs-energy/subsea-flexible-pipes/2.1",
            "https://identifier.buildingsmart.org/uri/bsird/rir/1.0",
        ]
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
            roots = args.roots or default_seed_roots()
            if not roots:
                print("! No seed roots found -- skipping entity tree crawl for IFC.")
            else:
                print(f"Seed roots ({len(roots)}): {', '.join(roots)}")
                crawler = Crawler(bsdd_client, dict_uri, args.max_classes, args.delay)
                crawler.crawl(roots)
                print(f"Crawled {len(crawler.visited)} IFC entity classes.")
                all_visited.update(crawler.visited)

            if not args.skip_group_of_properties:
                print("\nCrawling GroupOfProperties classes (every Pset_/Qto_ definition)...")
                gop_visited = crawl_group_of_properties(
                    bsdd_client, dict_uri, args.delay, args.max_group_of_properties
                )
                print(f"Crawled {len(gop_visited)} GroupOfProperties classes.")
                all_visited.update(gop_visited)
        else:
            print(f"\nCrawling domain classes for {dict_name}...")
            domain_visited = crawl_classes_by_type(
                bsdd_client, dict_uri, "class", args.delay, args.max_classes
            )
            print(f"Crawled {len(domain_visited)} domain classes.")
            all_visited.update(domain_visited)

    class_rows, property_rows, edge_rows = build_rows(all_visited)
    print(
        f"\nTotal Crawled across dictionaries: {len(class_rows)} classes, {len(property_rows)} unique properties, "
        f"{len(edge_rows)} class-property edges."
    )

    if args.dry_run:
        print("Dry run -- not writing to disk.")
        return

    if args.output_dir:
        save_local_reference_json(args.output_dir, class_rows, property_rows, edge_rows)
    print("Done.")


if __name__ == "__main__":
    main()
