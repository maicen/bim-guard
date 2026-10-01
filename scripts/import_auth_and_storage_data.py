#!/usr/bin/env python3
"""Import auth and storage data into self-hosted Supabase PostgreSQL."""

import json
import os
from pathlib import Path
import subprocess

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "migration"

def sql_quote(val):
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, (dict, list)):
        dumped = json.dumps(val).replace("'", "''")
        return f"'{dumped}'::jsonb"
    # string
    escaped = str(val).replace("'", "''")
    return f"'{escaped}'"

def generate_sql() -> str:
    lines = [
        "-- Migration of auth and storage data",
        "SET session_replication_role = replica;",
        ""
    ]

    # 1. storage.buckets
    with open(DATA_DIR / "storage_buckets.json") as f:
        buckets = json.load(f)
    for b in buckets:
        cols = ["id", "name", "owner", "created_at", "updated_at", "public", "avif_autodetection", "file_size_limit", "owner_id"]
        vals = [sql_quote(b.get(c)) for c in cols]
        lines.append(f"INSERT INTO storage.buckets ({', '.join(cols)}) VALUES ({', '.join(vals)}) ON CONFLICT (id) DO NOTHING;")

    lines.append("")

    # 2. auth.users
    with open(DATA_DIR / "auth_users.json") as f:
        users = json.load(f)
    user_cols = [
        "instance_id", "id", "aud", "role", "email", "encrypted_password",
        "email_confirmed_at", "invited_at", "confirmation_token", "confirmation_sent_at",
        "recovery_token", "recovery_sent_at", "email_change_token_new", "email_change",
        "email_change_sent_at", "last_sign_in_at", "raw_app_meta_data", "raw_user_meta_data",
        "is_super_admin", "created_at", "updated_at", "phone", "phone_confirmed_at",
        "phone_change", "phone_change_token", "phone_change_sent_at",
        "email_change_token_current", "email_change_confirm_status", "banned_until",
        "reauthentication_token", "reauthentication_sent_at", "is_sso_user", "deleted_at", "is_anonymous"
    ]
    for u in users:
        vals = [sql_quote(u.get(c)) for c in user_cols]
        lines.append(f"INSERT INTO auth.users ({', '.join(user_cols)}) VALUES ({', '.join(vals)}) ON CONFLICT (id) DO NOTHING;")

    lines.append("")

    # 3. auth.identities
    with open(DATA_DIR / "auth_identities.json") as f:
        identities = json.load(f)
    identity_cols = ["id", "provider_id", "user_id", "identity_data", "provider", "last_sign_in_at", "created_at", "updated_at"]
    for i in identities:
        vals = [sql_quote(i.get(c)) for c in identity_cols]
        lines.append(f"INSERT INTO auth.identities ({', '.join(identity_cols)}) VALUES ({', '.join(vals)}) ON CONFLICT (id) DO NOTHING;")

    lines.append("")

    # 4. storage.objects
    with open(DATA_DIR / "storage_objects.json") as f:
        objects = json.load(f)
    object_cols = ["id", "bucket_id", "name", "owner", "created_at", "updated_at", "last_accessed_at", "metadata", "version", "owner_id", "user_metadata"]
    for o in objects:
        vals = [sql_quote(o.get(c)) for c in object_cols]
        lines.append(f"INSERT INTO storage.objects ({', '.join(object_cols)}) VALUES ({', '.join(vals)}) ON CONFLICT (id) DO NOTHING;")

    lines.append("")
    lines.append("SET session_replication_role = DEFAULT;")
    return "\n".join(lines)

def main():
    sql = generate_sql()
    out_file = DATA_DIR / "auth_and_storage_data.sql"
    out_file.write_text(sql)
    print(f"Generated SQL written to {out_file} ({len(sql)} bytes).")

    pg_password = os.environ.get("POSTGRES_PASSWORD")
    if not pg_password:
        raise RuntimeError(
            "POSTGRES_PASSWORD is not set. "
            "Export it from docker/supabase/.env or your .env file before running this script."
        )

    print("Executing in supabase-db container as supabase_admin...")
    env = os.environ.copy()
    proc = subprocess.run(
        ["docker", "exec", "-e", f"PGPASSWORD={pg_password}", "-i", "supabase-db", "psql", "-U", "supabase_admin", "-d", "postgres"],
        input=sql,
        text=True,
        capture_output=True
    )
    if proc.returncode != 0:
        print("STDERR:", proc.stderr)
        raise RuntimeError("SQL execution failed")
    print("Execution output:")
    print("\n".join(proc.stdout.strip().split("\n")[-10:]))
    print("Done importing auth and storage data!")

if __name__ == "__main__":
    main()
