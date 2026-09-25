"""
tests/test_rule_builder.py
----------------------
Unit tests for Module 3 — RuleGenerator (validation/enrichment path), RuleStore,
rule schema validation, and edge cases.

Run with: pytest tests/test_rule_builder.py -v

Test groups:
  - RuleStore:           basic CRUD, get_all_rules, clear
  - RuleGenerator:       enrichment, validation, save_batch
  - Schema validation:   field checks against the rich schema
"""

import pytest
from rule_builder.rule_generator import RuleGenerator
from rule_builder.rule_store import RuleStore

TEST_DB = "tests/test_rules_m3.db"


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def store(tmp_path):
    db_path = str(tmp_path / "test_rules_m3.db")
    s = RuleStore(db_path)
    s.clear_all_rules()
    yield s
    s.close()


@pytest.fixture
def gen(store):
    return RuleGenerator(store)


# ═══════════════════════════════════════════════════════════════════════════════
# RuleStore — basic operations
# ═══════════════════════════════════════════════════════════════════════════════


def test_store_starts_empty(store):
    assert store.count() == 0


def test_store_save_and_retrieve(store):
    rule = {
        "ref": "9.8.2.1.(2)",
        "rule_type": "numeric_comparison",
        "target": "IfcStairFlight",
        "property_name": "Width",
        "operator": ">=",
        "check_value": 860,
        "unit": "mm",
        "severity": "mandatory",
        "desc": "Exit stair minimum width 860 mm",
    }
    store.save_rule(rule)
    assert store.count() == 1

    rules = store.get_all_rules()
    assert len(rules) == 1
    assert rules[0]["target"] == "IfcStairFlight"
    assert rules[0]["check_value"] == 860


def test_store_clear(store):
    store.save_rule(
        {
            "ref": "A",
            "rule_type": "numeric_comparison",
            "target": "IfcStairFlight",
            "property_name": "Width",
            "operator": ">=",
            "check_value": 860,
            "desc": "stair width",
            "severity": "mandatory",
        }
    )
    store.save_rule(
        {
            "ref": "B",
            "rule_type": "numeric_comparison",
            "target": "IfcDoor",
            "property_name": "ClearWidth",
            "operator": ">=",
            "check_value": 800,
            "desc": "door width",
            "severity": "mandatory",
        }
    )
    assert store.count() == 2
    store.clear_all_rules()
    assert store.count() == 0


def test_store_get_all_rules_returns_dicts(store):
    store.save_rule(
        {
            "ref": "9.8.2",
            "rule_type": "numeric_comparison",
            "target": "IfcStairFlight",
            "property_name": "Width",
            "operator": ">=",
            "check_value": 860,
            "desc": "stair",
            "severity": "mandatory",
        }
    )
    rules = store.get_all_rules()
    assert isinstance(rules, list)
    assert isinstance(rules[0], dict)


def test_store_fetch_rules_for_target(store):
    store.save_rule(
        {
            "ref": "R1",
            "rule_type": "numeric_comparison",
            "target": "IfcStairFlight",
            "property_name": "Width",
            "operator": ">=",
            "check_value": 860,
            "desc": "stair width",
            "severity": "mandatory",
        }
    )
    store.save_rule(
        {
            "ref": "R2",
            "rule_type": "numeric_comparison",
            "target": "IfcDoor",
            "property_name": "Height",
            "operator": ">=",
            "check_value": 1980,
            "desc": "door height",
            "severity": "mandatory",
        }
    )
    stair_rules = store.fetch_rules_for_target("IfcStairFlight")
    assert len(stair_rules) == 1
    assert stair_rules[0]["target"] == "IfcStairFlight"


def test_store_handles_duplicate_rules(store):
    """Saving the same rule twice should not crash."""
    rule = {
        "ref": "X",
        "rule_type": "numeric_comparison",
        "target": "IfcStairFlight",
        "property_name": "Width",
        "operator": ">=",
        "check_value": 860,
        "desc": "dup",
        "severity": "mandatory",
    }
    store.save_rule(rule)
    store.save_rule(rule)
    assert store.count() >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# Schema validation helper
# ═══════════════════════════════════════════════════════════════════════════════

REQUIRED_RULE_FIELDS = {"target", "property_name", "operator", "rule_type", "desc"}

VALID_OPERATORS = {
    ">=",
    "<=",
    "==",
    "!=",
    "between",
    "exists",
    "not_exists",
    "matches",
    "conforms_to",
}


def validate_rule_schema(rule_data: dict) -> list:
    """Returns list of issues. Empty list = valid."""
    issues = []

    missing = REQUIRED_RULE_FIELDS - set(rule_data.keys())
    if missing:
        issues.append(f"Missing fields: {missing}")

    if "operator" in rule_data:
        op = rule_data["operator"]
        if op not in VALID_OPERATORS:
            issues.append(f"Unknown operator: '{op}'")

    if "rule_type" in rule_data:
        from config import VALID_RULE_TYPES

        if rule_data["rule_type"] not in VALID_RULE_TYPES:
            issues.append(f"Unknown rule_type: '{rule_data['rule_type']}'")

    return issues


