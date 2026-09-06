"""Tests for the deterministic Finding Report narratives.

The contract these lock down is that a description names every input class with
its measured value and the threshold it crossed, and closes on the composite
against the band boundary. A narrative that silently drops a term reads exactly
like one where the term was fine, which is the failure mode worth a test.
"""

from __future__ import annotations

import pytest

from app.modules.comparator.issue_schema import RiskBand, make_issue
from app.modules.phase_6.finding_narrative import (
    build_description,
    build_mitigations,
)


def issue(code: str, band: RiskBand, score: float, *, mitigation: str = "", metadata=None):
    """Build a finished Issue the builders can narrate."""
    md = {"mechanism_code": code, "ruleset_version": f"BIMGUARD-{code} v1.0.0"}
    md.update(metadata or {})
    return make_issue(
        id="RPT-0001",
        element_id="GUID-1",
        rule_id=f"{code}.01",
        title="t",
        mechanism=f"{code} test",
        band=band,
        score=score,
        mitigation=mitigation,
        description="placeholder",
        metadata=md,
        citations=[],
    )


# ── MC-001 ────────────────────────────────────────────────────────────────────

MC_CATALOG = {
    "risk_band_thresholds": {"critical": 0.75},
    "flow_velocity_classes": {
        "FV0_STAGNANT": {"label": "Stagnant / dead-leg", "threshold_ms": 0.0, "reference": "CIBSE TM13:2013"},
    },
    "temperature_classes": {
        "T2_DANGER": {"range": "25–45°C", "reference": "CIBSE TM13:2013 — Legionella danger zone"},
    },
    "dead_leg_classes": {
        "DL3_LONG": {"label": "Long (> 10D)", "length_to_dia_ratio": "> 10", "reference": "HSE HSG274 Part 2"},
    },
}

MC_MEASUREMENTS = {
    "flow_velocity_class": "FV0_STAGNANT",
    "temperature_class": "T2_DANGER",
    "dead_leg_class": "DL3_LONG",
    "material_label": "",
    "material_source": "absent",
    "flow_velocity_ms": 0.0,
    "operating_temp_c": 30.0,
    "dead_leg_length_m": 2.5,
}


def test_mc_description_names_classes_values_score_and_boundary():
    text = build_description(
        issue("MC-001", RiskBand.CRITICAL, 0.958), MC_CATALOG, MC_MEASUREMENTS
    )
    for token in ("FV0_STAGNANT", "T2_DANGER", "DL3_LONG"):
        assert token in text, f"class {token} missing from: {text}"
    assert "0 m/s" in text
    assert "30 °C" in text
    assert "25–45°C" in text
    assert "CIBSE TM13:2013" in text
    assert "HSE HSG274 Part 2" in text
    assert "0.958" in text
    assert "0.75" in text
    assert "BIMGUARD-MC-001 v1.0.0" in text


def test_mc_absent_material_is_stated_not_dropped():
    text = build_description(
        issue("MC-001", RiskBand.CRITICAL, 0.958), MC_CATALOG, MC_MEASUREMENTS
    )
    assert "Material not recorded in the model; default susceptibility applied." in text


def test_mc_band_without_published_boundary_says_so():
    """MC-001 publishes only a Critical boundary; Medium must not invent one."""
    text = build_description(
        issue("MC-001", RiskBand.MEDIUM, 0.42), MC_CATALOG, MC_MEASUREMENTS
    )
    assert "no numeric boundary is published for this band" in text


# ── GC-001 ────────────────────────────────────────────────────────────────────

GC_CATALOG = {
    "risk_band_thresholds": {"critical": 0.85, "high": 0.65, "medium": 0.35},
    "environment_classes": {"E2_NORMAL": {"label": "Normal heated indoor", "voltage_threshold": 0.25}},
}

GC_MEASUREMENTS = {
    "material_anode_label": "Galvanised steel",
    "material_cathode_label": "Copper",
    "voltage_gap_v": 0.27,
    "env_threshold_v": 0.25,
    "environment_class": "E2_NORMAL",
    "area_ratio": 0.1,
    "area_ratio_band": "Unfavourable",
    "galvanic_couple": "bimetallic_pair_from_model",
}


def test_gc_description_names_materials_gap_threshold_ratio_and_boundary():
    text = build_description(issue("GC-001", RiskBand.MEDIUM, 0.59), GC_CATALOG, GC_MEASUREMENTS)
    assert "Galvanised steel" in text and "Copper" in text
    assert "0.27 V" in text
    assert "0.25 V" in text
    assert "Normal heated indoor" in text and "E2_NORMAL" in text
    assert "Unfavourable" in text
    assert "0.59" in text and "0.35" in text
    assert "BIMGUARD-GC-001 v1.0.0" in text


# ── CC-001 ────────────────────────────────────────────────────────────────────

CC_CATALOG = {
    "risk_band_thresholds": {"critical": 0.8, "high": 0.55, "medium": 0.3},
    "geometry_classes": {"Tight": {"description": "Weld neck flanges, compression fittings, lap joints"}},
    "environment_severity": {"T2_INTERMITTENT": {"label": "Intermittent wetting", "chloride_mgl": "< 50"}},
}

CC_MEASUREMENTS = {
    "joint_type_label": "Weld neck flange",
    "geometry_class": "Tight",
    "material_label": "SS 316 / 1.4401",
    "cct_value_c": 10.0,
    "operating_temp_c": 60.0,
    "environment_severity_key": "T2_INTERMITTENT",
}


