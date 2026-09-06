"""Benchmark for RulesetAccessService and DocumentAccessService batching optimization.

Measures the number of database calls (queries/round-trips) and execution time
for updating organization grants and project bindings when replacing existing items.
"""

from __future__ import annotations

import time
from typing import Any

from app.services.db_adapters import DatabaseAdapter
from app.services.document_access_service import DocumentAccessService
from app.services.ruleset_access_service import RulesetAccessService


class CallCountingAdapter(DatabaseAdapter):
    """Adapter wrapper that records operation counts and simulates network/DB latency."""

    def __init__(self, simulated_latency_s: float = 0.002):
        self._rows: list[dict[str, Any]] = []
        self.simulated_latency_s = simulated_latency_s
        self.reset_counts()

    def reset_counts(self) -> None:
        self.select_calls = 0
        self.insert_calls = 0
        self.insert_many_calls = 0
        self.delete_calls = 0
        self.delete_many_calls = 0
        self.total_inserted_rows = 0
        self.total_deleted_rows = 0

    @property
    def total_queries(self) -> int:
        return (
            self.select_calls
            + self.insert_calls
            + self.insert_many_calls
            + self.delete_calls
            + self.delete_many_calls
        )

    @property
    def columns_dict(self) -> dict[str, Any]:
        return {}

    @property
    def rows(self) -> list[dict[str, Any]]:
        return list(self._rows)

    def get(self, pk_value: Any) -> dict[str, Any] | None:
        return next((r for r in self._rows if r.get("id") == pk_value), None)

    def insert(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.insert_calls += 1
        self.total_inserted_rows += 1
        if self.simulated_latency_s:
            time.sleep(self.simulated_latency_s)
        row = dict(payload)
        row.setdefault("id", max((int(r.get("id", 0)) for r in self._rows), default=0) + 1)
        self._rows.append(row)
        return dict(row)

    def insert_many(self, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.insert_many_calls += 1
        self.total_inserted_rows += len(payloads)
        if self.simulated_latency_s:
            time.sleep(self.simulated_latency_s)
        inserted = []
        for payload in payloads:
            row = dict(payload)
            row.setdefault("id", max((int(r.get("id", 0)) for r in self._rows), default=0) + 1)
            self._rows.append(row)
            inserted.append(dict(row))
        return inserted

    def update(self, *, updates: dict[str, Any], pk_values: Any) -> None:
        pass

    def delete(self, pk_value: Any) -> None:
        self.delete_calls += 1
        self.total_deleted_rows += 1
        if self.simulated_latency_s:
            time.sleep(self.simulated_latency_s)
        self._rows = [r for r in self._rows if r.get("id") != pk_value]

    def delete_many(self, pk_values: list[Any]) -> None:
        self.delete_many_calls += 1
        self.total_deleted_rows += len(pk_values)
        if self.simulated_latency_s:
            time.sleep(self.simulated_latency_s)
        pk_set = set(pk_values)
        self._rows = [r for r in self._rows if r.get("id") not in pk_set]

    def rows_where(
        self,
        where_sql: str,
        params: list[Any] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        self.select_calls += 1
        if self.simulated_latency_s:
            time.sleep(self.simulated_latency_s)
        expr = where_sql.strip()
        field = expr.split("=")[0].strip()
        val = params[0] if params else None
        matching = [r for r in self._rows if r.get(field) == val]
        return matching[:limit] if limit is not None else matching


def run_benchmark(item_counts: list[int] = [10, 50, 100]):
    print(f"{'Operation':<35} | {'Items':<6} | {'Queries':<8} | {'Latency (ms)':<12}")
    print("-" * 70)

    for n in item_counts:
        # Ruleset Org Grants
        repo = CallCountingAdapter(simulated_latency_s=0.001)
        binding_repo = CallCountingAdapter(simulated_latency_s=0.001)
        svc = RulesetAccessService(repo, binding_repo)
        initial = [f"RULESET-{i:03d}" for i in range(n)]
        replacement = [f"RULESET-{i:03d}" for i in range(n // 2, n + n // 2)]

        # Initial seed
        svc.set_org_grants(1, initial)
        repo.reset_counts()

        t0 = time.perf_counter()
        svc.set_org_grants(1, replacement)
        dt_ms = (time.perf_counter() - t0) * 1000

        print(f"{'RulesetOrgGrants.set_org_grants':<35} | {n:<6} | {repo.total_queries:<8} | {dt_ms:<12.2f}")

        # Ruleset Project Bindings
        binding_repo.reset_counts()
        repo._rows = [{"id": i + 1, "organization_id": 1, "ruleset_id": f"RULESET-{i:03d}"} for i in range(200)]
        svc.set_project_bindings(101, initial, organization_id=1)
        binding_repo.reset_counts()

        t0 = time.perf_counter()
        svc.set_project_bindings(101, replacement, organization_id=1)
        dt_ms = (time.perf_counter() - t0) * 1000

        print(f"{'RulesetProjectBindings.set_bindings':<35} | {n:<6} | {binding_repo.total_queries:<8} | {dt_ms:<12.2f}")

        # Document Org Grants
        doc_repo = CallCountingAdapter(simulated_latency_s=0.001)
        doc_binding_repo = CallCountingAdapter(simulated_latency_s=0.001)
        doc_svc = DocumentAccessService(doc_repo, doc_binding_repo)
        doc_initial = list(range(1, n + 1))
        doc_replacement = list(range(n // 2 + 1, n + n // 2 + 1))

        doc_svc.set_org_grants(1, doc_initial)
        doc_repo.reset_counts()

        t0 = time.perf_counter()
        doc_svc.set_org_grants(1, doc_replacement)
        dt_ms = (time.perf_counter() - t0) * 1000

        print(f"{'DocumentOrgGrants.set_org_grants':<35} | {n:<6} | {doc_repo.total_queries:<8} | {dt_ms:<12.2f}")


if __name__ == "__main__":
    run_benchmark()
