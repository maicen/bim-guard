"""One-off utility: dump every table exposed by PostgREST to JSON via the service-role key.

Used as a fallback DB backup path when direct Postgres/pooler credentials in .env
are unavailable or incorrect. Schema (DDL) is not captured here — it is already
versioned in supabase/migrations/. This captures data only.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

PAGE_SIZE = 1000

TABLES = [
    "model_enhancement_version_counters",
    "groups",
    "uploaded_files",
    "bcf_topics",
    "organization_invites",
    "rule_folders",
    "standards_by_project",
    "model_enhancement_lineage",
    "project_ruleset_bindings",
    "role_permissions",
    "client_documents",
    "report_artifacts",
    "rules",
    "llm_provider_instances",
    "bcf_viewpoints",
    "static_data_assets",
    "audit_log",
    "profiles",
    "memberships",
    "issue_history",
    "group_project_grants",
    "parsing_engine_instances",
    "github_repositories",
    "projects",
    "organization_project_grants",
    "organization_document_grants",
    "keep_alive",
    "document_pages",
    "scim_tokens",
    "rule_snapshots",
    "organizations",
    "rule_extraction_drafts",
    "project_ifc_files",
    "project_document_bindings",
    "documents",
    "bcf_comments",
    "document_nodes",
    "app_settings",
    "llm_task_model_assignments",
    "project_naming_config",
    "organization_ruleset_grants",
]

HEADERS = {
    "apikey": SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
    "Accept-Profile": "public",
}


def dump_table(client: httpx.Client, table: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        headers = {
            **HEADERS,
            "Range-Unit": "items",
            "Range": f"{offset}-{offset + PAGE_SIZE - 1}",
            "Prefer": "count=exact",
        }
        resp = client.get(
            f"{SUPABASE_URL}/rest/v1/{table}",
            params={"select": "*"},
            headers=headers,
        )
        if resp.status_code not in (200, 206):
            raise RuntimeError(f"{table}: HTTP {resp.status_code}: {resp.text[:500]}")
        batch = resp.json()
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(__file__).resolve().parent.parent / "data" / "backups" / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = {"timestamp": ts, "source": SUPABASE_URL, "tables": {}}

    with httpx.Client(timeout=60.0) as client:
        for table in TABLES:
            try:
                rows = dump_table(client, table)
            except Exception as exc:  # noqa: BLE001
                print(f"FAILED {table}: {exc}", file=sys.stderr)
                manifest["tables"][table] = {"error": str(exc)}
                continue
            (out_dir / f"{table}.json").write_text(json.dumps(rows, indent=2, default=str))
            manifest["tables"][table] = {"row_count": len(rows)}
            print(f"{table}: {len(rows)} rows")

    (out_dir / "_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\nDump written to {out_dir}")


if __name__ == "__main__":
    main()