# ═══════════════════════════════════════════════════════════════════════════════
# RuleGenerator — enrichment and validation
# ═══════════════════════════════════════════════════════════════════════════════


def test_generator_enriches_plain_target(gen, store):
    """Plain word like 'stair' should be mapped to 'IfcStairFlight'."""
    rule = {
        "ref": "9.8",
        "rule_type": "numeric_comparison",
        "target": "stair",
        "property_name": "Width",
        "operator": ">=",
        "check_value": 860,
        "desc": "stair width",
        "severity": "mandatory",
    }
    gen.save_single(rule)
    rules = store.get_all_rules()
    assert rules[0]["target"] == "IfcStairFlight"


def test_generator_auto_fills_property_set(gen, store):
    """property_set should be auto-filled from IFC_PROPERTY_SET_MAP when omitted."""
    rule = {
        "ref": "9.8",
        "rule_type": "numeric_comparison",
        "target": "IfcStairFlight",
        "property_name": "Width",
        "operator": ">=",
        "check_value": 860,
        "desc": "stair width",
        "severity": "mandatory",
    }
    gen.save_single(rule)
    rules = store.get_all_rules()
    assert rules[0].get("property_set") == "Pset_StairFlightCommon"


def test_generator_skips_invalid_operator(gen, store):
    """A rule with an unrecognised operator should be rejected."""
    rule = {
        "ref": "9.8",
        "rule_type": "numeric_comparison",
        "target": "IfcStairFlight",
        "property_name": "Width",
        "operator": "GREATER_THAN",  # invalid
        "check_value": 860,
        "desc": "stair width",
        "severity": "mandatory",
    }
    result = gen.save_single(rule)
    assert result is None
    assert store.count() == 0


def test_generator_skips_invalid_rule_type(gen, store):
    """A rule with an old/unknown rule_type should be rejected."""
    rule = {
        "ref": "9.8",
        "rule_type": "json_check",  # old name
        "target": "IfcStairFlight",
        "property_name": "Width",
        "operator": ">=",
        "check_value": 860,
        "desc": "stair width",
        "severity": "mandatory",
    }
    result = gen.save_single(rule)
    assert result is None
    assert store.count() == 0


def test_generator_numeric_range_requires_min_max(gen, store):
    """numeric_range without value_min/value_max should be rejected."""
    rule = {
        "ref": "T9.8.4.1",
        "rule_type": "numeric_range",
        "target": "IfcStairFlight",
        "property_name": "RiserHeight",
        "operator": "between",
        "check_value": None,
        # value_min and value_max intentionally omitted
        "desc": "riser height range",
        "severity": "mandatory",
    }
    result = gen.save_single(rule)
    assert result is None


def test_generator_numeric_range_saves_with_min_max(gen, store):
    """numeric_range with value_min/value_max should save successfully."""
    rule = {
        "ref": "T9.8.4.1",
        "rule_type": "numeric_range",
        "target": "IfcStairFlight",
        "property_name": "RiserHeight",
        "operator": "between",
        "check_value": None,
        "value_min": 125,
        "value_max": 200,
        "unit": "mm",
        "desc": "riser height range",
        "severity": "mandatory",
    }
    result = gen.save_single(rule)
    assert result is not None
    assert store.count() == 1


def test_generator_exists_operator_skips_check_value(gen, store):
    """Exists operator should not require check_value."""
    rule = {
        "ref": "QA",
        "rule_type": "prohibition",
        "target": "IfcDoor",
        "property_name": "Width",
        "operator": "exists",
        "check_value": None,
        "desc": "door must have Width property",
        "severity": "informational",
    }
    result = gen.save_single(rule)
    assert result is not None


def test_generator_save_batch_counts_saved(gen, store):
    """save_batch should save valid rules and skip invalid ones."""
    rules = [
        {
            "ref": "A",
            "rule_type": "numeric_comparison",
            "target": "IfcStairFlight",
            "property_name": "Width",
            "operator": ">=",
            "check_value": 860,
            "desc": "stair width",
            "severity": "mandatory",
        },
        {
            "ref": "B",
            "rule_type": "json_check",  # invalid — should be skipped
            "target": "IfcDoor",
            "property_name": "Height",
            "operator": ">=",
            "check_value": 1980,
            "desc": "door height",
            "severity": "mandatory",
        },
        {
            "ref": "C",
            "rule_type": "numeric_range",
            "target": "IfcStairFlight",
            "property_name": "TreadDepth",
            "operator": "between",
            "check_value": None,
            "value_min": 255,
            "value_max": 355,
            "desc": "tread depth",
            "severity": "mandatory",
        },
    ]
    saved = gen.save_batch(rules)
    assert len(saved) == 2  # A and C pass; B fails
    assert store.count() == 2

