"""Ingest the official IFC 2x3 TC1 release (EXPRESS + Pset XML) for local reference.

Companion to ingest_ifc_release.py (IFC 4.3), reusing its EXPRESS/PSD-XML
parsers -- the same normative-source pattern, applied to the older IFC 2x3
schema that ifcopenshell already parses transparently in this app's IFC
reader (app/modules/ifc_reader/ifc_parser.py already handles IFC 2x3 model
files; this script is not about model parsing, only about caching IFC 2x3's
own schema reference data for lookup/authoring use).

Unlike IFC 4.3, bSDD has no "ifc/2x3" dictionary entry (its "ifc" dictionary
is version 4.3 only), so this writes to its own data/reference/ifc2x3/ files
rather than merging into data/reference/bsdd/ -- there is nothing there to
merge into, and treating this as bSDD data would misrepresent its source.

IFC 2x3's release layout differs from 4.3's: the EXPRESS schema and the Pset
XML archive are two separate top-level downloads (not one release zip with
everything nested inside), and the Pset XML files sit under per-domain
subdirectories (IfcKernel/, IfcSharedBldgElements/, ...) rather than flat.
IFC 2x3 has no Qto_ (Quantity Set) XML files at all -- that concept was
formalized later -- so quantities aren't part of this dataset.

The ifcOWL/RDF/TTL representation buildingSMART's own schema-specifications
page links to for IFC 2x3
(https://standards.buildingsmart.org/IFC/DEV/IFC2x3/TC1/OWL/IFC2X3_TC1.rdf)
returns 404 on buildingSMART's own site as of 2026-09-15 (verified with a
real browser, not just a blocked scripted request) -- that link is broken on
their end, not something this script can fetch around.

Usage:
    uv run python scripts/ingest_ifc2x3_release.py
    uv run python scripts/ingest_ifc2x3_release.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.ingest_ifc_release import (  # noqa: E402
    build_entity_class_rows,
    parse_defined_types,
    parse_entity_hierarchy,
    parse_pset_file,
)

EXP_URL = "https://raw.githubusercontent.com/buildingSMART/Standards-builds/main/IFC/RELEASE/IFC2x3/TC1/EXPRESS/IFC2X3_TC1.exp"
PSD_ZIP_URL = "https://raw.githubusercontent.com/buildingSMART/Standards-builds/main/IFC/RELEASE/IFC2x3/TC1/psd_IFC2x3_TC1_20071227.zip"

# Not a bSDD dictionary URI (none exists for IFC 2x3) -- the release's own
# canonical location, used as a stable source identifier for these rows.
IFC2X3_SOURCE_URI = "https://standards.buildingsmart.org/IFC/RELEASE/IFC2x3/TC1"

DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache" / "ifc2x3-release"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "reference" / "ifc2x3"


def _download(url: str, dest: Path, force: bool) -> Path:
    if dest.exists() and not force:
        print(f"Using cached {dest}")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url} ...")
    with httpx.stream("GET", url, follow_redirects=True, timeout=60.0) as response:
        response.raise_for_status()
        tmp_path = dest.with_suffix(dest.suffix + ".part")
        with tmp_path.open("wb") as fh:
            for chunk in response.iter_bytes():
                fh.write(chunk)
    tmp_path.replace(dest)
    print(f"Saved {dest} ({dest.stat().st_size / 1000:.0f} KB)")
    return dest


def download_ifc2x3_release(cache_dir: Path, force: bool = False) -> tuple[Path, Path]:
    """Download the EXPRESS schema and the Pset XML archive (two separate files)."""
    exp_path = _download(EXP_URL, cache_dir / "IFC2X3_TC1.exp", force)
    psd_zip_path = _download(PSD_ZIP_URL, cache_dir / "psd_IFC2x3_TC1.zip", force)
    return exp_path, psd_zip_path


def extract_pset_files(psd_zip_path: Path, work_dir: Path) -> list[Path]:
    """Extract the Pset archive and return every Pset_*.xml path (nested under per-domain dirs)."""
    extract_dir = work_dir / "psd"
    with zipfile.ZipFile(psd_zip_path) as zf:
        zf.extractall(extract_dir)
    return sorted(extract_dir.rglob("Pset_*.xml"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR, help="Where to cache downloads (default: data/cache/ifc2x3-release, gitignored)")
    parser.add_argument("--force-download", action="store_true", help="Re-download even if cached")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Where to write the reference JSON (default: data/reference/ifc2x3)")
    parser.add_argument("--dry-run", action="store_true", help="Parse and print counts without writing to disk")
    args = parser.parse_args()

    exp_path, psd_zip_path = download_ifc2x3_release(args.cache_dir, force=args.force_download)
    exp_text = exp_path.read_text(encoding="utf-8")

    print("\nParsing EXPRESS entity hierarchy...")
    hierarchy = parse_entity_hierarchy(exp_text)
    class_rows = build_entity_class_rows(hierarchy, IFC2X3_SOURCE_URI)
    print(f"Parsed {len(class_rows)} IFC 2x3 entities.")

    print("\nParsing Pset definitions...")
    alias_map = parse_defined_types(exp_text)
    pset_paths = extract_pset_files(psd_zip_path, args.cache_dir)
    prop_rows: dict[str, dict] = {}
    edge_rows: list[dict] = []
    for i, path in enumerate(pset_paths, start=1):
        pset_class_row, props, edges = parse_pset_file(path, IFC2X3_SOURCE_URI, alias_map)
        class_rows[pset_class_row["uri"]] = pset_class_row
        for p in props:
            prop_rows[p["uri"]] = p
        edge_rows.extend(edges)
        if i % 100 == 0 or i == len(pset_paths):
            print(f"  [{i}/{len(pset_paths)}] parsed {path.name}")
    print(f"Parsed {len(pset_paths)} Psets, {len(prop_rows)} unique properties, {len(edge_rows)} edges.")

    print(
        f"\nTotal: {len(class_rows)} classes (entities + Psets), "
        f"{len(prop_rows)} unique properties, {len(edge_rows)} class-property edges."
    )

    if args.dry_run:
        print("Dry run -- not writing to disk.")
        return

    args.output_dir.mkdir(parents=True, exist_ok=True)
    import json

    (args.output_dir / "ifc2x3_classes.json").write_text(json.dumps(list(class_rows.values()), indent=2), encoding="utf-8")
    (args.output_dir / "ifc2x3_properties.json").write_text(json.dumps(list(prop_rows.values()), indent=2), encoding="utf-8")
    (args.output_dir / "ifc2x3_class_properties.json").write_text(json.dumps(edge_rows, indent=2), encoding="utf-8")
    print(f"Saved local reference JSON to {args.output_dir}")


if __name__ == "__main__":
    main()
