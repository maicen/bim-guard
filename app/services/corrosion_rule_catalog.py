"""Database-backed corrosion rule catalogs.

These helpers turn the seeded rule rows back into the lookup tables used by
the corrosion engines and the module 4 compliance runner. The database is the
source of truth, including static ruleset payloads stored in static_data_assets.
"""

from __future__ import annotations

import json
from typing import Any

from app.services.rules_service import RuleService
from app.services.static_data_service import StaticDataService

_FALLBACK_RULESETS: dict[str, dict[str, Any]] = {
    "galvanic_corrosion_ruleset.json": {
        "ruleset_id": "BIMGUARD-GC-001",
        "ruleset_version": "1.0.0",
        "description": "Offline fallback ruleset for galvanic corrosion checks.",
        "galvanic_series": {
            "materials": {
                "ss316_passive": {"potential_v": 0.08, "label": "SS 316 (passive)", "noble": True, "pren_typical": 25},
                "ss304_passive": {"potential_v": 0.12, "label": "SS 304 (passive)", "noble": True, "pren_typical": 19},
                "copper": {"potential_v": 0.28, "label": "Copper", "noble": True},
                "brass": {"potential_v": 0.32, "label": "Brass (70/30)", "noble": False},
                "cast_iron": {"potential_v": 0.52, "label": "Cast iron", "noble": False},
                "carbon_steel": {"potential_v": 0.55, "label": "Carbon / mild steel", "noble": False},
                "aluminium": {"potential_v": 0.70, "label": "Aluminium alloys", "noble": False},
                "galv_steel": {"potential_v": 0.82, "label": "Galvanised steel", "noble": False},
            }
        },
        "environment_classes": {
            "E1_CONTROLLED": {"label": "Fully controlled / dry indoor", "voltage_threshold_v": 0.50, "multiplier": 0.20},
            "E2_NORMAL": {"label": "Normal heated indoor", "voltage_threshold_v": 0.25, "multiplier": 0.40},
            "E3_HUMID": {"label": "Humid plant room", "voltage_threshold_v": 0.15, "multiplier": 0.65},
            "E5_EXPOSED": {"label": "External exposed", "voltage_threshold_v": 0.10, "multiplier": 0.85},
        },
        "zone_to_env": {"pool": "E6_POOL", "plant room": "E3_HUMID", "external": "E5_EXPOSED", "roof": "E5_EXPOSED"},
        "area_ratio_bands": {"bands": [{"label": "Favourable", "min_ratio": 5.0, "risk_score": 0.2}, {"label": "Acceptable", "min_ratio": 2.0, "risk_score": 0.4}, {"label": "Moderate", "min_ratio": 0.5, "risk_score": 0.6}, {"label": "Critical", "min_ratio": 0.0, "risk_score": 1.0}]},
        "pren_thresholds": {"by_environment": {"E2_NORMAL": {"min_pren": 18, "note": "SS304 adequate"}, "E3_HUMID": {"min_pren": 25, "note": "SS316 required"}}, "formula": "PREN = %Cr + 3.3 x %Mo + 16 x %N"},
        "risk_bands": {"Low": {"range": "< 0.35", "bcf_action": "Asset register only — no BCF issue"}, "Medium": {"range": "0.35 - 0.65", "bcf_action": "BCF Normal priority"}, "High": {"range": "0.65 - 0.85", "bcf_action": "BCF Major priority"}, "Critical": {"range": "> 0.85", "bcf_action": "BCF Critical priority — immediate remediation"}},
        "mitigation_catalogue": {"MIT-GC-001": "Install dielectric isolation gaskets at all contact points between dissimilar metals"},
        "common_mep_pairings": [{"anode": "carbon_steel", "cathode": "ss316_passive", "gap_v": 0.47, "env": "E3_HUMID", "band": "Critical"}],
    },
    "crevice_corrosion_ruleset.json": {
        "ruleset_id": "BIMGUARD-CC-001",
        "ruleset_version": "1.0.0",
        "description": "Offline fallback ruleset for crevice corrosion checks.",
        "cct_table": {"grades": {"ss316_passive": {"cct_c": 10, "label": "SS 316 / 1.4401", "pren_typical": 25}, "ss304_passive": {"cct_c": -5, "label": "SS 304 / 1.4301", "pren_typical": 19}, "duplex2205": {"cct_c": 25, "label": "Duplex 2205 / 1.4462", "pren_typical": 35}}},
        "geometry_classes": {"Open": {"risk": 0.35, "description": "Open geometry"}, "Moderate": {"risk": 0.60, "description": "Moderate geometry"}, "Tight": {"risk": 0.80, "description": "Tight geometry"}, "Critical": {"risk": 1.00, "description": "Critical crevice geometry"}},
        "joint_type_library": {"types": {"JT-001": {"label": "Butt weld / socket", "geometry": "Tight", "risk": 0.75, "ifc_types": ["pipe", "flange"]}}},
        "environment_severity": {"classes": {"BUILDING_SERVICES": {"label": "Building services pipework", "severity": 0.35, "chloride_mgl": "variable"}, "T2_INTERMITTENT": {"label": "Intermittent wetting", "severity": 0.40, "chloride_mgl": "<50"}}},
        "risk_bands": {"Low": {"range": "< 0.30", "bcf_action": "Asset register only — no BCF issue"}, "Medium": {"range": "0.30 - 0.55", "bcf_action": "BCF Normal priority"}, "High": {"range": "0.55 - 0.80", "bcf_action": "BCF Major priority"}, "Critical": {"range": "> 0.80", "bcf_action": "BCF Critical priority — immediate remediation"}},
        "mitigation_catalogue": {"MIT-CC-001": "Specify non-metallic isolation gasket and positive drainage"},
    },
    "mic_corrosion_ruleset.json": {
        "ruleset_id": "BIMGUARD-MC-001",
        "ruleset_version": "1.0.0",
        "description": "Offline fallback ruleset for MIC checks.",
        "flow_velocity_classes": {"FV0_STAGNANT": {"label": "Stagnant", "risk": 1.0, "threshold_ms": 0.0}, "FV2_LOW": {"label": "Low", "risk": 0.6, "threshold_ms": 0.2}, "FV4_GOOD": {"label": "Good", "risk": 0.2, "threshold_ms": 0.5}},
        "temperature_classes": {"T2_DANGER": {"range": "20–45°C", "risk": 0.8, "t_min": 20.0, "t_max": 45.0}, "T4_SAFE_HOT": {"range": ">45°C", "risk": 0.2, "t_min": 45.0, "t_max": 100.0}},
        "dead_leg_classes": {"DL0_THROUGH": {"label": "Through-flow", "risk": 0.0, "length_to_dia_ratio": "0"}, "DL3_LONG": {"label": "Long dead leg", "risk": 0.8, "length_to_dia_ratio": ">10"}, "DL5_UNKNOWN": {"label": "Unknown", "risk": 0.5, "length_to_dia_ratio": "n/a"}},
        "material_susceptibility": {
            "carbon_steel": {"score": 0.85, "label": "Carbon steel", "reference": "MIC susceptible"},
            "ss316": {"score": 0.4, "label": "SS316", "reference": "Lower risk"},
            "unknown": {"score": 0.5, "label": "Unknown", "reference": "Unknown"},
            "default": {"score": 0.5, "label": "Unknown", "reference": "Unknown"},
        },
        "system_type_modifiers": {"DOMESTICCOLDWATER": {"multiplier": 1.2, "rationale": "Cold water system"}, "UNKNOWN": {"multiplier": 1.0, "rationale": "Unknown system"}},
        "under_insulation_risk": {"dry": 0.1, "wet": 0.8},
        "risk_bands": {"Low": {"range": "< 0.25", "bcf_action": "Asset register only — no BCF issue"}, "Medium": {"range": "0.25 - 0.50", "bcf_action": "BCF Normal priority"}, "High": {"range": "0.50 - 0.75", "bcf_action": "BCF Major priority"}, "Critical": {"range": "> 0.75", "bcf_action": "BCF Critical priority — immediate remediation"}},
        "mitigation_catalogue": {"MIT-MIC-001": "Eliminate dead-leg and flush regularly"},
    },
}


