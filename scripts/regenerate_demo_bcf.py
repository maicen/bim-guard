#!/usr/bin/env python
"""Regenerate the corrosion-engine demo BCF archives and validate them.

Runs the standalone validation demo of each engine (GC-001 galvanic, CC-001
crevice, MC-001 microbiological), which writes one BCF 2.1 archive to
``docs/bcf_exports/`` and one asset-register CSV to ``docs/validation/data/``,
then validates every ``markup.bcf`` and ``viewpoint.bcfv`` in those archives
against the buildingSMART BCF 2.1 schemas vendored under
``tests/schemas/bcf21/``.

Usage::

    uv run python scripts/regenerate_demo_bcf.py            # regenerate + validate
    uv run python scripts/regenerate_demo_bcf.py --validate-only
    uv run python scripts/regenerate_demo_bcf.py --sweep     # also report on data/validation_bcf/*.bcf

``--sweep`` only *reports* on the archives written by the 38-model sweep
(``scripts/eval/test_all_38_models.py``); it does not regenerate them, because
that needs a full ``--refresh`` run of the sweep over ~1.4 GB of cached models.

Exit status is non-zero when any regenerated demo archive fails validation.
"""

from __future__ import annotations

import argparse
import io
import sys
import zipfile
from collections import Counter
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "tests" / "schemas" / "bcf21"
SWEEP_DIR = REPO_ROOT / "data" / "validation_bcf"

sys.path.insert(0, str(REPO_ROOT))


def _schemas():
    import xmlschema

    return (
        xmlschema.XMLSchema(SCHEMA_DIR / "markup.xsd"),
        xmlschema.XMLSchema(SCHEMA_DIR / "visinfo.xsd"),
    )


def validate_archive(path: Path, schemas) -> tuple[int, Counter]:
    """Return ``(topic_count, violations)`` for one archive.

    ``violations`` maps a short reason to how many parts raised it, so a
    thousand-topic archive with one systematic fault prints one line.
    """
    markup_schema, visinfo_schema = schemas
    violations: Counter = Counter()
    topics = 0
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        for required in ("bcf.version", "project.bcfp"):
            if required not in names:
                violations[f"missing {required}"] += 1
        for name in names:
            if name.endswith("markup.bcf"):
                topics += 1
                schema = markup_schema
            elif name.endswith("viewpoint.bcfv"):
                schema = visinfo_schema
            elif name.endswith("snapshot.png"):
                if not zf.read(name).startswith(b"\x89PNG\r\n\x1a\n"):
                    violations["snapshot.png is not a PNG"] += 1
                continue
            else:
                continue
            for error in schema.iter_errors(zf.read(name).decode("utf-8")):
                violations[str(error.reason)[:120]] += 1
    return topics, violations


def regenerate() -> list[Path]:
    """Run the three engine demos, returning the archive paths they wrote."""
    from app.engines import bimguard_corrosion_engine as gc
    from app.engines import bimguard_crevice_engine as cc
    from app.engines import bimguard_mic_engine as mc

    written: list[Path] = []
    for label, module in (("GC-001", gc), ("CC-001", cc), ("MC-001", mc)):
        sink = io.StringIO()
        with redirect_stdout(sink):
            module.run_validation_demo()
        path = REPO_ROOT / module.DEMO_BCF_PATH
        status = "written" if path.exists() else "NOT WRITTEN (no topics above Low?)"
        print(f"  {label}: {module.DEMO_BCF_PATH} — {status}")
        if path.exists():
            written.append(path)
    return written


def demo_archives() -> list[Path]:
    from app.engines import bimguard_corrosion_engine as gc
    from app.engines import bimguard_crevice_engine as cc
    from app.engines import bimguard_mic_engine as mc

    return [REPO_ROOT / m.DEMO_BCF_PATH for m in (gc, cc, mc) if (REPO_ROOT / m.DEMO_BCF_PATH).exists()]


def report(paths: list[Path], schemas) -> int:
    """Validate *paths*, print one line each, return the number that failed."""
    failed = 0
    for path in paths:
        topics, violations = validate_archive(path, schemas)
        verdict = "OK " if not violations else "BAD"
        print(f"  {verdict} topics={topics:5} {path.relative_to(REPO_ROOT).as_posix()}")
        for reason, count in violations.most_common(4):
            print(f"        x{count}: {reason}")
        failed += bool(violations)
    return failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--validate-only", action="store_true", help="skip regeneration")
    parser.add_argument("--sweep", action="store_true", help="also report on data/validation_bcf/*.bcf")
    args = parser.parse_args()

    schemas = _schemas()

    if not args.validate_only:
        print("Regenerating engine demo archives")
        regenerate()

    print("\nValidating engine demo archives against BCF 2.1 markup.xsd + visinfo.xsd")
    paths = demo_archives()
    failed = report(paths, schemas)
    print(f"  {len(paths) - failed}/{len(paths)} demo archives valid")

    if args.sweep:
        sweep = sorted(SWEEP_DIR.glob("*.bcf"))
        print(f"\nReport only: {len(sweep)} sweep archives in {SWEEP_DIR.relative_to(REPO_ROOT).as_posix()}")
        sweep_failed = report(sweep, schemas)
        print(f"  {len(sweep) - sweep_failed}/{len(sweep)} sweep archives valid "
              "(regenerate with scripts/eval/test_all_38_models.py --refresh)")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
