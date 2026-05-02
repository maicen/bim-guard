"""Migrate SQLite tables into Supabase PostgREST tables.

This script is designed for one-way migration during a cutover window.
It reads rows from the local SQLite database and upserts them into
existing Supabase tables using the Supabase Python client.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
from collections.abc import Iterable
from typing import Any

from dotenv import load_dotenv
from supabase import Client, create_client


DEFAULT_TABLES = ("projects", "documents", "rules")


def _build_client() -> Client:
    """Create a Supabase client from environment variables."""
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()

    if not url:
        raise ValueError("SUPABASE_URL is required.")
    if not key:
        raise ValueError("SUPABASE_SERVICE_ROLE_KEY is required for migration writes.")

    return create_client(url, key)


def _list_tables(conn: sqlite3.Connection) -> list[str]:
    """Return user-defined table names from SQLite."""
    cursor = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    )
    return [row[0] for row in cursor.fetchall()]


def _table_columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    """Return ordered column names for a SQLite table."""
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]


def _fetch_rows(conn: sqlite3.Connection, table_name: str) -> list[dict[str, Any]]:
    """Fetch all rows from a SQLite table as dictionaries."""
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


def _chunked(items: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    """Yield fixed-size chunks from the input list."""
    for idx in range(0, len(items), size):
        yield items[idx : idx + size]


def _truncate_table(client: Client, table_name: str, columns: list[str]) -> None:
    """Delete all rows in destination table using a broad filter."""
    if "id" in columns:
        client.table(table_name).delete().gte("id", 0).execute()
        return
    # Fallback path for tables without numeric id.
    client.table(table_name).delete().neq(columns[0], "__never__").execute()


def migrate_table(
    client: Client,
    conn: sqlite3.Connection,
    table_name: str,
    *,
    chunk_size: int,
    truncate_first: bool,
) -> tuple[int, int]:
    """Migrate one table and return (migrated_rows, failed_rows)."""
    columns = _table_columns(conn, table_name)
    rows = _fetch_rows(conn, table_name)

    if not rows:
        return 0, 0

    if truncate_first:
        _truncate_table(client, table_name, columns)

    migrated = 0
    failed = 0

    for batch in _chunked(rows, chunk_size):
        try:
            if "id" in columns:
                (
                    client.table(table_name)
                    .upsert(batch, on_conflict="id", ignore_duplicates=False)
                    .execute()
                )
            else:
                client.table(table_name).insert(batch).execute()
            migrated += len(batch)
        except Exception:
            failed += len(batch)

    return migrated, failed


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Migrate SQLite rows to Supabase tables.")
    parser.add_argument(
        "--sqlite-path",
        default="data/bimguard.sqlite",
        help="Path to source SQLite file.",
    )
    parser.add_argument(
        "--tables",
        default=",".join(DEFAULT_TABLES),
        help="Comma-separated table names to migrate.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Rows per request batch.",
    )
    parser.add_argument(
        "--truncate-first",
        action="store_true",
        help="Delete destination table rows before migration.",
    )
    parser.add_argument(
        "--all-user-tables",
        action="store_true",
        help="Migrate all non-system SQLite tables instead of --tables.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the migration process."""
    load_dotenv(override=False)
    args = parse_args()

    client = _build_client()

    conn = sqlite3.connect(args.sqlite_path)
    try:
        if args.all_user_tables:
            tables = _list_tables(conn)
        else:
            tables = [item.strip() for item in args.tables.split(",") if item.strip()]

        if not tables:
            print("No tables selected for migration.")
            return 1

        total_migrated = 0
        total_failed = 0

        for table_name in tables:
            migrated, failed = migrate_table(
                client,
                conn,
                table_name,
                chunk_size=args.chunk_size,
                truncate_first=args.truncate_first,
            )
            total_migrated += migrated
            total_failed += failed
            print(
                f"[{table_name}] migrated={migrated} failed={failed} "
                f"truncate_first={args.truncate_first}"
            )

        print(f"DONE migrated={total_migrated} failed={total_failed}")
        return 0 if total_failed == 0 else 2
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
