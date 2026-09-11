"""Tests for wiring CDEStateMachine's Gate 1 filename check to a project's naming config.

Prefers the configured convention (`project_naming_config`) instead of
always enforcing the default 7-field ISO19650Validator scheme regardless of
what a project chose.
"""

from __future__ import annotations

from app.services.cde_state_machine import CDEStateMachine
from app.services.naming_config_service import DEFAULTS, NamingConfigService


class _StubNamingConfigService(NamingConfigService):
    """A NamingConfigService whose `get_for_project` is fixed, no DB access."""

    def __init__(self, config: dict | None) -> None:
        # Deliberately skips the real __init__ / DB adapter wiring.
        self._config = config

    def get_for_project(self, project_id: int) -> dict:
        if self._config is None:
            return {"project_id": project_id, "is_configured": False, **DEFAULTS}
        return self._config


def test_build_pattern_matches_a_rendered_name():
    service = NamingConfigService.__new__(NamingConfigService)
    config = {
        **DEFAULTS,
        "project_code": "PRJ1",
        "originator_code": "BIMG",
        "active_convention": "iso19650",
        "separator": "_",
    }
    name = service.render_name(config)
    is_valid, fields, errors = service.validate_name(config, name + ".ifc")
    assert is_valid, errors
    assert fields["project"] == "PRJ1"
    assert fields["originator"] == "BIMG"


def test_validate_name_rejects_a_non_matching_name():
    service = NamingConfigService.__new__(NamingConfigService)
    config = {**DEFAULTS, "active_convention": "iso19650", "separator": "_"}
    is_valid, _fields, errors = service.validate_name(config, "totally-different-scheme.ifc")
    assert not is_valid
    assert errors


def test_gate1_uses_configured_convention_when_project_has_one():
    naming = NamingConfigService.__new__(NamingConfigService)
    config = {
        **DEFAULTS,
        "project_code": "PRJ1",
        "originator_code": "BIMG",
        "active_convention": "iso19650",
        "separator": "_",
        "is_configured": True,
    }
    filename = naming.render_name(config) + ".ifc"

    stub = _StubNamingConfigService(config)
    result = CDEStateMachine.evaluate_transition(
        "WIP",
        "SHARED",
        filename=filename,
        project_id=42,
        naming_config_service=stub,
    )
    assert result.allowed, result.reason

    # The same filename fails the *default* ISO19650Validator 7-field
    # hyphenated scheme, proving the configured convention -- not the
    # fallback -- is what actually validated it.
    default_result = CDEStateMachine.evaluate_transition(
        "WIP", "SHARED", filename=filename, project_id=None
    )
    assert not default_result.allowed


def test_gate1_falls_back_to_default_scheme_when_unconfigured():
    stub = _StubNamingConfigService(None)
    # Default 7-field ISO scheme, valid per ISO19650Validator.
    result = CDEStateMachine.evaluate_transition(
        "WIP",
        "SHARED",
        filename="PRJ1-BIMG-01-00-M3-A-0001.ifc",
        project_id=99,
        naming_config_service=stub,
    )
    assert result.allowed, result.reason
