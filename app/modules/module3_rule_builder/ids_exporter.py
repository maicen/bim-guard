"""IDS export adapter for rule rows stored in the canonical BIMGuard rule table.

This module intentionally exports only a strict subset of rules that are
compatible with buildingSMART IDS. Proprietary logic such as scoring models,
threshold bands, material-property catalogs, and mitigation catalogues remain in
BIMGuard's internal schema and are not forced into the IDS representation.

Export (`build_ids_document`) is built via `ifctester.ids` (buildingSMART's
own IDS 1.0 implementation, installed alongside `ifcopenshell`) rather than
hand-built `xml.etree.ElementTree`, so the output is schema-correct for free
instead of an approximation of the IDS 1.0 XSD.

Import (`import_ids_ruleset`) tries the same strict library first — so a
real, schema-correct IDS document (from another tool, or from this module's
own export) parses correctly — and falls back to the original hand-rolled
`xml.etree.ElementTree` parser when strict parsing fails, since it also has
to accept the older, more lenient XML shape this module itself produced
before this refactor (and that existing fixtures/tests are still written
against).
"""

from __future__ import annotations

import json
from typing import Any
from xml.etree import ElementTree as ET

import ifctester.ids as ifctester_ids

from app.logging_config import get_logger

logger = get_logger(__name__)


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


def _is_numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _restriction_for_row(row: dict[str, Any]) -> ifctester_ids.Restriction | None:
    """Build an XSD restriction facet from a row's operator + bound(s), if any.

    Range operators (between) set both minInclusive/maxInclusive. Single-sided
    comparisons set the corresponding one-sided bound. Equality/exists need
    no restriction — the plain `value=` on the Property facet already pins
    the exact value. `!=` has no direct XSD-restriction equivalent and is
    left unrestricted, matching the prior exporter's best-effort behaviour.
    """
    operator = str(row.get("operator") or "").strip().lower()
    base = "double" if _is_numeric(_parse_scalar(row.get("check_value"))) else "string"

    if operator in {"between", "range"}:
        range_values = _range_values(row)
        if not range_values:
            return None
        min_value, max_value = range_values
        options: dict[str, Any] = {}
        if min_value:
            options["minInclusive"] = min_value
        if max_value:
            options["maxInclusive"] = max_value
        return ifctester_ids.Restriction(options=options, base=base) if options else None

    bound_tag = {">=": "minInclusive", ">": "minExclusive", "<=": "maxInclusive", "<": "maxExclusive"}.get(
        operator
    )
    if bound_tag is None:
        return None
    bound_value = _value_text(row.get("check_value"))
    if not bound_value:
        return None
    return ifctester_ids.Restriction(options={bound_tag: bound_value}, base=base)


def build_ids_document(
    rows: list[dict[str, Any]],
    *,
    ifc_schema_version: str = "IFC4",
    export_identifier: str | None = None,
) -> str:
    """Build a schema-correct IDS 1.0 XML document via `ifctester.ids`.

    Raises:
        ValueError: If no row has both a target IFC class and property name —
            the IDS 1.0 schema requires at least one `<specification>`, so
            there is no valid empty document to return.
    """
    exportable_rows = [
        row for row in filter_exportable_rules(rows) if row.get("target_ifc_class")
    ]
    if not exportable_rows:
        raise ValueError(
            "No rows contain both a target IFC class and property name — "
            "IDS 1.0 requires at least one specification."
        )

    document = ifctester_ids.Ids(
        title=(export_identifier or "bim-guard-export").strip() or "bim-guard-export",
        description="Generated from BIMGuard internal property_check rules.",
    )

    for index, row in enumerate(exportable_rows, start=1):
        target = row.get("target_ifc_class")
        if not target:
            continue

        spec = ifctester_ids.Specification(
            name=str(row.get("reference") or f"rule-{index}"),
            ifcVersion=[ifc_schema_version],
        )
        spec.applicability.append(ifctester_ids.Entity(name=str(target)))

        cardinality = str(row.get("cardinality") or "required").strip()
        if cardinality not in {"required", "optional", "prohibited"}:
            cardinality = "required"

        operator = str(row.get("operator") or "").strip().lower()
        restriction = _restriction_for_row(row)
        if restriction is not None:
            value: Any = restriction
        elif operator not in {"exists", "not_exists", ""}:
            value = _value_text(row.get("check_value")) or None
        else:
            value = None

        spec.requirements.append(
            ifctester_ids.Property(
                propertySet=str(row.get("property_set") or "").strip() or "Property_Set",
                baseName=str(row.get("property_name") or "").strip() or "PropertyName",
                value=value,
                cardinality="prohibited" if operator == "not_exists" else cardinality,
            )
        )
        document.specifications.append(spec)

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + document.to_string()


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


