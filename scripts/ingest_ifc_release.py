"""Ingest the official IFC 4.3.2.0 release into the local bSDD reference DuckDB.

Alternative source for scripts/crawl_bsdd_ontology.py's IFC 4.3 portion: instead
of crawling api.bsdd.buildingsmart.org one class/Pset at a time (subject to an
undocumented, real rate limit -- see BSDD_MAX_CONCURRENT_REQUESTS in
app/services/bsdd_client.py), this parses the normative IFC 4.3.2.0 release
(ISO 16739-1:2024, "Official" status per
https://technical.buildingsmart.org/standards/ifc/ifc-schema-specifications/)
directly:

  - IFC4X3_ADD2.exp (the EXPRESS schema) gives the complete entity hierarchy
    (876 ENTITY declarations, one SUBTYPE OF per entity) in a single ~10s
    download -- no BFS ancestor/descendant crawl needed.
  - annex-a-psd.zip gives every Pset_*/Qto_* definition (760 files) as
    structured XML with clean <ApplicableClasses> (which IFC entities a Pset
    applies to) and <PropertyDef>/<QtoDef> definitions -- replacing the
    biggest N+1 offender in the API crawl (400+ individual get_class() calls)
    with local file parsing.

The canonical host (standards.buildingsmart.org) sits behind a Cloudflare bot
challenge and can't be fetched by a plain script. The identical file is also
mirrored, unprotected, on GitHub at buildingSMART/Standards-builds -- that's
what this script downloads.

Domain dictionaries (ACCORD, RIR, Subsea pipes, Uniclass 2015) aren't part of
the IFC release and are left untouched -- they still come from
scripts/crawl_bsdd_ontology.py's API-based crawl.

Usage:
    uv run python scripts/ingest_ifc_release.py
    uv run python scripts/ingest_ifc_release.py --dry-run
    uv run python scripts/ingest_ifc_release.py --force-download
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.crawl_bsdd_ontology import (  # noqa: E402
    DEFAULT_REFERENCE_DIR,
    IFC43_DICTIONARY_URI,
    load_existing_reference_data,
    save_local_reference_data,
)

RELEASE_ZIP_URL = "https://raw.githubusercontent.com/buildingSMART/Standards-builds/main/IFC/RELEASE/IFC4_3/IFC4.3.2.0.zip"
DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache" / "ifc-release"

# Paths inside IFC4.3.2.0.zip.
_EXP_PATH_IN_ZIP = "IFC4_3/HTML/IFC4X3_ADD2.exp"
_PSD_ZIP_PATH_IN_ZIP = "IFC4_3/HTML/annex-a-psd.zip"

# EXPRESS primitive keywords -> the simplified type buckets bSDD's own API
# normalizes IFC defined types down to (verified against the live-crawled
# data already on disk: 1196 "Real", 691 "String", 207 "Boolean", 102
# "Integer", plus a handful of raw leftovers bSDD itself didn't normalize).
_PRIMITIVE_BUCKETS = {
    "REAL": "Real",
    "NUMBER": "Real",
    "INTEGER": "Integer",
    "BOOLEAN": "Boolean",
    "LOGICAL": "Boolean",
    "STRING": "String",
    "BINARY": "String",
}
# QtoDef uses a small fixed <QtoType> enum instead of <DataType type="...">.
_QTO_TYPE_BUCKETS = {
    "Q_COUNT": "Integer",
    "Q_LENGTH": "Real",
    "Q_AREA": "Real",
    "Q_VOLUME": "Real",
    "Q_WEIGHT": "Real",
    "Q_TIME": "Real",
}

_ENTITY_BLOCK_RE = re.compile(r"^ENTITY\s+(?P<name>Ifc\w+)\b(?P<body>.*?)^END_ENTITY;", re.DOTALL | re.MULTILINE)
_SUBTYPE_RE = re.compile(r"SUBTYPE OF\s*\(\s*(?P<parent>Ifc\w+)\s*\)\s*;")
_TYPE_ALIAS_RE = re.compile(r"^TYPE\s+(?P<name>Ifc\w+)\s*=\s*(?P<rhs>.+?);", re.DOTALL | re.MULTILINE)
_CAMEL_SPLIT_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def humanize_code(code: str, prefix: str) -> str:
    """Strip prefix and split PascalCase, e.g. "IfcWallStandardCase" -> "Wall Standard Case".

    Matches the naming convention already in the bSDD-derived reference data
    on disk (verified: IfcPipeSegment -> "Pipe Segment", IfcBuildingStorey ->
    "Building Storey", etc.) so ingested and previously-crawled rows read the
    same way.
    """
    stripped = code[len(prefix):] if code.startswith(prefix) else code
    return _CAMEL_SPLIT_RE.sub(" ", stripped)


def download_release(cache_dir: Path, force: bool = False) -> Path:
    """Download (or reuse a cached copy of) the official IFC4.3.2.0.zip."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    zip_path = cache_dir / "IFC4.3.2.0.zip"
    if zip_path.exists() and not force:
        print(f"Using cached release bundle: {zip_path}")
        return zip_path

    print(f"Downloading official IFC 4.3.2.0 release from {RELEASE_ZIP_URL} ...")
    with httpx.stream("GET", RELEASE_ZIP_URL, follow_redirects=True, timeout=60.0) as response:
        response.raise_for_status()
        tmp_path = zip_path.with_suffix(".zip.part")
        with tmp_path.open("wb") as fh:
            for chunk in response.iter_bytes():
                fh.write(chunk)
    tmp_path.replace(zip_path)
    print(f"Saved {zip_path} ({zip_path.stat().st_size / 1_000_000:.1f} MB)")
    return zip_path


