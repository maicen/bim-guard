#!/usr/bin/env python
"""Measure every IFC model on disk and write a manifest of facts, not claims.

``data/models-manifest.json`` is upstream metadata and is not trustworthy: 33 of
its 34 ``sha256`` fields are not valid digests, and its material columns are
invented (see ``data/test_models/README.md``). This script does not read, repair
or edit it. It opens each model present under ``--models-dir`` and writes a
parallel file recording only what the file itself says:

* ``sha256`` -- computed over the bytes on disk.
* ``size_bytes`` -- from the filesystem.
* ``ifc_schema`` -- the model's declared schema.
* ``class_counts`` -- **exact-type** counts of the four classes
  ``phase_6d_seismic.BRACED_CLASSES`` treats as braceable, plus
  ``IfcDistributionElement``. Exact type, not ``by_type``'s default
  subtype-inclusive count, because the seismic engine keys on
  ``entity.is_a()`` and IFC nests these (``IfcPipeSegment`` and
  ``IfcDuctSegment`` are both subtypes of ``IfcFlowSegment``, which is itself a
  subtype of ``IfcDistributionElement``); a subtype-inclusive count would
  report the same element under three headings.
* ``ifc_material_names`` -- the distinct ``IfcMaterial.Name`` values actually
  present. An empty list means the file carries none.
* ``material_pct_file_only`` -- the file-only material coverage measured by
  ``scripts/trace_material_coverage.py --no-inference``, read from its JSON
  output. ``null`` when that model holds no piping elements and the tracer
  therefore reports nothing for it.

THESE LAST TWO MEASURE DIFFERENT THINGS, AND WILL DISAGREE

    ``ifc_material_names`` counts ``IfcMaterial`` entities.
    ``material_pct_file_only`` counts elements whose material the reader
    resolved from the file, and ``piping_producer.resolve_material`` accepts a
    second file-borne source: a ``Material``/``MaterialName`` property-set
    value, tagged ``MATERIAL_SOURCE_IFC`` alongside the material association.

    So a model can hold zero ``IfcMaterial`` entities and still report non-zero
    file-only coverage. ``Clinic_HVAC.ifc`` is exactly that case -- 0
    ``IfcMaterial``, no ``IfcRelAssociatesMaterial`` at all, and 13.4%
    coverage carried entirely in Psets. Both numbers are readings of the file;
    neither is inferred. Do not treat the pair as a contradiction.

Usage::

    uv run python scripts/trace_material_coverage.py
        --models-dir data/test_models --no-inference
        --json docs/validation/data/material-coverage-file-only.json
    uv run python scripts/measure_model_manifest.py

Exit codes: ``0`` every model measured, ``1`` at least one could not be read.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MODELS_DIR = REPO_ROOT / "data" / "test_models"
COVERAGE_JSON = REPO_ROOT / "docs" / "validation" / "data" / "material-coverage-file-only.json"
OUTPUT = REPO_ROOT / "data" / "models-manifest-measured.json"

#: The four classes the seismic engine treats as braceable, plus the parent
#: distribution class. Kept as a literal rather than imported so this script
#: records what it counted even if BRACED_CLASSES later changes.
COUNTED_CLASSES = (
    "IfcPipeSegment",
    "IfcDuctSegment",
    "IfcCableCarrierSegment",
    "IfcFlowSegment",
    "IfcDistributionElement",
)


def _sha256(path: Path) -> str:
    """Return the SHA-256 of *path*, read in chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_only_pct(coverage: dict, name: str) -> float | None:
    """Return the file-only material coverage for *name*, or None if untraced."""
    for entry in coverage.get("models", []):
        if entry.get("name") == name:
            total = entry.get("total") or 0
            if not total:
                return None
            return round(100.0 * entry.get("from_ifc", 0) / total, 1)
    return None


def measure(path: Path, coverage: dict) -> dict:
    """Open *path* and record what the file itself declares."""
    import ifcopenshell

    model = ifcopenshell.open(str(path))

    counts: dict[str, int] = {}
    for ifc_class in COUNTED_CLASSES:
        try:
            entities = model.by_type(ifc_class)
        except Exception:
            # A class absent from this schema (e.g. IFC2X3 vs IFC4) is 0, not
            # an error, but it is recorded as measured rather than assumed.
            counts[ifc_class] = 0
            continue
        counts[ifc_class] = sum(1 for e in entities if e.is_a() == ifc_class)

    try:
        materials = sorted(
            {
                str(m.Name).strip()
                for m in model.by_type("IfcMaterial")
                if getattr(m, "Name", None)
            }
        )
    except Exception:
        materials = []

    return {
        "filename": path.name,
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "ifc_schema": str(getattr(model, "schema", "") or "unknown"),
        "class_counts_exact_type": counts,
        "ifc_material_count": len(materials),
        "ifc_material_names": materials,
        "material_pct_file_only": _file_only_pct(coverage, path.name),
    }


def main(argv: list[str] | None = None) -> int:
    """Measure every model under --models-dir and write the manifest."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--models-dir", type=Path, default=MODELS_DIR)
    parser.add_argument("--coverage-json", type=Path, default=COVERAGE_JSON)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)

    paths = sorted(p for p in args.models_dir.rglob("*.ifc"))
    if not paths:
        print(f"No .ifc files under {args.models_dir}", file=sys.stderr)
        return 2

    coverage: dict = {}
    if args.coverage_json.is_file():
        coverage = json.loads(args.coverage_json.read_text(encoding="utf-8"))
    else:
        print(
            f"warning: {args.coverage_json} not found; "
            "material_pct_file_only will be null for every model",
            file=sys.stderr,
        )

    models: list[dict] = []
    failures = 0
    for path in paths:
        try:
            record = measure(path, coverage)
        except Exception as exc:  # noqa: BLE001 - one bad model must not lose the rest
            print(f"  ERROR {path.name}: {type(exc).__name__}: {exc}", file=sys.stderr)
            models.append({"filename": path.name, "error": f"{type(exc).__name__}: {exc}"})
            failures += 1
            continue
        models.append(record)
        pct = record["material_pct_file_only"]
        print(
            f"  {record['filename']:<46} {record['ifc_schema']:<8} "
            f"mat={record['ifc_material_count']:>3} "
            f"file-only={'n/a' if pct is None else f'{pct:.1f}%':>6}"
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "generated_by": "scripts/measure_model_manifest.py",
                "note": (
                    "Measured from the files on disk. This does not derive from, "
                    "correct, or replace data/models-manifest.json, whose sha256 "
                    "and material fields are upstream claims - see "
                    "data/test_models/README.md."
                ),
                "material_fields_measure_different_things": (
                    "ifc_material_names counts IfcMaterial entities. "
                    "material_pct_file_only counts piping elements whose material the "
                    "reader resolved from the file, which includes a Material/MaterialName "
                    "property-set value (piping_producer.resolve_material tags that "
                    "MATERIAL_SOURCE_IFC). A model can therefore carry 0 IfcMaterial and "
                    "still report non-zero file-only coverage - Clinic_HVAC.ifc does. "
                    "Both are readings of the file; neither is inferred."
                ),
                "models_dir": args.models_dir.as_posix(),
                "material_coverage_source": args.coverage_json.relative_to(
                    REPO_ROOT
                ).as_posix(),
                "class_counts_are": "exact IFC type (entity.is_a() == class), not subtype-inclusive",
                "model_count": len(models),
                "models": models,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\nWrote {args.out.relative_to(REPO_ROOT).as_posix()} ({len(models)} models)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
