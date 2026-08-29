"""Tests verifying that analysis workflows pull rules from the database."""

from app.engines import (
    bimguard_corrosion_engine,
    bimguard_crevice_engine,
    bimguard_mic_engine,
)
from app.services.corrosion_rule_catalog import (
    load_cc_catalog,
    load_gc_catalog,
    load_mc_catalog,
    reload_all_catalogs,
)
from app.services.rules_service import RuleService


def test_corrosion_catalogs_load_from_db():
    """Verify that GC, CC, and MC catalogs load their rules and thresholds from DB."""
    gc_cat = load_gc_catalog()
    assert gc_cat["ruleset_id"] == "BIMGUARD-GC-001"
    assert "galvanic_series" in gc_cat
    assert len(gc_cat["galvanic_series"]) > 0
    assert "risk_band_thresholds" in gc_cat
    assert "medium" in gc_cat["risk_band_thresholds"]
    assert "scoring_model" in gc_cat

    cc_cat = load_cc_catalog()
    assert cc_cat["ruleset_id"] == "BIMGUARD-CC-001"
    assert "cct_table" in cc_cat
    assert len(cc_cat["cct_table"]) > 0
    assert "risk_band_thresholds" in cc_cat
    assert "scoring_model" in cc_cat

    mc_cat = load_mc_catalog()
    assert mc_cat["ruleset_id"] == "BIMGUARD-MC-001"
    assert "flow_velocity_classes" in mc_cat
    assert len(mc_cat["flow_velocity_classes"]) > 0
    assert "risk_band_thresholds" in mc_cat
    assert "scoring_model" in mc_cat


def test_engine_risk_classification_uses_db_thresholds(monkeypatch):
    """Verify engine risk band classification follows dynamically loaded catalog thresholds."""
    custom_gc_cat = {
        **bimguard_corrosion_engine._GC_CATALOG,
        "risk_band_thresholds": {"medium": 0.50, "high": 0.70, "critical": 0.90},
    }
    monkeypatch.setattr(bimguard_corrosion_engine, "_GC_CATALOG", custom_gc_cat)

    band, priority = bimguard_corrosion_engine.classify_gc001_risk(0.40)
    assert band == "Low"

    band, priority = bimguard_corrosion_engine.classify_gc001_risk(0.55)
    assert band == "Medium"


def test_engine_scoring_weights_use_db_model(monkeypatch):
    """Verify engine composite scoring weights are pulled from DB scoring model."""
    custom_gc_cat = {
        **bimguard_corrosion_engine._GC_CATALOG,
        "scoring_model": {"weights": {"voltage_risk": 0.8, "area_ratio_risk": 0.1, "environment_multiplier": 0.1}},
    }
    monkeypatch.setattr(bimguard_corrosion_engine, "_GC_CATALOG", custom_gc_cat)

    score = bimguard_corrosion_engine.calculate_gc001_score(1.0, 0.0, 0.0)
    assert round(score, 2) == 0.80


def test_flow_velocity_classification_uses_db_classes():
    """Verify flow velocity classification evaluates dynamically against DB class thresholds."""
    # Stagnant
    cls_key, data = bimguard_mic_engine.classify_flow_velocity(0.0)
    assert cls_key == "FV0_STAGNANT"
    assert data["risk"] == 1.0

    # Low velocity
    cls_key, data = bimguard_mic_engine.classify_flow_velocity(0.05)
    assert cls_key == "FV1_VERY_LOW"


def test_reload_all_catalogs_refreshes_engines():
    """Verify reload_all_catalogs executes and updates all three corrosion engines."""
    reload_all_catalogs()
    assert len(bimguard_corrosion_engine.GALVANIC_SERIES) > 0
    assert len(bimguard_crevice_engine.CCT_TABLE) > 0
    assert len(bimguard_mic_engine.FLOW_VELOCITY_CLASSES) > 0


def test_orchestrator_pulls_rules_by_folder_from_db():
    """Verify RuleService list_by_ruleset retrieves DB rules for custom rule folders."""
    svc = RuleService()
    folders = svc.list_folders()
    assert len(folders) > 0

    first_folder = folders[0]["ruleset_id"]
    rules_in_folder = svc.list_by_ruleset(first_folder)
    assert isinstance(rules_in_folder, list)
    for r in rules_in_folder:
        assert r.get("ruleset_id") == first_folder
