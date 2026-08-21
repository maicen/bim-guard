"""Database adapters exposing a table API backed by Supabase."""

from __future__ import annotations

import time
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


class SupabaseTableAdapter:
    """Table adapter backed by Supabase PostgREST queries."""

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
        response = execute_with_retry(
            lambda: self._client.table(self._table_name)
            .select("*")
            .eq(self._pk, pk_value)
            .limit(1)
        )
        rows = response.data or []
        return rows[0] if rows else None

    def insert(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Insert one row and return inserted payload from API."""
        try:
            response = execute_with_retry(
                lambda: self._client.table(self._table_name).insert(payload)
            )
            rows = response.data or []
            return rows[0] if rows else payload
        except APIError as exc:
            if self._should_retry_insert_with_pk(exc, payload):
                retry_payload = dict(payload)
                retry_payload[self._pk] = self._next_numeric_pk()
                response = execute_with_retry(
                    lambda: self._client.table(self._table_name).insert(retry_payload)
                )
                rows = response.data or []
                return rows[0] if rows else retry_payload
            raise

    def update(self, *, updates: dict[str, Any], pk_values: Any) -> None:
        """Update one row by primary key."""
        execute_with_retry(
            lambda: self._client.table(self._table_name).update(updates).eq(self._pk, pk_values)
        )

    def delete(self, pk_value: Any) -> None:
        """Delete one row by primary key."""
        execute_with_retry(
            lambda: self._client.table(self._table_name).delete().eq(self._pk, pk_value)
        )

    def rows_where(
        self,
        where_sql: str,
        params: list[Any] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Filter rows using a restricted SQL-like predicate subset."""
        expr = parse_where(where_sql, params)
        rows = self._select_filtered(expr, limit=limit)
        return rows[:limit] if limit is not None else rows

    def _select_all(self) -> list[dict[str, Any]]:
        """Select all rows using paginated range queries."""
        return self._run_select(limit=None, expr=None)

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
                return query.range(offset, offset + remaining - 1)

            response = execute_with_retry(_build)
            rows = response.data or []
            collected.extend(rows)

            if len(rows) < remaining:
                break

            offset += remaining

        return collected

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
