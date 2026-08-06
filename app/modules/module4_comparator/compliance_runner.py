"""
BIMGUARD AI — Compliance Runner
Connects IFC service elements to GC-001, CC-001, and MC-001 engines.
Returns unified results ready for BCF generation and dashboard.
"""

from ..module2_ifc_read.ifc_parser import ServiceElement
from app.engines.bimguard_corrosion_engine import (
    GCElement,
    MITIGATIONS_GC,
    assess_galvanic_risk,
)
from app.engines.bimguard_crevice_engine import (
    CCElement,
    MITIGATIONS_CC,
    assess_crevice_risk,
)
from app.engines.bimguard_mic_engine import (
    MICElement,
    MITIGATIONS as MITIGATIONS_MIC,
    assess_mic_risk,
)


def _band_int(b):
    return {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}.get(b, 0)


def _mitigation(g_band, g_gap, c_band, c_geo, mat, env) -> str:
    overall = max(g_band, c_band, key=_band_int)
    if overall == "LOW":
        return "None required — log in asset register"
    if overall == "CRITICAL":
        if c_geo == "critical":
            return "CRITICAL: Redesign joint geometry + material grade upgrade mandatory"
        return "CRITICAL: Full material substitution or isolation system — consult corrosion specialist"
    if c_geo in ("tight", "critical") and env in ("coastal", "swimming_pool", "marine_splash"):
        rec = "duplex 2205" if env in ("coastal", "swimming_pool") else "super-duplex 2507"
        return f"Upgrade to {rec} + specify full-face PTFE gasket or plastic-lined support"
    if g_gap and g_gap > 0.3:
        return "Specify PTFE isolation sleeve + neoprene washer at all contact points"
    return "Specify isolation gasket; ensure positive drainage; add to inspection schedule"


def _action(band):
    return {
        "LOW": "Log — include in corrosion asset register, no immediate action",
        "MEDIUM": "Flag — specify mitigation on next drawing issue; raise RFI",
        "HIGH": "BLOCK — BCF issued; lead engineer to confirm resolution before next model issue",
        "CRITICAL": "BLOCK — compliance failure; notify client; redesign or substitution mandatory",
    }[band]


def _join_mitigations(codes: list[str], catalogue: dict[str, str]) -> str:
    texts = [catalogue.get(code, code) for code in codes if code]
    return " | ".join(texts)


def _normalise_mic_material(material: str) -> str:
    """Map parser-centric material keys to MIC engine material families."""
    key = (material or "").strip().lower()
    if "ss_316" in key or "ss316" in key or "316" in key:
        return "ss316"
    if "ss_304" in key or "ss304" in key or "304" in key:
        return "ss304"
    if "duplex" in key and "2507" in key:
        return "duplex2205"
    if "duplex" in key or "2205" in key:
        return "duplex2205"
    if "galv" in key or "galvan" in key:
        return "galv_steel"
    if "carbon" in key or "mild" in key:
        return "carbon_steel"
    if "cast" in key and "iron" in key:
        return "cast_iron"
    if "copper" in key:
        return "copper"
    if "brass" in key:
        return "brass"
    if "alum" in key:
        return "aluminium"
    if "titan" in key:
        return "titanium"
    return key or "unknown"


def _normalise_mic_system(system_name: str) -> str:
    """Best-effort mapping from IFC/system labels to MC-001 system modifiers."""
    raw = (system_name or "").strip().upper()
    compact = raw.replace(" ", "")
    if "FIRE" in compact:
        return "FIREPROTECTION"
    if "CHILLED" in compact:
        return "CHILLEDWATER"
    if "CONDENS" in compact:
        return "CONDENSERWATER"
    if "COLD" in compact and "WATER" in compact:
        return "DOMESTICCOLDWATER"
    if "HOT" in compact and "WATER" in compact:
        return "DOMESTICHOTWATER"
    return compact or "UNKNOWN"


