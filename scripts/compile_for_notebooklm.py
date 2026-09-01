"""Compile BIMGUARD AI source code and documentation into NotebookLM corpora.

Two Markdown documents are produced, one per NotebookLM workspace:

* ``bimguard_seismic_rules.md``   -> "FMP: BIMGUARD AI - Seismic"
* ``bimguard_corrosion_rules.md`` -> "FMP: BIMGUARD AI - Corrosion"

Every discovered file is routed to exactly one of three categories by
:data:`ROUTING_RULES`: ``seismic``, ``corrosion``, or ``shared``. Shared files
(README, orchestration, seeding, general architecture docs) are appended to
BOTH documents so each notebook understands the overall system.

Usage::

    python scripts/compile_for_notebooklm.py            # write both documents
    python scripts/compile_for_notebooklm.py --list     # audit routing, write nothing

Configuration lives in the constants below.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from fnmatch import fnmatchcase
from pathlib import Path

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent

SEISMIC = "seismic"
CORROSION = "corrosion"
SHARED = "shared"

#: Directories scanned recursively, relative to the repository root.
TARGET_DIRS: list[str] = [
    "app/engines",     # GC-001, CC-001, MC-001 and ARCH-* compliance kernels
    "app/modules",     # Document parsing, IFC read, rule build, comparator pipeline
    "app/services",    # Rule catalogs, ruleset seeding, analysis runner
    "data/rulesets",   # Static JSON rule packs (MM-001, XM-001) + jurisdiction configs
    "docs",            # Standards research, validation reports, submissions
]

#: Extra individual files, given as glob patterns relative to the repository
#: root. Patterns are supported so generated jurisdiction configs are picked
#: up without having to name each one.
EXTRA_FILES: list[str] = [
    "README.md",
]

#: Only files carrying one of these suffixes are included.
ALLOWED_EXTENSIONS: set[str] = {".py", ".md", ".json", ".xml", ".csv", ".txt"}

#: Directory names skipped anywhere in the tree (caches, vendored code, VCS).
EXCLUDED_DIR_NAMES: set[str] = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "node_modules",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".ipynb_checkpoints",
    "dist",
    "build",
    ".egg-info",
}

#: Path globs skipped outright. Matched against the repository-relative POSIX
#: path, so ``data/validation_*`` cannot accidentally catch ``docs/validation``.
EXCLUDED_PATH_PATTERNS: list[str] = [
    "data/uploads/*",
    "data/cache/*",
    "data/validation_*",
    "*.patch",
    "*.log",
]

#: Maps a file suffix onto the language hint used for the Markdown fence.
LANGUAGE_BY_EXTENSION: dict[str, str] = {
    ".py": "python",
    ".md": "markdown",
    ".json": "json",
    ".xml": "xml",
    ".csv": "csv",
    ".txt": "text",
}

# --------------------------------------------------------------------------
# Routing
# --------------------------------------------------------------------------
#
# Ordered ``(glob, category)`` pairs; the FIRST match wins, and anything
# unmatched falls through to SHARED. Patterns are matched case-insensitively
# against the repository-relative POSIX path, and ``*`` crosses directory
# separators -- so ``*seismic*`` matches the substring anywhere in the path.
#
# Order is deliberate:
#   1. Pinned SHARED files, so architecture-wide code is never captured by a
#      domain keyword it happens to mention (ruleset_seeder.py seeds both).
#   2. Explicit domain paths.
#   3. Domain keyword fallbacks.
#
ROUTING_RULES: list[tuple[str, str]] = [
    # -- 1. Pinned shared: architecture both notebooks need -----------------
    ("README.md", SHARED),
    ("app/modules/README.md", SHARED),
    ("app/services/ruleset_seeder.py", SHARED),
    ("app/services/rules_service.py", SHARED),
    ("app/services/projects_service.py", SHARED),
    ("app/services/analysis_runner.py", SHARED),
    ("app/services/pipeline_tracker.py", SHARED),
    ("app/modules/orchestrator.py", SHARED),
    ("app/modules/contracts.py", SHARED),
    ("app/modules/config.py", SHARED),
    ("docs/architecture.md", SHARED),
    ("docs/BIMGUARD_DATA_ARCHITECTURE.md", SHARED),
    ("docs/CONVENTIONS.md", SHARED),
    ("docs/INTEGRATION_GUIDE.md", SHARED),
    ("docs/PHASE_6_DATA_CONTRACTS.md", SHARED),

    # -- 2. Scraped standards ----------------------------------------------
    # Written by fetch_standards.py, which bakes the --seismic / --corrosion
    # flag into the filename. Scoped to the directory so the broad "*iso*"
    # pattern cannot claim unrelated files elsewhere in the tree.
    ("docs/scraped_standards/*seismic*", SEISMIC),
    ("docs/scraped_standards/*corrosion*", CORROSION),
    ("docs/scraped_standards/*iso*", CORROSION),

    # -- 2. Explicit corrosion paths ---------------------------------------
    ("app/engines/*", CORROSION),                  # all five kernels
    ("app/services/corrosion_rule_catalog.py", CORROSION),
    ("data/rulesets/mm_001_*", CORROSION),         # MM-001 material media
    ("data/rulesets/xm_001_*", CORROSION),         # XM-001 cross material
    ("app/modules/module4_comparator/galvanic.py", CORROSION),
    ("app/modules/phase_6/phase_6c_corrosion_ui.py", CORROSION),

    # -- 2. Explicit seismic paths -----------------------------------------
    ("data/rulesets/config_*.json", SEISMIC),      # EN 1998-1 / DIN 4149 configs
    ("app/modules/module2_producer/generate_expanded_config.py", SEISMIC),
    ("app/modules/phase_6/phase_6d_seismic.py", SEISMIC),
    ("app/modules/module5_reporter/blue_halo_bcf_exporter.py", SEISMIC),
    ("docs/HERMES_CONTEXT.md", SEISMIC),

    # -- 3. Corrosion keyword fallbacks ------------------------------------
    ("*galvanic*", CORROSION),
    ("*corrosion*", CORROSION),
    ("*crevice*", CORROSION),
    ("*microbiolog*", CORROSION),
    ("*mic_engine*", CORROSION),
    ("*gc_001*", CORROSION),
    ("*gc-001*", CORROSION),
    ("*cc_001*", CORROSION),
    ("*cc-001*", CORROSION),
    ("*mc_001*", CORROSION),
    ("*mc-001*", CORROSION),
    ("*mm_001*", CORROSION),
    ("*mm-001*", CORROSION),
    ("*xm_001*", CORROSION),
    ("*xm-001*", CORROSION),
    ("*mm_xm*", CORROSION),
    # Compact ruleset ids, as used in doc filenames (e.g. Q02_..._GC001_...)
    ("*gc001*", CORROSION),
    ("*cc001*", CORROSION),
    ("*mc001*", CORROSION),
    ("*mm001*", CORROSION),
    ("*xm001*", CORROSION),
    ("*couples*", CORROSION),
    ("*material*", CORROSION),
    ("*piping*", CORROSION),
    ("*ss316*", CORROSION),
    ("*iso_9223*", CORROSION),
    ("*iso9223*", CORROSION),

    # -- 3. Seismic keyword fallbacks --------------------------------------
    ("*seismic*", SEISMIC),
    ("*bracing*", SEISMIC),
    ("*clearance*", SEISMIC),
    ("*clash*", SEISMIC),
    ("*halo*", SEISMIC),
    ("*hermes*", SEISMIC),
    ("*sb_001*", SEISMIC),
    ("*sb-001*", SEISMIC),
    ("*sb001*", SEISMIC),
    ("*en_1998*", SEISMIC),
    ("*en1998*", SEISMIC),
    ("*din_4149*", SEISMIC),
    ("*din4149*", SEISMIC),
    ("*asce*", SEISMIC),
    ("*smacna*", SEISMIC),
    ("*nfpa*", SEISMIC),
    ("*fema*", SEISMIC),
]

#: Category assigned to any file no routing rule claims.
DEFAULT_CATEGORY = SHARED

#: Per-output document configuration.
OUTPUTS: dict[str, dict[str, str]] = {
    SEISMIC: {
        "filename": "bimguard_seismic_rules.md",
        "workspace": "FMP: BIMGUARD AI - Seismic",
        "title": "BIMGUARD AI — Seismic Bracing & Clearance Corpus",
        "preamble": (
            "Seismic slice of the BIMGUARD AI OpenBIM compliance application: "
            "the SB-001 (Blue Halo) bracing-clearance engine, generated "
            "jurisdiction configs, halo volume generation and clash logic, "
            "plus the shared platform architecture. Compiled for analysis "
            "against seismic restraint codes (EN 1998-1, DIN 4149, ASCE 7-22, "
            "NFPA 13, SMACNA, FEMA E-74)."
        ),
    },
    CORROSION: {
        "filename": "bimguard_corrosion_rules.md",
        "workspace": "FMP: BIMGUARD AI - Corrosion",
        "title": "BIMGUARD AI — Corrosion & Materials Corpus",
        "preamble": (
            "Corrosion slice of the BIMGUARD AI OpenBIM compliance "
            "application: the GC-001 galvanic, CC-001 crevice, MC-001 "
            "microbiological, MM-001 material-media and XM-001 cross-material "
            "rule logic, their catalogs and rule packs, plus the shared "
            "platform architecture. Compiled for analysis against corrosion "
            "standards (ISO 9223, ISO 12944, ASTM G82)."
        ),
    },
}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def is_excluded(path: Path) -> bool:
    """Return ``True`` when *path* is in an excluded dir or matches a skip glob."""
    if any(
        part in EXCLUDED_DIR_NAMES or part.endswith(".egg-info")
        for part in path.parts
    ):
        return True
    posix = path.as_posix().lower()
    return any(fnmatchcase(posix, pat.lower()) for pat in EXCLUDED_PATH_PATTERNS)


def classify(path: Path) -> tuple[str, str]:
    """Return ``(category, matched_pattern)`` for *path*.

    ``matched_pattern`` is ``"<default>"`` when no rule claimed the file.
    """
    posix = path.as_posix().lower()
    for pattern, category in ROUTING_RULES:
        if fnmatchcase(posix, pattern.lower()):
            return category, pattern
    return DEFAULT_CATEGORY, "<default>"


def language_for(path: Path) -> str:
    """Return the Markdown code-fence language hint for *path*."""
    return LANGUAGE_BY_EXTENSION.get(path.suffix.lower(), "")


def fence_for(content: str) -> str:
    """Return a fence long enough not to be closed early by *content*.

    Markdown files frequently embed their own triple-backtick blocks, which
    would otherwise terminate the wrapper fence prematurely.
    """
    longest = 0
    run = 0
    for char in content:
        if char == "`":
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    return "`" * max(3, longest + 1)


def read_text(path: Path) -> str:
    """Read *path* as UTF-8, replacing any undecodable bytes."""
    return path.read_text(encoding="utf-8", errors="replace")


def collect_files() -> list[Path]:
    """Return every eligible file, as paths relative to the repository root.

    Files matched by :data:`EXTRA_FILES` come first, followed by the contents
    of each target directory in configuration order. Within a directory, files
    are sorted by path so the export is deterministic between runs.
    """
    collected: list[Path] = []
    seen: set[Path] = set()
    output_paths = {
        (REPO_ROOT / cfg["filename"]).resolve() for cfg in OUTPUTS.values()
    }

    def add(candidate: Path) -> None:
        resolved = candidate.resolve()
        if resolved in output_paths or resolved in seen:
            return
        seen.add(resolved)
        collected.append(candidate.relative_to(REPO_ROOT))

    for pattern in EXTRA_FILES:
        matches = sorted(
            candidate
            for candidate in REPO_ROOT.glob(pattern)
            if candidate.is_file()
            and candidate.suffix.lower() in ALLOWED_EXTENSIONS
            and not is_excluded(candidate.relative_to(REPO_ROOT))
        )
        if not matches:
            print(f"  ! no files matched: {pattern}", file=sys.stderr)
        for candidate in matches:
            add(candidate)

    for directory in TARGET_DIRS:
        base = REPO_ROOT / directory
        if not base.is_dir():
            print(f"  ! skipped missing directory: {directory}", file=sys.stderr)
            continue
        for candidate in sorted(base.rglob("*")):
            if not candidate.is_file():
                continue
            if candidate.suffix.lower() not in ALLOWED_EXTENSIONS:
                continue
            if is_excluded(candidate.relative_to(REPO_ROOT)):
                continue
            add(candidate)

    return collected


def group_by_directory(files: list[Path]) -> dict[str, list[Path]]:
    """Group *files* under their parent directory, preserving discovery order."""
    groups: dict[str, list[Path]] = {}
    for path in files:
        parent = path.parent.as_posix()
        label = "(repository root)" if parent == "." else parent
        groups.setdefault(label, []).append(path)
    return groups


def build_document(category: str, files: list[Path], shared_count: int) -> str:
    """Render the Markdown document for *category* over *files*."""
    cfg = OUTPUTS[category]
    groups = group_by_directory(files)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    parts: list[str] = [
        f"# {cfg['title']}",
        "",
        cfg["preamble"],
        "",
        f"- **NotebookLM workspace:** {cfg['workspace']}",
        f"- **Generated:** {timestamp}",
        f"- **Source repository:** `{REPO_ROOT.name}`",
        f"- **File types included:** "
        f"{', '.join(f'`{e}`' for e in sorted(ALLOWED_EXTENSIONS))}",
        f"- **Files included:** {len(files)} "
        f"({len(files) - shared_count} {category}-specific, "
        f"{shared_count} shared architecture files also present in the "
        f"companion notebook)",
        "",
        "---",
        "",
    ]

    for directory, group in groups.items():
        parts.append(f"## {directory}")
        parts.append("")
        for path in group:
            content = read_text(REPO_ROOT / path).replace("\r\n", "\n").rstrip()
            fence = fence_for(content)
            parts.append(f"### {path.as_posix()}")
            parts.append("")
            parts.append(f"{fence}{language_for(path)}")
            parts.append(content)
            parts.append(fence)
            parts.append("")
            parts.append("---")
            parts.append("")

    return "\n".join(parts)


def print_routing_report(routed: list[tuple[Path, str, str]]) -> None:
    """Print every file with its assigned category and the rule that matched."""
    width = max(len(path.as_posix()) for path, _, _ in routed)
    for path, category, pattern in sorted(
        routed, key=lambda row: (row[1], row[0].as_posix())
    ):
        print(f"{category:<9}  {path.as_posix():<{width}}  <- {pattern}")


def main(argv: list[str] | None = None) -> int:
    """Compile both corpora and write them to the repository root."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--list",
        action="store_true",
        help="print the routing decision for every file and exit without writing",
    )
    args = parser.parse_args(argv)

    print(f"Scanning {REPO_ROOT}...")
    files = collect_files()
    if not files:
        print("No matching files found — nothing written.", file=sys.stderr)
        return 1

    routed = [(path, *classify(path)) for path in files]

    if args.list:
        print_routing_report(routed)
        return 0

    buckets: dict[str, list[Path]] = {SEISMIC: [], CORROSION: [], SHARED: []}
    for path, category, _ in routed:
        buckets[category].append(path)

    shared = buckets[SHARED]
    print(
        f"Routed {len(files)} files: "
        f"{len(buckets[SEISMIC])} seismic, "
        f"{len(buckets[CORROSION])} corrosion, "
        f"{len(shared)} shared (written to both)"
    )

    for category in (SEISMIC, CORROSION):
        # Preserve global discovery order when merging shared files back in.
        wanted = set(buckets[category]) | set(shared)
        selected = [path for path in files if path in wanted]
        document = build_document(category, selected, shared_count=len(shared))
        output_path = REPO_ROOT / OUTPUTS[category]["filename"]
        output_path.write_text(document, encoding="utf-8")
        size_mb = output_path.stat().st_size / (1024 * 1024)
        print(
            f"  {OUTPUTS[category]['filename']:<30} "
            f"{len(selected):>4} files  "
            f"{len(document.split()):>9,} words  "
            f"{size_mb:>5.2f} MB"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
