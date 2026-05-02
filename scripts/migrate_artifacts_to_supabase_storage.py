"""Upload local BIM-Guard artifacts to Supabase Storage.

The script walks the local data directory and uploads files to a bucket,
preserving relative paths so migration remains reversible and auditable.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from supabase import Client, create_client


@dataclass(slots=True)
class UploadResult:
    """Summary values for the storage migration run."""

    uploaded: int = 0
    skipped: int = 0
    failed: int = 0


def _build_client() -> Client:
    """Create a Supabase client from environment variables."""
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()

    if not url:
        raise ValueError("SUPABASE_URL is required.")
    if not key:
        raise ValueError("SUPABASE_SERVICE_ROLE_KEY is required for storage migration writes.")

    return create_client(url, key)


def _sha256_bytes(content: bytes) -> str:
    """Return SHA-256 checksum for given bytes."""
    return hashlib.sha256(content).hexdigest()


def _iter_files(source_dir: Path, include_db_file: bool) -> list[Path]:
    """Collect files from source directory recursively."""
    files: list[Path] = []
    for path in source_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix in {".shm", ".wal"}:
            continue
        if not include_db_file and path.name == "bimguard.sqlite":
            continue
        files.append(path)
    return files


def _to_storage_key(path: Path, source_dir: Path, prefix: str) -> str:
    """Map local path to storage object key."""
    relative = path.relative_to(source_dir).as_posix()
    normalized_prefix = prefix.strip("/")
    if not normalized_prefix:
        return relative
    return f"{normalized_prefix}/{relative}"


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Upload local artifacts to Supabase Storage.")
    parser.add_argument(
        "--source-dir",
        default="data",
        help="Root directory to upload recursively.",
    )
    parser.add_argument(
        "--bucket",
        default=os.getenv("SUPABASE_STORAGE_BUCKET", "bim-guard-artifacts"),
        help="Destination bucket name.",
    )
    parser.add_argument(
        "--prefix",
        default="migration",
        help="Object key prefix in bucket.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without uploading.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip upload when object key already exists.",
    )
    parser.add_argument(
        "--include-db-file",
        action="store_true",
        help="Include SQLite db file in artifact upload.",
    )
    return parser.parse_args()


def _list_existing_keys(client: Client, bucket: str, prefix: str) -> set[str]:
    """List existing object keys under prefix for skip-existing mode."""
    normalized_prefix = prefix.strip("/")
    cursor = ""
    keys: set[str] = set()

    while True:
        response = client.storage.from_(bucket).list(
            path=normalized_prefix,
            options={"limit": 1000, "offset": int(cursor or 0)},
        )
        items = response or []
        if not items:
            break

        for item in items:
            name = item.get("name", "")
            if not name:
                continue
            keys.add(f"{normalized_prefix}/{name}" if normalized_prefix else name)

        if len(items) < 1000:
            break
        cursor = str(int(cursor or 0) + 1000)

    return keys


def main() -> int:
    """Run artifact migration to Supabase Storage."""
    load_dotenv(override=False)
    args = parse_args()

    source_dir = Path(args.source_dir)
    if not source_dir.exists() or not source_dir.is_dir():
        print(f"Source directory not found: {source_dir}")
        return 1

    client = _build_client()
    files = _iter_files(source_dir, include_db_file=args.include_db_file)
    existing_keys: set[str] = set()

    if args.skip_existing and not args.dry_run:
        existing_keys = _list_existing_keys(client, args.bucket, args.prefix)

    result = UploadResult()

    for path in files:
        key = _to_storage_key(path, source_dir, args.prefix)

        if args.skip_existing and key in existing_keys:
            result.skipped += 1
            print(f"SKIP {key}")
            continue

        content = path.read_bytes()
        checksum = _sha256_bytes(content)

        if args.dry_run:
            result.skipped += 1
            print(f"DRYRUN {key} bytes={len(content)} sha256={checksum}")
            continue

        try:
            client.storage.from_(args.bucket).upload(
                path=key,
                file=content,
                file_options={"upsert": "true"},
            )
            result.uploaded += 1
            print(f"UPLOADED {key} bytes={len(content)} sha256={checksum}")
        except Exception as exc:
            result.failed += 1
            print(f"FAILED {key} error={exc}")

    print(f"DONE uploaded={result.uploaded} skipped={result.skipped} failed={result.failed}")
    return 0 if result.failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
