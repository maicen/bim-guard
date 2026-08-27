from typing import Any

from app.engines.bimguard_corrosion_engine import GCElement, assess_galvanic_risk
from app.engines.bimguard_crevice_engine import CCElement, assess_crevice_risk
from app.engines.bimguard_mic_engine import MICElement, assess_mic_risk
from app.modules.module4_comparator.engine_registry import DEFAULT_ENGINE_REGISTRY, register_default_engines


def _coerce_gc_element(element: Any) -> GCElement:
    info = getattr(element, "get_info", lambda: {})()
    material = info.get("material") or getattr(element, "material", "") or "carbon_steel"
    paired = info.get("paired_material") or getattr(element, "paired_material", "") or material
    return GCElement(
        global_id_anode=str(getattr(element, "GlobalId", "anode")),
        global_id_cathode=str(getattr(element, "GlobalId", "cathode")),
        material_anode=str(material),
        material_cathode=str(paired),
        anode_area_m2=float(info.get("anode_area_m2", 1.0) or 1.0),
        cathode_area_m2=float(info.get("cathode_area_m2", 1.0) or 1.0),
        zone_category=str(info.get("zone_category") or getattr(element, "zone_category", "") or ""),
        floor=str(info.get("floor") or getattr(element, "floor", "Unknown") or "Unknown"),
        system_type=str(info.get("system_type") or getattr(element, "system_type", "Unknown") or "Unknown"),
    )


def _coerce_cc_element(element: Any) -> CCElement:
    info = getattr(element, "get_info", lambda: {})()
    return CCElement(
        global_id=str(getattr(element, "GlobalId", None) or getattr(element, "global_id", "")),
        element_type=str(getattr(element, "is_a", lambda: getattr(element, "element_type", ""))() or "IfcPipeSegment"),
        material=str(info.get("material") or getattr(element, "material", "") or "stainless_steel"),
        joint_description=str(info.get("joint_description") or getattr(element, "joint_description", "") or "tight"),
        operating_temp_c=float(info.get("operating_temp_c") or getattr(element, "operating_temp_c", 20.0) or 20.0),
        zone_category=str(info.get("zone_category") or getattr(element, "zone_category", "") or ""),
        system_type=str(info.get("system_type") or getattr(element, "system_type", "Unknown") or "Unknown"),
        floor=str(info.get("floor") or getattr(element, "floor", "Unknown") or "Unknown"),
    )


def _coerce_mic_element(element: Any) -> MICElement:
    info = getattr(element, "get_info", lambda: {})()
    return MICElement(
        global_id=str(getattr(element, "GlobalId", None) or getattr(element, "global_id", "")),
        element_type=str(getattr(element, "is_a", lambda: getattr(element, "element_type", ""))() or "IfcPipeSegment"),
        system_type=str(info.get("system_type") or getattr(element, "system_type", "Unknown") or "Unknown"),
        material=str(info.get("material") or getattr(element, "material", "") or "carbon_steel"),
        nominal_diameter_m=float(info.get("nominal_diameter_m") or getattr(element, "nominal_diameter_m", 0.1) or 0.1),
        flow_velocity_ms=info.get("flow_velocity_ms", getattr(element, "flow_velocity_ms", None)),
        operating_temp_c=info.get("operating_temp_c", getattr(element, "operating_temp_c", None)),
        dead_leg_length_m=info.get("dead_leg_length_m", getattr(element, "dead_leg_length_m", None)),
        insulation_condition=str(info.get("insulation_condition") or getattr(element, "insulation_condition", "unknown") or "unknown"),
        floor=str(info.get("floor") or getattr(element, "floor", "Unknown") or "Unknown"),
        zone=str(info.get("zone") or getattr(element, "zone", "Unknown") or "Unknown"),
    )


def run_galvanic_compliance_check(element: Any) -> dict[str, Any]:
    """Compatibility wrapper returning the runner payload used by Module 4."""
    result = assess_galvanic_risk(_coerce_gc_element(element))
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
            "crevice_geometry": "",
        },
    }


def run_crevice_compliance_check(element: Any) -> dict[str, Any]:
    """Compatibility wrapper returning the runner payload used by Module 4."""
    result = assess_crevice_risk(_coerce_cc_element(element))
    return {
        "band": result.risk_band,
        "score": result.composite_score,
        "details": {
            "crevice_geometry": result.geometry_class,
            "joint_type": result.joint_type_code,
            "cct_adequate": result.cct_adequacy_score,
            "environment_severity": result.environment_severity_key,
        },
    }


