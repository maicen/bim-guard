"""Coverage for the door and window core-property rulesets under data/rulesets/."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.modules.config import VALID_OPERATORS

_RULESET_DIR = Path(__file__).resolve().parents[1] / "data" / "rulesets"

_RULESETS = [
    ("bimguard_door_core_20_ruleset.json", "BIMGUARD-DOOR-CORE-20", "IfcDoor"),
    ("bimguard_window_core_20_ruleset.json", "BIMGUARD-WINDOW-CORE-20", "IfcWindow"),
]


@pytest.mark.rules
@pytest.mark.parametrize(("filename", "ruleset_id", "ifc_class"), _RULESETS)
def test_core_ruleset_is_well_formed(filename, ruleset_id, ifc_class):
    payload = json.loads((_RULESET_DIR / filename).read_text(encoding="utf-8"))
    rules = payload["rules"]

    assert payload["ruleset_id"] == ruleset_id
    # The database only accepts the Arch category.
    assert payload["category"] == "Arch"
    assert len(rules) == 20
    assert len({r["reference"] for r in rules}) == 20
    for rule in rules:
        assert rule["target_ifc_class"] == ifc_class
        assert rule["description"]
        assert rule["property_name"]
        assert rule["check_category"]
        # "documented" is a comparator operator outside VALID_OPERATORS.
        assert rule["operator"] in {*VALID_OPERATORS, "documented"}
        if rule["operator"] not in ("exists", "documented"):
            assert "check_value" in rule


@pytest.mark.rules
@pytest.mark.parametrize(("filename", "_ruleset_id", "_ifc_class"), _RULESETS)
def test_illustrative_thresholds_are_flagged_for_review(filename, _ruleset_id, _ifc_class):
    """A threshold that is not from a cited code must not read as verified."""
    payload = json.loads((_RULESET_DIR / filename).read_text(encoding="utf-8"))
    for rule in payload["rules"]:
        assert rule["description"].startswith("Illustrative threshold") == rule["needs_review"]
