"""Load extended building-code rules from database static assets."""

from __future__ import annotations

from app.services.static_data_service import StaticDataService

def _load_extended_rules() -> list[dict]:
    """Read extended code rules from database static assets."""
    payload = StaticDataService().get_asset_json("ruleset:BUILDING-CODE-PART9-EXT")
    if not isinstance(payload, dict):
        raise ValueError("Missing static asset ruleset:BUILDING-CODE-PART9-EXT")
    rules = payload.get("rules")
    if not isinstance(rules, list):
        raise ValueError("Invalid extended ruleset: expected a 'rules' array")
    return rules


EXTENDED_CODE_RULES = _load_extended_rules()
