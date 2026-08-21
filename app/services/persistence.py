"""Persistence bootstrap utilities for Supabase tables."""

import os
from typing import Any

from app.services.db_adapters import SupabaseTableAdapter
from app.utils import load_env_file
from supabase import create_client

load_env_file()


class _MemoryResult:
    """Simple response object for in-memory table queries."""

    def __init__(self, data: list[dict[str, Any]] | None = None):
        self.data = data or []


class _MemoryQuery:
    """Minimal query-object compatible with SupabaseTableAdapter."""

    def __init__(self, client: "_MemoryClient", table_name: str):
        self._client = client
        self._table_name = table_name
        self._select_cols: list[str] | None = None
        self._filters: list[tuple[str, str, Any]] = []
        self._range_start: int | None = None
        self._range_end: int | None = None
        self._limit: int | None = None
        self._order_by: tuple[str, bool] | None = None

    def select(self, *cols: str):
        self._select_cols = list(cols)
        return self

    def eq(self, field: str, value: Any):
        self._filters.append((field, "eq", value))
        return self

    def ilike(self, field: str, value: Any):
        self._filters.append((field, "ilike", str(value)))
        return self

    def order(self, field: str, desc: bool = False):
        self._order_by = (field, bool(desc))
        return self

    def limit(self, n: int):
        self._limit = n
        return self

    def range(self, start: int, end: int):
        self._range_start = start
        self._range_end = end
        return self

    def execute(self):
        rows = list(self._client._tables.get(self._table_name, []))
        for field, op, value in self._filters:
            filtered = []
            for row in rows:
                current = row.get(field)
                if op == "eq" and current == value:
                    filtered.append(row)
                elif op == "ilike":
                    pattern = str(value).lower().replace("%", "")
                    row_value = str(current or "").lower()
                    if pattern in row_value:
                        filtered.append(row)
            rows = filtered

        if self._order_by is not None:
            sort_field, descending = self._order_by
            rows = sorted(rows, key=lambda row: str(row.get(sort_field) or ""), reverse=descending)

        if self._range_start is not None and self._range_end is not None:
            rows = rows[self._range_start : self._range_end + 1]

        if self._limit is not None:
            rows = rows[: self._limit]

        if self._select_cols is not None and self._select_cols != ["*"]:
            rows = [{key: row.get(key) for key in self._select_cols if key in row} for row in rows]

        return _MemoryResult(rows)


class _MemoryTable:
    """Minimal table implementation for offline runtime operations."""

    def __init__(self, client: "_MemoryClient", table_name: str):
        self._client = client
        self._table_name = table_name

    def select(self, *cols: str):
        return _MemoryQuery(self._client, self._table_name).select(*cols)

    def insert(self, payload: dict[str, Any]):
        rows = self._client._tables.setdefault(self._table_name, [])
        rows.append(dict(payload))
        return payload

    def update(self, updates: dict[str, Any]):
        return _MemoryQueryWithMutation(self._client, self._table_name, updates=updates)

    def delete(self):
        return _MemoryQueryWithMutation(self._client, self._table_name, updates={})

    def eq(self, field: str, value: Any):
        return _MemoryQueryWithMutation(self._client, self._table_name).eq(field, value)

    def __getattr__(self, name: str):
        if name in {"rows", "rows_where"}:
            raise AttributeError(name)
        raise AttributeError(f"{self.__class__.__name__} has no attribute {name}")


class _MemoryQueryWithMutation(_MemoryQuery):
    """Query object that can apply updates and deletes."""

    def __init__(self, client: "_MemoryClient", table_name: str, *, updates: dict[str, Any] | None = None):
        super().__init__(client, table_name)
        self._updates = updates or {}

    def update(self, updates: dict[str, Any]):
        self._updates.update(updates)
        return self

    def delete(self):
        self._delete = True
        return self

    def execute(self):
        rows = list(self._client._tables.get(self._table_name, []))
        for field, op, value in self._filters:
            filtered = []
            for row in rows:
                current = row.get(field)
                if op == "eq" and current == value:
                    filtered.append(row)
                elif op == "ilike":
                    if str(value).lower().replace("%", "") in str(current or "").lower():
                        filtered.append(row)
            rows = filtered

        if getattr(self, "_delete", False):
            self._client._tables[self._table_name] = [
                row for row in self._client._tables.get(self._table_name, []) if row not in rows
            ]
            return _MemoryResult([])

        for row in rows:
            row.update(self._updates)

        return _MemoryResult(rows)


class _MemoryClient:
    """Fallback client used when Supabase credentials are absent."""

    def __init__(self):
        self._tables: dict[str, list[dict[str, Any]]] = {}

    def table(self, table_name: str):
        return _MemoryTable(self, table_name)


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
        if not url or not key:
            cls._db = _MemoryClient()
            return cls._db

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
