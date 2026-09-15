"""Unit tests for app.api.documents._no_parsing_engine_detail's permission-aware messaging."""

from __future__ import annotations

from types import SimpleNamespace

from app.api.documents import _no_parsing_engine_detail
from app.modules.permissions import Action


class _FakePermissions:
    def __init__(self, allowed: bool):
        self._allowed = allowed

    def can(self, organization_id: int, user_id: str, action: Action) -> bool:
        assert action == Action.MANAGE_PARSING_ENGINES
        return self._allowed


def test_self_serve_message_when_caller_can_manage_parsing_engines():
    current_user = SimpleNamespace(id="owner-1")
    detail = _no_parsing_engine_detail(1, current_user, _FakePermissions(allowed=True))
    assert "External Providers" in detail
    assert "ask" not in detail.lower()


def test_ask_admin_message_when_caller_cannot_manage_parsing_engines():
    current_user = SimpleNamespace(id="member-1")
    detail = _no_parsing_engine_detail(1, current_user, _FakePermissions(allowed=False))
    assert "ask an organization owner or admin" in detail.lower()


def test_ask_admin_message_when_no_organization_context():
    current_user = SimpleNamespace(id="anon-1")
    detail = _no_parsing_engine_detail(None, current_user, _FakePermissions(allowed=True))
    assert "ask an organization owner or admin" in detail.lower()
