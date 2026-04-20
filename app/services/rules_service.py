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

    # ── Web CRUD ──────────────────────────────────────────────────────────────

    def list_rules(self) -> list[dict]:
        return rows_desc_by_id(self._rules)

    def get_rule(self, rule_id: int) -> dict | None:
        return self._rules.get(rule_id)

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
                "rule_type":          rule_type.strip() or "numeric_comparison",
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
                "rule_type":        rule_type.strip() or "numeric_comparison",
                "description":      description.strip(),
                "target_ifc_class": target_ifc_class.strip(),
                "parameters":       self._norm_json(parameters),
                "updated_at":       now_iso_utc(),
            },
            pk_values=rule_id,
        )

    def delete_rule(self, rule_id: int):
        self._rules.delete(rule_id)

    # ── Pipeline query methods ────────────────────────────────────────────────
    # Used by RuleStore adapter so the CLI pipeline reads from the same table.

    def count(self) -> int:
        return len(list(self._rules.rows))

    def fetch_rules_for_target(self, target_ifc_class: str) -> list[dict]:
        return list(self._rules.rows_where("target_ifc_class = ?", [target_ifc_class]))

    def fetch_mandatory_rules(self) -> list[dict]:
        return list(self._rules.rows_where("severity = 'mandatory'"))

    def fetch_rules_by_ref(self, ref: str) -> list[dict]:
        return list(self._rules.rows_where("reference LIKE ?", [f"%{ref}%"]))

    def fetch_needs_review(self) -> list[dict]:
        return list(self._rules.rows_where("needs_review = 1"))

    def get_existing_entity_types(self) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for r in self._rules.rows:
            t = r.get("target_ifc_class") or ""
            if t and t not in seen:
                seen.add(t)
                result.append(t)
        return result

    def get_rules_sample(self, limit: int = 3) -> list[dict]:
        return list(self._rules.rows_where("severity = 'mandatory'", limit=limit))

    def summary(self) -> dict:
        rules = list(self._rules.rows)
        by_entity: dict[str, int] = {}
        by_source: dict[str, int] = {}
        mandatory_count = 0
        for r in rules:
            target = r.get("target_ifc_class") or ""
            by_entity[target] = by_entity.get(target, 0) + 1
            source = r.get("extraction_method") or ""
            by_source[source] = by_source.get(source, 0) + 1
            if r.get("severity") == "mandatory":
                mandatory_count += 1
        return {
            "total":           len(rules),
            "mandatory_count": mandatory_count,
            "by_entity":       by_entity,
            "by_source":       by_source,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _norm_json(self, value: str) -> str:
        raw = (value or "").strip()
        if not raw:
            return "{}"
        try:
            return json.dumps(json.loads(raw), separators=(",", ":"))
        except json.JSONDecodeError:
            return raw
