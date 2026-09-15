"""Bearer-token authentication for SCIM 2.0 provisioning requests.

Distinct from Supabase-JWT human auth (app.auth): each organization gets one
rotatable, hashed bearer token that an external IdP (Okta, Azure AD, ...)
presents on every /api/scim/v2/* request. The raw token is generated once at
mint time and never stored -- only its SHA-256 hash lives in
public.scim_tokens (see supabase/migrations/20260915104053_create_scim_tokens.sql).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any

from app.services.db_adapters import DatabaseAdapter

_TOKEN_PREFIX = "scim_"


class ScimTokenService:
    """Domain service for minting, verifying, and revoking SCIM bearer tokens."""

    def __init__(self, scim_tokens_repo: DatabaseAdapter):
        """Initialize service with a persistence repository adapter."""
        self._repo = scim_tokens_repo

    @staticmethod
    def _hash(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    def mint(self, organization_id: int) -> str:
        """Issue a fresh token for *organization_id*, replacing any existing one.

        Returns the raw token -- the only time it is ever available; only
        its hash is persisted. `scim_tokens.organization_id` is unique, so
        any prior row (active or revoked) is deleted first.
        """
        raw_token = f"{_TOKEN_PREFIX}{secrets.token_urlsafe(32)}"
        existing = self._any_row_for_org(organization_id)
        if existing is not None:
            self._repo.delete(existing["id"])
        self._repo.insert(
            {
                "organization_id": organization_id,
                "token_hash": self._hash(raw_token),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return raw_token

    def revoke(self, organization_id: int) -> None:
        """Revoke *organization_id*'s SCIM token, if it has an active one."""
        existing = self._any_row_for_org(organization_id)
        if existing is not None and not existing.get("revoked_at"):
            self._repo.update(
                updates={"revoked_at": datetime.now(timezone.utc).isoformat()},
                pk_values=existing["id"],
            )

    def status(self, organization_id: int) -> dict[str, Any] | None:
        """Return the token metadata (never the raw value) for *organization_id*, or None."""
        return self._any_row_for_org(organization_id)

    def authenticate(self, raw_token: str) -> int | None:
        """Return the organization_id a valid, unrevoked *raw_token* belongs to, else None."""
        token_hash = self._hash(raw_token)
        for row in self._repo.rows:
            if row.get("token_hash") == token_hash and not row.get("revoked_at"):
                self._repo.update(
                    updates={"last_used_at": datetime.now(timezone.utc).isoformat()},
                    pk_values=row["id"],
                )
                return row["organization_id"]
        return None

    def _any_row_for_org(self, organization_id: int) -> dict[str, Any] | None:
        rows = self._repo.rows_where("organization_id = ?", [organization_id])
        return rows[0] if rows else None
