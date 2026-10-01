"""Database adapters exposing a table API backed by Supabase."""

from __future__ import annotations

import abc
import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Callable

from httpx import TransportError
from postgrest.exceptions import APIError

from app.logging_config import get_logger
from app.services.cache import adapter_cache_service

logger = get_logger(__name__)

_RETRY_ATTEMPTS = 3
_RETRY_BASE_DELAY_S = 0.2


def execute_with_retry(build_query: Callable[[], Any], *, attempts: int = _RETRY_ATTEMPTS) -> Any:
    """Execute a PostgREST query, retrying transient transport failures.

    Supabase's pooled HTTP/2 connections can go stale between requests and the
    next call fails with ``httpx.RemoteProtocolError: Server disconnected``.
    The query is rebuilt on every attempt so each retry acquires a fresh
    connection instead of reusing the dead one.
    """
    for attempt in range(attempts):
        try:
            return build_query().execute()
        except TransportError:
            if attempt == attempts - 1:
                raise
            time.sleep(_RETRY_BASE_DELAY_S * (2**attempt))


@dataclass(slots=True)
class _WhereExpr:
    """Normalized where-expression model for adapter filtering."""

    field: str
    operator: str
    value: Any


def parse_where(where_sql: str, params: list[Any] | None = None) -> _WhereExpr:
    """Parse a restricted SQL-like predicate used by existing services."""
    where = where_sql.strip()
    args = params or []

    if where.upper().endswith(" IS NULL"):
        field = where[:-8].strip()
        return _WhereExpr(field=field, operator="is_null", value=None)

    if " LIKE ?" in where:
        field = where.split(" LIKE ?", 1)[0].strip()
        pattern = str(args[0]) if args else ""
        return _WhereExpr(field=field, operator="like", value=pattern)

    if " = ?" in where:
        field = where.split(" = ?", 1)[0].strip()
        value = args[0] if args else None
        return _WhereExpr(field=field, operator="eq", value=value)

    if " = '" in where and where.endswith("'"):
        field, literal = where.split(" = '", 1)
        value = literal[:-1]
        return _WhereExpr(field=field.strip(), operator="eq", value=value)

    if " = " in where:
        field, literal = where.split(" = ", 1)
        value: Any = literal.strip()
        if str(value).isdigit():
            value = int(value)
        return _WhereExpr(field=field.strip(), operator="eq", value=value)

    raise ValueError(f"Unsupported where expression: {where_sql}")


