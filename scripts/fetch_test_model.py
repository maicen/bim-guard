r"""Download verified IFC test models into ``data/test_models/``.

Models live in the companion repository ``maicen/bimguard-test-models`` rather
than here, so the core engine repo stays small. This script pulls one model, or
a curated multi-discipline set, on demand.

Every download is checked against the ``sha256`` recorded upstream, so a
truncated transfer or an HTML error page served in place of a model is caught
rather than parsed as IFC. A file that is already present and matches its
checksum is left alone.

WHICH UPSTREAM METADATA IS TRUSTED

    The test-models repository publishes three metadata files and they do not
    agree. ``metadata/models-manifest.json`` carries fabricated values: 33 of
    its 34 ``sha256`` fields are not valid digests (32 or 40 characters rather
    than 64, several of them the repeated keyboard walk ``1928374e``, and one
    value shared verbatim by six different files). Its ``material_pct`` and
    ``materials_summary`` columns disagree with measurement in the same
    direction -- it claims ``craslabbim.ifc`` holds 6120 piping elements at
    38.4% material coverage where the measured profile records zero of both.

    This script therefore takes checksums only from
    ``metadata/download_results.json`` (38 real, unique 64-character digests,
    recorded when each file was fetched from its original source). Downloads
    verify against those byte for byte. ``models-manifest.json`` is not read.

    ``metadata/piping_profile.json`` supplies the element and ``mat%`` columns
    shown by ``--list``, but ITS MATERIAL FIGURES ARE ALSO UNRELIABLE and are
    reported as an upstream claim rather than a measurement. Direct inspection
    of ``Clinic_Plumbing.ifc`` finds one ``IfcMaterial`` entity
    (``Chrome - DELTA - Polished``) where the profile claims
    ``Copper_C12200:480; CarbonSteel:48``; ``Clinic_HVAC.ifc`` contains no
    ``IfcMaterial`` entity at all. Verify a model before relying on it for a
    material-dependent engine::

        grep -oiE "IFCMATERIAL\('[^']*'" data/test_models/<model>.ifc | sort -u

Usage::

    python scripts/fetch_test_model.py --list
    python scripts/fetch_test_model.py hospital
    python scripts/fetch_test_model.py Clinic_Plumbing.ifc
    python scripts/fetch_test_model.py --set clinic

Authentication is not required (the repository is public). If ``GITHUB_TOKEN``
or ``GH_TOKEN`` is set it is sent anyway, which raises the anonymous rate limit
and allows the same script to work if the repository is ever made private.

Exit codes: ``0`` success, ``1`` download/verification failure, ``2`` usage error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Where downloaded models land. Gitignored - see .gitignore.
DEST_DIR = REPO_ROOT / "data" / "test_models"

TEST_MODELS_REPO = "maicen/bimguard-test-models"
BRANCH = "HEAD"
RAW_BASE = f"https://raw.githubusercontent.com/{TEST_MODELS_REPO}/{BRANCH}"

#: Real SHA-256 digests, recorded at fetch time. See "WHICH UPSTREAM METADATA
#: IS TRUSTED" above for why models-manifest.json is deliberately not used.
DOWNLOAD_RESULTS_PATH = "metadata/download_results.json"

#: Measured element and material counts, produced by parsing each model.
PIPING_PROFILE_PATH = "metadata/piping_profile.json"

#: Bytes per read. Large enough to keep the socket busy, small enough to report
#: progress on a 80 MB model.
CHUNK = 1 << 20

#: Default model per category, by upstream reputation only. None of these has
#: been confirmed to carry piping materials - see the metadata warning above.
#: The galvanic engine can only raise a finding where the model actually names
#: dissimilar metals, so verify before using one to exercise GC-001.
CATEGORY_DEFAULTS: dict[str, str] = {
    "hospital": "Clinic_Plumbing.ifc",
    "office": "wbdg_office_mep.ifc",
    "industrial": "craslabbim.ifc",
}

#: Curated multi-discipline sets. Seismic clearance is a question about a
#: building rather than a file - the brace is in the mechanical model and the
#: beam it must clear is in the structural one - so a clearance run needs every
#: discipline of one building. The first entry is the primary model.
MODEL_SETS: dict[str, tuple[str, ...]] = {
    "clinic": ("Clinic_Plumbing.ifc", "Clinic_Structural.ifc", "Clinic_HVAC.ifc"),
    "west-riverside": (
        "west_riverside_hospital_mech_ifc4.ifc",
        "west_riverside_hospital_str_ifc4.ifc",
        "west_riverside_hospital_plumb_ifc4.ifc",
    ),
    "duplex": ("Duplex_Plumbing_20121113.ifc", "Duplex_MEP_20110907.ifc", "Duplex_A_20110907.ifc"),
}

#: Every IFC part 21 file opens with this token. Guards against a redirect or
#: error page being written to disk under a .ifc name.
IFC_MAGIC = b"ISO-10303-21"


class FetchError(RuntimeError):
    """Raised when a model cannot be downloaded or fails verification."""


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------


def _request(url: str) -> urllib.request.Request:
    """Build a request, attaching a GitHub token when one is in the environment."""
    request = urllib.request.Request(url)
    request.add_header("User-Agent", "bimguard-fetch-test-model")
    token = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    return request


def _fetch_json(path: str) -> Any:
    """Fetch and decode one JSON metadata file from the test-models repository."""
    url = f"{RAW_BASE}/{path}"
    try:
        with urllib.request.urlopen(_request(url), timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        hint = ""
        if exc.code in (401, 403, 404):
            hint = (
                f" Check that {TEST_MODELS_REPO} is reachable; set GITHUB_TOKEN "
                "if it is private or you are being rate limited."
            )
        raise FetchError(f"Could not read {path} ({exc.code} {exc.reason}).{hint}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise FetchError(f"Could not read {path}: {exc}") from exc


def _is_sha256(value: object) -> bool:
    """Return whether *value* is a syntactically valid SHA-256 hex digest."""
    text = str(value or "").strip().lower()
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def load_manifest() -> list[dict[str, Any]]:
    """Build the model catalogue from the two trustworthy metadata files.

    Download records supply identity, size and checksum; the piping profile
    supplies measured element and material counts. Entries whose checksum is
    not a valid digest are kept but flagged, so a model can still be fetched
    while the missing verification is reported rather than silently skipped.
    """
    downloads = _fetch_json(DOWNLOAD_RESULTS_PATH)
    if not isinstance(downloads, list) or not downloads:
        raise FetchError(f"{DOWNLOAD_RESULTS_PATH} is empty or not a list of entries.")

    profile_rows = _fetch_json(PIPING_PROFILE_PATH)
    profiles = {
        str(row.get("filename")): row for row in profile_rows if isinstance(row, dict)
    }

    catalogue: list[dict[str, Any]] = []
    for row in downloads:
        filename = str(row.get("name") or "").strip()
        folder = str(row.get("folder") or "").strip()
        if not filename or not folder:
            continue
        measured = profiles.get(filename, {})
        digest = str(row.get("sha256") or "").strip().lower()
        catalogue.append(
            {
                "filename": filename,
                "name": filename.rsplit(".", 1)[0].replace("_", " "),
                "path": f"models/{folder}/{filename}",
                "category": str(row.get("category") or folder),
                "ifc_schema": str(row.get("schema") or ""),
                "size_bytes": int(row.get("size_bytes") or 0),
                "sha256": digest if _is_sha256(digest) else "",
                "material_pct": float(measured.get("material_pct") or 0.0),
                "materials": str(measured.get("materials") or ""),
                "piping_elements": int(
                    measured.get("elements") or row.get("flow_entities") or row.get("pipe_entities") or 0
                ),
                "source_url": str(row.get("url") or ""),
                "kind": str(row.get("kind") or "ifc"),
            }
        )

    if not catalogue:
        raise FetchError("No usable entries found in the upstream metadata.")
    return catalogue


def _sha256_of(path: Path) -> str:
    """Return the hex SHA-256 of *path*, read in chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def download(entry: dict[str, Any], dest_dir: Path, force: bool = False) -> Path:
    """Download one manifest *entry* into *dest_dir* and verify its checksum.

    An existing file whose checksum already matches is kept and returned
    without re-downloading, so the script is safe to re-run.
    """
    filename = entry["filename"]
    expected = str(entry.get("sha256") or "").strip().lower()
    target = dest_dir / filename

    if target.exists() and not force:
        if not expected:
            print(f"  {filename}: already present (no valid checksum upstream, kept as is)")
            return target
        if _sha256_of(target) == expected:
            print(f"  {filename}: already present and verified, skipping")
            return target
        print(f"  {filename}: present but checksum differs, re-downloading")

    url = f"{RAW_BASE}/{entry['path']}"
    total = int(entry.get("size_bytes") or 0)
    dest_dir.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".part")
    digest = hashlib.sha256()
    read = 0

    print(f"  {filename}: downloading {_human(total)} from {entry['path']}")
    try:
        with urllib.request.urlopen(_request(url), timeout=120) as response, tmp.open("wb") as out:
            while True:
                block = response.read(CHUNK)
                if not block:
                    break
                out.write(block)
                digest.update(block)
                read += len(block)
                _progress(read, total)
        _progress_done()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
        tmp.unlink(missing_ok=True)
        raise FetchError(f"Download of {filename} failed: {exc}") from exc

    actual = digest.hexdigest()
    if expected and actual != expected:
        tmp.unlink(missing_ok=True)
        raise FetchError(
            f"{filename} failed checksum verification.\n"
            f"  expected sha256 {expected}\n  received sha256 {actual}\n"
            "The transfer was truncated or the upstream file changed."
        )
    if not expected:
        print(f"    warning: no valid upstream checksum for {filename}; integrity unverified")
        print(f"    computed sha256 {actual}")

    if filename.lower().endswith(".ifc"):
        with tmp.open("rb") as handle:
            head = handle.read(len(IFC_MAGIC) + 64)
        if IFC_MAGIC not in head:
            tmp.unlink(missing_ok=True)
            raise FetchError(
                f"{filename} does not look like an IFC part 21 file "
                f"(no {IFC_MAGIC.decode()} header). An error page may have been served."
            )

    tmp.replace(target)
    return target


