"""Persistence bootstrap utilities for Supabase tables."""

import os

from app.services.db_adapters import SupabaseTableAdapter
from supabase import create_client


class PersistenceService:
    """Centralize Supabase database bootstrap for route modules."""

    DB_BACKEND = "supabase"
    _db = None

    @classmethod
    def get_db(cls):
        """Return a singleton Supabase client."""
        if cls._db is not None:
            return cls._db

        url = os.getenv("SUPABASE_URL", "").strip()
        key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
            or os.getenv("SUPABASE_KEY", "").strip()
        )
        if not url:
            raise ValueError("SUPABASE_URL is required")
        if not key:
            raise ValueError("SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY is required")

        cls._db = create_client(url, key)
        return cls._db

    @classmethod
    def get_table(
        cls,
        table_name: str,
        schema: dict,
        pk: str = "id",
        required_columns: dict | None = None,
    ):
        """Create or migrate a table, then return the table handle."""
        db = cls.get_db()
        table = SupabaseTableAdapter(db, table_name, schema, pk=pk)
        for column_name, column_type in (required_columns or {}).items():
            table.add_column(column_name, column_type)
        return table
