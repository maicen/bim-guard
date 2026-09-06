"""Unit tests for batched access service operations and database adapters."""

from __future__ import annotations

from typing import Any

import pytest

from app.services.db_adapters import DatabaseAdapter, SQLiteTableAdapter, SupabaseTableAdapter
from app.services.document_access_service import DocumentAccessService
from app.services.ruleset_access_service import RulesetAccessService


class MockTrackingAdapter(DatabaseAdapter):
    """Database adapter tracking calls to insert, insert_many, delete, delete_many."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self._rows = [dict(r) for r in (rows or [])]
        self.insert_calls = 0
        self.insert_many_calls = 0
        self.delete_calls = 0
        self.delete_many_calls = 0

    @property
    def columns_dict(self) -> dict[str, Any]:
        return {}

    @property
    def rows(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self._rows]

    def get(self, pk_value: Any) -> dict[str, Any] | None:
        return next((dict(r) for r in self._rows if r.get("id") == pk_value), None)

    def insert(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.insert_calls += 1
        row = dict(payload)
        row.setdefault("id", max((int(r.get("id", 0)) for r in self._rows), default=0) + 1)
        self._rows.append(row)
        return dict(row)

    def insert_many(self, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.insert_many_calls += 1
        inserted = []
        for payload in payloads:
            row = dict(payload)
            row.setdefault("id", max((int(r.get("id", 0)) for r in self._rows), default=0) + 1)
            self._rows.append(row)
            inserted.append(dict(row))
        return inserted

    def update(self, *, updates: dict[str, Any], pk_values: Any) -> None:
        for r in self._rows:
            if r.get("id") == pk_values:
                r.update(updates)

    def delete(self, pk_value: Any) -> None:
        self.delete_calls += 1
        self._rows = [r for r in self._rows if r.get("id") != pk_value]

    def delete_many(self, pk_values: list[Any]) -> None:
        self.delete_many_calls += 1
        pk_set = set(pk_values)
        self._rows = [r for r in self._rows if r.get("id") not in pk_set]

    def rows_where(
        self,
        where_sql: str,
        params: list[Any] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        field = where_sql.split("=")[0].strip()
        val = params[0] if params else None
        res = [dict(r) for r in self._rows if r.get(field) == val]
        return res[:limit] if limit is not None else res


def test_ruleset_access_service_batches_queries():
    org_repo = MockTrackingAdapter()
    proj_repo = MockTrackingAdapter()
    service = RulesetAccessService(org_repo, proj_repo)

    # Initial grant of 10 rulesets -> 1 batch insert
    service.set_org_grants(1, [f"RS-{i}" for i in range(10)])
    assert org_repo.insert_many_calls == 1
    assert org_repo.insert_calls == 0
    assert org_repo.delete_many_calls == 0
    assert org_repo.delete_calls == 0
    assert len(service.list_org_grants(1)) == 10

    # Replace with 5 old and 5 new rulesets -> 1 batch delete (5 items) and 1 batch insert (5 items)
    org_repo.insert_many_calls = 0
    service.set_org_grants(1, [f"RS-{i}" for i in range(5, 15)])
    assert org_repo.delete_many_calls == 1
    assert org_repo.delete_calls == 0
    assert org_repo.insert_many_calls == 1
    assert org_repo.insert_calls == 0
    assert sorted(service.list_org_grants(1)) == sorted([f"RS-{i}" for i in range(5, 15)])

    # Clear org grants -> 1 batch delete
    org_repo.delete_many_calls = 0
    service.set_org_grants(1, [])
    assert org_repo.delete_many_calls == 1
    assert org_repo.list_org_grants(1) == [] if hasattr(org_repo, "list_org_grants") else service.list_org_grants(1) == []


def test_ruleset_project_bindings_batches_queries():
    org_repo = MockTrackingAdapter()
    proj_repo = MockTrackingAdapter()
    service = RulesetAccessService(org_repo, proj_repo)

    service.set_org_grants(1, [f"RS-{i}" for i in range(20)])
    # Bind 10 to project 100 -> 1 batch insert
    service.set_project_bindings(100, [f"RS-{i}" for i in range(10)], organization_id=1)
    assert proj_repo.insert_many_calls == 1
    assert proj_repo.insert_calls == 0
    assert len(service.list_project_bindings(100)) == 10

    # Replace with 5 existing + 5 new -> 1 batch delete + 1 batch insert
    proj_repo.insert_many_calls = 0
    proj_repo.delete_many_calls = 0
    service.set_project_bindings(100, [f"RS-{i}" for i in range(5, 15)], organization_id=1)
    assert proj_repo.delete_many_calls == 1
    assert proj_repo.delete_calls == 0
    assert proj_repo.insert_many_calls == 1
    assert proj_repo.insert_calls == 0
    assert sorted(service.list_project_bindings(100)) == sorted([f"RS-{i}" for i in range(5, 15)])


def test_document_access_service_batches_queries():
    org_repo = MockTrackingAdapter()
    proj_repo = MockTrackingAdapter()
    service = DocumentAccessService(org_repo, proj_repo)

    # Initial grant of 10 documents -> 1 batch insert
    service.set_org_grants(1, list(range(1, 11)))
    assert org_repo.insert_many_calls == 1
    assert org_repo.insert_calls == 0
    assert len(service.list_org_grants(1)) == 10

    # Replace with 5 existing + 5 new -> 1 batch delete + 1 batch insert
    org_repo.insert_many_calls = 0
    org_repo.delete_many_calls = 0
    service.set_org_grants(1, list(range(6, 16)))
    assert org_repo.delete_many_calls == 1
    assert org_repo.delete_calls == 0
    assert org_repo.insert_many_calls == 1
    assert org_repo.insert_calls == 0
    assert sorted(service.list_org_grants(1)) == list(range(6, 16))

    # Project bindings with batching
    service.set_project_bindings(200, list(range(6, 11)), organization_id=1)
    assert proj_repo.insert_many_calls == 1
    assert proj_repo.insert_calls == 0

    # Project can only bind what org is granted
    with pytest.raises(ValueError, match="not granted to this organization"):
        service.set_project_bindings(200, [999], organization_id=1)


def test_sqlite_table_adapter_batch_operations():
    import fastlite
    db = fastlite.database(":memory:")
    table = db.t.test_items
    table.create(dict(id=int, name=str), pk="id")
    adapter = SQLiteTableAdapter(table)

    # insert_many
    items = [{"id": i, "name": f"item-{i}"} for i in range(1, 11)]
    adapter.insert_many(items)
    assert len(list(adapter.rows)) == 10

    # delete_many
    adapter.delete_many([1, 2, 3])
    remaining_ids = [r["id"] for r in adapter.rows]
    assert remaining_ids == list(range(4, 11))

    # delete_many empty list does not fail
    adapter.delete_many([])
    assert len(list(adapter.rows)) == 7


def test_supabase_table_adapter_memory_fallback_batch_operations():
    class DummyClient:
        pass

    adapter = SupabaseTableAdapter(DummyClient(), "test_table", {"id": int, "name": str}, pk="id")
    adapter._use_memory_fallback = True

    # insert_many
    adapter.insert_many([{"id": 1, "name": "a"}, {"id": 2, "name": "b"}, {"id": 3, "name": "c"}])
    assert len(adapter.rows) == 3

    # delete_many
    adapter.delete_many([1, 3])
    assert [r["id"] for r in adapter.rows] == [2]

    # delete_many empty list
    adapter.delete_many([])
    assert len(adapter.rows) == 1
