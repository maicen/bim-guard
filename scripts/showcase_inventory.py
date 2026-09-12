"""Inventory every real IFC model, measured through the piping audit's own parser.

WHY THIS EXISTS

    Before showing what the engines produce, it has to be clear what the models
    can support. GC-001 and CC-001 refuse an element whose material the IFC does
    not carry; MC-001 refuses one with no flow velocity, dead-leg length or
    operating temperature. On a corpus where most elements are refused, the
    engines are not "finding nothing" -- they are declining to invent inputs,
    and the report has to be able to say which.

    So coverage here is not measured with a hand-rolled heuristic. It calls the
    audit's own gates, ``_material_gate`` and ``_hydraulics_gate``
    (app/modules/phase_6/phase_6c_corrosion_ui.py:498 and :526), through the
    same ``parse_ifc_bytes(..., with_piping=True)`` the audit parses with
    (app/services/analysis_runner.py:220). A file's material percentage here is
    therefore exactly the fraction of its elements GC-001 and CC-001 will score.

READ-ONLY

    The models live in the main tree and are never copied, written or opened for
    writing. Only their bytes are read.

USAGE

    uv run python scripts/showcase_inventory.py
    uv run python scripts/showcase_inventory.py --models-root <dir> --limit 5
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# app.services must be imported before phase_6c. phase_6c imports app.engines,
# which imports app.services, which imports analysis_runner, which imports
# phase_6c -- so entering the cycle at phase_6c leaves it partially initialised
# and the import fails. Entering at app.services is the order the running app
# uses and resolves cleanly.
import app.services.analysis_runner  # noqa: E402,F401  (import order matters)
from app.modules.phase_6.phase_6b_parsing import parse_ifc_bytes  # noqa: E402
from app.modules.phase_6.phase_6c_corrosion_ui import (  # noqa: E402
    _hydraulics_gate,
    _material_gate,
    _mic_element,
)

#: The main tree's model corpus. Absolute and read-only: the models are
#: gitignored there and must not be copied into this worktree.
DEFAULT_MODELS_ROOT = Path(r"D:\Zigurat Masters\bim-guard\test-models\models")

#: Where the inventory lands.
OUT_DIR = REPO_ROOT / "docs" / "validation" / "engine-showcase-2026-09-08"

#: ``get_system_name`` returns this when an element belongs to no IfcSystem
#: (app/modules/ifc_reader/ifc_parser.py:572), so it is the "no system" marker
#: rather than an empty string.
UNASSIGNED_SYSTEM = "Unassigned"


@dataclass
class FileReport:
    """One IFC file, as the piping audit's parser sees it."""

    path: str
    name: str
    directory: str
    size_bytes: int
    schema: str
    valid: bool
    error: str | None
    parse_seconds: float
    element_count: int
    piping_element_count: int
    material_ok: int
    system_ok: int
    hydraulics_ok: int
    type_counts: dict[str, int] = field(default_factory=dict)

    @property
    def material_pct(self) -> float:
        return 100.0 * self.material_ok / self.element_count if self.element_count else 0.0

    @property
    def system_pct(self) -> float:
        return 100.0 * self.system_ok / self.element_count if self.element_count else 0.0

    @property
    def hydraulics_pct(self) -> float:
        return 100.0 * self.hydraulics_ok / self.element_count if self.element_count else 0.0


def inspect(path: Path) -> FileReport:
    """Parse one model and count what each engine gate would accept."""
    size = path.stat().st_size
    started = time.monotonic()
    content = path.read_bytes()
    parsed = parse_ifc_bytes(content, source_ref=str(path), with_piping=True)
    elapsed = time.monotonic() - started

    quality = parsed.get("quality", {}) or {}
    elements = parsed.get("elements", []) or []

    material_ok = system_ok = hydraulics_ok = 0
    for element in elements:
        if _material_gate(element) is None:
            material_ok += 1
        system = (element.system or "").strip()
        if system and system != UNASSIGNED_SYSTEM:
            system_ok += 1
        if _hydraulics_gate(_mic_element(element)) is None:
            hydraulics_ok += 1

    return FileReport(
        path=str(path),
        name=path.name,
        directory=path.parent.name,
        size_bytes=size,
        schema=parsed.get("schema") or "",
        valid=bool(quality.get("valid", False)),
        error=quality.get("error"),
        parse_seconds=round(elapsed, 2),
        element_count=len(elements),
        piping_element_count=len(parsed.get("piping_elements", []) or []),
        material_ok=material_ok,
        system_ok=system_ok,
        hydraulics_ok=hydraulics_ok,
        type_counts=dict(parsed.get("type_counts", {}) or {}),
    )