def extract_release_assets(zip_path: Path, work_dir: Path) -> tuple[Path, Path]:
    """Extract the EXPRESS schema and every Pset_/Qto_ XML into work_dir.

    Returns (path to the .exp file, path to the directory of Pset_/Qto_.xml
    files).
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as outer:
        exp_path = work_dir / "IFC4X3_ADD2.exp"
        exp_path.write_bytes(outer.read(_EXP_PATH_IN_ZIP))

        psd_dir = work_dir / "psd"
        if psd_dir.exists():
            shutil.rmtree(psd_dir)
        psd_dir.mkdir(parents=True)
        with zipfile.ZipFile(outer.open(_PSD_ZIP_PATH_IN_ZIP)) as inner:
            for member in inner.namelist():
                name = Path(member).name
                if name.startswith(("Pset_", "Qto_")) and name.endswith(".xml"):
                    (psd_dir / name).write_bytes(inner.read(member))
    return exp_path, psd_dir


# ── EXPRESS schema parsing (entity hierarchy + defined-type resolution) ─────


def parse_defined_types(exp_text: str) -> dict[str, str]:
    """Build the raw alias map from every `TYPE X = <rhs>;` declaration."""
    return {m.group("name"): m.group("rhs").strip() for m in _TYPE_ALIAS_RE.finditer(exp_text)}


def resolve_data_type_bucket(raw_type: str | None, alias_map: dict[str, str], max_hops: int = 12) -> str | None:
    """Resolve an IFC defined type down to one of bSDD's simplified buckets.

    E.g. "IfcPositiveLengthMeasure" -> "Real", by walking the EXPRESS
    `TYPE X = Y;` alias chain to its primitive.

    Enumeration/select types resolve to "String", matching bSDD's own
    convention of surfacing enum values via allowed_values with data_type
    "String" (verified: Pset_WallCommon's Status -> data_type "String",
    allowed_values ["DEMOLISH", "EXISTING", ...] in the live-crawled data).
    """
    if not raw_type:
        return None
    current = raw_type
    for _ in range(max_hops):
        primitive = _PRIMITIVE_BUCKETS.get(current.upper())
        if primitive:
            return primitive
        rhs = alias_map.get(current)
        if rhs is None:
            return "String"
        rhs_upper = rhs.upper()
        if rhs_upper.startswith(("ENUMERATION", "SELECT", "LIST", "SET", "ARRAY", "BAG")):
            return "String"
        base_primitive = _PRIMITIVE_BUCKETS.get(rhs_upper.split("(")[0].strip())
        if base_primitive:
            return base_primitive
        next_match = re.match(r"(Ifc\w+)", rhs)
        if not next_match:
            return "String"
        current = next_match.group(1)
    return "String"


def parse_entity_hierarchy(exp_text: str) -> dict[str, str | None]:
    """Return {entity_code: parent_code_or_None} for every ENTITY in the schema."""
    hierarchy: dict[str, str | None] = {}
    for match in _ENTITY_BLOCK_RE.finditer(exp_text):
        name = match.group("name")
        subtype_match = _SUBTYPE_RE.search(match.group("body"))
        hierarchy[name] = subtype_match.group("parent") if subtype_match else None
    return hierarchy


def build_entity_class_rows(hierarchy: dict[str, str | None], dictionary_uri: str) -> dict[str, dict]:
    """One "Class"-type row per EXPRESS entity, keyed by bSDD class URI.

    definition/description are left None here -- the EXPRESS schema itself
    carries no prose text (that lives in separately-built HTML docs). The
    merge step in main() keeps whatever definition a prior live bSDD crawl
    already captured for a given class rather than blanking it out.
    """
    rows: dict[str, dict] = {}
    for code, parent_code in hierarchy.items():
        uri = f"{dictionary_uri}/class/{code}"
        rows[uri] = {
            "uri": uri,
            "code": code,
            "name": humanize_code(code, "Ifc"),
            "dictionary_uri": dictionary_uri,
            "class_type": "Class",
            "parent_class_uri": f"{dictionary_uri}/class/{parent_code}" if parent_code else None,
            "related_ifc_entities": [],
            "definition": None,
            "description": None,
        }
    return rows


# ── PSD/QTO XML parsing (Pset_/Qto_ classes, properties, edges) ─────────────


def _parse_property_type(property_type_el: ElementTree.Element, alias_map: dict[str, str]) -> tuple[str | None, list[str]]:
    """Resolve one <PropertyType> to (data_type_bucket, allowed_values).

    Uniformly handles TypePropertySingleValue/BoundedValue/ListValue/TableValue
    by grabbing the first <DataType type="..."/> found anywhere under the
    element -- verified against the release's actual PropertyType usage
    (2512 SingleValue, 518 EnumeratedValue, 174 BoundedValue, 121 TableValue,
    27 ListValue; no other variant appears in IFC 4.3.2.0's Psets).
    """
    enum_el = property_type_el.find(".//EnumList")
    if enum_el is not None:
        allowed = [item.text for item in enum_el.findall("EnumItem") if item.text]
        return "String", allowed
    data_type_el = property_type_el.find(".//DataType")
    raw_type = data_type_el.get("type") if data_type_el is not None else None
    return resolve_data_type_bucket(raw_type, alias_map), []


def parse_pset_file(path: Path, dictionary_uri: str, alias_map: dict[str, str]) -> tuple[dict, list[dict], list[dict]]:
    """Parse one Pset_*.xml (<PropertySetDef>) into (class_row, prop_rows, edge_rows)."""
    root = ElementTree.parse(path).getroot()
    code = root.findtext("Name") or path.stem
    definition = (root.findtext("Definition") or "").strip() or None
    applicable = [c.text for c in root.findall("./ApplicableClasses/ClassName") if c.text]

    class_uri = f"{dictionary_uri}/class/{code}"
    class_row = {
        "uri": class_uri,
        "code": code,
        "name": f"Property Set: {humanize_code(code, 'Pset_')}",
        "dictionary_uri": dictionary_uri,
        "class_type": "GroupOfProperties",
        "parent_class_uri": None,
        "related_ifc_entities": applicable,
        "definition": definition,
        "description": None,
    }

    prop_rows: list[dict] = []
    edge_rows: list[dict] = []
    for prop_def in root.findall("./PropertyDefs/PropertyDef"):
        prop_name = prop_def.findtext("Name")
        if not prop_name:
            continue
        prop_definition = (prop_def.findtext("Definition") or "").strip() or None
        property_type_el = prop_def.find("PropertyType")
        data_type, allowed_values = (None, []) if property_type_el is None else _parse_property_type(property_type_el, alias_map)

        prop_uri = f"{dictionary_uri}/prop/{prop_name}"
        prop_rows.append(
            {
                "uri": prop_uri,
                "code": prop_name,
                "name": humanize_code(prop_name, ""),
                "data_type": data_type,
                "definition": prop_definition,
                "description": None,
                "units": [],
            }
        )
        edge_rows.append(
            {
                "class_uri": class_uri,
                "property_uri": prop_uri,
                "property_set": code,
                "data_type": data_type,
                "units": [],
                "allowed_values": allowed_values,
            }
        )
    return class_row, prop_rows, edge_rows


def parse_qto_file(path: Path, dictionary_uri: str) -> tuple[dict, list[dict], list[dict]]:
    """Parse one Qto_*.xml (<QtoSetDef>) into (class_row, prop_rows, edge_rows)."""
    root = ElementTree.parse(path).getroot()
    code = root.findtext("Name") or path.stem
    definition = (root.findtext("Definition") or "").strip() or None
    applicable = [c.text for c in root.findall("./ApplicableClasses/ClassName") if c.text]

    class_uri = f"{dictionary_uri}/class/{code}"
    class_row = {
        "uri": class_uri,
        "code": code,
        "name": f"Quantity Set: {humanize_code(code, 'Qto_')}",
        "dictionary_uri": dictionary_uri,
        "class_type": "GroupOfProperties",
        "parent_class_uri": None,
        "related_ifc_entities": applicable,
        "definition": definition,
        "description": None,
    }

    prop_rows: list[dict] = []
    edge_rows: list[dict] = []
    for qto_def in root.findall("./QtoDefs/QtoDef"):
        prop_name = qto_def.findtext("Name")
        if not prop_name:
            continue
        prop_definition = (qto_def.findtext("Definition") or "").strip() or None
        qto_type = qto_def.findtext("QtoType") or ""
        data_type = _QTO_TYPE_BUCKETS.get(qto_type, "Real")

        prop_uri = f"{dictionary_uri}/prop/{prop_name}"
        prop_rows.append(
            {
                "uri": prop_uri,
                "code": prop_name,
                "name": humanize_code(prop_name, ""),
                "data_type": data_type,
                "definition": prop_definition,
                "description": None,
                "units": [],
            }
        )
        edge_rows.append(
            {
                "class_uri": class_uri,
                "property_uri": prop_uri,
                "property_set": code,
                "data_type": data_type,
                "units": [],
                "allowed_values": [],
            }
        )
    return class_row, prop_rows, edge_rows


def ingest_psd_directory(psd_dir: Path, dictionary_uri: str, alias_map: dict[str, str]) -> tuple[dict[str, dict], dict[str, dict], list[dict]]:
    """Parse every Pset_/Qto_ XML file into merged (class_rows, prop_rows, edge_rows)."""
    class_rows: dict[str, dict] = {}
    prop_rows: dict[str, dict] = {}
    edge_rows: list[dict] = []

    files = sorted(psd_dir.glob("*.xml"))
    for i, path in enumerate(files, start=1):
        if path.name.startswith("Pset_"):
            class_row, props, edges = parse_pset_file(path, dictionary_uri, alias_map)
        elif path.name.startswith("Qto_"):
            class_row, props, edges = parse_qto_file(path, dictionary_uri)
        else:
            continue
        class_rows[class_row["uri"]] = class_row
        for p in props:
            prop_rows[p["uri"]] = p
        edge_rows.extend(edges)
        if i % 100 == 0 or i == len(files):
            print(f"  [{i}/{len(files)}] parsed {path.name}")

    return class_rows, prop_rows, edge_rows


# ── Merge with existing on-disk reference data ───────────────────────────────


def merge_reference_data(
    existing_classes: dict[str, dict],
    existing_props: dict[str, dict],
    existing_edges: list[dict],
    new_classes: dict[str, dict],
    new_props: dict[str, dict],
    new_edges: list[dict],
) -> tuple[dict[str, dict], dict[str, dict], list[dict]]:
    """Merge freshly-ingested rows into whatever is already on disk.

    Class-hierarchy rows ("Class" class_type, i.e. IFC entities): the EXPRESS
    schema is authoritative for structure (parent/child), but carries no
    prose -- keep an existing definition/description if we don't have one of
    our own, so re-running this script never blanks out text a prior live
    bSDD crawl already captured.

    Pset_/Qto_ rows and their properties: the official release is strictly
    more authoritative than a live bSDD crawl (it's bSDD's own source), so
    these fully replace whatever was there before, edges included -- any
    stale edge belonging to a class we just regenerated is dropped first.
    """
    merged_classes = dict(existing_classes)
    for uri, row in new_classes.items():
        prior = merged_classes.get(uri)
        if prior and row["class_type"] == "Class":
            row = {
                **row,
                "definition": row.get("definition") or prior.get("definition"),
                "description": row.get("description") or prior.get("description"),
            }
        merged_classes[uri] = row

    merged_props = dict(existing_props)
    merged_props.update(new_props)

    regenerated_class_uris = {uri for uri, row in new_classes.items() if row["class_type"] == "GroupOfProperties"}
    merged_edges = [e for e in existing_edges if e["class_uri"] not in regenerated_class_uris]
    merged_edges.extend(new_edges)

    return merged_classes, merged_props, merged_edges


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="Where to cache the downloaded release zip (default: data/cache/ifc-release, gitignored)",
    )
    parser.add_argument("--force-download", action="store_true", help="Re-download the release zip even if cached")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_REFERENCE_DIR,
        help="Local directory to store the merged reference DuckDB file (default: data/reference/bsdd)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Parse and print counts without writing to disk")
    parser.add_argument("--skip-entities", action="store_true", help="Skip the EXPRESS entity hierarchy, ingest only Pset_/Qto_ classes")
    parser.add_argument("--skip-psd", action="store_true", help="Skip Pset_/Qto_ ingestion, ingest only the entity hierarchy")
    args = parser.parse_args()

    zip_path = download_release(args.cache_dir, force=args.force_download)
    with tempfile.TemporaryDirectory(prefix="ifc_release_") as tmp:
        exp_path, psd_dir = extract_release_assets(zip_path, Path(tmp))
        exp_text = exp_path.read_text(encoding="utf-8")

        new_classes: dict[str, dict] = {}
        new_props: dict[str, dict] = {}
        new_edges: list[dict] = []

        if not args.skip_entities:
            print("\nParsing EXPRESS entity hierarchy...")
            hierarchy = parse_entity_hierarchy(exp_text)
            entity_rows = build_entity_class_rows(hierarchy, IFC43_DICTIONARY_URI)
            print(f"Parsed {len(entity_rows)} IFC entities.")
            new_classes.update(entity_rows)

        if not args.skip_psd:
            print("\nParsing Pset_/Qto_ definitions...")
            alias_map = parse_defined_types(exp_text)
            psd_classes, psd_props, psd_edges = ingest_psd_directory(psd_dir, IFC43_DICTIONARY_URI, alias_map)
            print(f"Parsed {len(psd_classes)} Pset_/Qto_ classes, {len(psd_props)} unique properties, {len(psd_edges)} edges.")
            new_classes.update(psd_classes)
            for uri, row in psd_props.items():
                new_props[uri] = row
            new_edges.extend(psd_edges)

    existing_classes, existing_props, existing_edges = load_existing_reference_data(args.output_dir)
    merged_classes, merged_props, merged_edges = merge_reference_data(
        existing_classes, existing_props, existing_edges, new_classes, new_props, new_edges
    )

    print(
        f"\nFinal Combined Ontology: {len(merged_classes)} classes, {len(merged_props)} unique properties, "
        f"{len(merged_edges)} class-property edges."
    )

    if args.dry_run:
        print("Dry run -- not writing to disk.")
        return

    save_local_reference_data(
        args.output_dir,
        list(merged_classes.values()),
        list(merged_props.values()),
        merged_edges,
    )
    print("Done.")


if __name__ == "__main__":
    main()
