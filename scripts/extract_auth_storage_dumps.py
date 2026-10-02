#!/usr/bin/env python3
"""Export and format auth & storage data for self-hosted Supabase migration."""

import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "migration"
DATA_DIR.mkdir(parents=True, exist_ok=True)

def parse_step(path: str):
    with open(path) as f:
        data = json.load(f)
    txt = data["result"]
    m = re.search(r"<untrusted-data-[^>]+>\s*(\[.*?\])\s*</untrusted-data-[^>]+>", txt, re.DOTALL)
    if not m:
        raise ValueError(f"No untrusted-data match in {path}")
    parsed = json.loads(m.group(1))
    return parsed[0]["json_agg"]

def main():
    users = parse_step("/Users/sam/.gemini/antigravity-ide/brain/ab39f3fb-6e1a-45f7-9e6c-ae4e00955651/.system_generated/steps/431/output.txt")
    identities = parse_step("/Users/sam/.gemini/antigravity-ide/brain/ab39f3fb-6e1a-45f7-9e6c-ae4e00955651/.system_generated/steps/435/output.txt")
    objects = parse_step("/Users/sam/.gemini/antigravity-ide/brain/ab39f3fb-6e1a-45f7-9e6c-ae4e00955651/.system_generated/steps/437/output.txt")
    buckets = [{
        "id": "bim-guard-artifacts",
        "name": "bim-guard-artifacts",
        "owner": None,
        "created_at": "2026-05-02 14:30:28.164902+00",
        "updated_at": "2026-05-02 14:30:28.164902+00",
        "public": False,
        "avif_autodetection": False,
        "file_size_limit": None,
        "allowed_mime_types": None,
        "owner_id": None
    }]

    with open(DATA_DIR / "auth_users.json", "w") as f:
        json.dump(users, f, indent=2)
    with open(DATA_DIR / "auth_identities.json", "w") as f:
        json.dump(identities, f, indent=2)
    with open(DATA_DIR / "storage_buckets.json", "w") as f:
        json.dump(buckets, f, indent=2)
    with open(DATA_DIR / "storage_objects.json", "w") as f:
        json.dump(objects, f, indent=2)

    print(f"Saved {len(users)} users, {len(identities)} identities, {len(buckets)} buckets, {len(objects)} objects to {DATA_DIR}.")

if __name__ == "__main__":
    main()
