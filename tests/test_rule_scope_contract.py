"""A rule's scope (``applies_when``) round-trips through the rule API contracts.

The manual rule editor sets a room type by writing ``applies_when``. That only
works if an edit can save it (``RuleUpdateRequest`` / ``RuleService.update_rule``)
and the editor can read it back (``RuleResponse``) so it neither loses a scope a
rule already had nor overwrites the other keys in it.
"""

from __future__ import annotations

import json

import pytest

from app.modules.contracts import RuleResponse, RuleUpdateRequest
from app.services.rules_service import RuleService


class TestRuleResponseDecodesTheStoredScope:
    def test_a_stored_json_string_becomes_a_dict(self):
        response = RuleResponse(id=1, applies_when='{"room_type_any_of": ["bedroom"]}')
        assert response.applies_when == {"room_type_any_of": ["bedroom"]}

    def test_an_already_decoded_dict_passes_through(self):
        response = RuleResponse(id=1, applies_when={"material_any_of": ["gypsum"]})
        assert response.applies_when == {"material_any_of": ["gypsum"]}

    @pytest.mark.parametrize("stored", [None, "", "  ", "{}", {}, "not json"])
    def test_no_scope_reads_as_null(self, stored):
        assert RuleResponse(id=1, applies_when=stored).applies_when is None

    def test_a_row_without_the_column_reads_as_null(self):
        assert RuleResponse(id=1).applies_when is None


class TestRuleUpdateRequestScope:
    def test_omitting_it_leaves_the_scope_alone(self):
        assert "applies_when" not in RuleUpdateRequest(description="x").model_dump(exclude_unset=True)

    def test_an_empty_dict_is_an_explicit_clear(self):
        assert RuleUpdateRequest(applies_when={}).model_dump(exclude_unset=True) == {"applies_when": {}}

    def test_a_scope_is_carried_through(self):
        payload = RuleUpdateRequest(applies_when={"room_type_any_of": ["kitchen"]})
        assert payload.model_dump(exclude_unset=True)["applies_when"] == {"room_type_any_of": ["kitchen"]}


class _FakeRules:
    """Stands in for the rules table, recording what update_rule writes."""

    def __init__(self):
        self.updates: dict = {}

    def update(self, updates, pk_values):
        self.updates = updates


@pytest.fixture()
def service():
    svc = object.__new__(RuleService)
    svc._rules = _FakeRules()
    svc.get_rule = lambda rule_id: {
        "ruleset_id": "TEST-SET",
        "mechanism": "CODE",
        "applies_when": '{"storey_any_of": ["L01"]}',
    }
    svc._ensure_folder = lambda *args, **kwargs: None
    svc._drop_folder_if_orphan = lambda *args, **kwargs: None
    return svc


class TestUpdateRuleWritesTheScope:
    def test_a_supplied_scope_replaces_the_stored_one(self, service):
        service.update_rule(1, applies_when={"room_type_any_of": ["bedroom"]})
        assert json.loads(service._rules.updates["applies_when"]) == {"room_type_any_of": ["bedroom"]}

    def test_an_empty_scope_clears_it(self, service):
        service.update_rule(1, applies_when={})
        assert json.loads(service._rules.updates["applies_when"]) == {}

    def test_omitting_it_does_not_touch_the_stored_scope(self, service):
        service.update_rule(1, description="reworded")
        assert "applies_when" not in service._rules.updates