def _operator_from_restriction(restriction: "ifctester_ids.Restriction") -> tuple[str, Any, Any, Any]:
    """Map a parsed Restriction facet to (operator, check_value, value_min, value_max)."""
    options = restriction.options or {}
    has_min = "minInclusive" in options or "minExclusive" in options
    has_max = "maxInclusive" in options or "maxExclusive" in options

    if has_min and has_max:
        min_value = options.get("minInclusive", options.get("minExclusive"))
        max_value = options.get("maxInclusive", options.get("maxExclusive"))
        return "between", None, _coerce_ids_scalar(str(min_value)), _coerce_ids_scalar(str(max_value))
    if "minInclusive" in options:
        return ">=", _coerce_ids_scalar(str(options["minInclusive"])), None, None
    if "minExclusive" in options:
        return ">", _coerce_ids_scalar(str(options["minExclusive"])), None, None
    if "maxInclusive" in options:
        return "<=", _coerce_ids_scalar(str(options["maxInclusive"])), None, None
    if "maxExclusive" in options:
        return "<", _coerce_ids_scalar(str(options["maxExclusive"])), None, None
    if "enumeration" in options:
        values = options["enumeration"]
        first = values[0] if isinstance(values, list) and values else values
        return "=", _coerce_ids_scalar(str(first)), None, None
    if "pattern" in options:
        pattern = options["pattern"]
        first = pattern[0] if isinstance(pattern, list) and pattern else pattern
        return "matches", first, None, None
    return "=", None, None, None