def run_compliance_checks(elements: list[ServiceElement]) -> list[dict]:
    """
    Runs GC-001, CC-001, and MC-001 on every service element.
    Returns a list of result dicts ready for the dashboard, BCF, and asset register.
    """
    results = []

    for el in elements:
        g_result = assess_galvanic_risk(
            GCElement(
                global_id_anode=el.guid,
                global_id_cathode=el.guid,
                material_anode=el.material_a,
                material_cathode=el.material_b or el.material_a,
                anode_area_m2=float(el.anode_area_m2 or 1.0),
                cathode_area_m2=float(el.cathode_area_m2 or 1.0),
                zone_category=el.location_tag,
                floor=el.floor,
                system_type=el.system,
            )
        )

        c_result = assess_crevice_risk(
            CCElement(
                global_id=el.guid,
                element_type=el.ifc_type,
                material=el.material_a,
                joint_description=el.joint_type,
                operating_temp_c=20.0,
                zone_category=el.location_tag,
                system_type=el.system,
                floor=el.floor,
            )
        )

        m_result = assess_mic_risk(
            MICElement(
                global_id=el.guid,
                element_type=el.ifc_type,
                system_type=_normalise_mic_system(el.system),
                material=_normalise_mic_material(el.material_a),
                nominal_diameter_m=0.05,
                flow_velocity_ms=0.30,
                operating_temp_c=20.0,
                dead_leg_length_m=0.0,
                insulation_condition="unknown",
                floor=el.floor,
                zone=el.location_tag,
            )
        )

        g_score = g_result.composite_score
        g_band = g_result.risk_band
        g_gap = g_result.voltage_gap_v
        g_thr = g_result.env_threshold_v
        anodic = g_result.material_anode_key
        pren_fail = not g_result.pren_adequate

        c_score = c_result.composite_score
        c_band = c_result.risk_band
        c_geo = c_result.geometry_class
        cct_ok = c_result.cct_adequacy_score < 0.6

        m_score = m_result.composite_score
        m_band = m_result.risk_band

        overall_score = max(g_score, c_score, m_score)
        g_int, c_int, m_int = _band_int(g_band), _band_int(c_band), _band_int(m_band)
        if g_int >= c_int and g_int >= m_int:
            overall_band = g_band
            dominant = "galvanic"
            mit = _join_mitigations(g_result.mitigations, MITIGATIONS_GC)
        elif c_int >= g_int and c_int >= m_int:
            overall_band = c_band
            dominant = "crevice"
            mit = _join_mitigations(c_result.mitigations, MITIGATIONS_CC)
        else:
            overall_band = m_band
            dominant = "mic"
            mit = _join_mitigations(m_result.mitigations, MITIGATIONS_MIC)

        if not mit:
            mit = _mitigation(
                g_band,
                g_gap,
                c_band,
                c_geo,
                g_result.material_anode_key,
                g_result.environment_class,
            )

        results.append(
            {
                # Identity
                "guid": el.guid,
                "name": el.name,
                "ifc_type": el.ifc_type,
                "description": el.description,
                "floor": el.floor,
                "system": el.system,
                "position": el.position,
                "length_m": el.length_m,
                # Materials
                "material_a": el.material_a,
                "material_b": el.material_b or el.material_a,
                "anodic_material": anodic,
                "environment": el.location_tag,
                "joint_type": el.joint_type,
                # Galvanic
                "galvanic_score": g_score,
                "galvanic_band": g_band,
                "voltage_gap_V": round(g_gap, 4),
                "voltage_threshold": g_thr,
                "pren_fail": pren_fail,
                # Crevice
                "crevice_score": c_score,
                "crevice_band": c_band,
                "crevice_geometry": c_geo,
                "cct_adequate": cct_ok,
                # MIC
                "mic_score": m_score,
                "mic_band": m_band,
                "mic_flow_class": m_result.flow_velocity_class,
                "mic_temperature_class": m_result.temperature_class,
                "mic_dead_leg_class": m_result.dead_leg_class,
                # Overall
                "overall_score": round(overall_score, 4),
                "overall_band": overall_band,
                "dominant_mechanism": dominant,
                "action": _action(overall_band),
                "mitigation": mit,
            }
        )

    return results
