"""Seed built-in BIMGuard engine rulesets into the shared rules table.

The seeding operations are idempotent: each routine checks whether its
``ruleset_id`` already exists before inserting rows.
"""

import json

from app.services.rules_service import RuleService
from app.services.static_data_service import StaticDataService

_DEFAULT_CODE_RULESET_FILES = (
    "building_code_part9_ruleset.json",
    "building_code_part9_ext_ruleset.json",
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _load(filename: str) -> dict:
    asset_key_map = {
        "building_code_part9_ruleset.json": "ruleset:BUILDING-CODE-PART9",
        "building_code_part9_ext_ruleset.json": "ruleset:BUILDING-CODE-PART9-EXT",
        "galvanic_corrosion_ruleset.json": "ruleset:BIMGUARD-GC-001",
        "crevice_corrosion_ruleset.json": "ruleset:BIMGUARD-CC-001",
        "mic_corrosion_ruleset.json": "ruleset:BIMGUARD-MC-001",
    }

    asset_key = asset_key_map.get(filename)
    if asset_key:
        payload = StaticDataService().get_asset_json(asset_key)
        if isinstance(payload, dict):
            return payload
    raise RuntimeError(f"Missing static ruleset asset: {filename}")


def _create(svc: RuleService, **kwargs) -> None:
    """Thin wrapper that sets extraction_method='seed' by default."""
    kwargs.setdefault("extraction_method", "seed")
    kwargs.setdefault("severity", "mandatory")
    svc.create_rule(**kwargs)


def _seed_json_ruleset(svc: RuleService, filename: str) -> int:
    """Seed one ruleset JSON document via RuleService.import_ruleset()."""
    payload = _load(filename)
    ruleset_id = str(payload.get("ruleset_id") or "").strip()
    if not ruleset_id:
        raise ValueError(f"Ruleset file '{filename}' is missing ruleset_id")
    if svc.has_ruleset(ruleset_id):
        return 0
    return svc.import_ruleset(payload)


def seed_architectural_code_rules(svc: RuleService) -> int:
    """Ensure hardcoded architectural egress, exit, daylight, and fire separation rules exist in DB."""
    count = 0
    rules_to_seed = [
        {
            "reference": "CODE 9.9.10.1",
            "rule_type": "egress_path",
            "rule_category": "circulation",
            "description": "Maximum egress travel distance from habitable room to exit — 25.0 m",
            "target_ifc_class": "IfcSpace",
            "property_name": "TravelDistance",
            "operator": "<=",
            "check_value": 25.0,
            "unit": "m",
            "ruleset_id": "BUILDING-CODE-PART9",
            "mechanism": "CODE",
            "category": "Arch",
            "severity": "mandatory",
        },
        {
            "reference": "CODE 9.9.4.1",
            "rule_type": "numeric_comparison",
            "rule_category": "circulation",
            "description": "Minimum number of exterior exits per building storey — 1",
            "target_ifc_class": "IfcBuildingStorey",
            "property_name": "ExitCount",
            "operator": ">=",
            "check_value": 1.0,
            "unit": "count",
            "ruleset_id": "BUILDING-CODE-PART9",
            "mechanism": "CODE",
            "category": "Arch",
            "severity": "mandatory",
        },
        {
            "reference": "CODE 9.7.2.3",
            "rule_type": "spatial_adjacency",
            "rule_category": "daylight",
            "description": "Minimum window glazing area to floor area ratio for habitable spaces — 1/10 (0.10)",
            "target_ifc_class": "IfcSpace",
            "property_name": "DaylightRatio",
            "operator": ">=",
            "check_value": 0.10,
            "unit": "ratio",
            "ruleset_id": "BUILDING-CODE-PART9",
            "mechanism": "CODE",
            "category": "Arch",
            "severity": "mandatory",
        },
        {
            "reference": "CODE 9.10.9.14.PW",
            "rule_type": "spatial_adjacency",
            "rule_category": "fire_safety",
            "description": "Fire-rated wall between dwelling units (party wall) — minimum 45-minute fire resistance",
            "target_ifc_class": "IfcWall",
            "property_name": "FireRating",
            "operator": ">=",
            "check_value": 45.0,
            "unit": "min",
            "ruleset_id": "BUILDING-CODE-PART9",
            "mechanism": "CODE",
            "category": "Arch",
            "severity": "mandatory",
        },
    ]

    existing_refs = {
        str(r.get("reference") or "")
        for r in svc.list_rules()
    }

    for item in rules_to_seed:
        if item["reference"] not in existing_refs:
            _create(svc, **item)
            count += 1

    return count


def seed_default_code_rulesets(svc: RuleService) -> dict[str, int]:
    """Seed baseline/extended building-code rulesets from JSON files."""
    seeded: dict[str, int] = {}
    for filename in _DEFAULT_CODE_RULESET_FILES:
        payload = _load(filename)
        ruleset_id = str(payload.get("ruleset_id") or "").strip() or filename
        seeded[ruleset_id] = _seed_json_ruleset(svc, filename)
    seed_architectural_code_rules(svc)
    return seeded


def _seed_risk_bands(
    svc: RuleService,
    *,
    ruleset_id: str,
    prefix: str,
    bands: dict,
    target_ifc_class: str = "IfcPipeSegment",
) -> None:
    """Seed composite-score threshold rows for a ruleset."""
    for band_name, band_data in bands.items():
        if band_name not in {"Medium", "High", "Critical"}:
            continue
        range_text = str((band_data or {}).get("range") or "")
        threshold = None
        if "-" in range_text:
            threshold = range_text.split("-", 1)[0].strip().strip("<>")
        elif ">" in range_text:
            threshold = range_text.replace(">", "").strip()
        _create(
            svc,
            reference=f"{prefix}.BAND.{band_name.upper()}",
            rule_type="risk_band",
            rule_category="threshold_band",
            description=band_data.get("bcf_action", band_name),
            check_value=threshold,
            keyword=band_name,
            ruleset_id=ruleset_id,
            target_ifc_class=target_ifc_class,
            parameters=json.dumps({"band": band_name, **band_data}),
        )


# ── GC-001 — Galvanic Corrosion ───────────────────────────────────────────────


def _seed_gc001(svc: RuleService) -> int:
    RULESET_ID = "BIMGUARD-GC-001"
    if svc.has_ruleset(RULESET_ID):
        _seed_risk_bands(
            svc,
            ruleset_id=RULESET_ID,
            prefix="GC-001",
            bands=_load("galvanic_corrosion_ruleset.json")["risk_bands"],
        )
        return 0

    gc = _load("galvanic_corrosion_ruleset.json")
    TARGET = "IfcPipeSegment"
    MECH = "GC-001"
    count = 0

    def _r(**kw):
        nonlocal count
        _create(svc, mechanism=MECH, ruleset_id=RULESET_ID, target_ifc_class=TARGET, **kw)
        count += 1

    # ── Scoring model ─────────────────────────────────────────────────────────
    sm = gc["scoring_model"]
    _r(
        reference="GC-001.SCORING",
        rule_type="scoring_model",
        rule_category="scoring_model",
        description=sm["formula"],
        parameters=json.dumps(sm),
    )

    _seed_risk_bands(svc, ruleset_id=RULESET_ID, prefix="GC-001", bands=gc["risk_bands"])

    # ── Environment classes (E1–E7) ───────────────────────────────────────────
    env_src = gc["environment_classes"].get("source", "NASA-STD-6012")
    for key, data in gc["environment_classes"].items():
        if key == "source":
            continue
        _r(
            reference=f"GC-001.ENV.{key}",
            rule_type="environment_class",
            rule_category="reference_config",
            description=f"{key} — {data['label']}: threshold {data['voltage_threshold_v']} V, multiplier {data['multiplier']}",
            check_value=data["voltage_threshold_v"],
            operator="<=",
            unit="V",
            source_text=f"Source: {env_src}",
            parameters=json.dumps({**data, "class_key": key}),
        )

    # ── Area ratio bands ──────────────────────────────────────────────────────
    ar_src = gc["area_ratio_bands"].get("source", "Prosoco Technical Note 104")
    for band in gc["area_ratio_bands"]["bands"]:
        ref_key = band["label"].upper().replace(" ", "_")
        _r(
            reference=f"GC-001.AREA_RATIO.{ref_key}",
            rule_type="area_ratio_band",
            rule_category="threshold_band",
            description=f"Area ratio band — {band['label']}: min ratio {band['min_ratio']}, risk score {band['risk_score']}",
            check_value=band["risk_score"],
            value_min=band["min_ratio"],
            operator=">=",
            source_text=f"Source: {ar_src}",
            parameters=json.dumps(band),
        )

    # ── Galvanic series materials ─────────────────────────────────────────────
    mat_src = gc["galvanic_series"].get("source", "WorldStainless / Euro Inox")
    for mat_key, mat in gc["galvanic_series"]["materials"].items():
        noble_label = "noble (cathodic)" if mat.get("noble") else "active (anodic)"
        _r(
            reference=f"GC-001.MAT.{mat_key.upper()}",
            rule_type="galvanic_series_entry",
            rule_category="material_property",
            description=f"{mat['label']}: potential {mat['potential_v']} V ({noble_label})",
            check_value=mat["potential_v"],
            unit="V",
            keyword=mat_key,
            source_text=f"Source: {mat_src}",
            parameters=json.dumps({**mat, "material_key": mat_key}),
        )

    # ── PREN thresholds by environment ────────────────────────────────────────
    pren = gc["pren_thresholds"]
    pren_src = pren.get("source", "IMOA Design Manual 4th Ed.")
    for env_key, pdata in pren["by_environment"].items():
        _r(
            reference=f"GC-001.PREN.{env_key}",
            rule_type="pren_threshold",
            rule_category="threshold_band",
            description=f"Min PREN {pdata['min_pren']} for {env_key}: {pdata['note']}",
            check_value=pdata["min_pren"],
            operator=">=",
            source_text=f"Source: {pren_src}",
            parameters=json.dumps(
                {**pdata, "environment_class": env_key, "formula": pren.get("formula", "")}
            ),
        )

    # ── Mitigations ───────────────────────────────────────────────────────────
    for code, desc in gc["mitigation_catalogue"].items():
        _r(
            reference=code,
            rule_type="mitigation",
            rule_category="mitigation",
            description=desc,
            severity="recommended",
            parameters=json.dumps({"code": code}),
        )

    print(f"[RulesetSeeder] GC-001: {count} rules seeded")
    return count


# ── CC-001 — Crevice Corrosion ────────────────────────────────────────────────


def _seed_cc001(svc: RuleService) -> int:
    RULESET_ID = "BIMGUARD-CC-001"
    if svc.has_ruleset(RULESET_ID):
        _seed_risk_bands(
            svc,
            ruleset_id=RULESET_ID,
            prefix="CC-001",
            bands=_load("crevice_corrosion_ruleset.json")["risk_bands"],
        )
        return 0

    cc = _load("crevice_corrosion_ruleset.json")
    TARGET = "IfcPipeFitting"
    MECH = "CC-001"
    count = 0

    def _r(**kw):
        nonlocal count
        _create(svc, mechanism=MECH, ruleset_id=RULESET_ID, target_ifc_class=TARGET, **kw)
        count += 1

    # ── Scoring model ─────────────────────────────────────────────────────────
    sm = cc["scoring_model"]
    _r(
        reference="CC-001.SCORING",
        rule_type="scoring_model",
        rule_category="scoring_model",
        description=sm["formula"],
        parameters=json.dumps(sm),
    )

    _seed_risk_bands(svc, ruleset_id=RULESET_ID, prefix="CC-001", bands=cc["risk_bands"])

    # ── CCT grades ────────────────────────────────────────────────────────────
    cct = cc["cct_table"]
    cct_src = cct.get("test_conditions", "ASTM G48 Method B")
    for mat_key, mat in cct["grades"].items():
        _r(
            reference=f"CC-001.CCT.{mat_key.upper()}",
            rule_type="cct_material",
            rule_category="material_property",
            description=f"{mat['label']}: CCT = {mat['cct_c']} °C, PREN = {mat['pren_typical']}",
            check_value=mat["cct_c"],
            unit="°C",
            keyword=mat_key,
            source_text=f"Source: {cct_src}",
            parameters=json.dumps({**mat, "material_key": mat_key}),
        )

    # ── Geometry classes ──────────────────────────────────────────────────────
    geom = cc["geometry_classes"]
    geom_src = geom.get("description", "CIBSE Guide G / CIRIA C692")
    for class_key, data in geom.items():
        if class_key == "description":
            continue
        _r(
            reference=f"CC-001.GEOM.{class_key.upper()}",
            rule_type="geometry_class",
            rule_category="reference_config",
            description=f"Geometry {class_key}: width {data.get('crevice_width_mm', '')}, risk {data['risk']}",
            check_value=data["risk"],
            source_text=f"Source: {geom_src}",
            parameters=json.dumps({**data, "class_key": class_key}),
        )

    # ── Joint types (JT-001 … JT-014) ────────────────────────────────────────
    for jt_code, jt in cc["joint_type_library"]["types"].items():
        _r(
            reference=f"CC-001.JT.{jt_code}",
            rule_type="joint_type",
            rule_category="reference_config",
            description=f"{jt_code} — {jt['label']}: geometry {jt['geometry']}, risk {jt['risk']}",
            check_value=jt["risk"],
            keyword=jt_code,
            parameters=json.dumps({**jt, "joint_code": jt_code}),
        )

    # ── Environment severity classes ──────────────────────────────────────────
    env_src = cc["environment_severity"].get("source", "EN ISO 15329:2007")
    for env_key, data in cc["environment_severity"]["classes"].items():
        _r(
            reference=f"CC-001.ENV.{env_key}",
            rule_type="environment_severity",
            rule_category="reference_config",
            description=f"{env_key} — {data['label']}: severity {data['severity']}",
            check_value=data["severity"],
            source_text=f"Source: {env_src}",
            parameters=json.dumps({**data, "class_key": env_key}),
        )

    # ── Mitigations ───────────────────────────────────────────────────────────
    for code, desc in cc["mitigation_catalogue"].items():
        _r(
            reference=code,
            rule_type="mitigation",
            rule_category="mitigation",
            description=desc,
            severity="recommended",
            parameters=json.dumps({"code": code}),
        )

    print(f"[RulesetSeeder] CC-001: {count} rules seeded")
    return count


# ── MC-001 — Microbially Influenced Corrosion ─────────────────────────────────


def _seed_mc001(svc: RuleService) -> int:
    RULESET_ID = "BIMGUARD-MC-001"
    if svc.has_ruleset(RULESET_ID):
        _seed_risk_bands(
            svc,
            ruleset_id=RULESET_ID,
            prefix="MC-001",
            bands=_load("mic_corrosion_ruleset.json")["risk_bands"],
        )
        return 0

    mc = _load("mic_corrosion_ruleset.json")
    TARGET = "IfcPipeSegment"
    MECH = "MC-001"
    count = 0

    def _r(**kw):
        nonlocal count
        _create(svc, mechanism=MECH, ruleset_id=RULESET_ID, target_ifc_class=TARGET, **kw)
        count += 1

    # ── Scoring model ─────────────────────────────────────────────────────────
    sm = mc["scoring_model"]
    _r(
        reference="MC-001.SCORING",
        rule_type="scoring_model",
        rule_category="scoring_model",
        description=sm["formula"],
        parameters=json.dumps(sm),
    )

    _seed_risk_bands(svc, ruleset_id=RULESET_ID, prefix="MC-001", bands=mc["risk_bands"])

    # ── Flow velocity classes ─────────────────────────────────────────────────
    for fv_key, data in mc["flow_velocity_classes"].items():
        _r(
            reference=f"MC-001.FLOW.{fv_key}",
            rule_type="flow_velocity_class",
            rule_category="threshold_band",
            description=f"{fv_key} — {data['label']}: risk {data['risk']}",
            check_value=data["risk"],
            value_min=data.get("threshold_ms"),
            unit="m/s",
            source_text=f"Source: {data.get('reference', 'CIBSE TM13:2013')}",
            parameters=json.dumps({**data, "class_key": fv_key}),
        )

    # ── Temperature classes ───────────────────────────────────────────────────
    for t_key, data in mc["temperature_classes"].items():
        _r(
            reference=f"MC-001.TEMP.{t_key}",
            rule_type="temperature_class",
            rule_category="threshold_band",
            description=f"{t_key} — {data['range']}: risk {data['risk']}",
            check_value=data["risk"],
            unit="°C",
            source_text=f"Source: {data.get('reference', 'WHO GDWQ / CIBSE TM13')}",
            parameters=json.dumps({**data, "class_key": t_key}),
        )

    # ── Dead-leg classes ──────────────────────────────────────────────────────
    for dl_key, data in mc["dead_leg_classes"].items():
        _r(
            reference=f"MC-001.DEADLEG.{dl_key}",
            rule_type="dead_leg_class",
            rule_category="threshold_band",
            description=f"{dl_key} — {data['label']}: L/D {data['length_to_dia_ratio']}, risk {data['risk']}",
            check_value=data["risk"],
            source_text=f"Source: {data.get('reference', 'HSE HSG274 Part 2')}",
            parameters=json.dumps({**data, "class_key": dl_key}),
        )

    # ── Material MIC susceptibility ───────────────────────────────────────────
    for mat_key, mat in mc["material_susceptibility"].items():
        _r(
            reference=f"MC-001.MAT.{mat_key.upper()}",
            rule_type="material_susceptibility",
            rule_category="material_property",
            description=f"{mat['label']}: MIC susceptibility score {mat['score']}",
            check_value=mat["score"],
            keyword=mat_key,
            source_text=f"Source: {mat.get('reference', 'NACCE TPC 11')}",
            parameters=json.dumps({**mat, "material_key": mat_key}),
        )

    # ── System type modifiers ─────────────────────────────────────────────────
    for sys_key, data in mc["system_type_modifiers"].items():
        _r(
            reference=f"MC-001.SYS.{sys_key}",
            rule_type="system_modifier",
            rule_category="reference_config",
            description=f"{sys_key}: MIC risk multiplier {data['multiplier']} — {data.get('rationale', '')}",
            check_value=data["multiplier"],
            keyword=sys_key,
            parameters=json.dumps({**data, "system_key": sys_key}),
        )

    # ── Under-insulation risk states ──────────────────────────────────────────
    for state_key, risk in mc["under_insulation_risk"].items():
        _r(
            reference=f"MC-001.UIC.{state_key.upper()}",
            rule_type="under_insulation_risk",
            rule_category="threshold_band",
            description=f"Insulation condition '{state_key}': UIC risk {risk}",
            check_value=risk,
            parameters=json.dumps({"state_key": state_key, "risk": risk}),
        )

    # ── Mitigations ───────────────────────────────────────────────────────────
    for code, desc in mc["mitigation_catalogue"].items():
        _r(
            reference=code,
            rule_type="mitigation",
            rule_category="mitigation",
            description=desc,
            severity="recommended",
            parameters=json.dumps({"code": code}),
        )

    print(f"[RulesetSeeder] MC-001: {count} rules seeded")
    return count


def seed_seismic_rules(svc: RuleService) -> int:
    """Seed Blue Halo seismic bracing clearance rules (BIMGUARD-SB-001) per EN 1998-1 / DIN 4149."""
    rules_to_seed = [
        {
            "reference": "SB-001.01",
            "rule_type": "numeric_comparison",
            "rule_category": "property_check",
            "category": "seismic",
            "description": "Seismic pipe bracing threshold — pipe diameter >= 63.0 mm requires Blue Halo clearance envelope",
            "target_ifc_class": "IfcPipeSegment",
            "property_name": "NominalDiameter",
            "operator": ">=",
            "check_value": 63.0,
            "unit": "mm",
            "ruleset_id": "BIMGUARD-SB-001",
            "mechanism": "SEISMIC",
            "severity": "mandatory",
        },
        {
            "reference": "SB-001.02",
            "rule_type": "spatial_clearance",
            "rule_category": "property_check",
            "category": "seismic",
            "description": "Seismic bracing access clearance envelope — 200 mm buffer volume around braced services",
            "target_ifc_class": "IfcPipeSegment",
            "property_name": "ClearanceZone",
            "operator": ">=",
            "check_value": 200.0,
            "unit": "mm",
            "ruleset_id": "BIMGUARD-SB-001",
            "mechanism": "SEISMIC",
            "severity": "mandatory",
        },
        {
            "reference": "SB-001.03",
            "rule_type": "numeric_comparison",
            "rule_category": "property_check",
            "category": "seismic",
            "description": "Maximum transverse seismic brace spacing — 1.0 m per EN 1998-1 / DIN 4149",
            "target_ifc_class": "IfcPipeSegment",
            "property_name": "TransverseBraceSpacing",
            "operator": "<=",
            "check_value": 1.0,
            "unit": "m",
            "ruleset_id": "BIMGUARD-SB-001",
            "mechanism": "SEISMIC",
            "severity": "mandatory",
        },
        {
            "reference": "SB-001.04",
            "rule_type": "numeric_comparison",
            "rule_category": "property_check",
            "category": "seismic",
            "description": "Maximum longitudinal seismic brace spacing — 1.5 m per EN 1998-1 / DIN 4149",
            "target_ifc_class": "IfcPipeSegment",
            "property_name": "LongitudinalBraceSpacing",
            "operator": "<=",
            "check_value": 1.5,
            "unit": "m",
            "ruleset_id": "BIMGUARD-SB-001",
            "mechanism": "SEISMIC",
            "severity": "mandatory",
        },
        {
            "reference": "SB-001.05",
            "rule_type": "numeric_range",
            "rule_category": "property_check",
            "category": "seismic",
            "description": "Seismic brace installation angle — permissible range 35° to 70° from horizontal",
            "target_ifc_class": "IfcPipeSegment",
            "property_name": "BraceAngle",
            "operator": "between",
            "value_min": 35.0,
            "value_max": 70.0,
            "unit": "deg",
            "ruleset_id": "BIMGUARD-SB-001",
            "mechanism": "SEISMIC",
            "severity": "mandatory",
        },
    ]

    count = 0
    existing_refs = {str(r.get("reference") or "") for r in svc.list_rules()}
    for item in rules_to_seed:
        if item["reference"] not in existing_refs:
            _create(svc, **item)
            count += 1
    return count


# ── Public entry point ────────────────────────────────────────────────────────


def seed_engine_rulesets(svc: RuleService) -> dict[str, int]:
    """
    Seed GC-001, CC-001, MC-001, architectural code rules, and Blue Halo seismic rules.

    Idempotent: skips any ruleset already present in the DB.
    Returns a dict of {ruleset_id: rows_inserted}.
    """
    try:
        gc = _seed_gc001(svc)
        cc = _seed_cc001(svc)
        mc = _seed_mc001(svc)
        arch = seed_architectural_code_rules(svc)
        seismic = seed_seismic_rules(svc)
        return {
            "BIMGUARD-GC-001": gc,
            "BIMGUARD-CC-001": cc,
            "BIMGUARD-MC-001": mc,
            "BUILDING-CODE-PART9-ARCH": arch,
            "BIMGUARD-SB-001": seismic,
        }
    except Exception as exc:
        print(f"[RulesetSeeder] Warning: {exc}")
        return {}
