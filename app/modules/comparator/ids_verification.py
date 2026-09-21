"""Generic buildingSMART IDS/LOIN and bSDD semantic verification.

Framework-agnostic checks against IFC elements: neither depends on any
compliance engine, so they apply to any analysis domain's element set.
"""

from typing import Any


def run_ids_loin_verification(elements: list[Any], ids_rules: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate IFC elements against Level of Information Need (LOIN) / buildingSMART IDS rules.

    Checks:
    - Required Property Sets and Property Names
    - Value tolerances and range boundaries (e.g. min/max, tolerance +/- delta)
    - Material assignments
    - Classifications (e.g. Uniclass 2015 / OmniClass)
    """
    total_checks = 0
    passed_checks = 0
    violations = []

    for element in elements:
        if hasattr(element, "is_a") and callable(getattr(element, "is_a")):
            element_type = element.is_a()
        elif isinstance(element, dict) and callable(element.get("is_a")):
            element_type = element["is_a"]()
        elif isinstance(element, dict):
            element_type = str(element.get("element_type") or element.get("is_a") or "")
        else:
            element_type = getattr(element, "element_type", "") or ""

        guid = str(getattr(element, "GlobalId", None) or (element.get("GlobalId") if isinstance(element, dict) else None) or getattr(element, "global_id", None) or "")
        info = element.get_info() if hasattr(element, "get_info") and callable(getattr(element, "get_info")) else (element.get("get_info")() if isinstance(element, dict) and callable(element.get("get_info")) else (element if isinstance(element, dict) else {}))

        for rule in ids_rules:
            target_class = str(rule.get("target_ifc_class") or "").strip()
            if target_class and target_class != "*" and target_class.lower() != element_type.lower():
                continue

            prop_name = str(rule.get("property_name") or "").strip()
            pset = str(rule.get("property_set") or "").strip()
            rule_ref = str(rule.get("reference") or f"LOIN-{rule.get('id', '0')}")
            check_value = rule.get("check_value")
            value_min = rule.get("value_min")
            value_max = rule.get("value_max")
            tolerance = rule.get("tolerance")

            total_checks += 1
            has_prop = False
            prop_val = None

            if isinstance(info, dict):
                if prop_name in info:
                    has_prop = True
                    prop_val = info[prop_name]
                elif pset and isinstance(info.get("psets"), dict) and pset in info["psets"] and prop_name in info["psets"][pset]:
                    has_prop = True
                    prop_val = info["psets"][pset][prop_name]
                elif pset and pset in info.get("psets", {}):
                    has_prop = True

            if not has_prop and hasattr(element, prop_name):
                has_prop = True
                prop_val = getattr(element, prop_name)

            # Check material or classification rules
            if not has_prop and prop_name.lower() == "material":
                mat = getattr(element, "material", None) or (info.get("material") if isinstance(info, dict) else None)
                if mat:
                    has_prop = True
                    prop_val = mat
            elif not has_prop and "classification" in prop_name.lower():
                cls = getattr(element, "classification", None) or (info.get("classification") if isinstance(info, dict) else None)
                if cls:
                    has_prop = True
                    prop_val = cls

            if not has_prop:
                violations.append({
                    "element_guid": guid,
                    "element_type": element_type,
                    "rule_reference": rule_ref,
                    "property_set": pset,
                    "property_name": prop_name,
                    "message": f"Element {guid} ({element_type}) missing required LOIN property '{prop_name}' in pset '{pset or 'Default'}'",
                })
                continue

            # Value & tolerance validation
            value_valid = True
            if prop_val is not None and check_value is not None and tolerance is not None:
                try:
                    num_actual = float(prop_val)
                    num_target = float(check_value)
                    num_tol = float(tolerance)
                    if abs(num_actual - num_target) > num_tol:
                        value_valid = False
                        violations.append({
                            "element_guid": guid,
                            "element_type": element_type,
                            "rule_reference": rule_ref,
                            "property_set": pset,
                            "property_name": prop_name,
                            "message": f"Element {guid} value {num_actual} for '{prop_name}' exceeds tolerance +/-{num_tol} of target {num_target}",
                        })
                except (ValueError, TypeError):
                    pass
            elif prop_val is not None and (value_min is not None or value_max is not None):
                try:
                    num_actual = float(prop_val)
                    if value_min is not None and num_actual < float(value_min):
                        value_valid = False
                        violations.append({
                            "element_guid": guid,
                            "element_type": element_type,
                            "rule_reference": rule_ref,
                            "property_set": pset,
                            "property_name": prop_name,
                            "message": f"Element {guid} value {num_actual} for '{prop_name}' is below minimum required {value_min}",
                        })
                    elif value_max is not None and num_actual > float(value_max):
                        value_valid = False
                        violations.append({
                            "element_guid": guid,
                            "element_type": element_type,
                            "rule_reference": rule_ref,
                            "property_set": pset,
                            "property_name": prop_name,
                            "message": f"Element {guid} value {num_actual} for '{prop_name}' exceeds maximum allowed {value_max}",
                        })
                except (ValueError, TypeError):
                    pass

            if value_valid:
                passed_checks += 1

    compliance_percent = 100.0 if total_checks == 0 else round((passed_checks / total_checks) * 100.0, 2)
    return {
        "passed": compliance_percent == 100.0 and len(violations) == 0,
        "compliance_percent": compliance_percent,
        "total_checks": total_checks,
        "passed_checks": passed_checks,
        "failed_checks": len(violations),
        "violations": violations,
    }


def run_bsdd_semantic_verification(
    elements: list[Any],
    dictionary_uri: str = "https://identifier.buildingsmart.org/uri/buildingsmart/ifc-4.3",
    bsdd_client: Any | None = None,
) -> dict[str, Any]:
    """Validate IFC elements against global buildingSMART Data Dictionaries (bSDD).

    Cross-references extracted material definitions, default properties, and property
    sets with bSDD allowed values and classifications instead of hardcoded dictionaries.
    """
    from app.services.bsdd_client import DEFAULT_BSDD_CLIENT

    client = bsdd_client or DEFAULT_BSDD_CLIENT
    all_violations = []
    total_checks = 0
    passed_checks = 0

    for element in elements:
        res = client.validate_element_semantics(element, dictionary_uri=dictionary_uri)
        total_checks += res.total_properties_checked
        passed_checks += res.passed_count
        for v in res.violations:
            all_violations.append(
                {
                    "element_guid": v.element_guid,
                    "element_type": v.element_type,
                    "field_checked": v.field_checked,
                    "expected_constraint": v.expected_constraint,
                    "actual_value": v.actual_value,
                    "severity": v.severity,
                    "message": v.message,
                    "dictionary_uri": v.dictionary_uri or dictionary_uri,
                }
            )

    score = 100.0 if total_checks == 0 else round((passed_checks / total_checks) * 100.0, 2)
    has_blocking_errors = any(v["severity"] == "error" for v in all_violations)

    return {
        "passed": not has_blocking_errors,
        "dictionary_uri": dictionary_uri,
        "total_elements_checked": len(elements),
        "total_checks": total_checks,
        "passed_checks": passed_checks,
        "failed_checks": len(all_violations),
        "compliance_percent": score,
        "violations": all_violations,
    }
