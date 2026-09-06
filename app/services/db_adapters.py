"""Database adapters exposing a table API backed by Supabase."""

from __future__ import annotations

import abc
import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Callable

from httpx import TransportError
from postgrest.exceptions import APIError

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
    def update(self, *, updates: dict[str, Any], pk_values: Any) -> None:
        """Update row by primary key."""

    @abc.abstractmethod
    def delete(self, pk_value: Any) -> None:
        """Delete row by primary key."""

    @abc.abstractmethod
    def delete_many(self, pk_values: list[Any]) -> None:
        """Delete multiple rows by primary keys."""

    @abc.abstractmethod
    def rows_where(
        self,
        where_sql: str,
        params: list[Any] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Query rows matching predicate."""

    def save_report(self, report_data: dict[str, Any]) -> dict[str, Any]:
        """Persist a compliance report entity."""
        return self.insert(report_data)


class SQLiteTableAdapter(DatabaseAdapter):
    """Expose a thin compatibility layer around a fastlite table object.

    Used only for the isolated SQLite connections PersistenceService hands to
    tests/the eval harness (see get_isolated_sqlite_db) — Supabase remains the
    sole runtime backend for the live app.
    """

    def __init__(self, table: Any):
        """Store underlying fastlite table reference."""
        self._table = table

    @property
    def columns_dict(self) -> dict[str, Any]:
        """Return table columns map."""
        return self._table.columns_dict

    @property
    def rows(self) -> Iterable[dict[str, Any]]:
        """Return all table rows."""
        return self._table.rows

    def create(self, schema: dict[str, Any], *, pk: str, if_not_exists: bool = True) -> None:
        """Create table if missing."""
        self._table.create(schema, pk=pk, if_not_exists=if_not_exists)

    def add_column(self, column_name: str, column_type: Any) -> None:
        """Add table column."""
        self._table.add_column(column_name, column_type)

    def get(self, pk_value: Any) -> dict[str, Any] | None:
        """Get one row by primary key."""
        try:
            return self._table.get(pk_value)
        except Exception:
            return None

    def insert(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Insert one row."""
        return self._table.insert(payload)

    def insert_many(self, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Insert multiple rows."""
        if not payloads:
            return []
        try:
            self._table.insert_all(payloads)
            return payloads
        except Exception:
            return [self.insert(payload) for payload in payloads]

    def update(self, *, updates: dict[str, Any], pk_values: Any) -> None:
        """Update one row by primary key."""
        self._table.update(updates=updates, pk_values=pk_values)

    def delete(self, pk_value: Any) -> None:
        """Delete one row by primary key."""
        try:
            self._table.delete(pk_value)
        except Exception:
            pass

    def delete_many(self, pk_values: list[Any]) -> None:
        """Delete multiple rows by primary keys."""
        if not pk_values:
            return

        try:
            placeholders = ",".join(["?"] * len(pk_values))
            # fastlite assumes the first PK if we don't have multiple
            pk_col = self._table.pks[0]
            self._table.delete_where(f"{pk_col} IN ({placeholders})", pk_values)
        except Exception:
            for pk_value in pk_values:
                self.delete(pk_value)

    def rows_where(
        self,
        where_sql: str,
        params: list[Any] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Filter rows using fastlite's native rows_where."""
        return list(self._table.rows_where(where_sql, params or [], limit=limit))


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
                (
                    r
                    for r in self._memory_rows
                    if r.get(self._pk) == pk_value or str(r.get(self._pk)) == str(pk_value)
                ),
                None,
            )

        try:
            response = execute_with_retry(
                lambda: (
                    self._client.table(self._table_name).select("*").eq(self._pk, pk_value).limit(1)
                )
            )
            rows = response.data or []
            return rows[0] if rows else None
        except APIError as exc:
            if self._is_missing_table_error(exc):
                self._use_memory_fallback = True
                return self.get(pk_value)
            raise

    def insert(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Insert one row and return inserted payload from API."""
        if self._use_memory_fallback:
            row = dict(payload)
            if self._pk not in row:
                row[self._pk] = (
                    max((int(r.get(self._pk, 0)) for r in self._memory_rows), default=0) + 1
                )
            self._memory_rows.append(row)
            return dict(row)

        try:
            response = execute_with_retry(
                lambda: self._client.table(self._table_name).insert(payload)
            )
            rows = response.data or []
            return rows[0] if rows else payload
        except APIError as exc:
            if self._is_missing_table_error(exc) or getattr(exc, "code", None) == "23503":
                self._use_memory_fallback = True
                return self.insert(payload)
            if self._should_retry_insert_with_pk(exc, payload):
                retry_payload = dict(payload)
                retry_payload[self._pk] = self._next_numeric_pk()
                response = execute_with_retry(
                    lambda: self._client.table(self._table_name).insert(retry_payload)
                )
                rows = response.data or []
                return rows[0] if rows else retry_payload
            raise

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
            return inserted
        except APIError as exc:
            if self._is_missing_table_error(exc):
                self._use_memory_fallback = True
                return [self.insert(payload) for payload in payloads]
            raise

    def update(self, *, updates: dict[str, Any], pk_values: Any) -> None:
        """Update one row by primary key."""
        if self._use_memory_fallback:
            for row in self._memory_rows:
                if row.get(self._pk) == pk_values or str(row.get(self._pk)) == str(pk_values):
                    row.update(updates)
            return

        try:
            execute_with_retry(
                lambda: self._client.table(self._table_name).update(updates).eq(self._pk, pk_values)
            )
        except APIError as exc:
            if self._is_missing_table_error(exc):
                self._use_memory_fallback = True
                self.update(updates=updates, pk_values=pk_values)
                return
            raise

    def delete(self, pk_value: Any) -> None:
        """Delete one row by primary key."""
        if self._use_memory_fallback:
            self._memory_rows[:] = [
                r
                for r in self._memory_rows
                if not (r.get(self._pk) == pk_value or str(r.get(self._pk)) == str(pk_value))
            ]
            return

        try:
            execute_with_retry(
                lambda: self._client.table(self._table_name).delete().eq(self._pk, pk_value)
            )
        except APIError as exc:
            if self._is_missing_table_error(exc):
                self._use_memory_fallback = True
                self.delete(pk_value)
                return
            raise

def delete_many(self, pk_values: list[Any]) -> None:
        """Delete multiple rows by primary keys in as few PostgREST round-trips as possible."""
        if not pk_values:
            return

        if self._use_memory_fallback:
            pk_set = {str(pk) for pk in pk_values}
            self._memory_rows[:] = [
                r for r in self._memory_rows if str(r.get(self._pk)) not in pk_set
            ]
            return

        chunk_size = 500
        try:
            for start in range(0, len(pk_values), chunk_size):
                chunk = pk_values[start : start + chunk_size]
                execute_with_retry(
                    lambda chunk=chunk: self._client.table(self._table_name).delete().in_(self._pk, chunk)
                )
        except APIError as exc:
            if self._is_missing_table_error(exc):
                self._use_memory_fallback = True
                self.delete_many(pk_values)
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
                if expr.operator == "eq" and (val == expr.value or str(val) == str(expr.value)):
                    matching.append(row)
                elif (
                    expr.operator == "like"
                    and str(expr.value).lower().replace("%", "") in str(val or "").lower()
                ):
                    matching.append(row)
            return matching[:limit] if limit is not None else matching

        try:
            expr = parse_where(where_sql, params)
            rows = self._select_filtered(expr, limit=limit)
            return rows[:limit] if limit is not None else rows
        except APIError as exc:
            if self._is_missing_table_error(exc):
                self._use_memory_fallback = True
                return self.rows_where(where_sql, params, limit)
            raise

    def _select_all(self) -> list[dict[str, Any]]:
        """Select all rows using paginated range queries."""
        if self._use_memory_fallback:
            return list(self._memory_rows)

        try:
            return self._run_select(limit=None, expr=None)
        except APIError as exc:
            if self._is_missing_table_error(exc):
                self._use_memory_fallback = True
                return list(self._memory_rows)
            raise

    def _select_filtered(self, expr: _WhereExpr, limit: int | None) -> list[dict[str, Any]]:
        """Select rows matching the expression using paginated queries."""
        return self._run_select(limit=limit, expr=expr)

    def _run_select(self, *, limit: int | None, expr: _WhereExpr | None) -> list[dict[str, Any]]:
        """Execute paginated select queries and collect all rows."""
        page_size = 1000
        offset = 0
        collected: list[dict[str, Any]] = []

        while True:
            remaining = page_size
            if limit is not None:
                remaining = min(remaining, limit - len(collected))
                if remaining <= 0:
                    break

            def _build(offset=offset, remaining=remaining):
                query = self._client.table(self._table_name).select("*")
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
        msg = str(getattr(exc, "message", "") or getattr(exc, "details", "") or "")
        return code in {"PGRST205", "42P01"} or "schema cache" in msg or "does not exist" in msg

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
            lambda: (
                self._client.table(self._table_name)
                .select(self._pk)
                .order(self._pk, desc=True)
                .limit(1)
            )
        )
        rows = response.data or []
        if not rows:
            return 1

        current = rows[0].get(self._pk)
        try:
            return int(current) + 1
        except (TypeError, ValueError):
            return 1

    @staticmethod
    def _apply_expr(query: Any, expr: _WhereExpr) -> Any:
        """Apply parsed filter expression to a Supabase query."""
        if expr.operator == "eq":
            return query.eq(expr.field, expr.value)

        if expr.operator == "like":
            pattern = str(expr.value)
            if pattern.startswith("%") and pattern.endswith("%"):
                core = pattern.strip("%")
                return query.ilike(expr.field, f"%{core}%")
            return query.ilike(expr.field, pattern)

        raise ValueError(f"Unsupported operator: {expr.operator}")