def _import_ids_ruleset_strict(xml_text: str, ruleset_id: str | None = None) -> list[dict[str, Any]]:
    """Parse a schema-correct IDS 1.0 document via `ifctester.ids`.

    Raises on anything that isn't valid per the real IDS 1.0 XSD — callers
    should fall back to `_import_ids_ruleset_legacy` for older/lenient XML.
    """
    import tempfile
    from pathlib import Path

    if not xml_text or not xml_text.strip():
        return []

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".ids", encoding="utf-8", delete=False
        ) as tmp_file:
            tmp_file.write(xml_text)
            tmp_path = tmp_file.name
        document = ifctester_ids.open(tmp_path, validate=False)
    except Exception as exc:  # noqa: BLE001 - surfaced at the calling API layer
        raise ValueError(f"Invalid IDS XML: {exc}") from exc
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)

    base_ruleset_id = (ruleset_id or document.info.get("title") or "IMPORTED-IDS").strip()
    rows: list[dict[str, Any]] = []

    for index, spec in enumerate(document.specifications, start=1):
        spec_name = (spec.name or f"IDS-{index}").strip()
        entity_name = ""
        for facet in spec.applicability:
            if isinstance(facet, ifctester_ids.Entity):
                entity_name = str(facet.name or "").strip()
                break

        for requirement in spec.requirements:
            if isinstance(requirement, ifctester_ids.Property):
                prop_name = str(requirement.baseName or "").strip()
                if not entity_name or not prop_name:
                    continue

                operator, check_value, value_min, value_max = "=", None, None, None
                if isinstance(requirement.value, ifctester_ids.Restriction):
                    operator, check_value, value_min, value_max = _operator_from_restriction(
                        requirement.value
                    )
                elif requirement.value is not None:
                    check_value = _coerce_ids_scalar(str(requirement.value))
                elif requirement.cardinality == "prohibited":
                    operator = "not_exists"
                else:
                    operator = "exists"

                rows.append(
                    {
                        "reference": spec_name,
                        "rule_type": "numeric_comparison",
                        "description": f"Imported from IDS: {spec_name}",
                        "target_ifc_class": entity_name,
                        "property_set": str(requirement.propertySet or "").strip(),
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

            elif isinstance(requirement, ifctester_ids.Classification):
                system_name = str(requirement.system or "Classification").strip()
                cls_value = str(requirement.value).strip() if requirement.value is not None else None
                rows.append(
                    {
                        "reference": f"{spec_name}-CLS",
                        "rule_type": "classification_check",
                        "description": f"Imported classification from IDS: {spec_name}",
                        "target_ifc_class": entity_name,
                        "property_set": system_name,
                        "property_name": "Classification",
                        "operator": "=",
                        "check_value": cls_value,
                        "rule_category": "property_check",
                        "ruleset_id": base_ruleset_id,
                        "mechanism": "CODE",
                        "severity": "mandatory",
                        "source_text": f"Imported classification {system_name}",
                    }
                )

            elif isinstance(requirement, ifctester_ids.Material):
                mat_value = str(requirement.value).strip() if requirement.value is not None else None
                rows.append(
                    {
                        "reference": f"{spec_name}-MAT",
                        "rule_type": "material_check",
                        "description": f"Imported material from IDS: {spec_name}",
                        "target_ifc_class": entity_name,
                        "property_set": "Material",
                        "property_name": "Material",
                        "operator": "=",
                        "check_value": mat_value,
                        "rule_category": "property_check",
                        "ruleset_id": base_ruleset_id,
                        "mechanism": "CODE",
                        "severity": "mandatory",
                        "source_text": f"Imported material requirement for {entity_name}",
                    }
                )

    return rows


def _operator_from_ids_type(value: str | None) -> str:
    """Map IDS restriction types to BIMGuard operator strings (legacy parser)."""
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


def _import_ids_ruleset_legacy(xml_text: str, ruleset_id: str | None = None) -> list[dict[str, Any]]:
    """Hand-rolled ElementTree parser for the module's pre-refactor XML shape.

    Kept for XML this module produced before the `ifctester.ids`-based
    export existed (plain text nodes rather than `<simpleValue>`-wrapped
    ones, and an invented `<minValue>`/`<maxValue>` range shape that isn't
    part of the real IDS 1.0 schema).
    """
    try:
        root = ET.fromstring(xml_text.encode("utf-8"))
    except ET.ParseError as exc:
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

            tolerance_attr = requirement.attrib.get("tolerance")
            tolerance = _coerce_ids_scalar(tolerance_attr) if tolerance_attr else None

            value_el = requirement.find("ids:value", ns)
            min_el = requirement.find("ids:minValue", ns)
            max_el = requirement.find("ids:maxValue", ns)
            restriction_el = requirement.find("ids:restriction", ns)
            operator = "="
            check_value = None
            value_min = None
            value_max = None

            if value_el is not None:
                simple_el = value_el.find("ids:simpleValue", ns)
                if simple_el is not None and simple_el.text is not None:
                    check_value = _coerce_ids_scalar(simple_el.text.strip())
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
                    "tolerance": tolerance,
                    "rule_category": "property_check",
                    "ruleset_id": base_ruleset_id,
                    "mechanism": "CODE",
                    "severity": "mandatory",
                    "source_text": f"Imported from IDS specification {spec_name}",
                }
            )

        for req_cls in spec.findall("ids:requirements/ids:classification", ns):
            system_el = req_cls.find("ids:system", ns)
            val_el = req_cls.find("ids:value", ns)
            system_name = system_el.text.strip() if system_el is not None and system_el.text else "Classification"
            cls_value = val_el.text.strip() if val_el is not None and val_el.text else None
            rows.append(
                {
                    "reference": f"{spec_name}-CLS",
                    "rule_type": "classification_check",
                    "description": f"Imported classification from IDS: {spec_name}",
                    "target_ifc_class": entity_name,
                    "property_set": system_name,
                    "property_name": "Classification",
                    "operator": "=",
                    "check_value": cls_value,
                    "rule_category": "property_check",
                    "ruleset_id": base_ruleset_id,
                    "mechanism": "CODE",
                    "severity": "mandatory",
                    "source_text": f"Imported classification {system_name}",
                }
            )

        for req_mat in spec.findall("ids:requirements/ids:material", ns):
            val_el = req_mat.find("ids:value", ns)
            mat_value = val_el.text.strip() if val_el is not None and val_el.text else None
            rows.append(
                {
                    "reference": f"{spec_name}-MAT",
                    "rule_type": "material_check",
                    "description": f"Imported material from IDS: {spec_name}",
                    "target_ifc_class": entity_name,
                    "property_set": "Material",
                    "property_name": "Material",
                    "operator": "=",
                    "check_value": mat_value,
                    "rule_category": "property_check",
                    "ruleset_id": base_ruleset_id,
                    "mechanism": "CODE",
                    "severity": "mandatory",
                    "source_text": f"Imported material requirement for {entity_name}",
                }
            )

    return rows