def _progress(read: int, total: int) -> None:
    """Render an in-place progress line on a terminal."""
    if not sys.stderr.isatty():
        return
    if total:
        pct = min(100.0, read * 100.0 / total)
        sys.stderr.write(f"\r    {_human(read)} / {_human(total)} ({pct:5.1f}%)")
    else:
        sys.stderr.write(f"\r    {_human(read)}")
    sys.stderr.flush()


def _progress_done() -> None:
    """Close off the progress line."""
    if sys.stderr.isatty():
        sys.stderr.write("\r" + " " * 48 + "\r")
        sys.stderr.flush()


def _human(size: int) -> str:
    """Format a byte count for humans."""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} GB"


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


def resolve(manifest: Sequence[dict[str, Any]], selector: str) -> dict[str, Any]:
    """Resolve a *selector* to one manifest entry.

    Accepts a category (``hospital``), an exact filename, a repository path or
    a case-insensitive substring of the model name.
    """
    key = selector.strip()
    lowered = key.lower()

    if lowered in CATEGORY_DEFAULTS:
        key = CATEGORY_DEFAULTS[lowered]
        lowered = key.lower()

    by_filename = {e["filename"].lower(): e for e in manifest}
    if lowered in by_filename:
        return by_filename[lowered]

    for entry in manifest:
        if entry["path"].lower() == lowered:
            return entry

    matches = [
        e for e in manifest if lowered in e["filename"].lower() or lowered in e["name"].lower()
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        names = ", ".join(sorted(e["filename"] for e in matches)[:8])
        raise FetchError(f"{selector!r} matches {len(matches)} models: {names}. Be more specific.")

    raise FetchError(f"No model matches {selector!r}. Run with --list to see what is available.")


def print_catalog(manifest: Sequence[dict[str, Any]], category: str = "") -> None:
    """Print the available models, optionally filtered to one *category*."""
    rows = [e for e in manifest if not category or e.get("category") == category]
    rows.sort(key=lambda e: (e.get("category", ""), -float(e.get("material_pct") or 0)))

    print(f"{'filename':<44}{'category':<12}{'schema':<9}{'size':>9}{'mat%':>7}  piping")
    print("-" * 96)
    for entry in rows:
        print(
            f"{entry['filename'][:43]:<44}"
            f"{entry.get('category', ''):<12}"
            f"{entry.get('ifc_schema', ''):<9}"
            f"{_human(int(entry.get('size_bytes') or 0)):>9}"
            f"{float(entry.get('material_pct') or 0):>7.1f}"
            f"  {entry.get('piping_elements', 0)}"
        )
    print()
    print("Sets (multi-discipline, for seismic clearance runs):")
    for name, members in MODEL_SETS.items():
        print(f"  --set {name:<16} {', '.join(members)}")
    print()
    print("mat% is the share of piping elements carrying a resolvable material.")
    print("The galvanic engine can only raise findings where materials are named.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(
        description=f"Download IFC test models from {TEST_MODELS_REPO} into data/test_models/.",
        epilog=(
            "Examples: python scripts/fetch_test_model.py hospital | "
            "python scripts/fetch_test_model.py --set clinic | "
            "python scripts/fetch_test_model.py --list --category industrial"
        ),
    )
    parser.add_argument(
        "model",
        nargs="?",
        help="category (hospital/office/industrial), filename, or name fragment",
    )
    parser.add_argument("--set", dest="model_set", choices=sorted(MODEL_SETS), help="fetch a curated multi-discipline set")
    parser.add_argument("--list", action="store_true", help="list available models and exit")
    parser.add_argument("--category", default="", help="restrict --list to one category")
    parser.add_argument("--dest", default=str(DEST_DIR), help="destination directory")
    parser.add_argument("--force", action="store_true", help="re-download even if already verified")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Fetch the requested model(s); see the module docstring for exit codes."""
    args = parse_args(argv)

    if not args.list and not args.model and not args.model_set:
        print(
            "error: name a model, a category, or --set. Run --list to see the catalog.",
            file=sys.stderr,
        )
        return 2

    try:
        manifest = load_manifest()
    except FetchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.list:
        print_catalog(manifest, args.category)
        return 0

    selectors: Iterable[str]
    if args.model_set:
        selectors = MODEL_SETS[args.model_set]
        print(f"Fetching set {args.model_set!r}: {len(MODEL_SETS[args.model_set])} models")
    else:
        selectors = [args.model]

    dest_dir = Path(args.dest)
    downloaded: list[Path] = []
    try:
        entries = [resolve(manifest, selector) for selector in selectors]
        for entry in entries:
            downloaded.append(download(entry, dest_dir, force=args.force))
    except FetchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("error: interrupted", file=sys.stderr)
        return 1

    print()
    print(f"Ready in {dest_dir.as_posix()}:")
    barren = []
    for path, entry in zip(downloaded, entries):
        material = float(entry.get("material_pct") or 0)
        print(
            f"  {path.name}  ({_human(path.stat().st_size)}, "
            f"{entry.get('ifc_schema', '?')}, {material:.1f}% materials resolved, "
            f"{entry.get('piping_elements', 0)} piping elements)"
        )
        if material <= 0.0:
            barren.append(entry["filename"])

    if barren:
        print()
        print("warning: no resolvable materials measured in " + ", ".join(barren))
        print("  The galvanic engine scores material pairs, so these models will")
        print("  produce no GC-001 findings. Use a model with a non-zero mat% -")
        print("  run --list to compare.")

    print()
    print("Next: python scripts/run_full_pipeline.py --model " + downloaded[0].as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
