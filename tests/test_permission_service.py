"""Unit tests for PermissionService's org-override-over-platform-default matrix.

Uses in-process fakes for the repo/membership/profile collaborators rather
than a live Supabase table, since these tests exercise pure role-evaluation
logic.
"""

from __future__ import annotations

import itertools
from types import SimpleNamespace

import pytest

from app.modules.permissions import Action
from app.services.permission_service import PermissionService


class _FakeRepo:
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

    def update(self, *, updates: dict, pk_values) -> None:
        row = self._rows.get(pk_values)
        if row:
            row.update(updates)

    def delete(self, pk) -> None:
        self._rows.pop(pk, None)


class _FakeMemberships:
    def __init__(self, roles: dict[tuple[int, str], str]):
        self._roles = roles

    def role_for_user(self, organization_id: int, user_id: str) -> str | None:
        return self._roles.get((organization_id, user_id))


class _FakeProfiles:
    def __init__(self, superadmins: set[str] = frozenset()):
        self._superadmins = superadmins

    def is_superadmin(self, user_id: str) -> bool:
        return user_id in self._superadmins


def _service(roles=None, superadmins=None):
    return PermissionService(
        role_permissions_repo=_FakeRepo(),
        membership_service=_FakeMemberships(roles or {}),
        profile_service=_FakeProfiles(superadmins or set()),
    )


def test_default_matrix_reproduces_admin_only_behavior():
    service = _service(roles={(1, "alice"): "admin", (1, "bob"): "member"})

    assert service.can(1, "alice", Action.MANAGE_ORG_MEMBERS) is True
    assert service.can(1, "bob", Action.MANAGE_ORG_MEMBERS) is False


def test_superadmin_bypasses_matrix_entirely():
    service = _service(roles={}, superadmins={"root"})
    assert service.can(1, "root", Action.MANAGE_ORG_MEMBERS) is True


def test_org_override_changes_can_result():
    service = _service(roles={(1, "bob"): "member"})
    assert service.can(1, "bob", Action.MANAGE_ORG_MEMBERS) is False

    service.set_min_role(1, Action.MANAGE_ORG_MEMBERS, "member")
    assert service.can(1, "bob", Action.MANAGE_ORG_MEMBERS) is True


def test_org_override_does_not_leak_to_other_orgs():
    service = _service(roles={(1, "bob"): "admin", (2, "carol"): "admin"})
    service.set_min_role(1, Action.MANAGE_ORG_MEMBERS, "owner")

    assert service.can(1, "bob", Action.MANAGE_ORG_MEMBERS) is False
    assert service.can(2, "carol", Action.MANAGE_ORG_MEMBERS) is True


def test_reset_to_default_removes_override():
    service = _service(roles={(1, "bob"): "member"})
    service.set_min_role(1, Action.MANAGE_ORG_MEMBERS, "member")
    assert service.can(1, "bob", Action.MANAGE_ORG_MEMBERS) is True

    service.reset_to_default(1, Action.MANAGE_ORG_MEMBERS)
    assert service.can(1, "bob", Action.MANAGE_ORG_MEMBERS) is False


def test_require_raises_404_for_non_member():
    service = _service(roles={})
    current_user = SimpleNamespace(id="stranger")
    with pytest.raises(Exception) as exc_info:
        service.require(1, current_user, Action.MANAGE_ORG_MEMBERS)
    assert exc_info.value.status_code == 404


def test_require_raises_403_for_under_privileged_member():
    service = _service(roles={(1, "bob"): "member"})
    current_user = SimpleNamespace(id="bob")
    with pytest.raises(Exception) as exc_info:
        service.require(1, current_user, Action.MANAGE_ORG_MEMBERS)
    assert exc_info.value.status_code == 403


def test_require_passes_for_sufficiently_privileged_member():
    service = _service(roles={(1, "alice"): "owner"})
    current_user = SimpleNamespace(id="alice")
    service.require(1, current_user, Action.MANAGE_ORG_MEMBERS)


def test_get_effective_matrix_merges_org_override_over_platform_default():
    service = _service()
    matrix = service.get_effective_matrix(1)
    assert matrix[Action.MANAGE_ORG_MEMBERS] == "admin"

    service.set_min_role(1, Action.MANAGE_ORG_MEMBERS, "owner")
    matrix = service.get_effective_matrix(1)
    assert matrix[Action.MANAGE_ORG_MEMBERS] == "owner"
    assert service.get_effective_matrix(None)[Action.MANAGE_ORG_MEMBERS] == "admin"
