"""Tests for SCIM 2.0 provisioning: token auth, and the /api/scim/v2 router.

ScimTokenService and ScimService are exercised with in-process fakes (same
approach as tests/test_permission_service.py) rather than a live Supabase
table, since these are pure logic/service-layer tests. The router itself is
exercised through TestClient with app.api.dependencies overridden to a fake
ScimService, so no real Supabase Auth account or organization is touched.
"""

from __future__ import annotations

import itertools

import pytest
from starlette.testclient import TestClient

from app.api.dependencies import get_scim_service, get_scim_token_service
from app.main import app
from app.services.scim_service import ScimGroupNotFound, ScimService, ScimUserNotFound
from app.services.scim_token_service import ScimTokenService

# -- ScimTokenService ---------------------------------------------------------


class _FakeTokenRepo:
    def __init__(self):
        self._rows: dict[int, dict] = {}
        self._ids = itertools.count(1)

    @property
    def rows(self):
        return list(self._rows.values())

    def rows_where(self, where_sql, params=None, limit=None):
        assert where_sql == "organization_id = ?"
        org_id = params[0]
        matches = [r for r in self._rows.values() if r["organization_id"] == org_id]
        return matches[:limit] if limit is not None else matches

    def insert(self, payload: dict) -> dict:
        row = dict(payload)
        row["id"] = next(self._ids)
        self._rows[row["id"]] = row
        return dict(row)

    def update(self, *, updates: dict, pk_values) -> None:
        self._rows[pk_values].update(updates)

    def delete(self, pk_value) -> None:
        self._rows.pop(pk_value, None)


def test_mint_returns_token_that_authenticates_to_the_right_org():
    service = ScimTokenService(scim_tokens_repo=_FakeTokenRepo())
    token = service.mint(organization_id=7)

    assert service.authenticate(token) == 7


def test_mint_replaces_any_existing_token_for_the_organization():
    service = ScimTokenService(scim_tokens_repo=_FakeTokenRepo())
    first = service.mint(organization_id=1)
    second = service.mint(organization_id=1)

    assert service.authenticate(first) is None
    assert service.authenticate(second) == 1


def test_revoke_stops_authentication():
    service = ScimTokenService(scim_tokens_repo=_FakeTokenRepo())
    token = service.mint(organization_id=1)
    service.revoke(1)

    assert service.authenticate(token) is None


def test_authenticate_rejects_unknown_token():
    service = ScimTokenService(scim_tokens_repo=_FakeTokenRepo())
    assert service.authenticate("scim_not-a-real-token") is None


def test_status_reports_configured_and_revoked_state():
    service = ScimTokenService(scim_tokens_repo=_FakeTokenRepo())
    assert service.status(1) is None

    service.mint(1)
    status = service.status(1)
    assert status is not None
    assert not status.get("revoked_at")

    service.revoke(1)
    assert service.status(1)["revoked_at"]


# -- ScimService (Users/Groups <-> membership/profile mapping) ----------------


class _FakeMembershipsRepo:
    def __init__(self):
        self._memberships: list[dict] = []
        self._groups: dict[int, dict] = {}
        self._ids = itertools.count(1)

    def add_member(self, organization_id, user_id, role):
        for m in self._memberships:
            if m["organization_id"] == organization_id and m["user_id"] == user_id:
                m["role"] = role
                return dict(m)
        row = {"id": next(self._ids), "organization_id": organization_id, "user_id": user_id, "role": role, "group_id": None}
        self._memberships.append(row)
        return dict(row)

    def remove_member(self, organization_id, user_id):
        self._memberships = [
            m for m in self._memberships if not (m["organization_id"] == organization_id and m["user_id"] == user_id)
        ]

    def role_for_user(self, organization_id, user_id):
        return next(
            (m["role"] for m in self._memberships if m["organization_id"] == organization_id and m["user_id"] == user_id),
            None,
        )

    def list_members_raw(self, organization_id):
        return [dict(m) for m in self._memberships if m["organization_id"] == organization_id]

    def create_group(self, organization_id, name):
        gid = next(self._ids)
        self._groups[gid] = {"id": gid, "organization_id": organization_id, "name": name}
        return dict(self._groups[gid])

    def get_group(self, group_id):
        g = self._groups.get(group_id)
        return dict(g) if g else None

    def list_groups(self, organization_id):
        return [dict(g) for g in self._groups.values() if g["organization_id"] == organization_id]

    def set_member_group(self, organization_id, user_id, group_id):
        m = next(
            (m for m in self._memberships if m["organization_id"] == organization_id and m["user_id"] == user_id),
            None,
        )
        if m is None:
            raise ValueError("not a member")
        m["group_id"] = group_id

    def delete_group(self, organization_id, group_id):
        g = self._groups.get(group_id)
        if g is None or g["organization_id"] != organization_id:
            raise ValueError("not found")
        for m in self._memberships:
            if m.get("group_id") == group_id:
                m["group_id"] = None
        del self._groups[group_id]


class _FakeProfiles:
    def __init__(self):
        self._profiles: dict[str, dict] = {}

    def get(self, user_id):
        return self._profiles.get(user_id)

    def ensure_profile(self, user_id, *, full_name="", avatar_url="", email=""):
        if user_id not in self._profiles:
            self._profiles[user_id] = {"id": user_id, "full_name": full_name, "email": email}
        return self._profiles[user_id]

    def update(self, user_id, updates):
        self.ensure_profile(user_id)
        self._profiles[user_id].update(updates)
        return self._profiles[user_id]

    def get_many(self, user_ids):
        return {uid: self._profiles[uid] for uid in user_ids if uid in self._profiles}


