#!/usr/bin/env python3
"""Migrate all storage artifacts from hosted Supabase to self-hosted Supabase."""

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "migration"
STORAGE_CACHE_DIR = DATA_DIR / "storage_artifacts"
STORAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

HOSTED_URL = os.environ.get("HOSTED_SUPABASE_URL", "https://pmisdhiigakpjfuyxgfb.supabase.co")
HOSTED_SERVICE_KEY = os.environ.get("HOSTED_SUPABASE_SERVICE_ROLE_KEY", os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""))

LOCAL_URL = os.environ.get("LOCAL_SUPABASE_URL", "http://localhost:54321")
LOCAL_SERVICE_KEY = os.environ.get("LOCAL_SUPABASE_SERVICE_ROLE_KEY", os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""))

BUCKET = "bim-guard-artifacts"

def migrate_single_object(obj: dict, client_hosted: httpx.Client, client_local: httpx.Client) -> tuple[str, bool, str]:
    name = obj["name"]
    version = obj.get("version")
    content_type = obj.get("metadata", {}).get("mimetype", "application/octet-stream")
    expected_size = obj.get("metadata", {}).get("size")

    # Local backup file
    local_backup_path = STORAGE_CACHE_DIR / name
    local_backup_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Download if not locally cached
    content = None
    if local_backup_path.exists() and (expected_size is None or local_backup_path.stat().st_size == expected_size):
        content = local_backup_path.read_bytes()
    else:
        download_url = f"{HOSTED_URL}/storage/v1/object/authenticated/{BUCKET}/{name}"
        headers_down = {
            "Authorization": f"Bearer {HOSTED_SERVICE_KEY}",
            "apikey": HOSTED_SERVICE_KEY,
        }
        for attempt in range(3):
            try:
                resp = client_hosted.get(download_url, headers=headers_down, timeout=60.0)
                if resp.status_code == 200:
                    content = resp.content
                    local_backup_path.write_bytes(content)
                    break
                elif resp.status_code == 404:
                    return name, False, "404 Not Found on hosted Supabase"
                else:
                    time.sleep(1.0)
            except Exception as e:
                if attempt == 2:
                    return name, False, f"Download error: {e}"
                time.sleep(1.0)

    if content is None:
        return name, False, "Failed to retrieve content"

    # 2. Upload to self-hosted Supabase Storage API
    upload_url = f"{LOCAL_URL}/storage/v1/object/{BUCKET}/{name}"
    headers_up = {
        "Authorization": f"Bearer {LOCAL_SERVICE_KEY}",
        "apikey": LOCAL_SERVICE_KEY,
        "x-upsert": "true",
        "Content-Type": content_type or "application/octet-stream"
    }

    for attempt in range(3):
        try:
            resp_up = client_local.post(upload_url, headers=headers_up, content=content, timeout=120.0)
            if resp_up.status_code in (200, 201):
                return name, True, f"Migrated ({len(content)} bytes)"
            else:
                if attempt == 2:
                    return name, False, f"Upload status {resp_up.status_code}: {resp_up.text}"
                time.sleep(1.0)
        except Exception as e:
            if attempt == 2:
                return name, False, f"Upload error: {e}"
            time.sleep(1.0)

    return name, False, "Unknown failure"

def main():
    objects_file = DATA_DIR / "storage_objects.json"
    with open(objects_file) as f:
        objects = json.load(f)

    print(f"Starting migration of {len(objects)} storage objects...")
    success_count = 0
    fail_count = 0

    with httpx.Client() as client_hosted, httpx.Client() as client_local:
        with ThreadPoolExecutor(max_workers=6) as executor:
            future_to_obj = {
                executor.submit(migrate_single_object, obj, client_hosted, client_local): obj
                for obj in objects
            }
            for i, future in enumerate(as_completed(future_to_obj), 1):
                name, success, msg = future.result()
                if success:
                    success_count += 1
                    if i % 20 == 0 or i == len(objects):
                        print(f"[{i}/{len(objects)}] {name} -> {msg}")
                else:
                    fail_count += 1
                    print(f"FAILED [{i}/{len(objects)}] {name}: {msg}")

    print(f"\nMigration completed: {success_count} succeeded, {fail_count} failed out of {len(objects)}.")
    if fail_count > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