def federation_groups(reports: list[FileReport]) -> dict[str, list[str]]:
    """Directories holding more than one model, which the seismic step can federate.

    ``run_seismic_analysis`` takes a primary model plus ``extra_models`` and
    unions their geometry (app/modules/phase_6/phase_6d_seismic.py:371), so any
    set of files that belong to one building is federatable. Directory is the
    only grouping the corpus itself records.
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for report in reports:
        if report.element_count or report.valid:
            groups[report.directory].append(report.name)
    return {k: sorted(v) for k, v in sorted(groups.items()) if len(v) > 1}


def markdown(reports: list[FileReport], groups: dict[str, list[str]], root: Path) -> str:
    """Render the inventory as a table sorted by material coverage."""
    ordered = sorted(
        reports, key=lambda r: (r.material_pct, r.element_count), reverse=True
    )
    lines = [
        "# IFC inventory, measured through the audit's own parser",
        "",
        f"Corpus root: `{root}` (main tree, read-only, never copied).",
        f"Files found: **{len(reports)}**. Parsed with "
        "`parse_ifc_bytes(..., with_piping=True)`, the same call "
        "`_run_corrosion_tracked` makes at `app/services/analysis_runner.py:220`.",
        "",
        "Coverage columns are not heuristics. **Material %** is the share of "
        "elements `_material_gate` lets through, i.e. exactly what GC-001 and "
        "CC-001 will score. **Hydraulics %** is the share `_hydraulics_gate` "
        "lets through, i.e. exactly what MC-001 will score. **System %** is the "
        "share whose element belongs to a named `IfcSystem` rather than "
        f"`{UNASSIGNED_SYSTEM}`.",
        "",
        "| # | File | Dir | MB | Schema | Elements | Material % | System % | Hydraulics % | Parse s |",
        "| ---: | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for index, r in enumerate(ordered, start=1):
        note = "" if r.valid else " **(unreadable)**"
        lines.append(
            f"| {index} | `{r.name}`{note} | {r.directory} | {r.size_bytes / 1048576:.1f} | "
            f"{r.schema or '-'} | {r.element_count:,} | {r.material_pct:.1f} | "
            f"{r.system_pct:.1f} | {r.hydraulics_pct:.1f} | {r.parse_seconds:.1f} |"
        )

    lines += [
        "",
        "## Files the seismic step can federate",
        "",
        "`run_seismic_analysis` unions the geometry of a primary model and every "
        "`extra_models` entry, so any group of models describing one building is "
        "federatable. Directory is the only grouping the corpus records:",
        "",
    ]
    for directory, names in groups.items():
        lines.append(f"- **{directory}** ({len(names)} models): " + ", ".join(f"`{n}`" for n in names))

    lines += [
        "",
        "### How project 1542's set is identified",
        "",
        "The repository records it in two places, both cited rather than guessed:",
        "",
        "- `docs/validation/final-audit-2026-09-06.md:135` — attaching all three "
        "West Riverside discipline models to project **1542** failed; "
        "**2 of 3 attached (plumb IFC4 23.8 MB, str IFC4 6.5 MB)** and the "
        "69.7 MB mech model returned `413 Payload too large`.",
        "- `docs/demo/RUNBOOK.md` (Seismic on 1542) — \"The federation is two "
        "models, `west_riverside_hospital_plumb_ifc4.ifc` and "
        "`west_riverside_hospital_str_ifc4.ifc`\".",
        "",
        "So 1542 is those two files, and that is what this showcase federates.",
        "",
        "### How project 1540's model is identified",
        "",
        "`docs/demo/RUNBOOK.md` (\"Piping on a real model with no materials "
        "(1540)\") names it *FINAL AUDIT Piping WR Plumb IFC4* — West Riverside "
        "hospital plumbing, IFC4, 23.8 MB, 8,539 piping elements — i.e. "
        "`west_riverside_hospital_plumb_ifc4.ifc`.",
        "",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Inventory the corpus and write the markdown and its JSON sidecar."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--models-root", type=Path, default=DEFAULT_MODELS_ROOT)
    parser.add_argument("--limit", type=int, default=0, help="Inspect at most N files")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)

    root: Path = args.models_root
    if not root.is_dir():
        print(f"Models root not found: {root}", file=sys.stderr)
        return 2

    paths = sorted(p for p in root.rglob("*.ifc") if p.is_file())
    if args.limit:
        paths = paths[: args.limit]
    print(f"Found {len(paths)} IFC files under {root}", flush=True)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    sidecar = args.out_dir / "01_inventory.json"

    reports: list[FileReport] = []
    for index, path in enumerate(paths, start=1):
        print(f"[{index}/{len(paths)}] {path.name} ...", end="", flush=True)
        try:
            report = inspect(path)
        except Exception as exc:  # a corpus file must never abort the sweep
            print(f" FAILED {exc}", flush=True)
            report = FileReport(
                path=str(path), name=path.name, directory=path.parent.name,
                size_bytes=path.stat().st_size, schema="", valid=False,
                error=str(exc), parse_seconds=0.0, element_count=0,
                piping_element_count=0, material_ok=0, system_ok=0, hydraulics_ok=0,
            )
        else:
            print(
                f" {report.element_count:,} elements, "
                f"material {report.material_pct:.1f}%, {report.parse_seconds:.1f}s",
                flush=True,
            )
        reports.append(report)
        # Written after every file so a long sweep is never lost to one crash.
        sidecar.write_text(
            json.dumps([asdict(r) for r in reports], indent=2), encoding="utf-8"
        )

    groups = federation_groups(reports)
    (args.out_dir / "01_inventory.md").write_text(
        markdown(reports, groups, root), encoding="utf-8"
    )
    print(f"\nWrote {args.out_dir / '01_inventory.md'} and its JSON sidecar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