def test_cc_description_names_joint_cct_environment_and_boundary():
    text = build_description(issue("CC-001", RiskBand.HIGH, 0.643), CC_CATALOG, CC_MEASUREMENTS)
    assert "Weld neck flange" in text and "Tight" in text
    assert "SS 316 / 1.4401" in text
    assert "10 °C" in text and "60 °C" in text
    assert "ASTM G48 Method B" in text
    assert "Intermittent wetting" in text and "T2_INTERMITTENT" in text
    assert "0.643" in text and "0.55" in text


# ── MM-001 / XM-001 ───────────────────────────────────────────────────────────


def test_mm_description_names_cell_verdict_and_environment():
    md = {
        "material": "SS316",
        "medium": "pool_water",
        "environment_class": "T3_chloride",
        "environment_severity": "0.8",
        "operating_temperature_c": "28.0",
        "temperature_stress": "0.35",
        "compatibility_score": "0.85",
        "failure_mechanism": "chloride_pitting_and_SCC",
        "predicted_lifespan_years": "8",
    }
    text = build_description(
        issue("MM-001", RiskBand.HIGH, 0.708, metadata=md),
        {"risk_band_thresholds": {"high": 0.55}},
    )
    assert "SS316" in text and "pool_water" in text
    assert "0.85" in text and "T3_chloride" in text
    assert "chloride pitting and SCC" in text
    assert "0.708" in text and "0.55" in text


def test_xm_description_names_both_materials_joint_and_pairing():
    md = {
        "anode_id": "CHW-P05",
        "cathode_id": "CHW-M06",
        "anode_material": "CarbonSteel",
        "cathode_material": "SS316",
        "voltage_gap_v": "0.47",
        "separation": "direct_contact",
        "separation_factor": "1.0",
        "environment_class": "T2_humid",
        "environment_severity": "0.4",
        "mitigated": "False",
    }
    text = build_description(
        issue("XM-001", RiskBand.MEDIUM, 0.615, metadata=md),
        {"risk_band_thresholds": {"medium": 0.3}},
    )
    assert "CarbonSteel" in text and "SS316" in text
    assert "0.47 V" in text
    assert "direct contact" in text
    assert "T2_humid" in text
    assert "unmitigated" in text
    assert "0.615" in text and "0.3" in text


# ── mitigations ───────────────────────────────────────────────────────────────

MIT_CATALOG = {
    "mitigations": {
        "MIT-MIC-001": "Eliminate dead-leg — reconfigure pipework to active through-flow configuration (HSE HSG274 preferred solution)",
        "MIT-MIC-003": "Increase design flow velocity to minimum 0.3 m/s — revise pipe sizing or reroute to reduce network length",
    }
}


def test_mitigations_resolve_every_known_code():
    got = build_mitigations(
        issue("MC-001", RiskBand.CRITICAL, 0.9, mitigation="MIT-MIC-001; MIT-MIC-003"),
        MIT_CATALOG,
    )
    assert [m["code"] for m in got] == ["MIT-MIC-001", "MIT-MIC-003"]
    assert got[0]["title"] == "Eliminate dead-leg"
    assert got[0]["description"].startswith("Eliminate dead-leg —")
    assert all(m["description"] for m in got)
    # addresses is filled from the catalogue's own wording, not invented.
    assert got[0].get("addresses")


def test_unknown_mitigation_code_yields_placeholder_not_exception():
    got = build_mitigations(
        issue("MC-001", RiskBand.CRITICAL, 0.9, mitigation="MIT-MIC-001; MIT-MIC-999"),
        MIT_CATALOG,
    )
    assert got[1] == {"code": "MIT-MIC-999", "title": "Unlisted mitigation", "description": ""}


def test_free_prose_mitigation_passes_through():
    """MM-001 and XM-001 emit prose, not codes; it must survive intact."""
    prose = "Break metallic continuity with a dielectric union."
    got = build_mitigations(issue("XM-001", RiskBand.MEDIUM, 0.6, mitigation=prose), {})
    assert got == [{"code": "", "title": "Recommended action", "description": prose}]


def test_no_mitigation_yields_empty_list():
    assert build_mitigations(issue("MC-001", RiskBand.LOW, 0.1, mitigation=""), MIT_CATALOG) == []


# ── data-quality notes ────────────────────────────────────────────────────────


def test_data_quality_note_text_is_unchanged():
    """A data-quality note has no mechanism builder and keeps its own reason."""
    original = (
        "Flow velocity, temperature and dead-leg length are absent from the "
        "model, so MC-001 could not score this element."
    )
    dq = make_issue(
        id="RPT-0002",
        element_id="GUID-2",
        rule_id="MC-001.DATA",
        title="Unassessed",
        mechanism="data_quality",
        band=RiskBand.LOW,
        score=0.1,
        mitigation="",
        description=original,
        metadata={"check": "hydraulic_data_unavailable"},
        citations=[],
    )
    assert build_description(dq, MC_CATALOG) == original


@pytest.mark.parametrize("code", ["GC-001", "CC-001", "MC-001"])
def test_builder_failure_falls_back_to_existing_description(code):
    """A narrative must never take a finding down with it."""
    i = issue(code, RiskBand.HIGH, 0.7)
    # A catalog of the wrong shape makes every table lookup fail.
    assert build_description(i, {"risk_band_thresholds": None}, {"bad": object()})
