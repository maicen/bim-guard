"""Supabase Auth account management — a superadmin-only capability.

Deleting a user's ``auth.users`` row goes through the Supabase Admin Auth
API rather than a table adapter: PostgREST's ``service_role`` grants only
reach ``public.*`` tables, not the ``auth`` schema. Once deleted, the row's
dependents in ``public.profiles`` and ``public.memberships`` cascade
automatically (both FK ``on delete cascade`` to ``auth.users`` -- see
``supabase/migrations/20260905091058_create_profiles.sql`` and
``20260904235344_create_organizations_and_memberships.sql``).
"""

from __future__ import annotations

from typing import Any


class UserAdminService:
    """Thin wrapper around the Supabase Admin Auth API."""

    def __init__(self, client: Any):
        """Initialize with the service-role Supabase client."""
        self._client = client

    def delete_user(self, user_id: str) -> None:
        """Permanently delete a user's Supabase Auth account."""
        self._client.auth.admin.delete_user(user_id)
