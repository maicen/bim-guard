"""Coverage for the fire-safety starter ruleset (data/rulesets/fire_safety_starter_ruleset.json)."""

from __future__ import annotations

from typing import Any

from app.services.db_adapters import DatabaseAdapter
from app.services.rules_service import RuleService
from app.services.ruleset_seeder import _DEFAULT_CODE_RULESET_FILES, _load, _seed_json_ruleset


class MockTableAdapter(DatabaseAdapter):
    """In-memory table adapter for test isolation (mirrors tests/test_arch_engine_di.py's)."""

    def __init__(self, initial_rows: list[dict[str, Any]] | None = None) -> None:
        self._rows: list[dict[str, Any]] = [dict(r) for r in (initial_rows or [])]

    @property
    def columns_dict(self) -> dict[str, Any]:
        return {"id": int, "reference": str}

    @property
    def rows(self):
        return list(self._rows)

    def get(self, pk_value: Any) -> dict[str, Any] | None:
        for r in self._rows:
            if r.get("id") == pk_value or r.get("reference") == pk_value:
                return dict(r)
        return None

    def insert(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = dict(payload)
        if "id" not in row:
            row["id"] = len(self._rows) + 1
        self._rows.append(row)
        return row

    def update(self, *, updates: dict[str, Any], pk_values: Any) -> None:
        for r in self._rows:
            if r.get("id") == pk_values:
                r.update(updates)

    def delete(self, pk_value: Any) -> None:
        self._rows = [r for r in self._rows if r.get("id") != pk_value]

    def rows_where(self, where_sql: str = "", params: list[Any] | None = None) -> list[dict[str, Any]]:
        return list(self._rows)


def test_fire_safety_starter_ruleset_is_registered():
    assert "fire_safety_starter_ruleset.json" in _DEFAULT_CODE_RULESET_FILES


def test_fire_safety_starter_ruleset_json_is_well_formed():
    payload = _load("fire_safety_starter_ruleset.json")

    assert payload["ruleset_id"] == "FIRE-SAFETY-STARTER"
    assert payload["rules"], "expected at least one starter rule"
    for rule in payload["rules"]:
        assert rule["reference"]
        assert rule["target_ifc_class"]
        assert rule["property_name"]
        assert rule["rule_category"] == "fire_safety"
        # Every starter rule must be flagged for review rather than presented
        # as an already-verified regulatory citation.
        assert rule["needs_review"] is True


def test_seed_json_ruleset_inserts_fire_safety_rows_and_resumes_idempotently():
    """Exercises just this one file, not the whole `_DEFAULT_CODE_RULESET_FILES` list.

    The other two default files resolve through StaticDataService's DB-backed
    asset store, which this unit test has no business depending on.
    """
    rules_svc = RuleService(rules_repo=MockTableAdapter(), folders_repo=MockTableAdapter())

    count = _seed_json_ruleset(rules_svc, "fire_safety_starter_ruleset.json")

    assert count == 7
    refs = {r["reference"] for r in rules_svc.list_rules()}
    assert "FIRE-SAFETY-STARTER.001" in refs
    assert "FIRE-SAFETY-STARTER.006" in refs

    # Idempotent: a second run inserts nothing new.
    assert _seed_json_ruleset(rules_svc, "fire_safety_starter_ruleset.json") == 0