class _FakeAuthAdmin:
    """Fake Supabase `.auth.admin` -- one seeded user, `new-user@example.com` creates a fresh id."""

    def __init__(self):
        self._users = [{"id": "existing-uid", "email": "existing@example.com"}]
        self._next = itertools.count(100)

    def list_users(self, page=1, per_page=200):
        return {"users": self._users if page == 1 else []}

    def create_user(self, payload):
        uid = f"created-{next(self._next)}"
        self._users.append({"id": uid, "email": payload["email"]})
        return {"user": {"id": uid}}


class _FakeDbClient:
    def __init__(self):
        self.auth = type("Auth", (), {"admin": _FakeAuthAdmin()})()


def _scim_service() -> ScimService:
    from app.services.membership_service import MembershipService

    repo = _FakeMembershipsRepo()
    memberships = MembershipService.__new__(MembershipService)
    # Bypass MembershipService's real constructor (which wants 6 distinct
    # DatabaseAdapter repos) -- only the methods ScimService actually calls
    # are needed, and _FakeMembershipsRepo implements those directly, so
    # delegate every relevant attribute to it.
    for name in (
        "add_member",
        "remove_member",
        "role_for_user",
        "list_members_raw",
        "create_group",
        "get_group",
        "list_groups",
        "set_member_group",
        "delete_group",
    ):
        setattr(memberships, name, getattr(repo, name))
    return ScimService(membership_service=memberships, profile_service=_FakeProfiles(), db_client=_FakeDbClient())


def test_create_user_reuses_existing_auth_account_by_email():
    scim = _scim_service()
    row = scim.create_user(1, user_name="existing@example.com", full_name="Existing Person")

    assert row["id"] == "existing-uid"
    assert row["active"] is True
    assert scim.get_user(1, "existing-uid")["user_name"] == "existing@example.com"


def test_create_user_provisions_a_new_auth_account_when_none_exists():
    scim = _scim_service()
    row = scim.create_user(1, user_name="new-user@example.com", full_name="New Person")

    assert row["id"].startswith("created-")
    assert row["active"] is True


def test_patch_user_active_false_deprovisions_without_touching_auth_identity():
    scim = _scim_service()
    row = scim.create_user(1, user_name="existing@example.com")
    user_id = row["id"]

    deactivated = scim.patch_user_active(1, user_id, False)
    assert deactivated["active"] is False
    with pytest.raises(ScimUserNotFound):
        scim.get_user(1, user_id)

    reactivated = scim.patch_user_active(1, user_id, True)
    assert reactivated["active"] is True


def test_delete_user_removes_membership_only():
    scim = _scim_service()
    row = scim.create_user(1, user_name="existing@example.com")
    scim.delete_user(1, row["id"])

    with pytest.raises(ScimUserNotFound):
        scim.get_user(1, row["id"])


def test_list_users_filters_by_user_name():
    scim = _scim_service()
    scim.create_user(1, user_name="existing@example.com")
    scim.create_user(1, user_name="new-user@example.com")

    total, rows = scim.list_users(1, user_name_filter="existing@example.com")
    assert total == 1
    assert rows[0]["user_name"] == "existing@example.com"


def test_group_lifecycle_create_replace_delete():
    scim = _scim_service()
    alice = scim.create_user(1, user_name="existing@example.com")["id"]
    bob = scim.create_user(1, user_name="new-user@example.com")["id"]

    group = scim.create_group(1, display_name="Estimators", member_ids=[alice])
    assert {m["value"] for m in group["members"]} == {alice}

    replaced = scim.replace_group(1, group["id"], display_name="Estimators", member_ids=[bob])
    assert {m["value"] for m in replaced["members"]} == {bob}

    scim.delete_group(1, group["id"])
    with pytest.raises(ScimGroupNotFound):
        scim.get_group(1, group["id"])


# -- Router: auth is enforced, and a mounted fake service round-trips --------

client = TestClient(app)


def test_scim_route_rejects_missing_token():
    resp = client.get("/api/scim/v2/Users")
    assert resp.status_code == 401


def test_scim_route_rejects_invalid_token():
    resp = client.get("/api/scim/v2/Users", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


def test_scim_users_round_trip_through_the_router():
    fake_service = _scim_service()
    fake_service.create_user(1, user_name="existing@example.com", full_name="Existing Person")

    class _FakeTokens:
        def authenticate(self, raw_token):
            return 1 if raw_token == "scim_test-token" else None

    app.dependency_overrides[get_scim_token_service] = lambda: _FakeTokens()
    app.dependency_overrides[get_scim_service] = lambda: fake_service
    try:
        resp = client.get("/api/scim/v2/Users", headers={"Authorization": "Bearer scim_test-token"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["totalResults"] == 1
        assert body["Resources"][0]["userName"] == "existing@example.com"

        create_resp = client.post(
            "/api/scim/v2/Users",
            headers={"Authorization": "Bearer scim_test-token"},
            json={"userName": "new-user@example.com", "active": True},
        )
        assert create_resp.status_code == 201
        assert create_resp.json()["userName"] == "new-user@example.com"

        new_user_id = create_resp.json()["id"]
        delete_resp = client.delete(
            f"/api/scim/v2/Users/{new_user_id}", headers={"Authorization": "Bearer scim_test-token"}
        )
        assert delete_resp.status_code == 204
    finally:
        app.dependency_overrides.pop(get_scim_token_service, None)
        app.dependency_overrides.pop(get_scim_service, None)
