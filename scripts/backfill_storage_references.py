"""Backfill local file paths to Supabase Storage references in DB rows.

This script updates projects.ifc_file_path and documents.file_path from
local paths to sb://bucket/key references based on the same key mapping
used during artifact migration uploads.
"""

from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv
from supabase import Client, create_client


def _build_client() -> Client:
    """Create Supabase client using server-side credentials."""
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url:
        raise ValueError("SUPABASE_URL is required.")
    if not key:
        raise ValueError("SUPABASE_SERVICE_ROLE_KEY is required for backfill writes.")
    return create_client(url, key)


def _normalize_path(path: str) -> str:
    """Normalize path separators for consistent mapping."""
    return path.replace("\\", "/")


def _to_relative_data_path(path: str) -> str | None:
    """Convert a local path string into a path relative to data/ if possible."""
    normalized = _normalize_path(path).strip()
    if not normalized:
        return None

    if normalized.startswith("data/"):
        return normalized.removeprefix("data/")

    marker = "/data/"
    if marker in normalized:
        return normalized.split(marker, 1)[1]

    if normalized.startswith("uploads/"):
        return normalized

    return None


def _to_storage_reference(relative_path: str, bucket: str, prefix: str) -> str:
    """Build sb:// reference for a relative data path."""
    prefix_norm = prefix.strip("/")
    key = relative_path.strip("/")
    if prefix_norm:
        key = f"{prefix_norm}/{key}"
    return f"sb://{bucket}/{key}"


def _object_exists(client: Client, bucket: str, key: str) -> bool:
    """Return True when the object exists in Supabase Storage."""
    try:
        content = client.storage.from_(bucket).download(key)
        return bool(content)
    except Exception:
        return False


def _backfill_table_field(
    client: Client,
    *,
    table_name: str,
    id_field: str,
    path_field: str,
    bucket: str,
    prefix: str,
    dry_run: bool,
    verify_object_exists: bool,
) -> tuple[int, int]:
    """Backfill one table's path field and return (updated, skipped)."""
    rows = client.table(table_name).select(f"{id_field},{path_field}").execute().data or []

    updated = 0
    skipped = 0

    for row in rows:
        ref = str(row.get(path_field) or "").strip()
        if not ref:
            skipped += 1
            continue
        if ref.startswith("sb://"):
            skipped += 1
            continue

        rel = _to_relative_data_path(ref)
        if rel is None:
            skipped += 1
            continue

        sb_ref = _to_storage_reference(rel, bucket, prefix)
        key = sb_ref.split(f"sb://{bucket}/", 1)[1]

        if verify_object_exists and not _object_exists(client, bucket, key):
            print(f"SKIP_MISSING_OBJECT {table_name}.{path_field} id={row.get(id_field)} key={key}")
            skipped += 1
            continue

        if dry_run:
            print(f"DRYRUN {table_name}.{path_field} id={row.get(id_field)} -> {sb_ref}")
            updated += 1
            continue

        (
            client.table(table_name)
            .update({path_field: sb_ref})
            .eq(id_field, row.get(id_field))
            .execute()
        )
        print(f"UPDATED {table_name}.{path_field} id={row.get(id_field)}")
        updated += 1

    return updated, skipped


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Backfill DB file references to sb:// URIs.")
    parser.add_argument(
        "--bucket",
        default=os.getenv("SUPABASE_STORAGE_BUCKET", "bim-guard-artifacts"),
        help="Supabase Storage bucket holding migrated artifacts.",
    )
    parser.add_argument(
        "--prefix",
        default="migration",
        help="Object key prefix used during artifact migration.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print proposed updates without writing to DB.",
    )
    parser.add_argument(
        "--no-verify-object-exists",
        action="store_true",
        help="Allow updates even when the target object cannot be confirmed.",
    )
    return parser.parse_args()


def main() -> int:
    """Run path backfill for projects and documents tables."""
    load_dotenv(override=False)
    args = parse_args()

    client = _build_client()

    p_updated, p_skipped = _backfill_table_field(
        client,
        table_name="projects",
        id_field="id",
        path_field="ifc_file_path",
        bucket=args.bucket,
        prefix=args.prefix,
        dry_run=args.dry_run,
        verify_object_exists=not args.no_verify_object_exists,
    )

    d_updated, d_skipped = _backfill_table_field(
        client,
        table_name="documents",
        id_field="id",
        path_field="file_path",
        bucket=args.bucket,
        prefix=args.prefix,
        dry_run=args.dry_run,
        verify_object_exists=not args.no_verify_object_exists,
    )

    print(
        "DONE "
        f"projects_updated={p_updated} projects_skipped={p_skipped} "
        f"documents_updated={d_updated} documents_skipped={d_skipped}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
