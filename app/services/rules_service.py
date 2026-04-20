import json

from app.services.persistence import PersistenceService
from app.utils import now_iso_utc, rows_desc_by_id

# Columns added in the rich-schema upgrade.
# PersistenceService.get_table() uses required_columns to ALTER TABLE
# for any column that does not yet exist, so old DBs migrate automatically.
_RICH_COLUMNS = {
    "source_text":        str,
    "property_set":       str,
    "property_name":      str,
    "fallback_property":  str,
    "operator":           str,
    "check_value":        str,   # JSON-encoded scalar / null
    "value_min":          str,
    "value_max":          str,
    "unit":               str,
    "applies_when":       str,   # JSON object string
    "severity":           str,
    "keyword":            str,
    "compliance_type":    str,
    "exceptions":         str,   # JSON array string
    "related_refs":       str,   # JSON array string
    "overridden_by":      str,
    "confidence":         str,
    "extraction_method":  str,
    "needs_review":       int,
}


class RuleService:
    """Encapsulates CRUD operations for compliance rules."""

    def __init__(self):
        self._rules = PersistenceService.get_table(
            "rules",
            {
                "id":             int,
                "reference":      str,
                "rule_type":      str,
                "description":    str,
                "target_ifc_class": str,
                "parameters":     str,   # kept for backward-compat
                "created_at":     str,
                "updated_at":     str,
            },
            required_columns=_RICH_COLUMNS,
        )

    # ── Queries ───────────────────────────────────────────────────────────────

    def list_rules(self):
        return rows_desc_by_id(self._rules)

    def get_rule(self, rule_id: int):
        return self._rules.get(rule_id)

    # ── Writes ────────────────────────────────────────────────────────────────

    def create_rule(
        self,
        reference: str,
        rule_type: str,
        description: str,
        target_ifc_class: str,
        parameters: str = "{}",
        # rich-schema fields (all optional for backward compat)
        source_text: str = "",
        property_set: str = "",
        property_name: str = "",
        fallback_property: str = "",
        operator: str = "",
        check_value=None,
        value_min=None,
        value_max=None,
        unit: str = "",
        applies_when: dict | None = None,
        severity: str = "mandatory",
        keyword: str = "",
        compliance_type: str = "",
        exceptions: list | None = None,
        related_refs: list | None = None,
        overridden_by: str = "",
        confidence: float | None = None,
        extraction_method: str = "manual",
        needs_review: bool = False,
    ):
        now = now_iso_utc()
        return self._rules.insert(
            {
                "reference":          reference.strip(),
                "rule_type":          rule_type.strip() or "numeric_range",
                "description":        description.strip(),
                "target_ifc_class":   target_ifc_class.strip(),
                "parameters":         self._norm_json(parameters),
                "source_text":        source_text or "",
                "property_set":       property_set or "",
                "property_name":      property_name or "",
                "fallback_property":  fallback_property or "",
                "operator":           operator or "",
                "check_value":        json.dumps(check_value),
                "value_min":          json.dumps(value_min),
                "value_max":          json.dumps(value_max),
                "unit":               unit or "",
                "applies_when":       json.dumps(applies_when or {}),
                "severity":           severity or "mandatory",
                "keyword":            keyword or "",
                "compliance_type":    compliance_type or "",
                "exceptions":         json.dumps(exceptions or []),
                "related_refs":       json.dumps(related_refs or []),
                "overridden_by":      overridden_by or "",
                "confidence":         str(confidence) if confidence is not None else "",
                "extraction_method":  extraction_method or "manual",
                "needs_review":       int(needs_review),
                "created_at":         now,
                "updated_at":         now,
            }
        )

    def update_rule(
        self,
        rule_id: int,
        reference: str,
        rule_type: str,
        description: str,
        target_ifc_class: str,
        parameters: str = "{}",
    ):
        self._rules.update(
            updates={
                "reference":        reference.strip(),
                "rule_type":        rule_type.strip() or "numeric_range",
                "description":      description.strip(),
                "target_ifc_class": target_ifc_class.strip(),
                "parameters":       self._norm_json(parameters),
                "updated_at":       now_iso_utc(),
            },
            pk_values=rule_id,
        )

    def delete_rule(self, rule_id: int):
        self._rules.delete(rule_id)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _norm_json(self, value: str) -> str:
        raw = (value or "").strip()
        if not raw:
            return "{}"
        try:
            return json.dumps(json.loads(raw), separators=(",", ":"))
        except json.JSONDecodeError:
            return raw
