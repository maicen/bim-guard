"""Test runner that automatically discovers and executes tests relevant to local git changes.

Inspects git status (unstaged, staged, untracked) and maps modified source
files (e.g. ``app/services/document_orchestrator_service.py`` or
``app/api/documents.py``) or directly modified test files to their
corresponding pytest targets.

Usage:
    uv run python scripts/test_relevant.py
    uv run python scripts/test_relevant.py -v
    uv run python scripts/test_relevant.py --dry-run
    uv run python scripts/test_relevant.py --all-changed  # includes diff against main
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_git_changed_files(include_diff_main: bool = False) -> list[str]:
    """Retrieve list of modified, added, and untracked files relative to HEAD or main."""
    changed: set[str] = set()

    # 1. Unstaged + staged + untracked files in working tree
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            # format: 'XY path' or 'R  path1 -> path2'
            parts = line[2:].strip().split(" -> ")
            changed.add(parts[-1].strip())
    except subprocess.SubprocessError:
        pass

    # 2. Optionally include commits on this branch compared to main
    if include_diff_main:
        try:
            res = subprocess.run(
                ["git", "diff", "--name-only", "origin/main...HEAD"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            for line in res.stdout.splitlines():
                if line.strip():
                    changed.add(line.strip())
        except subprocess.SubprocessError:
            pass

    return sorted(changed)


def map_source_to_tests(source_file: str, existing_tests: list[str]) -> set[str]:
    """Given a modified source file path, find matching test files."""
    matched: set[str] = set()
    path = Path(source_file)

    # If it's already a test file, target it directly
    if source_file.startswith("tests/") and source_file.endswith(".py"):
        if (REPO_ROOT / source_file).is_file():
            return {source_file}

    # Extract stem tokens (e.g., 'document_orchestrator_service' -> ['document', 'orchestrator'])
    stem = path.stem
    # Remove common suffixes like '_service', '_router', '_provider', '_engine'
    simplified = re.sub(r"(_service|_router|_provider|_engine|_client|_helpers)$", "", stem)
    singular = simplified[:-1] if simplified.endswith("s") else simplified

    # Direct name match: test_<stem>.py or test_<simplified>.py
    for candidate in [f"test_{stem}.py", f"test_{simplified}.py", f"test_{singular}.py"]:
        matches = [t for t in existing_tests if Path(t).name == candidate]
        matched.update(matches)

    # API route match: app/api/documents.py -> test_api_documents.py or test_documents*.py or test_document*.py
    if "app/api/" in source_file:
        for t in existing_tests:
            name = Path(t).name
            if any(k in name for k in (f"test_api_{simplified}", f"test_{simplified}", f"test_{singular}")):
                matched.add(t)

    # Keyword / substring match if nothing matched yet
    if not matched and len(singular) >= 4:
        for t in existing_tests:
            name = Path(t).name.lower()
            if singular in name or simplified in name:
                matched.add(t)

    # Token match for compound names (e.g. document_orchestrator -> test_document_*.py)
    if not matched:
        tokens = [tok.rstrip("s") for tok in simplified.split("_") if len(tok) >= 4]
        # Prioritize the first domain token
        if tokens:
            primary_token = tokens[0]
            for t in existing_tests:
                name = Path(t).name.lower()
                if f"test_{primary_token}" in name or f"_{primary_token}_" in name:
                    matched.add(t)

    return matched


def find_all_test_files() -> list[str]:
    """List all available test files under tests/."""
    test_dir = REPO_ROOT / "tests"
    if not test_dir.is_dir():
        return []
    return [
        str(p.relative_to(REPO_ROOT))
        for p in test_dir.rglob("test_*.py")
        if p.is_file()
    ]


def main() -> int:
    """Discover relevant tests based on git status and execute pytest."""
    parser = argparse.ArgumentParser(
        description="Run tests relevant to modified files in git.",
        add_help=False,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned pytest command without running it.",
    )
    parser.add_argument(
        "--all-changed",
        action="store_true",
        help="Include commits changed against origin/main in addition to working tree.",
    )
    parser.add_argument("-h", "--help", action="store_true", help="Show this help message")

    args, extra_pytest_args = parser.parse_known_args()

    if args.help:
        parser.print_help()
        print("\nAll extra arguments are forwarded directly to pytest (e.g. -v, -s, -x, -k).")
        return 0

    changed_files = get_git_changed_files(include_diff_main=args.all_changed)
    all_tests = find_all_test_files()

    targeted_tests: set[str] = set()
    for f in changed_files:
        matches = map_source_to_tests(f, all_tests)
        targeted_tests.update(matches)

    print("═══════════════════════════════════════════════════════════════")
    print("  BIM-Guard Targeted Test Runner")
    print("═══════════════════════════════════════════════════════════════")

    if changed_files:
        print(f"Detected {len(changed_files)} changed file(s):")
        for cf in changed_files[:10]:
            print(f"  • {cf}")
        if len(changed_files) > 10:
            print(f"  ... and {len(changed_files) - 10} more")
    else:
        print("No local changes detected in working tree.")

    cmd = ["pytest"]

    if targeted_tests:
        print(f"\nTargeting {len(targeted_tests)} relevant test file(s):")
        sorted_targets = sorted(targeted_tests)
        for tf in sorted_targets:
            print(f"  → {tf}")
        cmd.extend(sorted_targets)
    else:
        print("\nNo direct test file matches found for changes.")
        print("Falling back to pytest-picked (modified/untracked test files)...")
        cmd.append("--picked")

    if extra_pytest_args:
        cmd.extend(extra_pytest_args)

    print(f"\nExecuting command: {' '.join(cmd)}\n")

    if args.dry_run:
        return 0

    # Run pytest within uv environment
    full_cmd = ["uv", "run"] + cmd
    return subprocess.run(full_cmd, cwd=REPO_ROOT).returncode


if __name__ == "__main__":
    sys.exit(main())
