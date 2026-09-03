"""
app/services/revit_sync_service.py
------------------------------------
Converts pyRevit push data into Module 4's expected input format so the
compliance pipeline runs unchanged regardless of whether data came from
an IFC file (Module 2) or directly from Revit (pyRevit button).

pyRevit sends:
    {
        "elements": [
            {
                "ifc_class":    "IfcStairFlight",
                "name":         "Stair 1",
                "guid":         "abc-123",
                "storey":       "Level 1",
                "properties":   { "Width": 900.0, "RiserHeight": 175.0 }
            },
            ...
        ]
    }

This service produces the same list[dict] that IFCReader.extract_for_compliance()
returns, so Module 4 and 5 run with zero changes.
"""

from __future__ import annotations

import json

from app.services.rules_service import RuleService


class RevitSyncService:

    def build_extraction_results(
        self, elements: list[dict], theme: str = "Architecture"
    ) -> list[dict]:
        """
        Match pyRevit elements against the rule library and build Module 4 input.

        Args:
            elements: list of element dicts from pyRevit (see module docstring)
            theme:    "Architecture" or "MEP"

        Returns:
            list[dict] matching IFCReader.extract_for_compliance() output
        """
        rules = RuleService().list_by_theme(theme)

        # Index incoming elements by IFC class for O(1) lookup per rule
        by_class: dict[str, list[dict]] = {}
        for el in elements:
            cls = (el.get("ifc_class") or "").strip()
            if cls:
                by_class.setdefault(cls, []).append(el)

        results = []
        for rule in rules:
            target    = (rule.get("target_ifc_class") or "").strip()
            prop_name = (rule.get("property_name") or "").strip()
            operator  = (rule.get("operator") or "").strip()

            if not target or (not prop_name and operator not in ("exists", "not_exists")):
                continue

            element_results = []
            for el in by_class.get(target, []):
                props        = el.get("properties") or {}
                actual_value = props.get(prop_name)

                element_results.append({
                    "guid":           el.get("guid", ""),
                    "name":           el.get("name", ""),
                    "actual_value":   actual_value,
                    "found_pset":     "revit_parameter" if actual_value is not None else None,
                    "found":          actual_value is not None,
                    "value_type":     None,
                    "value_unit":     None,
                    "lower_bound":    None,
                    "upper_bound":    None,
                    "enum_values":    None,
                    "storey":         el.get("storey", ""),
                    "space":          el.get("space", ""),
                    "element_type":   el.get("element_type", ""),
                    "materials":      [],
                    "material_layers": [],
                })

            results.append({
                "rule_id":         rule.get("id"),
                "rule_ref":        str(rule.get("reference") or ""),
                "rule_desc":       str(rule.get("description") or ""),
                "target_ifc_class": target,
                "property_name":   prop_name,
                "property_set":    str(rule.get("property_set") or ""),
                "operator":        operator,
                "check_value":     _decode(rule.get("check_value")),
                "value_min":       _decode(rule.get("value_min")),
                "value_max":       _decode(rule.get("value_max")),
                "unit":            str(rule.get("unit") or ""),
                "severity":        str(rule.get("severity") or "mandatory"),
                "elements":        element_results,
            })

        return results


def _decode(val):
    """Parse a JSON-encoded scalar stored in the DB back to a Python number or None."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return val
    try:
        return json.loads(str(val))
    except Exception:
        return None
