#!/usr/bin/env python
"""Validate every BCF archive in the repository against the BCF 2.1 schemas.

``scripts/regenerate_demo_bcf.py`` validates the three engine demo archives it
regenerates, and reports on the 38-model sweep. This walks the whole corpus --
demos, batch exports, seismic runs, sweep archives, anything else on disk --
and gives one pass/fail line per archive, so the validation report can state
what fraction of the archives actually validate rather than what fraction of
one hand-picked directory does.

The distinction that matters when reading the output: an archive with **zero
topics validates trivially**. An empty zip has nothing to violate a schema. The
summary therefore reports the empty archives separately, because counting them
as passes flatters the result -- a corpus of empty archives would score 100%.

Archives are grouped by directory, since they were produced at different times
by different code. A directory that fails as a block is a stale artefact of an
older generator, not a live defect.

Usage::

    uv run python scripts/validate_bcf_corpus.py
    uv run python scripts/validate_bcf_corpus.py --roots docs/bcf_exports
    uv run python scripts/validate_bcf_corpus.py --json docs/validation/data/bcf-corpus.json

Exit status is 0 when every non-empty archive validates, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SCHEMA_DIR = REPO_ROOT / "tests" / "schemas" / "bcf21"

#: Searched when --roots is not given. Excludes .venv and .git implicitly by
#: naming only the directories the project writes archives into.
DEFAULT_ROOTS = ["docs/bcf_exports", "data/validation_bcf", "data"]

ARCHIVE_SUFFIXES = (".bcf", ".bcfzip")


def _schemas():
    """Load the vendored buildingSMART BCF 2.1 schemas."""
    import xmlschema

    return (
        xmlschema.XMLSchema(SCHEMA_DIR / "markup.xsd"),
        xmlschema.XMLSchema(SCHEMA_DIR / "visinfo.xsd"),
    )


def find_archives(roots: list[str]) -> list[Path]:
    """Collect every BCF archive under the given roots, de-duplicated."""
    found: set[Path] = set()
    for root in roots:
        base = (REPO_ROOT / root) if not Path(root).is_absolute() else Path(root)
        if base.is_file() and base.suffix.lower() in ARCHIVE_SUFFIXES:
            found.add(base)
            continue
        if not base.is_dir():
            continue
        for suffix in ARCHIVE_SUFFIXES:
            found.update(p for p in base.rglob(f"*{suffix}") if ".venv" not in p.parts)
    return sorted(found)


def validate_archive(path: Path, schemas) -> dict[str, Any]:
    """Validate every markup and viewpoint part inside one archive.

    Distinct schema errors are counted rather than listed one per occurrence:
    a malformed archive repeats the same violation once per topic, and twenty
    thousand identical lines carry no more information than one line and a
    count.
    """
    markup_schema, visinfo_schema = schemas
    topics = 0
    viewpoints = 0
    errors: Counter = Counter()

    try:
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                if name.endswith("markup.bcf"):
                    schema = markup_schema
                    topics += 1
                elif name.endswith(".bcfv"):
                    schema = visinfo_schema
                    viewpoints += 1
                else:
                    continue
                for error in schema.iter_errors(zf.read(name).decode("utf-8")):
                    errors[str(error.reason or error)] += 1
    except zipfile.BadZipFile as exc:
        return {
            "archive": _rel(path),
            "topics": 0,
            "viewpoints": 0,
            "empty": True,
            "valid": False,
            "errors": {f"not a readable zip: {exc}": 1},
        }

    return {
        "archive": _rel(path),
        "topics": topics,
        "viewpoints": viewpoints,
        "empty": topics == 0,
        "valid": not errors,
        "errors": dict(errors.most_common(5)),
    }


def _rel(path: Path) -> str:
    """Repo-relative path when possible, absolute otherwise."""
    return str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path)


def summarise(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Roll archives up, keeping empty ones out of the headline pass rate."""
    non_empty = [r for r in records if not r["empty"]]
    by_dir: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "valid": 0, "empty": 0, "non_empty": 0, "non_empty_valid": 0}
    )

    for record in records:
        directory = str(Path(record["archive"]).parent)
        block = by_dir[directory]
        block["total"] += 1
        block["valid"] += 1 if record["valid"] else 0
        if record["empty"]:
            block["empty"] += 1
        else:
            block["non_empty"] += 1
            block["non_empty_valid"] += 1 if record["valid"] else 0

    return {
        "archives_total": len(records),
        "archives_valid": sum(1 for r in records if r["valid"]),
        "archives_empty": sum(1 for r in records if r["empty"]),
        "archives_non_empty": len(non_empty),
        "archives_non_empty_valid": sum(1 for r in non_empty if r["valid"]),
        "topics_total": sum(r["topics"] for r in records),
        "by_directory": {k: dict(v) for k, v in sorted(by_dir.items())},
    }


def print_report(records: list[dict[str, Any]], totals: dict[str, Any]) -> None:
    """Print per-archive results grouped by directory."""
    current_dir = None
    for record in records:
        directory = str(Path(record["archive"]).parent)
        if directory != current_dir:
            current_dir = directory
            print(f"\n{directory}/")
        status = "OK " if record["valid"] else "BAD"
        note = "  (empty)" if record["empty"] else ""
        print(f"  {status} topics={record['topics']:>6}  {Path(record['archive']).name}{note}")
        if not record["valid"]:
            for reason, count in record["errors"].items():
                print(f"        x{count}: {reason[:110]}")

    print("\n" + "=" * 78)
    print("BCF 2.1 CORPUS VALIDATION")
    print("=" * 78)
    print(f"  archives                    : {totals['archives_total']}")
    print(f"  archives valid              : {totals['archives_valid']}")
    print(f"  archives empty (0 topics)   : {totals['archives_empty']}")
    print(
        f"  non-empty archives valid    : {totals['archives_non_empty_valid']}"
        f"/{totals['archives_non_empty']}"
    )
    print(f"  topics validated            : {totals['topics_total']}")
    print("\n  by directory                                  valid/total   non-empty valid")
    for directory, block in totals["by_directory"].items():
        print(
            f"    {directory:<44}{block['valid']:>3}/{block['total']:<7}"
            f"{block['non_empty_valid']:>8}/{block['non_empty']}"
        )


def main(argv: list[str] | None = None) -> int:
    """Validate the BCF corpus."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--roots", nargs="+", default=DEFAULT_ROOTS, help="Directories to search")
    parser.add_argument("--json", type=Path, default=None, help="Also write the record as JSON")
    args = parser.parse_args(argv)

    archives = find_archives(args.roots)
    if not archives:
        print(f"No BCF archives found under {args.roots}", file=sys.stderr)
        return 2

    schemas = _schemas()
    records = [validate_archive(path, schemas) for path in archives]
    totals = summarise(records)
    print_report(records, totals)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps({"totals": totals, "archives": records}, indent=2), encoding="utf-8"
        )
        print(f"\nWrote {args.json}")

    return 0 if totals["archives_non_empty_valid"] == totals["archives_non_empty"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
