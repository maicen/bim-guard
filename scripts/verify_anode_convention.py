"""
Determine the sign convention of the GC-001 galvanic series.

Two engines read that series with opposite conventions for which end is the
anode, so one of them names the wrong corroding material. See
docs/defects/defect_report_anode_convention.md.

This script settles it from the data, in either of two modes.

    uv run python scripts/verify_anode_convention.py                # live DB
    uv run python scripts/verify_anode_convention.py --from-seeder  # offline

The live mode reads the Supabase static asset 'ruleset:BIMGUARD-GC-001', which
is the running system's source of truth.

The offline mode resolves what the seeder feeds that asset from. Note that
ruleset_seeder.py holds no series literals of its own: it calls
StaticDataService().get_asset_json('ruleset:BIMGUARD-GC-001'), so it is a
consumer of the same asset, not its origin. The origin is the JSON payload
that was uploaded to it, checked in at data/rulesets/galvanic_corrosion_ruleset.json
until it was deleted from the tree. Offline mode recovers that payload from git
history and reports the full provenance chain, including its drift caveat: if
anyone edited the asset in the database after it was seeded, the recovered file
no longer matches what the engines actually read.

Two independent checks are run:

    1. The `noble` flag. Every entry carries one alongside potential_v, so
       whether noble materials hold higher or lower potentials settles the
       convention outright — no physics argument required.

    2. Zinc against copper. Zinc sacrifices to copper; that is what
       galvanising is. Whichever sign reading names zinc as anode is correct.

Both should agree. If they disagree, the series itself is inconsistent and
that is a bigger problem than the convention.
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path

# Run directly from scripts/ without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MORE_NEGATIVE = "more_negative_is_anodic"
MORE_POSITIVE = "more_positive_is_anodic"

# Substrings identifying the physics-anchor pair, matched case-insensitively
# against series keys and labels.
ANODE_ANCHOR = ("zinc", "galvanis", "galvaniz")
CATHODE_ANCHOR = ("copper", "cu_", "c12200")


def _potential(entry: object) -> float | None:
    """Extract potential_v from a series entry of either shape."""
    if isinstance(entry, (int, float)):
        return float(entry)
    if isinstance(entry, dict):
        value = entry.get("potential_v")
        return float(value) if value is not None else None
    return None


def _noble(entry: object) -> bool | None:
    """Extract the noble flag from a series entry, if present."""
    if isinstance(entry, dict) and isinstance(entry.get("noble"), bool):
        return entry["noble"]
    return None


def _find(series: dict, needles: tuple[str, ...]) -> tuple[str, object] | None:
    """Find the first entry whose key or label matches any needle."""
    for key, entry in series.items():
        label = entry.get("label", "") if isinstance(entry, dict) else ""
        haystack = f"{key} {label}".lower()
        if any(needle in haystack for needle in needles):
            return key, entry
    return None


def check_noble_flag(series: dict) -> str | None:
    """Infer the convention from the noble flag. Returns None if unusable."""
    noble_potentials = []
    active_potentials = []
    for entry in series.values():
        noble = _noble(entry)
        potential = _potential(entry)
        if noble is None or potential is None:
            continue
        (noble_potentials if noble else active_potentials).append(potential)

    if not noble_potentials or not active_potentials:
        print("  noble-flag check: UNUSABLE - entries lack noble flags or potentials")
        return None

    noble_mean = sum(noble_potentials) / len(noble_potentials)
    active_mean = sum(active_potentials) / len(active_potentials)
    print(f"  noble  (cathodic) n={len(noble_potentials):2d} mean potential {noble_mean:+.3f} V")
    print(f"  active (anodic)   n={len(active_potentials):2d} mean potential {active_mean:+.3f} V")

    if active_mean < noble_mean:
        print("  -> active materials sit LOWER: more negative is anodic")
        return MORE_NEGATIVE
    if active_mean > noble_mean:
        print("  -> active materials sit HIGHER: more positive is anodic")
        return MORE_POSITIVE
    print("  noble-flag check: INCONCLUSIVE - means are equal")
    return None


def check_zinc_copper(series: dict) -> str | None:
    """Infer the convention from the zinc/copper anchor pair."""
    anode = _find(series, ANODE_ANCHOR)
    cathode = _find(series, CATHODE_ANCHOR)
    if anode is None or cathode is None:
        print("  zinc/copper check: UNUSABLE - anchor materials not found in series")
        return None

    anode_key, anode_entry = anode
    cathode_key, cathode_entry = cathode
    anode_v = _potential(anode_entry)
    cathode_v = _potential(cathode_entry)
    if anode_v is None or cathode_v is None:
        print("  zinc/copper check: UNUSABLE - anchor entries carry no potential")
        return None

    print(f"  {anode_key:24s} {anode_v:+.3f} V   (known anode - galvanising sacrifices)")
    print(f"  {cathode_key:24s} {cathode_v:+.3f} V   (known cathode)")

    if anode_v < cathode_v:
        print("  -> the known anode sits LOWER: more negative is anodic")
        return MORE_NEGATIVE
    print("  -> the known anode sits HIGHER: more positive is anodic")
    return MORE_POSITIVE


# ---------------------------------------------------------------------------
# Series loading
# ---------------------------------------------------------------------------

SEEDER_PATH = Path("app/services/ruleset_seeder.py")
GC_ASSET_KEY = "ruleset:BIMGUARD-GC-001"


def _seeder_asset_key_for_galvanic() -> tuple[str | None, str | None]:
    """
    Read the seeder's own asset map to learn where its galvanic series comes from.

    Parsed with ast rather than imported: ruleset_seeder.py reaches the database
    at import time, which is exactly the condition the offline mode exists for.

    Returns:
        (filename, asset_key) as the seeder declares them, or (None, None).
    """
    if not SEEDER_PATH.exists():
        return None, None
    tree = ast.parse(SEEDER_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(getattr(t, "id", "") == "asset_key_map" for t in node.targets):
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        for key_node, value_node in zip(node.value.keys, node.value.values):
            try:
                filename = ast.literal_eval(key_node)
                asset_key = ast.literal_eval(value_node)
            except ValueError:
                continue
            if asset_key == GC_ASSET_KEY:
                return filename, asset_key
    return None, None


def _git(*args: str) -> str | None:
    """Run a git command, returning stdout or None if it fails."""
    try:
        result = subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout if result.returncode == 0 else None


def _recover_from_git(path: str) -> tuple[str | None, str | None]:
    """
    Recover the last tracked content of a file deleted from the tree.

    Returns:
        (content, commit) where commit is the revision the content was read
        from, or (None, None) if the file was never tracked.
    """
    log = _git("log", "--all", "--diff-filter=D", "--format=%H", "--", path)
    if log and log.strip():
        deleting = log.split()[0]
        content = _git("show", f"{deleting}^:{path}")
        if content:
            return content, f"{deleting[:7]}^"

    log = _git("log", "--all", "--format=%H", "-1", "--", path)
    if log and log.strip():
        commit = log.split()[0]
        content = _git("show", f"{commit}:{path}")
        if content:
            return content, commit[:7]
    return None, None


def load_series_from_seeder_source() -> tuple[dict, list[str]]:
    """
    Load the galvanic series the seeder feeds into the GC-001 asset.

    Follows the provenance chain rather than assuming it: reads the seeder's
    own asset map, resolves the payload filename, then finds that payload on
    disk or recovers it from git history.

    Returns:
        (materials, provenance) — the series entries and the human-readable
        chain of where they came from, including caveats.

    Raises:
        RuntimeError: If the payload cannot be located at all.
    """
    provenance: list[str] = []

    filename, asset_key = _seeder_asset_key_for_galvanic()
    if asset_key:
        provenance.append(f"{SEEDER_PATH} maps {filename!r} -> asset {asset_key!r}")
    else:
        filename = "galvanic_corrosion_ruleset.json"
        provenance.append(
            f"{SEEDER_PATH} did not declare an asset map entry; assuming {filename!r}"
        )
    provenance.append(
        "ruleset_seeder.py holds no series literals: it reads that asset via "
        "StaticDataService, so it consumes the payload rather than defining it"
    )

    repo_path = f"data/rulesets/{filename}"
    on_disk = Path(repo_path)
    if on_disk.exists():
        payload = json.loads(on_disk.read_text(encoding="utf-8"))
        provenance.append(f"payload read from the working tree at {repo_path}")
    else:
        content, commit = _recover_from_git(repo_path)
        if content is None:
            raise RuntimeError(
                f"{repo_path} is not in the working tree and has no git history. "
                "The series exists only in the database; run without --from-seeder."
            )
        payload = json.loads(content)
        provenance.append(f"payload recovered from git at {commit}:{repo_path}")
        provenance.append(
            "CAVEAT - this is the payload as last committed. If the database asset "
            "was edited after seeding, the engines read something else and this "
            "verdict does not describe the running system"
        )

    series = payload.get("galvanic_series") or {}
    materials = series.get("materials") or {}
    if not materials:
        raise RuntimeError(f"{repo_path} carries no galvanic_series.materials")

    for field in ("source", "reference_electrode", "reference_electrolyte", "note"):
        value = series.get(field)
        if value:
            provenance.append(f"series {field}: {value}")

    return materials, provenance


def load_series_from_database() -> tuple[dict, list[str]]:
    """
    Load the galvanic series the engines actually read at runtime.

    Returns:
        (materials, provenance).

    Raises:
        RuntimeError: If the catalogue cannot be reached or is empty.
    """
    try:
        from app.services.corrosion_rule_catalog import load_gc_catalog
    except ImportError as exc:
        raise RuntimeError(f"cannot import the catalogue loader: {exc}") from exc

    try:
        catalogue = load_gc_catalog()
    except Exception as exc:
        raise RuntimeError(f"{type(exc).__name__}: {exc}") from exc

    series = catalogue.get("galvanic_series") or {}
    materials = series.get("materials", series)
    if not materials:
        raise RuntimeError("the catalogue returned an empty galvanic series")
    return materials, [f"live Supabase static asset {GC_ASSET_KEY!r}"]


def report(materials: dict, provenance: list[str]) -> int:
    """Run both checks against a loaded series and print the verdict."""
    print("Provenance")
    for line in provenance:
        print(f"  {line}")
    print()
    print(f"GC-001 galvanic series: {len(materials)} entries")
    print()
    print("Check 1 - noble flag")
    by_flag = check_noble_flag(materials)
    print()
    print("Check 2 - zinc/copper physics anchor")
    by_anchor = check_zinc_copper(materials)
    print()

    verdicts = [v for v in (by_flag, by_anchor) if v is not None]
    if not verdicts:
        print("INCONCLUSIVE - neither check could run. Inspect the series by hand.")
        return 1
    if len(set(verdicts)) > 1:
        print("CHECKS DISAGREE - the series is internally inconsistent.")
        print("That is a larger problem than the convention. Do not proceed.")
        return 1

    convention = verdicts[0]
    print(f"CONVENTION: {convention}")
    print()
    if convention == MORE_NEGATIVE:
        print("  galvanic.py:190                  CORRECT (more negative = anode)")
        print("  bimguard_corrosion_engine.py:353 WRONG   - the LIVE engine")
        print()
        print("  Every galvanic BCF issue names the wrong victim. See the defect")
        print("  report for the one-line fix and its regression test.")
    else:
        print("  bimguard_corrosion_engine.py:353 CORRECT (more positive = anode)")
        print("  galvanic.py:190                  WRONG   - dormant, Path B")
        print()
        print("  No user-facing defect: the wrong engine is not wired up. Fix before")
        print("  Path B is enabled.")
    print()
    print(f"Set series_convention in xm_001_cross_material.json to: {convention}")
    print("Paste the values above into the defect report as evidence.")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Load the series from the chosen source and report the convention."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument(
        "--from-seeder",
        action="store_true",
        help="resolve the series from the seeder's source payload instead of the live database",
    )
    args = parser.parse_args(argv)

    try:
        if args.from_seeder:
            materials, provenance = load_series_from_seeder_source()
        else:
            materials, provenance = load_series_from_database()
    except RuntimeError as exc:
        print(f"Cannot read the GC-001 galvanic series: {exc}")
        if not args.from_seeder:
            print()
            print("The live series is the Supabase static asset "
                  f"{GC_ASSET_KEY!r}. Set SUPABASE_URL and the service key, or")
            print("re-run with --from-seeder to verify against the seeder's source payload.")
        return 2

    return report(materials, provenance)


if __name__ == "__main__":
    sys.exit(main())
