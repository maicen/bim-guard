"""Compatibility shim for the historical galvanic engine import path.

This project historically imported ``app.engines.bimguard_galvanic_engine``.
The real implementation lives in ``app.engines.bimguard_corrosion_engine``.
The shim keeps the legacy contract available without duplicating the engine
logic or breaking callers that expect a single ``run_galvanic_compliance_check``
entry point.
"""

from __future__ import annotations

from typing import Any

from app.engines.bimguard_corrosion_engine import GCElement, assess_galvanic_risk


def _coerce_gc_element(element: Any) -> GCElement:
    """Normalise a raw IFC-like object into the galvanic engine input model."""
    info = getattr(element, "get_info", lambda: {})()
    material = info.get("material") or getattr(element, "material", "") or "carbon_steel"
    paired_material = info.get("paired_material") or getattr(element, "paired_material", "") or material
    return GCElement(
        global_id_anode=str(getattr(element, "GlobalId", "anode")),
        global_id_cathode=str(getattr(element, "GlobalId", "cathode")),
        material_anode=str(material),
        material_cathode=str(paired_material),
        anode_area_m2=float(info.get("anode_area_m2", 1.0) or 1.0),
        cathode_area_m2=float(info.get("cathode_area_m2", 1.0) or 1.0),
        zone_category=str(info.get("zone_category") or getattr(element, "zone_category", "") or ""),
        floor=str(info.get("floor") or getattr(element, "floor", "Unknown") or "Unknown"),
        system_type=str(info.get("system_type") or getattr(element, "system_type", "Unknown") or "Unknown"),
    )


def run_galvanic_compliance_check(element: Any) -> dict[str, Any]:
    """Run the galvanic engine and return the historical dict payload."""
    gc_element = _coerce_gc_element(element)
    result = assess_galvanic_risk(gc_element)

    return {
        "band": result.risk_band,
        "score": result.composite_score,
        "details": {
            "voltage_gap_V": result.voltage_gap_v,
            "voltage_threshold": result.env_threshold_v,
            "area_ratio": result.area_ratio,
            "environment_class": result.environment_class,
            "pren_adequate": result.pren_adequate,
            "material_anode": result.material_anode_label,
            "material_cathode": result.material_cathode_label,
            "risk_band": result.risk_band,
        },
    }
