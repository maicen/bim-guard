"""Regression tests for the offline GC-001 fallback catalog.

Without a reachable rules store the corrosion engines run on
``corrosion_rule_catalog._FALLBACK_RULESETS``. That table once mapped the
``pool`` zone keyword to ``E6_POOL`` without defining the class, so
``classify_environment`` raised ``KeyError`` and the galvanic validation demo
(and any offline BCF export containing a pool element) aborted. These tests
pin both halves of the fix: the fallback is self-consistent, and the engine
tolerates an undefined class regardless of which catalog is loaded.
"""

from __future__ import annotations

import pytest

from app.engines import bimguard_corrosion_engine as gc
from app.engines import bimguard_crevice_engine as cc
from app.services import corrosion_rule_catalog as catalog
from app.services.corrosion_rule_catalog import _FALLBACK_RULESETS

_GC_FALLBACK = _FALLBACK_RULESETS["galvanic_corrosion_ruleset.json"]
_CC_FALLBACK = _FALLBACK_RULESETS["crevice_corrosion_ruleset.json"]


def test_fallback_zone_map_targets_are_all_defined():
    """Every ``zone_to_env`` target must exist in the fallback ``environment_classes``."""
    classes = set(_GC_FALLBACK["environment_classes"])
    missing = {zone: env for zone, env in _GC_FALLBACK["zone_to_env"].items() if env not in classes}
    assert not missing, f"fallback zone_to_env points at undefined classes: {missing}"


def test_fallback_pool_class_matches_seeded_ruleset():
    """The fallback pool class carries the seeded NASA-STD-6012 values."""
    pool = _GC_FALLBACK["environment_classes"]["E6_POOL"]
    assert pool["voltage_threshold_v"] == pytest.approx(0.10)
    assert pool["multiplier"] == pytest.approx(0.90)


def test_classify_environment_survives_undefined_class(monkeypatch):
    """A zone mapped to a class the catalog lacks degrades to E2_NORMAL, not KeyError."""
    monkeypatch.setattr(gc, "ZONE_TO_ENV", {"pool": "E9_UNDEFINED", "plant room": "E3_HUMID"})
    monkeypatch.setattr(
        gc,
        "ENVIRONMENT_CLASSES",
        {
            "E2_NORMAL": {"label": "Normal", "voltage_threshold_v": 0.25, "multiplier": 0.4},
            "E3_HUMID": {"label": "Humid", "voltage_threshold_v": 0.15, "multiplier": 0.65},
        },
    )
    env_key, env = gc.classify_environment("Pool Plant")
    assert env_key == "E2_NORMAL"
    assert env["multiplier"] == pytest.approx(0.4)
    # A defined target is still honoured.
    assert gc.classify_environment("Plant Room")[0] == "E3_HUMID"


def test_galvanic_pool_element_assesses_on_fallback_catalog(monkeypatch):
    """A pool element scores on the reduced fallback table exactly as the offline path loads it."""
    monkeypatch.setattr(
        catalog, "_load_json_ruleset", lambda filename: _FALLBACK_RULESETS[filename]
    )
    monkeypatch.setattr(catalog, "_rules_for", lambda ruleset_id: [])
    loaded = catalog.load_gc_catalog()
    monkeypatch.setattr(gc, "ENVIRONMENT_CLASSES", loaded["environment_classes"])
    monkeypatch.setattr(gc, "ZONE_TO_ENV", loaded["zone_to_env"])
    pool = gc.GCElement(
        global_id_anode="GC-POOL-A",
        global_id_cathode="GC-POOL-B",
        material_anode="galvanised steel",
        material_cathode="SS316",
        anode_area_m2=1.0,
        cathode_area_m2=4.0,
        zone_category="swimming pool",
        floor="L1",
        system_type="Pool Plant",
    )
    result = gc.assess_galvanic_risk(pool)
    assert result.environment_class == "E6_POOL"
    assert result.risk_band in {"Low", "Medium", "High", "Critical"}


# ---------------------------------------------------------------------------
# CC-001
# ---------------------------------------------------------------------------


def test_fallback_cct_table_covers_every_alias_target():
    """Each grade the static alias map can resolve to must exist in the fallback CCT table."""
    grades = set(_CC_FALLBACK["cct_table"]["grades"])
    missing = {alias: key for alias, key in cc.CC_MATERIAL_ALIASES.items() if key not in grades}
    assert not missing, f"fallback cct_table lacks alias targets: {missing}"


def test_assess_crevice_risk_survives_undefined_grade(monkeypatch):
    """A material aliased to a grade the catalog lacks is assessed without a CCT value."""
    monkeypatch.setattr(cc, "CCT_TABLE", {"ss316_passive": {"cct_c": 10, "label": "SS 316"}})
    element = cc.CCElement(
        global_id="CC-SD-001",
        element_type="IfcPipeSegment",
        material="super duplex 2507",
        joint_description="weld neck flange",
        operating_temp_c=35.0,
        zone_category="pool",
        system_type="Pool Plant",
        floor="B1",
    )
    result = cc.assess_crevice_risk(element)
    assert result.material_label == "super duplex 2507"
    assert result.risk_band in {"Low", "Medium", "High", "Critical"}
