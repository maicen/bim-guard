"""Create (or update) a confirmed Supabase Auth user for local development.

Local dev normally signs in via Google OAuth (see ``frontend/src/lib/auth.svelte.ts``),
which requires clicking through Google's consent screen every time the session
expires. This script uses the Supabase Admin API (service role key) to create a
real, email-confirmed user with a password, so a developer can instead sign in
with ``supabase.auth.signInWithPassword`` -- still a genuine Supabase session
verified the normal way by ``app/auth.py``, just without the OAuth round trip.

This never touches how the backend or frontend authenticate; it only seeds a
user credential. Run it once per environment:

    uv run python scripts/seed_dev_auth_user.py

Reads from the root ``.env``:
    SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY  (required)
    DEV_AUTH_EMAIL, DEV_AUTH_PASSWORD        (optional; sensible defaults below)
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

DEFAULT_EMAIL = "dev@bim-guard.local"
DEFAULT_PASSWORD = "bim-guard-dev-only"  # noqa: S105 - local dev fixture, not a real secret


def main() -> None:
    url = os.getenv("SUPABASE_URL", "").strip()
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not service_key:
        print("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env", file=sys.stderr)
        raise SystemExit(1)

    email = os.getenv("DEV_AUTH_EMAIL", DEFAULT_EMAIL).strip()
    password = os.getenv("DEV_AUTH_PASSWORD", DEFAULT_PASSWORD).strip()

    client = create_client(url, service_key)
    admin = client.auth.admin

    existing = next(
        (u for u in admin.list_users() if u.email == email),
        None,
    )
    if existing is not None:
        admin.update_user_by_id(existing.id, {"password": password, "email_confirm": True})
        print(f"Updated existing dev user: {email}")
        return

    admin.create_user(
        {
            "email": email,
            "password": password,
            "email_confirm": True,
        }
    )
    print(f"Created dev user: {email}")
    print("Add matching VITE_DEV_AUTH_EMAIL / VITE_DEV_AUTH_PASSWORD to frontend/.env")


if __name__ == "__main__":
    main()
