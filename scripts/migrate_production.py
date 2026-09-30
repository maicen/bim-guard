#!/usr/bin/env python3
"""Database migration runner for self-hosted production Supabase.

Applies pending SQL migrations from supabase/migrations/ to the self-hosted
production PostgreSQL instance, tracks applied versions in
supabase_migrations.schema_migrations, and reloads the PostgREST schema cache.

Usage:
    uv run python scripts/migrate_production.py --status
    uv run python scripts/migrate_production.py --dry-run
    uv run python scripts/migrate_production.py --apply
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = REPO_ROOT / "supabase" / "migrations"
DOCKER_SUPABASE_ENV = REPO_ROOT / "docker" / "supabase" / ".env"
APP_ENV = REPO_ROOT / ".env"


def _read_env_var(file_path: Path, key: str) -> str | None:
    if not file_path.exists():
        return None
    for line in file_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            if k.strip() == key:
                return v.strip().strip("'\"")
    return None


def get_db_url(cli_url: str | None = None) -> str:
    """Resolve the PostgreSQL connection string."""
    if cli_url:
        return cli_url

    env_url = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
    if env_url:
        return env_url

    # Check docker/supabase/.env for POSTGRES_PASSWORD
    password = _read_env_var(DOCKER_SUPABASE_ENV, "POSTGRES_PASSWORD")
    if not password:
        password = _read_env_var(APP_ENV, "POSTGRES_PASSWORD") or os.environ.get("POSTGRES_PASSWORD")

    if not password:
        password = "postgres"

    port = _read_env_var(DOCKER_SUPABASE_ENV, "POSTGRES_EXPOSED_PORT") or "54322"
    return f"postgresql://postgres:{password}@localhost:{port}/postgres?sslmode=disable"


def find_supabase_cli() -> str | None:
    """Find the supabase executable."""
    found = shutil.which("supabase")
    if found:
        return found
    common_paths = [
        "/opt/homebrew/bin/supabase",
        "/usr/local/bin/supabase",
        Path.home() / ".local" / "bin" / "supabase",
        Path.home() / ".bin" / "supabase",
    ]
    for p in common_paths:
        if Path(p).is_file() and os.access(p, os.X_OK):
            return str(p)
    return None


def reload_postgrest_cache() -> bool:
    """Send reload schema notification to PostgREST."""
    print("==> Reloading PostgREST schema cache (NOTIFY pgrst, 'reload schema')...")
    # Try via docker exec first
    docker = shutil.which("docker")
    if docker:
        res = subprocess.run(
            [docker, "exec", "-i", "supabase-db", "psql", "-U", "postgres", "-d", "postgres", "-c", "NOTIFY pgrst, 'reload schema';"],
            capture_output=True,
            text=True,
        )
        if res.returncode == 0:
            print("    PostgREST notified successfully via container.")
            return True

    # Fallback to psql if installed
    psql = shutil.which("psql")
    if psql:
        res = subprocess.run(
            [psql, get_db_url(), "-c", "NOTIFY pgrst, 'reload schema';"],
            capture_output=True,
            text=True,
        )
        if res.returncode == 0:
            print("    PostgREST notified successfully via psql.")
            return True

    print("    Warning: Could not notify PostgREST directly. If container is running, execute:")
    print("    docker exec -i supabase-db psql -U postgres -d postgres -c \"NOTIFY pgrst, 'reload schema';\"")
    return False


def run_status(db_url: str, supabase_bin: str | None) -> int:
    """Report migration status."""
    print(f"==> Inspecting migration status against {re.sub(r':([^@]+)@', ':****@', db_url)}...")
    if supabase_bin:
        cmd = [supabase_bin, "migration", "list", "--db-url", db_url]
        res = subprocess.run(cmd, cwd=str(REPO_ROOT))
        return res.returncode

    # Fallback inspection via psql
    print("Notice: 'supabase' CLI not found; querying via docker exec / psql...")
    docker = shutil.which("docker")
    if docker:
        res = subprocess.run(
            [docker, "exec", "-i", "supabase-db", "psql", "-U", "postgres", "-d", "postgres", "-c", "SELECT version, name FROM supabase_migrations.schema_migrations ORDER BY version;"],
            text=True,
        )
        return res.returncode

    print("Error: Neither 'supabase' CLI nor 'docker' is available to inspect migrations.")
    return 1


def run_dry_run(db_url: str, supabase_bin: str | None) -> int:
    """Perform a dry-run of pending migrations."""
    print(f"==> Dry-run: Checking pending migrations against {re.sub(r':([^@]+)@', ':****@', db_url)}...")
    if supabase_bin:
        cmd = [supabase_bin, "db", "push", "--dry-run", "--include-all", "--db-url", db_url]
        res = subprocess.run(cmd, cwd=str(REPO_ROOT))
        return res.returncode

    print("Error: 'supabase' CLI is required for dry-run validation.")
    return 1


def run_apply_cli(db_url: str, supabase_bin: str) -> int:
    """Apply migrations using the Supabase CLI."""
    print(f"==> Applying migrations via Supabase CLI against {re.sub(r':([^@]+)@', ':****@', db_url)}...")
    cmd = [supabase_bin, "db", "push", "--include-all", "--db-url", db_url]
    res = subprocess.run(cmd, cwd=str(REPO_ROOT))
    if res.returncode != 0:
        print(f"Error: Migration push failed with exit code {res.returncode}")
        return res.returncode

    reload_postgrest_cache()
    print("==> Migration run completed successfully.")
    return 0


def run_apply_direct_fallback() -> int:
    """Fallback migration runner executing pending SQL files via docker exec supabase-db."""
    print("==> Running fallback direct SQL migration runner via docker exec...")
    docker = shutil.which("docker")
    if not docker:
        print("Error: Docker is not available for direct migration execution.")
        return 1

    # Ensure schema_migrations table exists
    ensure_sql = """
    CREATE SCHEMA IF NOT EXISTS supabase_migrations;
    CREATE TABLE IF NOT EXISTS supabase_migrations.schema_migrations (
        version text PRIMARY KEY,
        statements text[],
        name text
    );
    """
    res = subprocess.run(
        [docker, "exec", "-i", "supabase-db", "psql", "-U", "postgres", "-d", "postgres", "-c", ensure_sql],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        print(f"Error initializing schema_migrations table: {res.stderr}")
        return res.returncode

    # Query already applied versions
    res = subprocess.run(
        [docker, "exec", "-i", "supabase-db", "psql", "-U", "postgres", "-d", "postgres", "-t", "-A", "-c", "SELECT version FROM supabase_migrations.schema_migrations;"],
        capture_output=True,
        text=True,
    )
    applied_versions = set(line.strip() for line in res.stdout.splitlines() if line.strip())

    # Get local migration files
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    pending = []
    for mf in migration_files:
        version = mf.name.split("_")[0]
        if version not in applied_versions:
            pending.append(mf)

    if not pending:
        print("==> Remote database is up to date (no pending migrations).")
        return 0

    print(f"==> Found {len(pending)} pending migrations to apply:")
    for mf in pending:
        print(f"    • {mf.name}")

    for mf in pending:
        version = mf.name.split("_")[0]
        name = mf.stem
        sql_content = mf.read_text(encoding="utf-8")
        print(f"==> Applying {mf.name}...")

        # Run within transaction
        apply_res = subprocess.run(
            [docker, "exec", "-i", "supabase-db", "psql", "-U", "postgres", "-d", "postgres", "-v", "ON_ERROR_STOP=1"],
            input=sql_content,
            capture_output=True,
            text=True,
        )
        if apply_res.returncode != 0:
            print(f"ERROR applying {mf.name}:\n{apply_res.stderr}")
            return apply_res.returncode

        # Record migration
        record_sql = f"INSERT INTO supabase_migrations.schema_migrations (version, name) VALUES ('{version}', '{name}') ON CONFLICT (version) DO NOTHING;"
        subprocess.run(
            [docker, "exec", "-i", "supabase-db", "psql", "-U", "postgres", "-d", "postgres", "-c", record_sql],
            check=True,
        )
        print(f"    ✓ {mf.name} recorded.")

    reload_postgrest_cache()
    print("==> All pending migrations applied successfully.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Supabase Production Migration Runner")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--status", action="store_true", help="List migration status (local vs remote)")
    mode_group.add_argument("--dry-run", action="store_true", help="Check what would be migrated without applying")
    mode_group.add_argument("--apply", action="store_true", help="Apply pending migrations (default)")
    parser.add_argument("--db-url", type=str, default=None, help="Custom PostgreSQL connection string")
    parser.add_argument("--force-fallback", action="store_true", help="Force direct execution bypassing supabase CLI")

    args = parser.parse_args()
    db_url = get_db_url(args.db_url)
    supabase_bin = None if args.force_fallback else find_supabase_cli()

    if args.status:
        return run_status(db_url, supabase_bin)
    if args.dry_run:
        return run_dry_run(db_url, supabase_bin)

    # Default is --apply
    if supabase_bin:
        return run_apply_cli(db_url, supabase_bin)
    else:
        return run_apply_direct_fallback()


if __name__ == "__main__":
    sys.exit(main())
