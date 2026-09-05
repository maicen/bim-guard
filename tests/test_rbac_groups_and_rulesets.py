"""Unit tests for the RBAC layer.

Groups, group -> project grants, and organization/project ruleset grants.

NO LIVE DATABASE. Repositories are in-memory FakeTables, so these tests never
touch Supabase and can freely create/delete organizations, groups, and grants
without any cleanup risk to real data.

Covers TODO.md's Priority 9 ask: "Add tests proving unauthorized roles/
organizations cannot invoke restricted API operations" -- at the service
layer, which is where both `app.api.projects.get_authorized_project` and
`app.api.organizations` delegate the actual decision.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.services.arch_analysis_service import ArchAnalysisService
from app.services.membership_service import MembershipService
from app.services.ruleset_access_service import RulesetAccessService


class FakeTable:
    """In-memory table.

    Supports the single-predicate ``col = ?`` queries every method under
    test issues.
    """

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self._rows = [dict(row) for row in (rows or [])]

    @property
    def rows(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self._rows]

    def get(self, pk_value: Any) -> dict[str, Any] | None:
        return next((dict(r) for r in self._rows if r.get("id") == pk_value), None)

    def insert(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = dict(payload)
        row.setdefault("id", max((int(r.get("id", 0)) for r in self._rows), default=0) + 1)
        self._rows.append(row)
        return dict(row)

    def update(self, *, updates: dict[str, Any], pk_values: Any) -> None:
        for row in self._rows:
            if row.get("id") == pk_values:
                row.update(updates)

    def delete(self, pk_value: Any) -> None:
        self._rows = [r for r in self._rows if r.get("id") != pk_value]

    def rows_where(
        self, where_sql: str = "", params: list[Any] | None = None, limit: int | None = None
    ) -> list[dict[str, Any]]:
        rows = self.rows
        if where_sql and params:
            field = where_sql.split("=")[0].strip()
            rows = [r for r in rows if r.get(field) == params[0]]
        return rows[:limit] if limit else rows


@pytest.fixture
def memberships() -> MembershipService:
    return MembershipService(
        memberships_repo=FakeTable(
            [
                {"id": 1, "organization_id": 10, "user_id": "owner-1", "role": "owner", "group_id": None},
                {"id": 2, "organization_id": 10, "user_id": "member-1", "role": "member", "group_id": None},
                {"id": 3, "organization_id": 10, "user_id": "member-2", "role": "member", "group_id": None},
            ]
        ),
        organizations_repo=FakeTable([{"id": 10, "name": "Acme", "slug": "acme"}]),
        invites_repo=FakeTable(),
        groups_repo=FakeTable(),
        group_project_grants_repo=FakeTable(),
        organization_project_grants_repo=FakeTable(),
    )


def test_owner_bypasses_group_gating(memberships: MembershipService) -> None:
    assert memberships.accessible_project_ids(10, "owner-1") is None
    assert memberships.member_can_access_project(10, "owner-1", 999) is True


def test_ungrouped_member_has_no_project_access(memberships: MembershipService) -> None:
    """Zero bindings unless assigned applies to people, not just projects."""
    assert memberships.accessible_project_ids(10, "member-1") == set()
    assert memberships.member_can_access_project(10, "member-1", 1) is False


def test_grouped_member_sees_only_granted_projects(memberships: MembershipService) -> None:
    group = memberships.create_group(10, "Estimators")
    memberships.set_member_group(10, "member-1", group["id"])
    memberships.set_group_project_grants(group["id"], [1, 2])

    assert memberships.accessible_project_ids(10, "member-1") == {1, 2}
    assert memberships.member_can_access_project(10, "member-1", 1) is True
    assert memberships.member_can_access_project(10, "member-1", 3) is False
    # A different member of the same org, not in the group, still sees nothing.
    assert memberships.member_can_access_project(10, "member-2", 1) is False


def test_group_names_are_unique_per_organization_case_insensitively(
    memberships: MembershipService,
) -> None:
    memberships.create_group(10, "Estimators")
    with pytest.raises(ValueError):
        memberships.create_group(10, "estimators")


def test_deleting_a_group_ungroups_its_members_rather_than_erroring(
    memberships: MembershipService,
) -> None:
    group = memberships.create_group(10, "Estimators")
    memberships.set_member_group(10, "member-1", group["id"])
    memberships.delete_group(10, group["id"])
    assert memberships.accessible_project_ids(10, "member-1") == set()


def test_set_member_group_rejects_a_group_from_another_organization(
    memberships: MembershipService,
) -> None:
    other_org_group = memberships._groups.insert({"organization_id": 999, "name": "Outsiders"})
    with pytest.raises(ValueError):
        memberships.set_member_group(10, "member-1", other_org_group["id"])


@pytest.fixture
def ruleset_access() -> RulesetAccessService:
    return RulesetAccessService(
        organization_ruleset_grants_repo=FakeTable(),
        project_ruleset_bindings_repo=FakeTable(),
    )


def test_new_project_has_zero_ruleset_bindings(ruleset_access: RulesetAccessService) -> None:
    assert ruleset_access.list_project_bindings(999) == []


def test_project_cannot_bind_a_ruleset_its_org_was_not_granted(
    ruleset_access: RulesetAccessService,
) -> None:
    ruleset_access.set_org_grants(10, ["BIMGUARD-GC-001"])
    with pytest.raises(ValueError):
        ruleset_access.set_project_bindings(1, ["BIMGUARD-CC-001"], organization_id=10)
    # The rejected request left no partial binding behind.
    assert ruleset_access.list_project_bindings(1) == []


def test_project_can_bind_a_ruleset_its_org_was_granted(
    ruleset_access: RulesetAccessService,
) -> None:
    ruleset_access.set_org_grants(10, ["BIMGUARD-GC-001", "BIMGUARD-CC-001"])
    ruleset_access.set_project_bindings(1, ["BIMGUARD-GC-001"], organization_id=10)

    assert ruleset_access.list_project_bindings(1) == ["BIMGUARD-GC-001"]
    assert ruleset_access.project_can_use_ruleset(1, "BIMGUARD-GC-001") is True
    assert ruleset_access.project_can_use_ruleset(1, "BIMGUARD-CC-001") is False


def test_narrowing_org_grants_does_not_retroactively_unbind_a_project(
    ruleset_access: RulesetAccessService,
) -> None:
    ruleset_access.set_org_grants(10, ["BIMGUARD-GC-001"])
    ruleset_access.set_project_bindings(1, ["BIMGUARD-GC-001"], organization_id=10)
    ruleset_access.set_org_grants(10, [])
    assert ruleset_access.list_project_bindings(1) == ["BIMGUARD-GC-001"]


def test_arch_analysis_rejects_a_ruleset_not_bound_to_the_project(
    ruleset_access: RulesetAccessService,
) -> None:
    service = ArchAnalysisService(
        projects_service=object(),
        rules_service=object(),
        documents_service=object(),
        report_service=object(),
        ruleset_access_service=ruleset_access,
    )
    with pytest.raises(ValueError, match="not assigned to this project"):
        service.run_analysis(project_id=1, rule_folder="BIMGUARD-GC-001")


def test_arch_analysis_allows_a_ruleset_bound_to_the_project(monkeypatch) -> None:
    """The gate opens once the ruleset is bound.

    Everything past that point is exercised by other test modules, so this
    only checks that the gate does not fire.
    """
    ruleset_access = RulesetAccessService(
        organization_ruleset_grants_repo=FakeTable(),
        project_ruleset_bindings_repo=FakeTable(),
    )
    ruleset_access.set_org_grants(10, ["BIMGUARD-GC-001"])
    ruleset_access.set_project_bindings(1, ["BIMGUARD-GC-001"], organization_id=10)

    service = ArchAnalysisService(
        projects_service=object(),
        rules_service=object(),
        documents_service=object(),
        report_service=object(),
        ruleset_access_service=ruleset_access,
    )

    import app.services.pipeline_services as pipeline_services

    monkeypatch.setattr(
        pipeline_services.PipelineOrchestratorService,
        "orchestrate_workflow",
        staticmethod(lambda **kwargs: {"error": "stopped before real orchestration"}),
    )
    with pytest.raises(ValueError, match="stopped before real orchestration"):
        service.run_analysis(project_id=1, rule_folder="BIMGUARD-GC-001")


# ---------------------------------------------------------------------------
# Cross-org project sharing (organization_project_grants)
# ---------------------------------------------------------------------------


@pytest.fixture
def two_org_memberships() -> MembershipService:
    """Two organizations: 10 owns project 1; 20 owns nothing but may be granted access."""
    return MembershipService(
        memberships_repo=FakeTable(
            [
                {"id": 1, "organization_id": 10, "user_id": "owner-1", "role": "owner", "group_id": None},
                {"id": 2, "organization_id": 20, "user_id": "owner-2", "role": "owner", "group_id": None},
                {"id": 3, "organization_id": 20, "user_id": "member-2", "role": "member", "group_id": None},
            ]
        ),
        organizations_repo=FakeTable(
            [{"id": 10, "name": "Acme", "slug": "acme"}, {"id": 20, "name": "Consultancy", "slug": "consultancy"}]
        ),
        invites_repo=FakeTable(),
        groups_repo=FakeTable(),
        group_project_grants_repo=FakeTable(),
        organization_project_grants_repo=FakeTable(),
    )


def test_project_is_invisible_to_a_non_owning_org_with_no_grant(
    two_org_memberships: MembershipService,
) -> None:
    assert two_org_memberships.organizations_with_project_access(1, owning_organization_id=10) == {10}
    assert two_org_memberships.member_can_access_project(20, "owner-2", 1) is True  # owner role alone
    # ...but org 20 has no claim to project 1 at all, which is what the API
    # layer actually checks (candidate_orgs & user_org_ids):
    assert 20 not in two_org_memberships.organizations_with_project_access(1, owning_organization_id=10)


def test_granting_a_project_to_another_org_makes_it_visible_to_that_orgs_owner(
    two_org_memberships: MembershipService,
) -> None:
    two_org_memberships.set_org_project_grants(20, [1])
    assert two_org_memberships.organizations_with_project_access(1, owning_organization_id=10) == {10, 20}
    # Org 20's owner clears the bar via role alone, same as any other project.
    assert two_org_memberships.member_can_access_project(20, "owner-2", 1) is True
    # A plain member of org 20 still needs a group grant -- being shared into
    # the org isn't a blanket grant to every one of its members.
    assert two_org_memberships.member_can_access_project(20, "member-2", 1) is False


def test_a_plain_member_of_the_grantee_org_needs_a_group_grant_too(
    two_org_memberships: MembershipService,
) -> None:
    two_org_memberships.set_org_project_grants(20, [1])
    group = two_org_memberships.create_group(20, "Auditors")
    two_org_memberships.set_member_group(20, "member-2", group["id"])
    two_org_memberships.set_group_project_grants(group["id"], [1])
    assert two_org_memberships.member_can_access_project(20, "member-2", 1) is True


def test_revoking_the_grant_removes_the_organization_from_project_access(
    two_org_memberships: MembershipService,
) -> None:
    two_org_memberships.set_org_project_grants(20, [1])
    two_org_memberships.set_org_project_grants(20, [])
    assert two_org_memberships.organizations_with_project_access(1, owning_organization_id=10) == {10}