def run_mic_compliance_check(element: Any) -> dict[str, Any]:
    """Compatibility wrapper returning the runner payload used by Module 4."""
    result = assess_mic_risk(_coerce_mic_element(element))
    return {
        "band": result.risk_band,
        "score": result.composite_score,
        "details": {
            "flow_class": result.flow_velocity_class,
            "temperature_class": result.temperature_class,
            "dead_leg_class": result.dead_leg_class,
            "material_susceptibility": result.material_susceptibility_score,
        },
    }


def run_compliance(elements: list[Any]) -> list[dict]:
    """Compatibility wrapper used by the orchestrator and legacy callers."""
    return run_compliance_checks(elements)


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


# Ensure the default registry is populated once the runner's own evaluator
# functions are available. This preserves the current public API while avoiding
# module import cycles during package load.
register_default_engines()


def _band_or_none(engine_result: dict) -> str | None:
    """Return the band an engine reported, or ``None`` if it reported none.

    Previously this was ``engine_result.get("band", "LOW")``. Substituting
    ``"LOW"`` made "not assessed" indistinguishable from "assessed and cleared":
    the element carried a band no engine produced, ``issue_adapter``'s
    ``if band_key not in result`` guard could never fire because the key was
    always written, and ``include_low=False`` then dropped the element
    entirely. An element the engines never touched vanished from the findings.

    Returning ``None`` — and omitting the key downstream — restores the guard.
    It deliberately does **not** raise: ``piping_schema``'s nullability policy
    requires a comparator that cannot run to emit a Low-severity
    ``mechanism="data_quality"`` issue "rather than crashing", and one
    unassessable element must not abort an analysis over thousands. See
    ``docs/PHASE_6_DATA_CONTRACTS.md`` §4.2, failure mode 5.
    """
    band = engine_result.get("band")
    if band is None or (isinstance(band, str) and not band.strip()):
        return None
    return band


def run_compliance_checks(elements: list[Any]) -> list[dict]:
    """Run the five corrosion engines against a list of IFC elements.

    Emits one dict per element, with keys:
    - guid, name, element_type (from IFC)
    - galvanic_band, galvanic_score, galvanic_details
    - crevice_band, crevice_score, crevice_details
    - mic_band, mic_score, mic_details
    - dominant_mechanism (the worst-case engine)
    - mitigation, action (combined across all three)

    The per-engine calls are resolved through a shared registry so future rule
    families can be added without expanding this function with more conditionals.
    """
    results = []

    for element in elements:
        g_result = DEFAULT_ENGINE_REGISTRY.evaluate("GC-001", element)
        c_result = DEFAULT_ENGINE_REGISTRY.evaluate("CC-001", element)
        m_result = DEFAULT_ENGINE_REGISTRY.evaluate("MC-001", element)

        info = getattr(element, "get_info", lambda: {})()
        details = info if isinstance(info, dict) else {}
        material = (
            details.get("material")
            or getattr(element, "material", None)
            or getattr(element, "Material", None)
            or ""
        )
        environment = (
            details.get("environment")
            or getattr(element, "environment", None)
            or getattr(element, "Environment", None)
            or ""
        )
        guid = getattr(element, "GlobalId", None) or getattr(element, "global_id", None) or getattr(element, "id", "")
        name = getattr(element, "Name", None) or getattr(element, "name", None) or "Unknown"
        element_type = getattr(element, "is_a", lambda: getattr(element, "element_type", ""))()

        # Assessed mechanisms only. A mechanism that produced no band is left
        # out entirely rather than given one — see _band_or_none.
        assessed = [
            (_band_or_none(g_result), "galvanic", g_result),
            (_band_or_none(c_result), "crevice", c_result),
            (_band_or_none(m_result), "mic", m_result),
        ]
        scored = [(band, mech) for band, mech, _ in assessed if band is not None]

        if scored:
            dominant_band, dominant_mechanism = max(scored, key=lambda x: _band_int(x[0]))
        else:
            # Nothing was assessed. Saying "LOW / galvanic" here would assert a
            # verdict no engine reached.
            dominant_band, dominant_mechanism = "", ""

        result = {
            "guid": guid,
            "name": name,
            "element_type": element_type,
            "dominant_mechanism": dominant_mechanism,
            "mitigation": _mitigation(
                _band_or_none(g_result) or "",
                g_result.get("details", {}).get("voltage_gap_V", 0),
                _band_or_none(c_result) or "",
                c_result.get("details", {}).get("crevice_geometry", ""),
                material,
                environment,
            ),
            "action": _action(dominant_band),
        }

        # Per-mechanism keys are written only for mechanisms that ran, so
        # issue_adapter's "if band_key not in result" guard can do its job.
        for band, mechanism, raw in assessed:
            if band is None:
                continue
            result[f"{mechanism}_band"] = band
            result[f"{mechanism}_score"] = raw.get("score", 0.0)
            result[f"{mechanism}_details"] = raw.get("details", {})

        results.append(result)

    return results
