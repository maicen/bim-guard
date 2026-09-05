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
        email: str = "",
    ) -> dict[str, Any]:
        """Return the caller's profile, creating it from Google's claims on first sign-in.

        ``email`` is stored alongside the profile (not just on ``auth.users``,
        which PostgREST does not expose) so organization admin screens can list
        members by email without a direct database query.
        """
        existing = self.get(user_id)
        if existing is not None:
            return existing
        return self._profiles.insert(
            {
                "id": user_id,
                "full_name": full_name,
                "avatar_url": avatar_url,
                "email": email,
            }
        )

    def update(self, user_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Merge *updates* into the caller's profile, provisioning it first if needed."""
        self.ensure_profile(user_id)
        self._profiles.update(updates=updates, pk_values=user_id)
        return self.get(user_id) or {}

    def get_many(self, user_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Return the profile rows for *user_ids*, keyed by id.

        A user with no profile row yet (never signed in, only invited) is
        simply absent from the result rather than an error.
        """
        return {uid: profile for uid in user_ids if (profile := self.get(uid)) is not None}

    def is_superadmin(self, user_id: str) -> bool:
        """Return whether *user_id* bypasses organization-membership checks entirely.

        Not reachable through :meth:`update` / ``PATCH /api/auth/profile`` --
        ``ProfileUpdateRequest`` has no such field, so this can only be set
        directly against the database (see
        ``supabase/migrations/20260905094121_organization_invites_and_superadmin.sql``).
        """
        profile = self.get(user_id)
        return bool(profile and profile.get("is_superadmin"))
