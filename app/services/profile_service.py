"""User profile lookups — display identity and preferences for authenticated users.

``public.profiles`` is 1:1 with ``auth.users``: it holds what Supabase's
Google OAuth claims don't carry as editable state (a display name, avatar,
title, default organization, and free-form preferences), auto-provisioned
from Google's own claims on first sign-in.
"""

from __future__ import annotations

from typing import Any

from app.services.db_adapters import DatabaseAdapter


class ProfileService:
    """Domain service for per-user profile records."""

    def __init__(self, profiles_repo: DatabaseAdapter):
        """Initialize service with a persistence repository adapter."""
        self._profiles = profiles_repo

    def get(self, user_id: str) -> dict[str, Any] | None:
        """Return the profile row for *user_id*, or None if not provisioned yet."""
        return self._profiles.get(user_id)

    def ensure_profile(
        self,
        user_id: str,
        *,
        full_name: str = "",
        avatar_url: str = "",
    ) -> dict[str, Any]:
        """Return the caller's profile, creating it from Google's claims on first sign-in."""
        existing = self.get(user_id)
        if existing is not None:
            return existing
        return self._profiles.insert(
            {
                "id": user_id,
                "full_name": full_name,
                "avatar_url": avatar_url,
            }
        )

    def update(self, user_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Merge *updates* into the caller's profile, provisioning it first if needed."""
        self.ensure_profile(user_id)
        self._profiles.update(updates=updates, pk_values=user_id)
        return self.get(user_id) or {}
