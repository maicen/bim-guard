from typing import Any
from pathlib import Path
 
from app.engines.bimguard_galvanic_engine import (
    run_galvanic_compliance_check,
)
from app.engines.bimguard_crevice_engine import (
    run_crevice_compliance_check,
)
from app.engines.bimguard_mic_engine import (
    run_mic_compliance_check,
)
 
 
def _band_int(b: str) -> int:
    """Rank a risk band for dominance comparison.
 
    Engines emit Title-case labels ("Low", "Critical"); the band is
    normalised to upper case so any casing ranks correctly. Unknown or
    empty bands rank lowest.
    """
    return {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}.get((b or "").upper(), 0)
 
 
def _mitigation(g_band, g_gap, c_band, c_geo, mat, env) -> str:
    overall = max(g_band, c_band, key=_band_int).upper()
    if overall == "LOW":
        return "None required — log in asset register"
    if overall == "CRITICAL":
        return "BLOCK — compliance failure; notify client; redesign or substitution mandatory"
    if g_band == "CRITICAL" or c_band == "CRITICAL":
        return "BLOCK — BCF issued; confirm resolution before next model issue"
    if mat == "Copper" and env == "Sulfidizing":
        return "Isolate — gasket required; add to inspection schedule"
    if c_geo == "Crevice" and c_band in ("HIGH", "CRITICAL"):
        return "Specify isolation gasket; ensure positive drainage; add to inspection schedule"
    return "Specify isolation gasket; ensure positive drainage; add to inspection schedule"
 
 
def _action(band: str) -> str:
    """Return the compliance action text for a risk band.
 
    The band is normalised to upper case so Title-case engine labels
    resolve; an unrecognised band falls back to the LOW action rather
    than raising KeyError.
    """
    actions = {
        "LOW": "Log — include in corrosion asset register, no immediate action",
        "MEDIUM": "Flag — specify mitigation on next drawing issue; raise RFI",
        "HIGH": "BLOCK — BCF issued; lead engineer to confirm resolution before next model issue",
        "CRITICAL": "BLOCK — compliance failure; notify client; redesign or substitution mandatory",
    }
    return actions.get((band or "").upper(), actions["LOW"])
 
 
def _join_mitigations(codes: list[str], catalogue: dict[str, str]) -> str:
    if not codes:
        return ""
    return "; ".join(catalogue.get(c, "") for c in codes if c in catalogue)
 
 
def run_compliance_checks(elements: list[Any]) -> list[dict]:
    """Run the five corrosion engines against a list of IFC elements.
    
    Emits one dict per element, with keys:
    - guid, name, element_type (from IFC)
    - galvanic_band, galvanic_score, galvanic_details
    - crevice_band, crevice_score, crevice_details
    - mic_band, mic_score, mic_details
    - dominant_mechanism (the worst-case engine)
    - mitigation, action (combined across all three)
    """
    results = []
    
    for element in elements:
        g_result = run_galvanic_compliance_check(element)
        c_result = run_crevice_compliance_check(element)
        m_result = run_mic_compliance_check(element)
        
        # Determine dominant mechanism
        bands = [
            (g_result.get("band", "LOW"), "galvanic"),
            (c_result.get("band", "LOW"), "crevice"),
            (m_result.get("band", "LOW"), "mic"),
        ]
        dominant_band, dominant_mechanism = max(bands, key=lambda x: _band_int(x[0]))
        
        result = {
            "guid": element.GlobalId,
            "name": element.Name,
            "element_type": element.is_a(),
            "galvanic_band": g_result.get("band", "LOW"),
            "galvanic_score": g_result.get("score", 0.0),
            "galvanic_details": g_result.get("details", {}),
            "crevice_band": c_result.get("band", "LOW"),
            "crevice_score": c_result.get("score", 0.0),
            "crevice_details": c_result.get("details", {}),
            "mic_band": m_result.get("band", "LOW"),
            "mic_score": m_result.get("score", 0.0),
            "mic_details": m_result.get("details", {}),
            "dominant_mechanism": dominant_mechanism,
            "mitigation": _mitigation(
                g_result.get("band", "LOW"),
                g_result.get("details", {}).get("voltage_gap_V", 0),
                c_result.get("band", "LOW"),
                c_result.get("details", {}).get("crevice_geometry", ""),
                element.get_info().get("material", ""),
                element.get_info().get("environment", ""),
            ),
            "action": _action(dominant_band),
        }
        results.append(result)
    
    return results
 