class DatabaseAdapter(abc.ABC):
    """Abstract base repository adapter for standard database operations."""

    @property
    @abc.abstractmethod
    def columns_dict(self) -> dict[str, Any]:
        """Return declared columns map."""

    @property
    @abc.abstractmethod
    def rows(self) -> Iterable[dict[str, Any]]:
        """Return all rows."""

    @abc.abstractmethod
    def get(self, pk_value: Any) -> dict[str, Any] | None:
        """Get row by primary key."""

    @abc.abstractmethod
    def insert(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Insert row into repository."""

    def insert_many(self, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Insert multiple rows. Default: one insert per row; adapters may override."""
        return [self.insert(payload) for payload in payloads]

    @abc.abstractmethod
    def update(
        self,
        updates_or_row: dict[str, Any] | None = None,
        pk: Any = None,
        *,
        updates: dict[str, Any] | None = None,
        pk_values: Any = None,
    ) -> None:
        """Update row by primary key."""

    @abc.abstractmethod
    def delete(self, pk_value: Any) -> None:
        """Delete row by primary key."""

    def delete_many(self, pk_values: list[Any]) -> None:
        """Delete multiple rows by primary key. Default: one delete per pk; adapters may override."""
        for pk in pk_values:
            self.delete(pk)

    def select_projected(self, columns: list[str]) -> list[dict[str, Any]]:
        """Return all rows projected to a subset of columns."""
        return [{col: r.get(col) for col in columns if col in r} for r in self.rows]

    @abc.abstractmethod
    def rows_where(
        self,
        where_sql: str,
        params: list[Any] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Query rows matching predicate."""

    def update_where(
        self,
        *,
        updates: dict[str, Any],
        where_sql: str,
        params: list[Any] | None = None,
    ) -> None:
        """Update rows matching predicate."""
        for row in self.rows_where(where_sql, params):
            pk_col = getattr(self, "_pk", "id")
            pk_val = row.get(pk_col) if pk_col in row else row.get("id")
            if pk_val is not None:
                self.update(updates=updates, pk_values=pk_val)

    def save_report(self, report_data: dict[str, Any]) -> dict[str, Any]:
        """Persist a compliance report entity."""
        return self.insert(report_data)


class InMemoryTableAdapter(DatabaseAdapter):
    """Expose an in-memory table implementing the DatabaseAdapter interface.

    Used for isolated test seams and offline harnesses — Supabase (PostgreSQL)
    remains the sole runtime database backend for the live app.
    """

    def __init__(
        self,
        table_or_name: Any = "memory_table",
        schema: dict[str, Any] | None = None,
        *,
        pk: str = "id",
        table_name: str | None = None,
    ) -> None:
        raw_name = table_name if table_name is not None else table_or_name
        self._table_name = getattr(raw_name, "name", str(raw_name))
        self._columns_dict: dict[str, Any] = dict(schema or {})
        self._pk = pk
        self._rows: list[dict[str, Any]] = []

    def _format_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Ensure all declared schema columns are present on returned rows (defaulting to None)."""
        formatted = {col: None for col in self._columns_dict}
        formatted.update(row)
        return formatted

    @property
    def columns_dict(self) -> dict[str, Any]:
        """Return declared columns map."""
        return self._columns_dict

    @property
    def rows(self) -> Iterable[dict[str, Any]]:
        """Return all rows."""
        return [self._format_row(r) for r in self._rows]

    @property
    def pks(self) -> list[str]:
        """Return primary keys list."""
        return [self._pk]

    def create(self, schema: dict[str, Any], *, pk: str, if_not_exists: bool = True) -> None:
        """Create or update table schema."""
        self._columns_dict.update(schema)
        self._pk = pk

    def add_column(self, column_name: str, column_type: Any) -> None:
        """Add column to schema."""
        self._columns_dict[column_name] = column_type

    def get(self, pk_value: Any) -> dict[str, Any] | None:
        """Get one row by primary key."""
        target = str(pk_value)
        for r in self._rows:
            if str(r.get(self._pk)) == target:
                return self._format_row(r)
        return None

    def insert(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Insert one row."""
        row = dict(payload)
        if self._pk not in row or row[self._pk] is None:
            max_id = max(
                (int(r[self._pk]) for r in self._rows if str(r.get(self._pk, "")).isdigit()),
                default=0,
            )
            row[self._pk] = max_id + 1
        self._rows.append(row)
        return self._format_row(row)

    def insert_many(self, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Insert multiple rows in a batch."""
        return [self.insert(p) for p in payloads]

    def update(
        self,
        updates_or_row: dict[str, Any] | None = None,
        pk: Any = None,
        *,
        updates: dict[str, Any] | None = None,
        pk_values: Any = None,
    ) -> None:
        """Update one row by primary key."""
        target_updates = dict(updates if updates is not None else (updates_or_row or {}))
        target_pk = pk_values if pk_values is not None else pk
        if target_pk is None and self._pk in target_updates:
            target_pk = target_updates[self._pk]
        target_payload = {k: v for k, v in target_updates.items() if k != self._pk}
        target_str = str(target_pk) if target_pk is not None else None
        for row in self._rows:
            if str(row.get(self._pk)) == target_str:
                row.update(target_payload)

    def delete(self, pk_value: Any) -> None:
        """Delete one row by primary key."""
        target_str = str(pk_value)
        self._rows = [r for r in self._rows if str(r.get(self._pk)) != target_str]

    def delete_many(self, pk_values: list[Any]) -> None:
        """Delete multiple rows by primary key in a single batch."""
        if not pk_values:
            return
        target_strs = {str(pk) for pk in pk_values}
        self._rows = [r for r in self._rows if str(r.get(self._pk)) not in target_strs]

    def rows_where(
        self,
        where_sql: str,
        params: list[Any] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Filter rows matching predicate."""
        expr = parse_where(where_sql, params)
        matching: list[dict[str, Any]] = []
        for raw_row in self._rows:
            row = self._format_row(raw_row)
            val = row.get(expr.field)
            if expr.operator == "is_null" and val is None:
                matching.append(dict(row))
            elif expr.operator == "eq" and (val == expr.value or str(val) == str(expr.value)):
                matching.append(dict(row))
            elif expr.operator == "like" and str(expr.value).lower().replace("%", "") in str(val or "").lower():
                matching.append(dict(row))
        return matching[:limit] if limit is not None else matching


class InMemoryDatabase:
    """In-memory database holding isolated InMemoryTableAdapters by name."""

    def __init__(self) -> None:
        self._tables: dict[str, InMemoryTableAdapter] = {}

    def __getitem__(self, table_name: str) -> InMemoryTableAdapter:
        if table_name not in self._tables:
            self._tables[table_name] = InMemoryTableAdapter(table_name=table_name)
        return self._tables[table_name]

    @property
    def t(self) -> InMemoryDatabase:
        return self

    def __getattr__(self, name: str) -> InMemoryTableAdapter:
        return self[name]


# Backward-compatibility alias
SQLiteTableAdapter = InMemoryTableAdapter


_SHARED_MEMORY_TABLES: dict[str, list[dict[str, Any]]] = {}
_USE_MEMORY_FALLBACK_TABLES: set[str] = set()


class SupabaseTableAdapter(DatabaseAdapter):
    """Table adapter backed by Supabase PostgREST queries with missing table fallback."""

    def __init__(
        self,
        client: Any,
        table_name: str,
        schema: dict[str, Any],
        *,
        pk: str,
    ):
        """Initialize Supabase table adapter metadata."""
        self._client = client
        self._table_name = table_name
        self._pk = pk
        self._columns_dict = dict(schema)
        self._memory_rows: list[dict[str, Any]] = _SHARED_MEMORY_TABLES.setdefault(table_name, [])

    @property
    def _use_memory_fallback(self) -> bool:
        return self._table_name in _USE_MEMORY_FALLBACK_TABLES

    @_use_memory_fallback.setter
    def _use_memory_fallback(self, value: bool) -> None:
        if value:
            _USE_MEMORY_FALLBACK_TABLES.add(self._table_name)
        else:
            _USE_MEMORY_FALLBACK_TABLES.discard(self._table_name)

    def _degrade_to_memory(self, operation: str, exc: Exception) -> None:
        """Switch this table to the in-process memory copy, and say so.

        The switch is module-level and nothing clears it, so from here until the
        process exits every read of the table returns the memory rows (usually
        none) and every write lands only in this process. It used to happen
        silently; a run scored from a table in this state could not be told
        apart from one scored from the database. Logged once per table, on the
        transition, because the condition is permanent rather than per call.
        """
        if not self._use_memory_fallback:
            logger.warning(
                "Table degraded to in-process memory table=%s operation=%s "
                "error_code=%s error=%s; results from this table are no longer "
                "authoritative for the rest of this process",
                self._table_name,
                operation,
                getattr(exc, "code", None),
                exc,
            )
        self._use_memory_fallback = True

    @property
    def columns_dict(self) -> dict[str, Any]:
        """Return known columns from declared schema."""
        return self._columns_dict

    @property
    def rows(self) -> list[dict[str, Any]]:
        """Return all table rows."""
        return self._select_all()

    def create(self, schema: dict[str, Any], *, pk: str, if_not_exists: bool = True) -> None:
        """No-op for Supabase; schema is managed outside runtime."""
        self._columns_dict.update(schema)

    def add_column(self, column_name: str, column_type: Any) -> None:
        """No-op for Supabase runtime; tracks declared columns only."""
        self._columns_dict[column_name] = column_type

    def get(self, pk_value: Any) -> dict[str, Any] | None:
        """Get one row by primary key."""
        if self._use_memory_fallback:
            return next(
                (r for r in self._memory_rows if r.get(self._pk) == pk_value or str(r.get(self._pk)) == str(pk_value)),
                None,
            )

        cache_key = self._cache_key("get", pk_value)
        cached = adapter_cache_service.get(cache_key)
        if cached is not None:
            return cached[0] if cached else None

        try:
            response = execute_with_retry(
                lambda: self._client.table(self._table_name)
                .select("*")
                .eq(self._pk, pk_value)
                .limit(1)
            )
            rows = response.data or []
            adapter_cache_service.set(cache_key, rows)
            return rows[0] if rows else None
        except APIError as exc:
            if self._is_missing_table_error(exc):
                self._degrade_to_memory("get", exc)
                return self.get(pk_value)
            raise

    def insert(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Insert one row and return inserted payload from API."""
        if self._use_memory_fallback:
            row = dict(payload)
            if self._pk not in row:
                row[self._pk] = max((int(r.get(self._pk, 0)) for r in self._memory_rows), default=0) + 1
            self._memory_rows.append(row)
            return dict(row)

        try:
            response = execute_with_retry(
                lambda: self._client.table(self._table_name).insert(payload)
            )
            rows = response.data or []
            self._invalidate_cache()
            return rows[0] if rows else payload
        except APIError as exc:
            if self._is_missing_table_error(exc) or getattr(exc, "code", None) == "23503":
                self._degrade_to_memory("insert", exc)
                return self.insert(payload)
            if self._should_retry_insert_with_pk(exc, payload):
                return self._insert_with_next_pk(payload, exc)
            raise

    def _insert_with_next_pk(self, payload: dict[str, Any], exc: APIError, attempts: int = 5) -> dict[str, Any]:
        """Retry an insert with an explicit PK, re-reading max(id) on each collision.

        PostgREST offers no row locking, so two concurrent fallback inserts can
        still compute the same "next" id and collide with each other -- this
        bounds that race to a few retries instead of failing (or silently
        colliding) on the first one.
        """
        last_exc = exc
        for _ in range(attempts):
            retry_payload = dict(payload)
            retry_payload[self._pk] = self._next_numeric_pk()
            try:
                response = execute_with_retry(
                    lambda retry_payload=retry_payload: self._client.table(self._table_name).insert(retry_payload)
                )
                rows = response.data or []
                self._invalidate_cache()
                return rows[0] if rows else retry_payload
            except APIError as retry_exc:
                if not self._should_retry_insert_with_pk(retry_exc, payload):
                    raise
                last_exc = retry_exc
        raise last_exc

    def insert_many(self, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Insert multiple rows in as few PostgREST round-trips as possible.

        Batches into chunks (rather than one INSERT per row) so bulk-import
        flows don't turn into hundreds/thousands of individual DB calls.
        """
        if not payloads:
            return []
        if self._use_memory_fallback:
            return [self.insert(payload) for payload in payloads]

        chunk_size = 500
        inserted: list[dict[str, Any]] = []
        try:
            for start in range(0, len(payloads), chunk_size):
                chunk = payloads[start : start + chunk_size]
                response = execute_with_retry(
                    lambda chunk=chunk: self._client.table(self._table_name).insert(chunk)
                )
                inserted.extend(response.data or [])
            self._invalidate_cache()
            return inserted
        except APIError as exc:
            if self._is_missing_table_error(exc):
                self._degrade_to_memory("insert_many", exc)
                return [self.insert(payload) for payload in payloads]
            raise

    def update(
        self,
        updates_or_row: dict[str, Any] | None = None,
        pk: Any = None,
        *,
        updates: dict[str, Any] | None = None,
        pk_values: Any = None,
    ) -> None:
        """Update one row by primary key."""
        target_updates = dict(updates if updates is not None else (updates_or_row or {}))
        target_pk = pk_values if pk_values is not None else pk
        if target_pk is None and self._pk in target_updates:
            target_pk = target_updates[self._pk]

        target_payload = {k: v for k, v in target_updates.items() if k != self._pk}

        if self._use_memory_fallback:
            for row in self._memory_rows:
                if row.get(self._pk) == target_pk or str(row.get(self._pk)) == str(target_pk):
                    row.update(target_payload)
            return

        try:
            execute_with_retry(
                lambda: self._client.table(self._table_name).update(target_payload).eq(self._pk, target_pk)
            )
            self._invalidate_cache()
        except APIError as exc:
            if self._is_missing_table_error(exc):
                self._degrade_to_memory("update", exc)
                self.update(updates=target_payload, pk_values=target_pk)
                return
            raise

    def delete(self, pk_value: Any) -> None:
        """Delete one row by primary key."""
        if self._use_memory_fallback:
            self._memory_rows[:] = [
                r for r in self._memory_rows
                if not (r.get(self._pk) == pk_value or str(r.get(self._pk)) == str(pk_value))
            ]
            return

        try:
            execute_with_retry(
                lambda: self._client.table(self._table_name).delete().eq(self._pk, pk_value)
            )
            self._invalidate_cache()
        except APIError as exc:
            if self._is_missing_table_error(exc):
                self._degrade_to_memory("delete", exc)
                self.delete(pk_value)
                return
            raise

    def delete_many(self, pk_values: list[Any]) -> None:
        """Delete multiple rows by primary key in batched PostgREST calls."""
        if not pk_values:
            return
        if self._use_memory_fallback:
            pk_set = set(pk_values)
            pk_str_set = {str(pk) for pk in pk_values}
            self._memory_rows[:] = [
                r for r in self._memory_rows
                if not (r.get(self._pk) in pk_set or str(r.get(self._pk)) in pk_str_set)
            ]
            return

        chunk_size = 500
        try:
            for start in range(0, len(pk_values), chunk_size):
                chunk = pk_values[start : start + chunk_size]
                execute_with_retry(
                    lambda chunk=chunk: self._client.table(self._table_name).delete().in_(self._pk, chunk)
                )
            self._invalidate_cache()
        except APIError as exc:
            if self._is_missing_table_error(exc):
                self._degrade_to_memory("delete_many", exc)
                pk_set = set(pk_values)
                pk_str_set = {str(pk) for pk in pk_values}
                self._memory_rows[:] = [
                    r for r in self._memory_rows
                    if not (r.get(self._pk) in pk_set or str(r.get(self._pk)) in pk_str_set)
                ]
                return
            raise

    def rows_where(
        self,
        where_sql: str,
        params: list[Any] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Filter rows using a restricted SQL-like predicate subset."""
        if self._use_memory_fallback:
            expr = parse_where(where_sql, params)
            matching = []
            for row in self._memory_rows:
                val = row.get(expr.field)
                if expr.operator == "is_null" and val is None:
                    matching.append(row)
                elif expr.operator == "eq" and (val == expr.value or str(val) == str(expr.value)):
                    matching.append(row)
                elif expr.operator == "like" and str(expr.value).lower().replace("%", "") in str(val or "").lower():
                    matching.append(row)
            return matching[:limit] if limit is not None else matching

        expr = parse_where(where_sql, params)
        cache_key = self._cache_key("where", expr.field, expr.operator, expr.value, limit)
        cached = adapter_cache_service.get(cache_key)
        if cached is not None:
            return list(cached)

        try:
            rows = self._select_filtered(expr, limit=limit)
            result = rows[:limit] if limit is not None else rows
            adapter_cache_service.set(cache_key, result)
            return result
        except APIError as exc:
            if self._is_missing_table_error(exc):
                self._degrade_to_memory("rows_where", exc)
                return self.rows_where(where_sql, params, limit)
            raise

    def _select_all(self) -> list[dict[str, Any]]:
        """Select all rows using paginated range queries, short-TTL cached."""
        if self._use_memory_fallback:
            return list(self._memory_rows)

        cache_key = self._cache_key("all")
        cached = adapter_cache_service.get(cache_key)
        if cached is not None:
            return list(cached)

        try:
            rows = self._run_select(limit=None, expr=None)
            adapter_cache_service.set(cache_key, rows)
            return rows
        except APIError as exc:
            if self._is_missing_table_error(exc):
                self._degrade_to_memory("select_all", exc)
                return list(self._memory_rows)
            raise

    def _select_filtered(self, expr: _WhereExpr, limit: int | None) -> list[dict[str, Any]]:
        """Select rows matching the expression using paginated queries."""
        return self._run_select(limit=limit, expr=expr)

    def _cache_key(self, op: str, *parts: Any) -> str:
        """Build a cache key scoped to this table and read operation."""
        suffix = ":".join(str(p) for p in parts)
        return f"adapter:{self._table_name}:{op}:{suffix}" if suffix else f"adapter:{self._table_name}:{op}"

    def _invalidate_cache(self) -> None:
        """Evict every cached read for this table after a write."""
        adapter_cache_service.invalidate(f"adapter:{self._table_name}:")

    def select_projected(self, columns: list[str]) -> list[dict[str, Any]]:
        """Select all rows projected to a subset of columns, avoiding large text TOAST retrieval."""
        if self._use_memory_fallback:
            return [{col: r.get(col) for col in columns if col in r} for r in self._memory_rows]

        cols_key = ",".join(sorted(columns))
        cache_key = self._cache_key("projected", cols_key)
        cached = adapter_cache_service.get(cache_key)
        if cached is not None:
            return list(cached)

        try:
            rows = self._run_select(limit=None, expr=None, columns=columns)
            adapter_cache_service.set(cache_key, rows)
            return rows
        except Exception:
            return [{col: r.get(col) for col in columns if col in r} for r in self.rows]

    def _run_select(
        self,
        *,
        limit: int | None,
        expr: _WhereExpr | None,
        columns: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute paginated select queries and collect all rows."""
        page_size = 1000
        offset = 0
        collected: list[dict[str, Any]] = []
        select_cols = ", ".join(columns) if columns else "*"

        while True:
            remaining = page_size
            if limit is not None:
                remaining = min(remaining, limit - len(collected))
                if remaining <= 0:
                    break

            def _build(offset=offset, remaining=remaining):
                query = self._client.table(self._table_name).select(select_cols)
                if expr is not None:
                    query = self._apply_expr(query, expr)
                # Range-based pagination is only stable across multiple calls
                # when the result set has a fixed order; without this, a
                # concurrent write can shift a row between pages and the same
                # row comes back twice (or a row gets skipped entirely).
                return query.order(self._pk).range(offset, offset + remaining - 1)

            response = execute_with_retry(_build)
            rows = response.data or []
            collected.extend(rows)

            if len(rows) < remaining:
                break

            offset += remaining

        return collected

    @staticmethod
    def _is_missing_table_error(exc: APIError) -> bool:
        """Return True when an APIError indicates the table does not exist in schema cache."""
        code = str(getattr(exc, "code", "") or "")
        msg = str(getattr(exc, "message", "") or getattr(exc, "details", "") or "").lower()
        # PGRST204 / 42703 indicate a missing or unrecognized column in the schema cache,
        # which must never degrade the entire table into ephemeral in-process memory.
        if code in {"PGRST204", "42703"} or "column" in msg:
            return False
        return (
            code in {"PGRST205", "42P01"}
            or ("table" in msg and "schema cache" in msg)
            or ("relation" in msg and "does not exist" in msg)
        )


    def _should_retry_insert_with_pk(self, exc: APIError, payload: dict[str, Any]) -> bool:
        """Return True when an insert failed due to duplicate primary key without explicit PK."""
        if self._pk in payload:
            return False

        code = str(getattr(exc, "code", "") or "")
        details = str(getattr(exc, "details", "") or "")
        return code == "23505" and f"Key ({self._pk})=(" in details

    def _next_numeric_pk(self) -> int:
        """Compute the next integer primary key value for fallback inserts."""
        response = execute_with_retry(
            lambda: self._client.table(self._table_name)
            .select(self._pk)
            .order(self._pk, desc=True)
            .limit(1)
        )
        rows = response.data or []
        if not rows:
            return 1

        current = rows[0].get(self._pk)
        try:
            return int(current) + 1
        except (TypeError, ValueError):
            return 1

    def update_where(
        self,
        *,
        updates: dict[str, Any],
        where_sql: str,
        params: list[Any] | None = None,
    ) -> None:
        """Update rows matching predicate in Supabase or fallback memory."""
        if self._use_memory_fallback:
            expr = parse_where(where_sql, params)
            for row in self._memory_rows:
                val = row.get(expr.field)
                if (expr.operator == "is_null" and val is None) or (
                    expr.operator == "eq" and (val == expr.value or str(val) == str(expr.value))
                ):
                    row.update(updates)
            return

        expr = parse_where(where_sql, params)
        try:
            execute_with_retry(
                lambda: self._apply_expr(self._client.table(self._table_name).update(updates), expr)
            )
            self._invalidate_cache()
        except APIError as exc:
            if self._is_missing_table_error(exc):
                self._degrade_to_memory("update_where", exc)
                self.update_where(updates=updates, where_sql=where_sql, params=params)
                return
            raise

    @staticmethod
    def _apply_expr(query: Any, expr: _WhereExpr) -> Any:
        """Apply parsed filter expression to a Supabase query."""
        if expr.operator == "is_null":
            return query.is_(expr.field, "null")

        if expr.operator == "eq":
            return query.eq(expr.field, expr.value)

        if expr.operator == "like":
            pattern = str(expr.value)
            if pattern.startswith("%") and pattern.endswith("%"):
                core = pattern.strip("%")
                return query.ilike(expr.field, f"%{core}%")
            return query.ilike(expr.field, pattern)

        raise ValueError(f"Unsupported operator: {expr.operator}")