def import_ids_ruleset(xml_text: str, ruleset_id: str | None = None) -> list[dict[str, Any]]:
    """Parse an IDS XML document into BIMGuard-compatible rule rows.

    Tries the strict `ifctester.ids` parser first (correct for real,
    schema-valid IDS 1.0 documents); falls back to a lenient hand-rolled
    parser for the older, non-schema-strict shape this module itself
    produced before its export was refactored onto `ifctester.ids`.
    """
    if not xml_text or not xml_text.strip():
        return []

    try:
        return _import_ids_ruleset_strict(xml_text, ruleset_id)
    except ValueError:
        logger.debug("Strict IDS parse failed; falling back to legacy parser", exc_info=True)
        return _import_ids_ruleset_legacy(xml_text, ruleset_id)


def translate_rule_drafts_to_ids(
    drafts: list[Any], *, ifc_schema_version: str = "IFC4", export_identifier: str | None = None
) -> str:
    """Build an IDS XML preview directly from extraction drafts, before promotion.

    Accepts `RuleExtractionDraft` objects (see app.modules.contracts) — each
    draft's `proposed_rule` is projected into the same row shape
    `build_ids_document` expects from canonical `rules` table rows, so a
    reviewer can preview the IDS a draft would produce without first
    promoting it into `public.rules`.

    `RuleCreateRequest` carries no target-IFC-class field (a pre-existing
    contract gap — the canonical `rules` table's `target_ifc_class` column
    is never populated by the extraction/bulk-save path today either), so
    drafts without one are filtered out by `filter_exportable_rules` just as
    canonical rule rows without a target are.
    """
    rows = [
        {
            "reference": draft.proposed_rule.rule_id,
            "rule_category": draft.proposed_rule.rule_category or "property_check",
            "target_ifc_class": "",
            "property_set": draft.proposed_rule.property_set or "",
            "property_name": draft.proposed_rule.property_name or "",
            "operator": draft.proposed_rule.operator or "==",
            "check_value": draft.proposed_rule.check_value,
            "value_min": draft.proposed_rule.value_min,
            "value_max": draft.proposed_rule.value_max,
            "value_min_property": draft.proposed_rule.value_min_property,
            "value_max_property": draft.proposed_rule.value_max_property,
        }
        for draft in drafts
    ]
    return build_ids_document(
        rows, ifc_schema_version=ifc_schema_version, export_identifier=export_identifier
    )


__all__ = [
    "build_ids_document",
    "export_ids_for_ruleset",
    "filter_exportable_rules",
    "import_ids_ruleset",
    "translate_rule_drafts_to_ids",
]

