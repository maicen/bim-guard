"""Load extended building-code rules from canonical JSON rulesets."""

from __future__ import annotations

import json
from pathlib import Path


_RULESETS_DIR = Path(__file__).resolve().parents[3] / "data" / "rulesets"
_RULESET_CANDIDATES = (
    _RULESETS_DIR / "building_code_part9_ext_ruleset.json",
)


def _resolve_ruleset_path() -> Path:
    """Return the first available extended ruleset path."""
    for path in _RULESET_CANDIDATES:
        if path.exists():
            return path
    return _RULESET_CANDIDATES[0]


def _load_extended_rules() -> list[dict]:
    """Read extended code rules from the JSON ruleset file."""
    payload = json.loads(_resolve_ruleset_path().read_text(encoding="utf-8"))
    rules = payload.get("rules")
    if not isinstance(rules, list):
        raise ValueError("Invalid extended ruleset: expected a 'rules' array")
    return rules


EXTENDED_CODE_RULES = _load_extended_rules()
