import json

from app.services.persistence import PersistenceService
from app.utils import now_iso_utc, rows_desc_by_id


class RuleService:
    """Encapsulates CRUD operations for compliance rules."""

    def __init__(self):
        self._rules = PersistenceService.get_table(
            "rules",
            {
                "id": int,
                "reference": str,
                "rule_type": str,
                "description": str,
                "target_ifc_class": str,
                "parameters": str,
                "created_at": str,
                "updated_at": str,
            },
        )

    def list_rules(self):
        return rows_desc_by_id(self._rules)

    def get_rule(self, rule_id: int):
        return self._rules.get(rule_id)

    def create_rule(
        self,
        reference: str,
        rule_type: str,
        description: str,
        target_ifc_class: str,
        parameters: str,
    ):
        now = now_iso_utc()
        normalized_parameters = self._normalize_parameters(parameters)
        return self._rules.insert(
            {
                "reference": reference.strip(),
                "rule_type": rule_type.strip() or "Required",
                "description": description.strip(),
                "target_ifc_class": target_ifc_class.strip(),
                "parameters": normalized_parameters,
                "created_at": now,
                "updated_at": now,
            }
        )

    def update_rule(
        self,
        rule_id: int,
        reference: str,
        rule_type: str,
        description: str,
        target_ifc_class: str,
        parameters: str,
    ):
        self._rules.update(
            updates={
                "reference": reference.strip(),
                "rule_type": rule_type.strip() or "Required",
                "description": description.strip(),
                "target_ifc_class": target_ifc_class.strip(),
                "parameters": self._normalize_parameters(parameters),
                "updated_at": now_iso_utc(),
            },
            pk_values=rule_id,
        )

    def delete_rule(self, rule_id: int):
        self._rules.delete(rule_id)

    def _normalize_parameters(self, value: str) -> str:
        raw = (value or "").strip()
        if not raw:
            return "{}"

        try:
            parsed = json.loads(raw)
            return json.dumps(parsed, separators=(",", ":"), ensure_ascii=True)
        except json.JSONDecodeError:
            # Preserve non-JSON free text to avoid destructive edits.
            return raw
