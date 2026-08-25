"""IDS export adapter for rule rows stored in the canonical BIMGuard rule table.

This module intentionally exports only a strict subset of rules that are
compatible with buildingSMART IDS. Proprietary logic such as scoring models,
threshold bands, material-property catalogs, and mitigation catalogues remain in
BIMGuard's internal schema and are not forced into the IDS representation.
"""

from __future__ import annotations

import json
from typing import Any
from xml.etree import ElementTree as ET


_SUPPORTED_OPERATORS = {
    ">=": "ge",
    "<=": "le",
    ">": "gt",
    "<": "lt",
    "=": "eq",
    "==": "eq",
    "!=": "ne",
}


def filter_exportable_rules(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return only the rule rows that are valid for IDS export.

    The canonical BIMGuard rules table stores a broader rule model than pure
    IDS property assertions. Real-world property_check rows often omit a
    property set and express range/existence semantics with value_min/value_max or
    `exists` / `not_exists` operators. We export those as long as they have an
    IFC target and a property name, because those are the essential IDS fields.
    """
    exportable: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("rule_category") or "").strip() != "property_check":
            continue

        target = str(row.get("target_ifc_class") or "").strip()
        prop_name = str(row.get("property_name") or "").strip()
        if not target or not prop_name:
            continue

        # Accept property checks with or without a property set. Many DB records
        # intentionally omit the set because the property is globally unique or
        # is represented by a fallback field instead.
        exportable.append(row)
    return exportable


def _parse_scalar(value: Any) -> Any:
    if value is None or value == "null":
        return None
    if isinstance(value, str):
        lowered = value.strip()
        if lowered in {"", "null"}:
            return None
        try:
            return json.loads(lowered)
        except json.JSONDecodeError:
            return value
    return value


def _operator_tag(operator: str) -> str:
    normalized = str(operator or "").strip()
    if normalized in {"between", "range"}:
        return "between"
    if normalized in {"exists", "not_exists"}:
        return "exists"
    return _SUPPORTED_OPERATORS.get(normalized, "eq")


def _value_text(value: Any) -> str:
    scalar = _parse_scalar(value)
    if scalar is None:
        return ""
    if isinstance(scalar, bool):
        return "true" if scalar else "false"
    return str(scalar)


def _range_values(row: dict[str, Any]) -> tuple[str, str] | None:
    min_value = _value_text(row.get("value_min"))
    max_value = _value_text(row.get("value_max"))
    if min_value or max_value:
        return min_value, max_value
    min_value = _value_text(row.get("value_min_property"))
    max_value = _value_text(row.get("value_max_property"))
    if min_value or max_value:
        return min_value, max_value
    return None


def export_ids_for_ruleset(
    ruleset_id: str,
    rows: list[dict[str, Any]],
    *,
    ifc_schema_version: str = "IFC4",
) -> str:
    """Export the IDS XML for a specific ruleset while filtering to exportable rows."""
    normalized = str(ruleset_id or "").strip()
    scoped_rows = rows if not normalized else [
        row for row in rows if str(row.get("ruleset_id") or "").strip() == normalized
    ]
    export_id = normalized or "bim-guard-export"
    return build_ids_document(
        scoped_rows,
        ifc_schema_version=ifc_schema_version,
        export_identifier=export_id,
    )


def build_ids_document(
    rows: list[dict[str, Any]],
    *,
    ifc_schema_version: str = "IFC4",
    export_identifier: str | None = None,
) -> str:
    """Build an IDS XML document for the subset of rules that are exportable."""
    exportable_rows = filter_exportable_rules(rows)

    ns = {
        "ids": "http://standards.buildingsmart.org/IDS",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    }

    ET.register_namespace("ids", ns["ids"])
    ET.register_namespace("xsi", ns["xsi"])

    ids_root = ET.Element(f"{{{ns['ids']}}}ids")
    ids_root.set("xmlns", ns["ids"])
    ids_root.set("xmlns:xsi", ns["xsi"])
    ids_root.set("xsi:schemaLocation", f"{ns['ids']} https://standards.buildingsmart.org/IDS/1.0/ids.xsd")
    ids_root.set("version", "1.0")
    ids_root.set("identifier", (export_identifier or "bim-guard-export").strip() or "bim-guard-export")

    info = ET.SubElement(ids_root, f"{{{ns['ids']}}}info")
    ET.SubElement(info, f"{{{ns['ids']}}}title").text = "BIMGuard IDS export"
    ET.SubElement(info, f"{{{ns['ids']}}}version").text = ifc_schema_version
    ET.SubElement(info, f"{{{ns['ids']}}}description").text = "Generated from BIMGuard internal property_check rules."

    specifications = ET.SubElement(ids_root, f"{{{ns['ids']}}}specifications")
    for index, row in enumerate(exportable_rows, start=1):
        if row.get("target_ifc_class") is None:
            continue

        spec = ET.SubElement(specifications, f"{{{ns['ids']}}}specification")
        spec.set("ifcVersion", ifc_schema_version)
        spec.set("name", str(row.get("reference") or f"rule-{index}"))

        applicability = ET.SubElement(spec, f"{{{ns['ids']}}}applicability")
        entity = ET.SubElement(applicability, f"{{{ns['ids']}}}entity")
        ET.SubElement(entity, f"{{{ns['ids']}}}name").text = str(row.get("target_ifc_class"))

        requirements = ET.SubElement(spec, f"{{{ns['ids']}}}requirements")
        requirement = ET.SubElement(requirements, f"{{{ns['ids']}}}property")
        requirement.set("dataType", "IFCLABEL")

        pset = str(row.get("property_set") or "").strip()
        if pset:
            requirement.set("uri", pset)
            property_set = ET.SubElement(requirement, f"{{{ns['ids']}}}propertySet")
            property_set.text = pset

        prop_name = ET.SubElement(requirement, f"{{{ns['ids']}}}name")
        prop_name.text = str(row.get("property_name"))

        value = ET.SubElement(requirement, f"{{{ns['ids']}}}value")
        simple = ET.SubElement(value, f"{{{ns['ids']}}}simpleValue")

        operator = str(row.get("operator") or "").strip()
        if operator.lower() in {"between", "range"}:
            range_values = _range_values(row)
            if range_values:
                min_value, max_value = range_values
                lower = ET.SubElement(requirement, f"{{{ns['ids']}}}minValue")
                lower.text = min_value
                upper = ET.SubElement(requirement, f"{{{ns['ids']}}}maxValue")
                upper.text = max_value
                continue

        simple.text = _value_text(row.get("check_value"))

        if operator:
            restriction = ET.SubElement(requirement, f"{{{ns['ids']}}}restriction")
            restriction.set("type", _operator_tag(operator))
            restriction.text = _value_text(row.get("check_value") or row.get("value_min") or row.get("value_max"))

    xml_bytes = ET.tostring(ids_root, encoding="utf-8")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_bytes.decode("utf-8")


def _coerce_ids_scalar(raw: str | None) -> Any:
    """Coerce a text value from IDS XML into Python per BIMGuard conventions."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        if "." in text or "e" in lowered:
            return float(text)
        return int(text)
    except ValueError:
        return text


def _operator_from_ids_type(value: str | None) -> str:
    """Map IDS restriction types to BIMGuard operator strings."""
    normalized = (value or "").strip().lower()
    mapping = {
        "ge": ">=",
        "gt": ">",
        "le": "<=",
        "lt": "<",
        "eq": "=",
        "ne": "!=",
    }
    return mapping.get(normalized, "=")


def import_ids_ruleset(xml_text: str, ruleset_id: str | None = None) -> list[dict[str, Any]]:
    """Parse an IDS XML document and return BIMGuard-compatible rule rows."""
    if not xml_text or not xml_text.strip():
        return []

    try:
        root = ET.fromstring(xml_text.encode("utf-8"))
    except ET.ParseError as exc:  # pragma: no cover - surfaced at the calling API layer
        raise ValueError(f"Invalid IDS XML: {exc}") from exc

    ns = {"ids": "http://standards.buildingsmart.org/IDS"}
    base_ruleset_id = (ruleset_id or root.attrib.get("identifier") or "IMPORTED-IDS").strip()
    rows: list[dict[str, Any]] = []

    for index, spec in enumerate(root.findall(".//ids:specification", ns), start=1):
        spec_name = (spec.attrib.get("name") or f"IDS-{index}").strip()
        entity_name = ""
        entity_el = spec.find("ids:applicability/ids:entity/ids:name", ns)
        if entity_el is not None and entity_el.text:
            entity_name = entity_el.text.strip()

        requirements = spec.findall("ids:requirements/ids:property", ns)
        if not requirements:
            continue

        for requirement in requirements:
            property_set = ""
            property_set_el = requirement.find("ids:propertySet", ns)
            if property_set_el is not None and property_set_el.text:
                property_set = property_set_el.text.strip()

            prop_name = ""
            prop_name_el = requirement.find("ids:name", ns)
            if prop_name_el is not None and prop_name_el.text:
                prop_name = prop_name_el.text.strip()

            if not entity_name or not prop_name:
                continue

            value_el = requirement.find("ids:value", ns)
            min_el = requirement.find("ids:minValue", ns)
            max_el = requirement.find("ids:maxValue", ns)
            restriction_el = requirement.find("ids:restriction", ns)
            simple_value = None
            operator = "="
            check_value = None
            value_min = None
            value_max = None

            if value_el is not None:
                simple_el = value_el.find("ids:simpleValue", ns)
                if simple_el is not None and simple_el.text is not None:
                    simple_value = simple_el.text.strip()
                    check_value = _coerce_ids_scalar(simple_value)
                    operator = "="
            elif min_el is not None or max_el is not None:
                if min_el is not None and min_el.text is not None:
                    value_min = _coerce_ids_scalar(min_el.text)
                if max_el is not None and max_el.text is not None:
                    value_max = _coerce_ids_scalar(max_el.text)
                operator = "between"
            elif restriction_el is not None:
                operator = _operator_from_ids_type(restriction_el.attrib.get("type"))
                restriction_value = restriction_el.text.strip() if restriction_el.text else ""
                check_value = _coerce_ids_scalar(restriction_value)

            rows.append(
                {
                    "reference": spec_name,
                    "rule_type": "numeric_comparison",
                    "description": f"Imported from IDS: {spec_name}",
                    "target_ifc_class": entity_name,
                    "property_set": property_set,
                    "property_name": prop_name,
                    "operator": operator,
                    "check_value": check_value,
                    "value_min": value_min,
                    "value_max": value_max,
                    "rule_category": "property_check",
                    "ruleset_id": base_ruleset_id,
                    "mechanism": "CODE",
                    "severity": "mandatory",
                    "source_text": f"Imported from IDS specification {spec_name}",
                }
            )

    return rows


__all__ = [
    "build_ids_document",
    "export_ids_for_ruleset",
    "filter_exportable_rules",
    "import_ids_ruleset",
]
