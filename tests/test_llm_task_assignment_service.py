"""Test suite for LLMTaskAssignmentService (per-org, per-task model shortlists)."""

from __future__ import annotations

from typing import Any

import pytest

from app.services.llm_provider_instances_service import LLMProviderInstancesService
from app.services.llm_task_assignment_service import LLMTaskAssignmentService


class _FakeAdapter:
    """In-memory stand-in for a Supabase table adapter."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self._next_id = 1

    def get(self, pk_value: Any) -> dict[str, Any] | None:
        return next((row for row in self.rows if row["id"] == pk_value), None)

    def insert(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = {"id": self._next_id, **payload}
        self._next_id += 1
        self.rows.append(row)
        return row

    def update(self, *, updates: dict[str, Any], pk_values: Any) -> None:
        for row in self.rows:
            if row["id"] == pk_values:
                row.update(updates)

    def delete(self, pk_value: Any) -> None:
        self.rows = [row for row in self.rows if row["id"] != pk_value]


def _services() -> tuple[LLMProviderInstancesService, LLMTaskAssignmentService]:
    instances = LLMProviderInstancesService(instances_repo=_FakeAdapter())
    assignments = LLMTaskAssignmentService(
        assignments_repo=_FakeAdapter(), provider_instances_service=instances
    )
    return instances, assignments


def _make_instance(instances: LLMProviderInstancesService, organization_id: int, name: str) -> int:
    row = instances.create_instance(
        organization_id, name=name, kind="openrouter", api_key="sk-test"
    )
    return row["id"]


def test_list_tasks_returns_the_registered_tasks():
    _, assignments = _services()
    keys = {task.key for task in assignments.list_tasks()}
    assert "rule_extraction" in keys
    assert "document_qa" in keys


def test_set_assignments_replaces_the_whole_set():
    instances, assignments = _services()
    instance_id = _make_instance(instances, organization_id=1, name="openrouter-main")

    first = assignments.set_assignments(
        1,
        "rule_extraction",
        models=[
            {"provider_instance_id": instance_id, "model_id": "openrouter/a", "model_name": "A"},
            {"provider_instance_id": instance_id, "model_id": "openrouter/b", "model_name": "B"},
        ],
    )
    assert {row["model_id"] for row in first} == {"openrouter/a", "openrouter/b"}

    second = assignments.set_assignments(
        1,
        "rule_extraction",
        models=[{"provider_instance_id": instance_id, "model_id": "openrouter/c", "model_name": "C"}],
    )
    current = assignments.list_assignments(1, "rule_extraction")
    assert {row["model_id"] for row in current} == {"openrouter/c"}
    assert len(second) == 1


def test_set_assignments_enforces_single_default():
    instances, assignments = _services()
    instance_id = _make_instance(instances, organization_id=1, name="openrouter-main")

    rows = assignments.set_assignments(
        1,
        "rule_extraction",
        models=[
            {"provider_instance_id": instance_id, "model_id": "openrouter/a", "model_name": "A"},
            {"provider_instance_id": instance_id, "model_id": "openrouter/b", "model_name": "B"},
        ],
        default_provider_instance_id=instance_id,
        default_model_id="openrouter/b",
    )
    defaults = [row for row in rows if row["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["model_id"] == "openrouter/b"


def test_set_assignments_rejects_instance_from_another_org():
    instances, assignments = _services()
    other_org_instance_id = _make_instance(instances, organization_id=2, name="other-org")

    with pytest.raises(ValueError, match="does not belong to this organization"):
        assignments.set_assignments(
            1,
            "rule_extraction",
            models=[
                {
                    "provider_instance_id": other_org_instance_id,
                    "model_id": "openrouter/a",
                    "model_name": "A",
                }
            ],
        )


def test_set_assignments_rejects_unknown_task_key():
    instances, assignments = _services()
    instance_id = _make_instance(instances, organization_id=1, name="openrouter-main")

    with pytest.raises(ValueError, match="task_key must be one of"):
        assignments.set_assignments(
            1,
            "not_a_real_task",
            models=[{"provider_instance_id": instance_id, "model_id": "openrouter/a", "model_name": "A"}],
        )


def test_set_assignments_rejects_duplicate_model():
    instances, assignments = _services()
    instance_id = _make_instance(instances, organization_id=1, name="openrouter-main")

    with pytest.raises(ValueError, match="shortlisted more than once"):
        assignments.set_assignments(
            1,
            "rule_extraction",
            models=[
                {"provider_instance_id": instance_id, "model_id": "openrouter/a", "model_name": "A"},
                {"provider_instance_id": instance_id, "model_id": "openrouter/a", "model_name": "A dup"},
            ],
        )


def test_list_assignments_is_scoped_per_organization():
    instances, assignments = _services()
    instance_1 = _make_instance(instances, organization_id=1, name="org1-provider")
    instance_2 = _make_instance(instances, organization_id=2, name="org2-provider")

    assignments.set_assignments(
        1,
        "rule_extraction",
        models=[{"provider_instance_id": instance_1, "model_id": "openrouter/a", "model_name": "A"}],
    )
    assignments.set_assignments(
        2,
        "rule_extraction",
        models=[{"provider_instance_id": instance_2, "model_id": "openrouter/b", "model_name": "B"}],
    )

    assert {row["model_id"] for row in assignments.list_assignments(1)} == {"openrouter/a"}
    assert {row["model_id"] for row in assignments.list_assignments(2)} == {"openrouter/b"}
