"""Unit tests for ParsingEngineInstancesService's two-tier (org vs. platform) scoping.

Uses an in-process fake repo rather than a live Supabase table — these tests
exercise pure scoping/default-selection logic, not persistence itself.
"""

from __future__ import annotations

import itertools

import pytest

from app.services.parsing_engine_instances_service import ParsingEngineInstancesService


class _FakeInstancesRepo:
    """Minimal stand-in for the DatabaseAdapter interface this service needs."""

    def __init__(self):
        self._rows: dict[int, dict] = {}
        self._ids = itertools.count(1)

    @property
    def rows(self):
        return list(self._rows.values())

    def insert(self, payload: dict) -> dict:
        row = dict(payload)
        row["id"] = next(self._ids)
        self._rows[row["id"]] = row
        return dict(row)

    def get(self, pk):
        row = self._rows.get(pk)
        return dict(row) if row else None

    def update(self, *, updates: dict, pk_values) -> None:
        row = self._rows.get(pk_values)
        if row:
            row.update(updates)

    def delete(self, pk) -> None:
        self._rows.pop(pk, None)


@pytest.fixture
def service():
    return ParsingEngineInstancesService(_FakeInstancesRepo())


def test_org_and_platform_instances_are_isolated(service):
    service.create_instance(None, name="platform-default", kind="docling-local", api_url="http://p")
    service.create_instance(1, name="org-instance", kind="docling-local", api_url="http://o")

    assert [r["name"] for r in service.list_instances(None)] == ["platform-default"]
    assert [r["name"] for r in service.list_instances(1)] == ["org-instance"]
    assert service.get_by_name(1, "platform-default") is None
    assert service.get_by_name(None, "org-instance") is None


def test_same_name_allowed_in_different_scopes(service):
    service.create_instance(None, name="local", kind="docling-local", api_url="http://p")
    created = service.create_instance(1, name="local", kind="docling-local", api_url="http://o")
    assert created["name"] == "local"
    assert created["organization_id"] == 1


def test_duplicate_name_within_same_scope_rejected(service):
    service.create_instance(1, name="local", kind="docling-local", api_url="http://o")
    with pytest.raises(ValueError, match="already exists"):
        service.create_instance(1, name="local", kind="docling-local", api_url="http://o2")


def test_get_effective_default_prefers_org_over_platform(service):
    service.create_instance(None, name="platform", kind="docling-local", api_url="http://p", is_default=True)
    org_row = service.create_instance(
        1, name="org-own", kind="docling-local", api_url="http://o", is_default=True
    )

    assert service.get_effective_default(1)["id"] == org_row["id"]


def test_get_effective_default_falls_back_to_platform_when_org_has_none(service):
    platform_row = service.create_instance(
        None, name="platform", kind="docling-local", api_url="http://p", is_default=True
    )

    assert service.get_effective_default(1)["id"] == platform_row["id"]
    assert service.get_effective_default(1) is not None


def test_single_default_enforced_per_scope(service):
    first = service.create_instance(1, name="a", kind="docling-local", api_url="http://a", is_default=True)
    second = service.create_instance(1, name="b", kind="docling-local", api_url="http://b", is_default=True)

    assert service.get_instance(1, first["id"])["is_default"] is False
    assert service.get_instance(1, second["id"])["is_default"] is True


def test_platform_default_unaffected_by_org_default_change(service):
    platform_row = service.create_instance(
        None, name="platform", kind="docling-local", api_url="http://p", is_default=True
    )
    service.create_instance(1, name="org", kind="docling-local", api_url="http://o", is_default=True)

    assert service.get_default(None)["id"] == platform_row["id"]