def _coerce_float(value: Any, default: float | None = None) -> float | None:
    """Return ``value`` as ``float`` when possible, otherwise ``default``."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _decode_json(value: Any) -> dict[str, Any]:
    """Decode a JSON string stored in a rule column."""
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _load_json_ruleset(filename: str) -> dict[str, Any]:
    """Load a canonical ruleset JSON payload from database static assets."""
    asset_map = {
        "galvanic_corrosion_ruleset.json": "ruleset:BIMGUARD-GC-001",
        "crevice_corrosion_ruleset.json": "ruleset:BIMGUARD-CC-001",
        "mic_corrosion_ruleset.json": "ruleset:BIMGUARD-MC-001",
    }
    fallback = _FALLBACK_RULESETS.get(filename)
    if fallback is not None:
        return fallback

    asset_key = asset_map.get(filename)
    if asset_key:
        try:
            payload = StaticDataService().get_asset_json(asset_key)
        except Exception:
            payload = None
        if isinstance(payload, dict):
            return payload
    raise RuntimeError(f"Missing static ruleset asset: {filename}")


def _rules_for(ruleset_id: str) -> list[dict[str, Any]]:
    """Return stored rows for a ruleset, or an empty list when unseeded."""
    try:
        return RuleService().list_by_ruleset(ruleset_id)
    except Exception:
        return []


def _risk_band_thresholds(
    rows: list[dict[str, Any]], json_data: dict[str, Any]
) -> dict[str, float]:
    """Build composite-score band thresholds from stored rows or JSON fallback."""
    thresholds: dict[str, float] = {}
    for row in rows:
        if row.get("rule_type") != "risk_band":
            continue
        params = _decode_json(row.get("parameters"))
        band = str(params.get("band") or row.get("keyword") or "").strip().lower()
        if band not in {"medium", "high", "critical"}:
            continue
        value = _coerce_float(row.get("check_value"))
        if value is not None:
            thresholds[band] = value

    if thresholds:
        return thresholds

    risk_bands = json_data.get("risk_bands") or {}
    for band_name, band_data in risk_bands.items():
        band_key = str(band_name).strip().lower()
        if band_key not in {"medium", "high", "critical"}:
            continue
        range_text = str((band_data or {}).get("range") or "")
        if "-" in range_text:
            lower = range_text.split("-", 1)[0].strip().strip("<>")
        else:
            lower = range_text.replace(">", "").replace("<", "").strip()
        value = _coerce_float(lower)
        if value is not None:
            thresholds[band_key] = value
    return thresholds


def _ordered_band_rows(rows: list[dict[str, Any]], rule_type: str) -> list[dict[str, Any]]:
    """Return band-like rows ordered from most permissive to most severe."""
    return [row for row in rows if row.get("rule_type") == rule_type]


def _build_area_ratio_bands(
    rows: list[dict[str, Any]], json_data: dict[str, Any]
) -> list[dict[str, Any]]:
    """Build the area-ratio risk bands used by GC-001."""
    band_rows = _ordered_band_rows(rows, "area_ratio_band")
    if band_rows:
        ordered = sorted(
            band_rows,
            key=lambda row: _coerce_float(_decode_json(row.get("parameters")).get("min_ratio"), 0.0)
            or 0.0,
            reverse=True,
        )
        bands: list[dict[str, Any]] = []
        for index, row in enumerate(ordered):
            params = _decode_json(row.get("parameters"))
            min_ratio = _coerce_float(params.get("min_ratio"), 0.0) or 0.0
            max_ratio = float("inf") if index == 0 else bands[-1]["min_ratio"]
            bands.append(
                {
                    "label": params.get("label")
                    or row.get("description")
                    or row.get("reference")
                    or "Band",
                    "min_ratio": min_ratio,
                    "max_ratio": max_ratio,
                    "risk": _coerce_float(row.get("check_value"), 1.0) or 1.0,
                }
            )
        return bands

    json_bands = (json_data.get("area_ratio_bands") or {}).get("bands") or []
    bands: list[dict[str, Any]] = []
    for index, band in enumerate(json_bands):
        min_ratio = _coerce_float(band.get("min_ratio"), 0.0) or 0.0
        max_ratio = float("inf") if index == 0 else bands[-1]["min_ratio"]
        bands.append(
            {
                "label": band.get("label", "Band"),
                "min_ratio": min_ratio,
                "max_ratio": max_ratio,
                "risk": _coerce_float(band.get("risk_score"), 1.0) or 1.0,
            }
        )
    return bands


def _build_map_from_rows(
    rows: list[dict[str, Any]], rule_type: str, *, key_field: str = "reference"
) -> dict[str, Any]:
    """Build a simple key/value map from rows with the requested rule type."""
    result: dict[str, Any] = {}
    for row in rows:
        if row.get("rule_type") != rule_type:
            continue
        params = _decode_json(row.get("parameters"))
        key = str(params.get(key_field) or row.get("keyword") or row.get("reference") or "").strip()
        if not key:
            continue
        result[key] = row
    return result


def load_gc_catalog() -> dict[str, Any]:
    """Load the GC-001 lookup tables from the database or fallback JSON."""
    json_data = _load_json_ruleset("galvanic_corrosion_ruleset.json")
    rows = _rules_for(json_data["ruleset_id"])

    if not rows:
        rows = []
        for material_key, material in (
            (json_data.get("galvanic_series") or {}).get("materials", {}).items()
        ):
            rows.append(
                {
                    "rule_type": "galvanic_series_entry",
                    "reference": f"GC-001.MAT.{material_key.upper()}",
                    "description": material.get("label", material_key),
                    "check_value": material.get("potential_v"),
                    "parameters": json.dumps({**material, "material_key": material_key}),
                }
            )
        for env_key, env in (json_data.get("environment_classes") or {}).items():
            if env_key == "source":
                continue
            rows.append(
                {
                    "rule_type": "environment_class",
                    "reference": f"GC-001.ENV.{env_key}",
                    "description": env.get("label", env_key),
                    "check_value": env.get("voltage_threshold_v"),
                    "parameters": json.dumps({**env, "class_key": env_key}),
                }
            )
        for band in (json_data.get("area_ratio_bands") or {}).get("bands", []):
            rows.append(
                {
                    "rule_type": "area_ratio_band",
                    "reference": f"GC-001.AREA_RATIO.{str(band.get('label', '')).upper().replace(' ', '_')}",
                    "description": band.get("label", "Band"),
                    "check_value": band.get("risk_score"),
                    "parameters": json.dumps(band),
                }
            )
        for env_key, pdata in (
            (json_data.get("pren_thresholds") or {}).get("by_environment", {}).items()
        ):
            rows.append(
                {
                    "rule_type": "pren_threshold",
                    "reference": f"GC-001.PREN.{env_key}",
                    "description": pdata.get("note", env_key),
                    "check_value": pdata.get("min_pren"),
                    "parameters": json.dumps(
                        {
                            **pdata,
                            "environment_class": env_key,
                            "formula": (json_data.get("pren_thresholds") or {}).get("formula", ""),
                        }
                    ),
                }
            )
        for band_name, band_data in (json_data.get("risk_bands") or {}).items():
            range_text = str((band_data or {}).get("range") or "")
            lower_bound = None
            if "-" in range_text:
                lower_bound = _coerce_float(range_text.split("-", 1)[0].strip().strip("<>"))
            elif ">" in range_text:
                lower_bound = _coerce_float(range_text.replace(">", "").strip())
            rows.append(
                {
                    "rule_type": "risk_band",
                    "reference": f"GC-001.BAND.{band_name.upper()}",
                    "description": band_data.get("bcf_action", band_name),
                    "check_value": lower_bound,
                    "keyword": band_name,
                    "parameters": json.dumps({"band": band_name, **band_data}),
                }
            )
        for code, desc in (json_data.get("mitigation_catalogue") or {}).items():
            rows.append(
                {
                    "rule_type": "mitigation",
                    "reference": code,
                    "description": desc,
                    "parameters": json.dumps({"code": code}),
                }
            )

    galvanic_series: dict[str, dict[str, Any]] = {}
    pren_values: dict[str, float] = {}
    environment_classes: dict[str, dict[str, Any]] = {}
    pren_thresholds: dict[str, float] = {}

    for row in rows:
        params = _decode_json(row.get("parameters"))
        rule_type = row.get("rule_type")
        if rule_type == "galvanic_series_entry":
            material_key = str(params.get("material_key") or row.get("keyword") or "").strip()
            potential = _coerce_float(row.get("check_value"), None)
            if material_key and potential is not None:
                galvanic_series[material_key] = {
                    "potential": potential,
                    "label": params.get("label") or row.get("description") or material_key,
                    "noble": bool(params.get("noble", False)),
                    "pren_typical": _coerce_float(params.get("pren_typical"), 0.0) or 0.0,
                }
                pren_typical = params.get("pren_typical")
                if pren_typical is not None:
                    pren_values[material_key] = _coerce_float(pren_typical, 0.0) or 0.0
        elif rule_type == "environment_class":
            env_key = str(
                params.get("class_key") or row.get("reference", "").split(".")[-1]
            ).strip()
            if env_key:
                environment_classes[env_key] = {
                    "label": params.get("label") or row.get("description") or env_key,
                    "voltage_threshold": _coerce_float(row.get("check_value"), 0.25) or 0.25,
                    "multiplier": _coerce_float(params.get("multiplier"), 1.0) or 1.0,
                }
        elif rule_type == "pren_threshold":
            env_key = str(
                params.get("environment_class") or row.get("reference", "").split(".")[-1]
            ).strip()
            if env_key:
                pren_thresholds[env_key] = _coerce_float(row.get("check_value"), 18.0) or 18.0

    return {
        "ruleset_id": json_data["ruleset_id"],
        "ruleset_version": json_data.get("ruleset_version", "1.0.0"),
        "description": json_data.get("description", ""),
        "galvanic_series": galvanic_series,
        "environment_classes": environment_classes,
        "zone_to_env": (
            next(
                (
                    _decode_json(row.get("parameters")).get("zone_map")
                    for row in rows
                    if row.get("rule_type") == "reference_config"
                    and _decode_json(row.get("parameters")).get("zone_map")
                ),
                None,
            )
            or {
                "pool": "E6_POOL",
                "swimming pool": "E6_POOL",
                "spa": "E6_POOL",
                "plant room": "E3_HUMID",
                "plantroom": "E3_HUMID",
                "mechanical room": "E3_HUMID",
                "boiler room": "E3_HUMID",
                "pump room": "E3_HUMID",
                "external": "E5_EXPOSED",
                "roof": "E5_EXPOSED",
                "car park": "E4_SHELTERED",
                "coastal": "E7_COASTAL",
                "marine": "E7_COASTAL",
                "cleanroom": "E1_CONTROLLED",
                "laboratory": "E1_CONTROLLED",
                "server room": "E1_CONTROLLED",
                "data centre": "E1_CONTROLLED",
            }
        ),
        "area_ratio_bands": _build_area_ratio_bands(rows, json_data),
        "pren_thresholds": pren_thresholds,
        "pren_values": pren_values,
        "risk_band_thresholds": _risk_band_thresholds(rows, json_data),
        "mitigations": {
            row["reference"]: row.get("description", "")
            for row in rows
            if row.get("rule_type") == "mitigation"
        },
        "scoring_model": _decode_json(
            next(
                (row.get("parameters") for row in rows if row.get("rule_type") == "scoring_model"),
                {},
            )
        ),
        "rules": rows,
    }


def reload_all_catalogs() -> None:
    """Reload all in-memory corrosion engine catalogs from the database."""
    try:
        from app.engines import bimguard_corrosion_engine

        if hasattr(bimguard_corrosion_engine, "reload_rules"):
            bimguard_corrosion_engine.reload_rules()
    except Exception:
        pass

    try:
        from app.engines import bimguard_crevice_engine

        if hasattr(bimguard_crevice_engine, "reload_rules"):
            bimguard_crevice_engine.reload_rules()
    except Exception:
        pass

    try:
        from app.engines import bimguard_mic_engine

        if hasattr(bimguard_mic_engine, "reload_rules"):
            bimguard_mic_engine.reload_rules()
    except Exception:
        pass


def load_cc_catalog() -> dict[str, Any]:
    """Load the CC-001 lookup tables from the database or fallback JSON."""
    json_data = _load_json_ruleset("crevice_corrosion_ruleset.json")
    rows = _rules_for(json_data["ruleset_id"])

    if not rows:
        rows = []
        for material_key, material in (json_data.get("cct_table") or {}).get("grades", {}).items():
            rows.append(
                {
                    "rule_type": "cct_material",
                    "reference": f"CC-001.CCT.{material_key.upper()}",
                    "description": material.get("label", material_key),
                    "check_value": material.get("cct_c"),
                    "parameters": json.dumps({**material, "material_key": material_key}),
                }
            )
        for class_key, data in (json_data.get("geometry_classes") or {}).items():
            if class_key == "description":
                continue
            rows.append(
                {
                    "rule_type": "geometry_class",
                    "reference": f"CC-001.GEOM.{class_key.upper()}",
                    "description": data.get("description", class_key),
                    "check_value": data.get("risk"),
                    "parameters": json.dumps({**data, "class_key": class_key}),
                }
            )
        for jt_code, jt in (json_data.get("joint_type_library") or {}).get("types", {}).items():
            rows.append(
                {
                    "rule_type": "joint_type",
                    "reference": f"CC-001.JT.{jt_code}",
                    "description": jt.get("label", jt_code),
                    "check_value": jt.get("risk"),
                    "keyword": jt_code,
                    "parameters": json.dumps({**jt, "joint_code": jt_code}),
                }
            )
        for env_key, data in (
            (json_data.get("environment_severity") or {}).get("classes", {}).items()
        ):
            rows.append(
                {
                    "rule_type": "environment_severity",
                    "reference": f"CC-001.ENV.{env_key}",
                    "description": data.get("label", env_key),
                    "check_value": data.get("severity"),
                    "parameters": json.dumps({**data, "class_key": env_key}),
                }
            )
        for band_name, band_data in (json_data.get("risk_bands") or {}).items():
            range_text = str((band_data or {}).get("range") or "")
            lower_bound = None
            if "-" in range_text:
                lower_bound = _coerce_float(range_text.split("-", 1)[0].strip().strip("<>"))
            elif ">" in range_text:
                lower_bound = _coerce_float(range_text.replace(">", "").strip())
            rows.append(
                {
                    "rule_type": "risk_band",
                    "reference": f"CC-001.BAND.{band_name.upper()}",
                    "description": band_data.get("bcf_action", band_name),
                    "check_value": lower_bound,
                    "keyword": band_name,
                    "parameters": json.dumps({"band": band_name, **band_data}),
                }
            )
        for code, desc in (json_data.get("mitigation_catalogue") or {}).items():
            rows.append(
                {
                    "rule_type": "mitigation",
                    "reference": code,
                    "description": desc,
                    "parameters": json.dumps({"code": code}),
                }
            )

    cct_table: dict[str, dict[str, Any]] = {}
    geometry_classes: dict[str, dict[str, Any]] = {}
    joint_types: dict[str, dict[str, Any]] = {}
    environment_severity: dict[str, dict[str, Any]] = {}

    for row in rows:
        params = _decode_json(row.get("parameters"))
        rule_type = row.get("rule_type")
        if rule_type == "cct_material":
            material_key = str(params.get("material_key") or row.get("keyword") or "").strip()
            if material_key:
                cct_table[material_key] = {
                    "cct_c": _coerce_float(row.get("check_value"), 0.0) or 0.0,
                    "pren_typical": _coerce_float(params.get("pren_typical"), 0.0) or 0.0,
                    "label": params.get("label") or row.get("description") or material_key,
                }
        elif rule_type == "geometry_class":
            class_key = str(
                params.get("class_key") or row.get("reference", "").split(".")[-1]
            ).strip()
            if class_key:
                geometry_classes[class_key] = {
                    "risk": _coerce_float(row.get("check_value"), 0.0) or 0.0,
                    "description": params.get("description") or row.get("description") or class_key,
                }
        elif rule_type == "joint_type":
            joint_code = str(
                params.get("joint_code")
                or row.get("keyword")
                or row.get("reference", "").split(".")[-1]
            ).strip()
            if joint_code:
                joint_types[joint_code] = {
                    "label": params.get("label") or row.get("description") or joint_code,
                    "geometry": params.get("geometry") or "Tight",
                    "risk": _coerce_float(row.get("check_value"), 0.75) or 0.75,
                    "ifc_keywords": params.get("ifc_keywords") or params.get("ifc_types") or [],
                }
        elif rule_type == "environment_severity":
            env_key = str(
                params.get("class_key") or row.get("reference", "").split(".")[-1]
            ).strip()
            if env_key:
                environment_severity[env_key] = {
                    "severity": _coerce_float(row.get("check_value"), 0.0) or 0.0,
                    "label": params.get("label") or row.get("description") or env_key,
                    "chloride_mgl": params.get("chloride_mgl", ""),
                }

    band_thresholds = _risk_band_thresholds(rows, json_data)
    return {
        "ruleset_id": json_data["ruleset_id"],
        "ruleset_version": json_data.get("ruleset_version", "1.0.0"),
        "description": json_data.get("description", ""),
        "cct_table": cct_table,
        "geometry_classes": geometry_classes,
        "joint_type_library": {"types": joint_types},
        "environment_severity": environment_severity,
        "risk_band_thresholds": band_thresholds,
        "mitigations": {
            row["reference"]: row.get("description", "")
            for row in rows
            if row.get("rule_type") == "mitigation"
        },
        "scoring_model": _decode_json(
            next(
                (row.get("parameters") for row in rows if row.get("rule_type") == "scoring_model"),
                {},
            )
        ),
        "rules": rows,
    }


def load_mc_catalog() -> dict[str, Any]:
    """Load the MC-001 lookup tables from the database or fallback JSON."""
    json_data = _load_json_ruleset("mic_corrosion_ruleset.json")
    rows = _rules_for(json_data["ruleset_id"])

    if not rows:
        rows = []
        for key, data in (json_data.get("flow_velocity_classes") or {}).items():
            rows.append(
                {
                    "rule_type": "flow_velocity_class",
                    "reference": f"MC-001.FLOW.{key}",
                    "description": data.get("label", key),
                    "check_value": data.get("risk"),
                    "parameters": json.dumps({**data, "class_key": key}),
                }
            )
        for key, data in (json_data.get("temperature_classes") or {}).items():
            rows.append(
                {
                    "rule_type": "temperature_class",
                    "reference": f"MC-001.TEMP.{key}",
                    "description": data.get("range", key),
                    "check_value": data.get("risk"),
                    "parameters": json.dumps({**data, "class_key": key}),
                }
            )
        for key, data in (json_data.get("dead_leg_classes") or {}).items():
            rows.append(
                {
                    "rule_type": "dead_leg_class",
                    "reference": f"MC-001.DEADLEG.{key}",
                    "description": data.get("label", key),
                    "check_value": data.get("risk"),
                    "parameters": json.dumps({**data, "class_key": key}),
                }
            )
        for key, data in (json_data.get("material_susceptibility") or {}).items():
            rows.append(
                {
                    "rule_type": "material_susceptibility",
                    "reference": f"MC-001.MAT.{key.upper()}",
                    "description": data.get("label", key),
                    "check_value": data.get("score"),
                    "keyword": key,
                    "parameters": json.dumps({**data, "material_key": key}),
                }
            )
        for key, data in (json_data.get("system_type_modifiers") or {}).items():
            rows.append(
                {
                    "rule_type": "system_modifier",
                    "reference": f"MC-001.SYS.{key}",
                    "description": data.get("rationale", key),
                    "check_value": data.get("multiplier"),
                    "keyword": key,
                    "parameters": json.dumps({**data, "system_key": key}),
                }
            )
        for key, risk in (json_data.get("under_insulation_risk") or {}).items():
            rows.append(
                {
                    "rule_type": "under_insulation_risk",
                    "reference": f"MC-001.UIC.{key.upper()}",
                    "description": f"{key}: {risk}",
                    "check_value": risk,
                    "parameters": json.dumps({"state_key": key, "risk": risk}),
                }
            )
        for band_name, band_data in (json_data.get("risk_bands") or {}).items():
            range_text = str((band_data or {}).get("range") or "")
            lower_bound = None
            if "-" in range_text:
                lower_bound = _coerce_float(range_text.split("-", 1)[0].strip().strip("<>"))
            elif ">" in range_text:
                lower_bound = _coerce_float(range_text.replace(">", "").strip())
            rows.append(
                {
                    "rule_type": "risk_band",
                    "reference": f"MC-001.BAND.{band_name.upper()}",
                    "description": band_data.get("bcf_action", band_name),
                    "check_value": lower_bound,
                    "keyword": band_name,
                    "parameters": json.dumps({"band": band_name, **band_data}),
                }
            )
        for code, desc in (json_data.get("mitigation_catalogue") or {}).items():
            rows.append(
                {
                    "rule_type": "mitigation",
                    "reference": code,
                    "description": desc,
                    "parameters": json.dumps({"code": code}),
                }
            )

    flow_velocity_classes: dict[str, dict[str, Any]] = {}
    temperature_classes: dict[str, dict[str, Any]] = {}
    dead_leg_classes: dict[str, dict[str, Any]] = {}
    material_susceptibility: dict[str, tuple[float, str, str]] = {}
    system_type_modifiers: dict[str, tuple[float, str]] = {}
    under_insulation_risk: dict[str, float] = {}

    for row in rows:
        params = _decode_json(row.get("parameters"))
        rule_type = row.get("rule_type")
        if rule_type == "flow_velocity_class":
            key = str(params.get("class_key") or row.get("reference", "").split(".")[-1]).strip()
            if key:
                flow_velocity_classes[key] = {
                    "label": params.get("label") or row.get("description") or key,
                    "threshold_ms": _coerce_float(params.get("threshold_ms"), 0.0) or 0.0,
                    "risk": _coerce_float(row.get("check_value"), 0.0) or 0.0,
                    "reference": params.get("reference") or "",
                }
        elif rule_type == "temperature_class":
            key = str(params.get("class_key") or row.get("reference", "").split(".")[-1]).strip()
            if key:
                temperature_classes[key] = {
                    "range": params.get("range") or row.get("description") or key,
                    "risk": _coerce_float(row.get("check_value"), 0.0) or 0.0,
                    "reference": params.get("reference") or "",
                    "t_min": _coerce_float(params.get("t_min"), 0.0) or 0.0,
                    "t_max": _coerce_float(params.get("t_max"), 0.0) or 0.0,
                }
        elif rule_type == "dead_leg_class":
            key = str(params.get("class_key") or row.get("reference", "").split(".")[-1]).strip()
            if key:
                dead_leg_classes[key] = {
                    "label": params.get("label") or row.get("description") or key,
                    "length_to_dia_ratio": params.get("length_to_dia_ratio") or "n/a",
                    "risk": _coerce_float(row.get("check_value"), 0.0) or 0.0,
                    "reference": params.get("reference") or "",
                }
        elif rule_type == "material_susceptibility":
            key = (
                str(
                    params.get("material_key")
                    or row.get("keyword")
                    or row.get("reference", "").split(".")[-1]
                )
                .strip()
                .lower()
            )
            if key:
                material_susceptibility[key] = (
                    _coerce_float(row.get("check_value"), 0.0) or 0.0,
                    params.get("label") or row.get("description") or key,
                    params.get("reference") or "",
                )
        elif rule_type == "system_modifier":
            key = (
                str(
                    params.get("system_key")
                    or row.get("keyword")
                    or row.get("reference", "").split(".")[-1]
                )
                .strip()
                .upper()
            )
            if key:
                system_type_modifiers[key] = (
                    _coerce_float(row.get("check_value"), 1.0) or 1.0,
                    params.get("rationale") or row.get("description") or key,
                )
        elif rule_type == "under_insulation_risk":
            state_key = (
                str(params.get("state_key") or row.get("reference", "").split(".")[-1])
                .strip()
                .lower()
            )
            if state_key:
                under_insulation_risk[state_key] = _coerce_float(row.get("check_value"), 0.0) or 0.0

    if "unknown" not in material_susceptibility:
        material_susceptibility["unknown"] = (0.5, "Unknown", "Unknown material")

    band_thresholds = _risk_band_thresholds(rows, json_data)
    return {
        "ruleset_id": json_data["ruleset_id"],
        "ruleset_version": json_data.get("ruleset_version", "1.0.0"),
        "description": json_data.get("description", ""),
        "flow_velocity_classes": flow_velocity_classes,
        "temperature_classes": temperature_classes,
        "dead_leg_classes": dead_leg_classes,
        "material_susceptibility": material_susceptibility,
        "system_type_modifiers": system_type_modifiers,
        "under_insulation_risk": under_insulation_risk,
        "risk_band_thresholds": band_thresholds,
        "mitigations": {
            row["reference"]: row.get("description", "")
            for row in rows
            if row.get("rule_type") == "mitigation"
        },
        "scoring_model": _decode_json(
            next(
                (row.get("parameters") for row in rows if row.get("rule_type") == "scoring_model"),
                {},
            )
        ),
        "rules": rows,
    }
