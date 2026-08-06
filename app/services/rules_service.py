"""Rule persistence service for CRUD, lookup, and ruleset import operations."""

import json
from typing import Any

from postgrest.exceptions import APIError

from app.services.persistence import PersistenceService
from app.utils import now_iso_utc, rows_desc_by_id

# ── Schema columns ────────────────────────────────────────────────────────────

_RICH_COLUMNS = {
    "source_text": str,
    "property_set": str,
    "property_name": str,
    "fallback_property": str,
    "operator": str,
    "check_value": str,  # JSON-encoded scalar / null
    "value_min": str,
    "value_max": str,
    # Relative bounds: when set, value_min/value_max above are ignored and the
    # bound is instead resolved per-element as (that element's own named
    # property + offset) — e.g. "tread depth between its run and its run plus
    # 25mm" -> value_max_property="Run", value_max_offset=25. Lets a rule
    # compare one property against another property of the SAME element
    # instead of only a fixed literal number.
    "value_min_property": str,
    "value_max_property": str,
    "value_min_offset": str,  # JSON-encoded numeric, default 0
    "value_max_offset": str,  # JSON-encoded numeric, default 0
    "unit": str,
    "applies_when": str,  # JSON object string
    "severity": str,
    "keyword": str,
    "compliance_type": str,
    "exceptions": str,  # JSON array string
    "related_refs": str,  # JSON array string
    "overridden_by": str,
    "confidence": str,
    "extraction_method": str,
    "needs_review": int,
}

# Columns that classify a rule within the broader multi-mechanism schema.
# Added via required_columns so existing DBs migrate automatically.
_META_COLUMNS = {
    "mechanism": str,  # "CODE" | "GC-001" | "CC-001" | "MC-001"
    "ruleset_id": str,  # "BUILDING-CODE-PART9" | "BIMGUARD-GC-001" | …
    "rule_category": str,  # "property_check" | "threshold_band" | "material_property"
    # | "scoring_model" | "mitigation" | "reference_config"
}

_FOLDER_COLUMNS = {
    "id": int,
    "ruleset_id": str,
    "display_name": str,
    "description": str,
    "mechanism_scope": str,
    "created_at": str,
    "updated_at": str,
}

# ── Valid controlled vocabulary ───────────────────────────────────────────────

MECHANISMS = {"GC-001", "CC-001", "MC-001", "IFC", "CODE"}

RULE_CATEGORIES = {
    "property_check",  # IFC element property assertion (building code)
    "scoring_model",  # Composite score formula + weights
    "threshold_band",  # Classification band with risk score
    "material_property",  # Material-level data (galvanic potential, CCT, MIC susceptibility)
    "reference_config",  # Named lookup entry (environment class, joint type, etc.)
    "mitigation",  # Remediation action catalogue entry
}

THEMES = {"Architecture", "MEP"}

_MEP_IFC_PREFIXES = (
    "IfcFlow",
    "IfcPipe",
    "IfcDuct",
    "IfcCable",
    "IfcDistribution",
    "IfcPump",
    "IfcBoiler",
    "IfcChiller",
    "IfcUnitary",
    "IfcSanitary",
)

FOLDER_MECHANISM_SCOPES = {"", *MECHANISMS}
_DEFAULT_CODE_MECHANISMS = {"", "IFC", "CODE"}


class RuleService:
    """
    Encapsulates CRUD + query operations for compliance rules.

    The single 'rules' table stores all rule types across mechanisms:
    - Building code property checks (property_check)
    - Engine lookup tables (threshold_band, reference_config, material_property)
    - Scoring formulae (scoring_model)
    - Mitigation catalogue (mitigation)
    """

    def __init__(self):
        """Initialize the rules table with required schema columns."""
        all_required = {**_RICH_COLUMNS, **_META_COLUMNS}
        self._rules = PersistenceService.get_table(
            "rules",
            {
                "id": int,
                "reference": str,
                "rule_type": str,
                "description": str,
                "target_ifc_class": str,
                "parameters": str,  # kept for backward-compat / engine data
                "created_at": str,
                "updated_at": str,
            },
            required_columns=all_required,
        )
        self._folders = PersistenceService.get_table(
            "rule_folders",
            _FOLDER_COLUMNS,
        )
        self._folders_enabled = True
        self._sync_folders_from_rules()

    @staticmethod
    def normalize_ruleset_id(value: str | None) -> str:
        """Normalize ruleset identifiers to a stable whitespace-collapsed form."""
        return " ".join((value or "").split())

    @staticmethod
    def _normalize_mechanism_scope(value: str | None) -> str:
        """Normalize folder scope to known mechanism values (or blank)."""
        normalized = (value or "").strip().upper()
        if normalized in FOLDER_MECHANISM_SCOPES:
            return normalized
        return ""

    def _disable_folders_if_missing(self, exc: APIError) -> bool:
        """Disable folder-table operations when Supabase schema lacks rule_folders."""
        code = str(getattr(exc, "code", "") or "")
        message = str(getattr(exc, "message", "") or exc)
        if code == "PGRST205" or "rule_folders" in message:
            self._folders_enabled = False
            return True
        return False

    def _folder_rows(self) -> list[dict[str, Any]]:
        """Return folder rows, or an empty list when folder table is unavailable."""
        if not self._folders_enabled:
            return []
        try:
            return list(self._folders.rows)
        except APIError as exc:
            if self._disable_folders_if_missing(exc):
                return []
            raise

    def _folder_insert(self, payload: dict[str, Any]) -> None:
        """Insert into folder table when available."""
        if not self._folders_enabled:
            return
        try:
            self._folders.insert(payload)
        except APIError as exc:
            if not self._disable_folders_if_missing(exc):
                raise

    def _folder_update(self, folder_id: int, updates: dict[str, Any]) -> None:
        """Update a folder row when available."""
        if not self._folders_enabled:
            return
        try:
            self._folders.update(updates=updates, pk_values=folder_id)
        except APIError as exc:
            if not self._disable_folders_if_missing(exc):
                raise

    def _folder_delete(self, folder_id: int) -> None:
        """Delete a folder row when available."""
        if not self._folders_enabled:
            return
        try:
            self._folders.delete(folder_id)
        except APIError as exc:
            if not self._disable_folders_if_missing(exc):
                raise

    def _sync_folders_from_rules(self) -> None:
        """Backfill folder rows from existing rule records during startup."""
        existing = {
            self.normalize_ruleset_id(row.get("ruleset_id") or "")
            for row in self._folder_rows()
            if self.normalize_ruleset_id(row.get("ruleset_id") or "")
        }
        now = now_iso_utc()
        for rule in self._rules.rows:
            ruleset_id = self.normalize_ruleset_id(rule.get("ruleset_id") or "")
            if not ruleset_id or ruleset_id in existing:
                continue
            self._folder_insert(
                {
                    "ruleset_id": ruleset_id,
                    "display_name": ruleset_id,
                    "description": "",
                    "mechanism_scope": self._normalize_mechanism_scope(rule.get("mechanism")),
                    "created_at": now,
                    "updated_at": now,
                }
            )
            existing.add(ruleset_id)

    def _ensure_folder(
        self,
        ruleset_id: str,
        display_name: str = "",
        description: str = "",
        mechanism_scope: str = "",
    ) -> None:
        """Ensure a folder row exists for a non-empty ruleset_id."""
        normalized = self.normalize_ruleset_id(ruleset_id)
        if not normalized:
            return
        scope = self._normalize_mechanism_scope(mechanism_scope)
        for row in self._folder_rows():
            row_id = self.normalize_ruleset_id(row.get("ruleset_id") or "")
            if row_id != normalized:
                continue

            updates: dict[str, Any] = {}
            incoming_name = (display_name or "").strip()
            incoming_desc = (description or "").strip()

            if incoming_name and not (row.get("display_name") or "").strip():
                updates["display_name"] = incoming_name
            if incoming_desc and not (row.get("description") or "").strip():
                updates["description"] = incoming_desc
            if scope and not (row.get("mechanism_scope") or "").strip():
                updates["mechanism_scope"] = scope

            if updates:
                updates["updated_at"] = now_iso_utc()
                self._folder_update(row["id"], updates)
            return

        now = now_iso_utc()
        self._folder_insert(
            {
                "ruleset_id": normalized,
                "display_name": (display_name or normalized).strip() or normalized,
                "description": (description or "").strip(),
                "mechanism_scope": scope,
                "created_at": now,
                "updated_at": now,
            }
        )

    def _drop_folder_if_orphan(self, ruleset_id: str) -> None:
        """Delete a folder row when no rules reference its ruleset_id anymore."""
        normalized = self.normalize_ruleset_id(ruleset_id)
        if not normalized:
            return
        if self.has_ruleset(normalized):
            return

        for folder in self._folder_rows():
            if self.normalize_ruleset_id(folder.get("ruleset_id") or "") != normalized:
                continue
            self._folder_delete(folder["id"])
            break

    # ── Web CRUD ──────────────────────────────────────────────────────────────

    def list_rules(self) -> list[dict]:
        """Return all rules ordered by newest first."""
        return rows_desc_by_id(self._rules)

    def get_rule(self, rule_id: int) -> dict | None:
        """Return a single rule by primary key."""
        return self._rules.get(rule_id)

    def create_rule(
        self,
        reference: str,
        rule_type: str,
        description: str,
        target_ifc_class: str,
        parameters: str = "{}",
        # rich schema
        source_text: str = "",
        property_set: str = "",
        property_name: str = "",
        fallback_property: str = "",
        operator: str = "",
        check_value=None,
        value_min=None,
        value_max=None,
        value_min_property: str = "",
        value_max_property: str = "",
        value_min_offset=0,
        value_max_offset=0,
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
        # classification meta
        mechanism: str = "",
        ruleset_id: str = "",
        rule_category: str = "property_check",
    ):
        """Insert a rule row into the rules table."""
        now = now_iso_utc()
        saved = self._rules.insert(
            {
                "reference": reference.strip(),
                "rule_type": rule_type.strip() or "numeric_comparison",
                "description": description.strip(),
                "target_ifc_class": target_ifc_class.strip(),
                "parameters": self._norm_json(parameters),
                "source_text": source_text or "",
                "property_set": property_set or "",
                "property_name": property_name or "",
                "fallback_property": fallback_property or "",
                "operator": operator or "",
                "check_value": json.dumps(check_value),
                "value_min": json.dumps(value_min),
                "value_max": json.dumps(value_max),
                "value_min_property": value_min_property or "",
                "value_max_property": value_max_property or "",
                "value_min_offset": json.dumps(self._parse_numeric(value_min_offset) or 0),
                "value_max_offset": json.dumps(self._parse_numeric(value_max_offset) or 0),
                "unit": unit or "",
                "applies_when": json.dumps(applies_when or {}),
                "severity": severity or "mandatory",
                "keyword": keyword or "",
                "compliance_type": compliance_type or "",
                "exceptions": json.dumps(exceptions or []),
                "related_refs": json.dumps(related_refs or []),
                "overridden_by": overridden_by or "",
                "confidence": str(confidence) if confidence is not None else "",
                "extraction_method": extraction_method or "manual",
                "needs_review": int(needs_review),
                "mechanism": mechanism or "",
                "ruleset_id": self.normalize_ruleset_id(ruleset_id),
                "rule_category": rule_category or "property_check",
                "created_at": now,
                "updated_at": now,
            }
        )
        self._ensure_folder(ruleset_id, mechanism_scope=mechanism)
        return saved

    def update_rule(
        self,
        rule_id: int,
        reference: str,
        rule_type: str,
        description: str,
        target_ifc_class: str,
        parameters: str = "{}",
        # identity
        mechanism: str = "",
        ruleset_id: str = "",
        rule_category: str = "",
        # ifc target
        property_set: str = "",
        property_name: str = "",
        fallback_property: str = "",
        # rule logic
        operator: str = "",
        check_value=None,
        value_min=None,
        value_max=None,
        value_min_property: str = "",
        value_max_property: str = "",
        value_min_offset=0,
        value_max_offset=0,
        unit: str = "",
        # classification
        severity: str = "mandatory",
        keyword: str = "",
        compliance_type: str = "",
        # content
        source_text: str = "",
        # meta
        confidence: float | None = None,
        needs_review: bool = False,
    ):
        """Update editable fields for an existing rule."""
        existing = self.get_rule(rule_id)
        old_ruleset_id = (existing or {}).get("ruleset_id") or ""

        self._rules.update(
            updates={
                "reference": reference.strip(),
                "rule_type": rule_type.strip() or "numeric_comparison",
                "description": description.strip(),
                "target_ifc_class": target_ifc_class.strip(),
                "parameters": self._norm_json(parameters),
                "mechanism": mechanism or "",
                "ruleset_id": self.normalize_ruleset_id(ruleset_id),
                "rule_category": rule_category or "",
                "property_set": property_set or "",
                "property_name": property_name or "",
                "fallback_property": fallback_property or "",
                "operator": operator or "",
                "check_value": json.dumps(self._parse_numeric(check_value)),
                "value_min": json.dumps(self._parse_numeric(value_min)),
                "value_max": json.dumps(self._parse_numeric(value_max)),
                "value_min_property": value_min_property or "",
                "value_max_property": value_max_property or "",
                "value_min_offset": json.dumps(self._parse_numeric(value_min_offset) or 0),
                "value_max_offset": json.dumps(self._parse_numeric(value_max_offset) or 0),
                "unit": unit or "",
                "severity": severity or "mandatory",
                "keyword": keyword or "",
                "compliance_type": compliance_type or "",
                "source_text": source_text or "",
                "confidence": str(confidence) if confidence is not None else "",
                "needs_review": int(bool(needs_review)),
                "updated_at": now_iso_utc(),
            },
            pk_values=rule_id,
        )

        self._ensure_folder(ruleset_id, mechanism_scope=mechanism)
        old_normalized = self.normalize_ruleset_id(old_ruleset_id)
        new_normalized = self.normalize_ruleset_id(ruleset_id)
        if old_normalized and old_normalized != new_normalized:
            self._drop_folder_if_orphan(old_normalized)

    @staticmethod
    def _parse_numeric(value):
        """Convert a form string value to float, or None if blank/invalid."""
        if value is None:
            return None
        s = str(value).strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None

    def delete_rule(self, rule_id: int):
        """Delete a rule by primary key."""
        existing = self.get_rule(rule_id)
        old_ruleset_id = (existing or {}).get("ruleset_id") or ""
        self._rules.delete(rule_id)
        self._drop_folder_if_orphan(old_ruleset_id)

    def set_rule_parameter(self, rule_id: int, key: str, value) -> None:
        """Merge one key into a rule's `parameters` JSON blob.

        Used for small per-rule interpretation settings (e.g. egress_direction)
        that don't warrant a dedicated column/migration — `parameters` already
        exists as a free-form JSON bag for exactly this kind of engine data.
        Leaves every other field untouched.
        """
        rule = self.get_rule(rule_id)
        if rule is None:
            return
        try:
            params = json.loads(rule.get("parameters") or "{}")
            if not isinstance(params, dict):
                params = {}
        except json.JSONDecodeError:
            params = {}
        params[key] = value
        self._rules.update(
            updates={"parameters": json.dumps(params), "updated_at": now_iso_utc()},
            pk_values=rule_id,
        )

    # ── Classification queries ────────────────────────────────────────────────

    def has_ruleset(self, ruleset_id: str) -> bool:
        """Return True if at least one rule with this ruleset_id exists."""
        normalized = self.normalize_ruleset_id(ruleset_id)
        if not normalized:
            return False
        return len(list(self._rules.rows_where("ruleset_id = ?", [normalized], limit=1))) > 0

    def folder_exists(self, ruleset_id: str) -> bool:
        """Return True if a folder row exists or any rule references the ruleset_id."""
        normalized = self.normalize_ruleset_id(ruleset_id)
        if not normalized:
            return False
        if self.has_ruleset(normalized):
            return True
        return any(
            self.normalize_ruleset_id(row.get("ruleset_id") or "") == normalized
            for row in self._folder_rows()
        )

    def create_folder(
        self,
        ruleset_id: str,
        display_name: str = "",
        description: str = "",
        mechanism_scope: str = "",
    ) -> bool:
        """Create an empty folder row for later rule assignment."""
        normalized = self.normalize_ruleset_id(ruleset_id)
        if not normalized or self.folder_exists(normalized):
            return False

        self._ensure_folder(
            normalized,
            display_name=display_name,
            description=description,
            mechanism_scope=mechanism_scope,
        )
        return self.folder_exists(normalized)

    def update_folder_metadata(
        self,
        ruleset_id: str,
        display_name: str,
        description: str,
        mechanism_scope: str,
    ) -> bool:
        """Update metadata fields for an existing folder by ruleset_id."""
        normalized = self.normalize_ruleset_id(ruleset_id)
        if not normalized:
            return False

        for folder in self._folder_rows():
            if self.normalize_ruleset_id(folder.get("ruleset_id") or "") != normalized:
                continue
            self._folder_update(
                folder["id"],
                {
                    "display_name": (display_name or "").strip(),
                    "description": (description or "").strip(),
                    "mechanism_scope": self._normalize_mechanism_scope(mechanism_scope),
                    "updated_at": now_iso_utc(),
                },
            )
            return True

        if self.has_ruleset(normalized):
            self._ensure_folder(
                normalized,
                display_name=display_name,
                description=description,
                mechanism_scope=mechanism_scope,
            )
            return True

        return False

    def list_by_mechanism(self, mechanism: str) -> list[dict]:
        """Return all rules for a corrosion or code-check mechanism."""
        return list(self._rules.rows_where("mechanism = ?", [mechanism]))

    def list_code_rules(self) -> list[dict]:
        """Return rule rows that represent generic building-code/property checks."""
        rows = list(self._rules.rows)
        selected: list[dict] = []
        for row in rows:
            category = str(row.get("rule_category") or "").strip().lower()
            mechanism = str(row.get("mechanism") or "").strip().upper()
            if category == "property_check" or mechanism in _DEFAULT_CODE_MECHANISMS:
                selected.append(row)
        return selected

    def list_by_ruleset(self, ruleset_id: str) -> list[dict]:
        """Return all rules that belong to a ruleset identifier."""
        normalized = self.normalize_ruleset_id(ruleset_id)
        if not normalized:
            return []
        return list(self._rules.rows_where("ruleset_id = ?", [normalized]))

    def list_folders(self) -> list[dict]:
        """Return folder rows with current rule counts, ordered by ruleset_id."""
        counts: dict[str, int] = {}
        for r in self._rules.rows:
            ruleset_id = self.normalize_ruleset_id(r.get("ruleset_id") or "")
            if not ruleset_id:
                continue
            counts[ruleset_id] = counts.get(ruleset_id, 0) + 1

        rows: list[dict] = []
        seen: set[str] = set()
        for folder in self._folder_rows():
            ruleset_id = self.normalize_ruleset_id(folder.get("ruleset_id") or "")
            if not ruleset_id or ruleset_id in seen:
                continue
            seen.add(ruleset_id)
            rows.append(
                {
                    "ruleset_id": ruleset_id,
                    "display_name": (folder.get("display_name") or "").strip() or ruleset_id,
                    "description": (folder.get("description") or "").strip(),
                    "mechanism_scope": self._normalize_mechanism_scope(
                        folder.get("mechanism_scope")
                    ),
                    "count": counts.get(ruleset_id, 0),
                }
            )

        for ruleset_id, count in counts.items():
            if ruleset_id in seen:
                continue
            rows.append(
                {
                    "ruleset_id": ruleset_id,
                    "display_name": ruleset_id,
                    "description": "",
                    "mechanism_scope": "",
                    "count": count,
                }
            )

        rows.sort(key=lambda row: ((row.get("display_name") or "").lower(), row["ruleset_id"]))
        return rows

    def rename_folder(self, old_id: str, new_id: str) -> int:
        """Bulk-rename a ruleset_id across every rule that has it. Returns rows updated."""
        old_id = self.normalize_ruleset_id(old_id)
        new_id = self.normalize_ruleset_id(new_id)
        if not old_id or not new_id or old_id == new_id:
            return 0

        now = now_iso_utc()
        updated = 0
        for rule in self.list_by_ruleset(old_id):
            self._rules.update(
                updates={"ruleset_id": new_id, "updated_at": now},
                pk_values=rule["id"],
            )
            updated += 1

        for folder in self._folder_rows():
            if self.normalize_ruleset_id(folder.get("ruleset_id") or "") != old_id:
                continue
            display_name = (folder.get("display_name") or "").strip()
            updates = {"ruleset_id": new_id, "updated_at": now}
            if not display_name or display_name == old_id:
                updates["display_name"] = new_id
            self._folder_update(folder["id"], updates)
            break
        self._ensure_folder(new_id)
        self._drop_folder_if_orphan(old_id)
        return updated

    def delete_folder(self, ruleset_id: str) -> int:
        """Delete every rule that belongs to a ruleset_id. Returns rows deleted."""
        ruleset_id = self.normalize_ruleset_id(ruleset_id)
        if not ruleset_id:
            return 0

        deleted = 0
        for rule in self.list_by_ruleset(ruleset_id):
            self._rules.delete(rule["id"])
            deleted += 1
        self._drop_folder_if_orphan(ruleset_id)
        return deleted

    def delete_rules(self, rule_ids: list[int]) -> int:
        """Delete multiple rules by primary key. Returns rows deleted."""
        deleted = 0
        for rule_id in rule_ids:
            if self.get_rule(rule_id) is None:
                continue
            self._rules.delete(rule_id)
            deleted += 1
        return deleted

    def list_by_category(self, rule_category: str) -> list[dict]:
        """Return all rules matching the provided rule category."""
        return list(self._rules.rows_where("rule_category = ?", [rule_category]))

    @staticmethod
    def normalize_theme(theme: str | None) -> str:
        """Normalize a user-selected theme to one of the supported values."""
        value = (theme or "").strip().lower()
        if value == "mep":
            return "MEP"
        return "Architecture"

    @classmethod
    def infer_theme(cls, rule: dict) -> str:
        """Infer Architecture vs MEP for a rule from mechanism and IFC target hints."""
        mechanism = (rule.get("mechanism") or "").strip().upper()
        if mechanism in {"GC-001", "CC-001", "MC-001"}:
            return "MEP"
        if mechanism in {"CODE", "IFC"}:
            return "Architecture"

        target = (rule.get("target_ifc_class") or "").strip()
        if target.startswith(_MEP_IFC_PREFIXES):
            return "MEP"

        return "Architecture"

    def list_by_theme(self, theme: str) -> list[dict]:
        """Return all rules categorized under the requested analysis theme."""
        selected = self.normalize_theme(theme)
        return [r for r in self._rules.rows if self.infer_theme(r) == selected]

    # ── Pipeline query methods (used by RuleStore adapter) ────────────────────

    def count(self) -> int:
        """Return the total number of rules in storage."""
        return len(list(self._rules.rows))

    def fetch_rules_for_target(self, target_ifc_class: str) -> list[dict]:
        """Return rules targeting a specific IFC class."""
        return list(self._rules.rows_where("target_ifc_class = ?", [target_ifc_class]))

    def fetch_mandatory_rules(self) -> list[dict]:
        """Return rules marked with mandatory severity."""
        return list(self._rules.rows_where("severity = 'mandatory'"))

    def fetch_rules_by_ref(self, ref: str) -> list[dict]:
        """Return rules whose reference contains the provided token."""
        return list(self._rules.rows_where("reference LIKE ?", [f"%{ref}%"]))

    def fetch_needs_review(self) -> list[dict]:
        """Return rules flagged for manual review, newest first."""
        rows = self._rules.rows_where("needs_review = 1")
        return sorted(rows, key=lambda row: row["id"], reverse=True)

    def count_needs_review(self) -> int:
        """Return the number of rules flagged for manual review."""
        return len(self._rules.rows_where("needs_review = 1"))

    def get_existing_entity_types(self) -> list[str]:
        """Return distinct target IFC classes present in stored rules."""
        seen: set[str] = set()
        result: list[str] = []
        for r in self._rules.rows:
            t = r.get("target_ifc_class") or ""
            if t and t not in seen:
                seen.add(t)
                result.append(t)
        return result

    def get_rules_sample(self, limit: int = 3) -> list[dict]:
        """Return a small sample of mandatory rules for previews."""
        return list(self._rules.rows_where("severity = 'mandatory'", limit=limit))

    def summary(self) -> dict:
        """Return aggregate counts of rules by entity, source, and mechanism."""
        rules = list(self._rules.rows)
        by_entity: dict[str, int] = {}
        by_source: dict[str, int] = {}
        by_mechanism: dict[str, int] = {}
        mandatory_count = 0
        for r in rules:
            target = r.get("target_ifc_class") or ""
            by_entity[target] = by_entity.get(target, 0) + 1
            source = r.get("extraction_method") or ""
            by_source[source] = by_source.get(source, 0) + 1
            mech = r.get("mechanism") or "—"
            by_mechanism[mech] = by_mechanism.get(mech, 0) + 1
            if r.get("severity") == "mandatory":
                mandatory_count += 1
        return {
            "total": len(rules),
            "mandatory_count": mandatory_count,
            "by_entity": by_entity,
            "by_source": by_source,
            "by_mechanism": by_mechanism,
        }

    # ── JSON ruleset import ───────────────────────────────────────────────────

    def import_ruleset(self, json_data: dict) -> int:
        """
        Import rules from a canonical JSON ruleset document.

        Expected format:
            {
                "ruleset_id": "MY-RULESET",
                "mechanism":  "GC-001",          # optional
                "rules": [
                    {
                        "ref":           "R-001",
                        "rule_type":     "numeric_comparison",
                        "rule_category": "property_check",
                        "desc":          "...",
                        "target":        "IfcDoor",
                        ...
                    }
                ]
            }

        Field names follow the CLI convention (ref/desc/target) OR the web
        convention (reference/description/target_ifc_class) — both accepted.
        Returns the number of rules successfully imported.
        """
        ruleset_id = str(json_data.get("ruleset_id") or "").strip()
        if not ruleset_id:
            raise ValueError("JSON ruleset must have a non-empty 'ruleset_id'.")

        rules = json_data.get("rules")
        if not isinstance(rules, list):
            raise ValueError("JSON ruleset must have a 'rules' array.")

        top_mechanism = str(json_data.get("mechanism") or "")
        saved = 0
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            desc = str(rule.get("desc") or rule.get("description") or "").strip()
            if not desc:
                continue
            self.create_rule(
                reference=str(rule.get("ref") or rule.get("reference") or "").strip(),
                rule_type=str(rule.get("rule_type") or "numeric_comparison"),
                description=desc,
                target_ifc_class=str(
                    rule.get("target") or rule.get("target_ifc_class") or "Unspecified"
                ).strip(),
                source_text=str(rule.get("source_text") or ""),
                property_set=str(rule.get("property_set") or ""),
                property_name=str(rule.get("property_name") or ""),
                fallback_property=str(rule.get("fallback_property") or ""),
                operator=str(rule.get("operator") or ""),
                check_value=(
                    rule.get("check_value") if "check_value" in rule else rule.get("value")
                ),
                value_min=rule.get("value_min"),
                value_max=rule.get("value_max"),
                unit=str(rule.get("unit") or ""),
                applies_when=rule.get("applies_when") or {},
                severity=str(rule.get("severity") or "mandatory"),
                keyword=str(rule.get("keyword") or ""),
                compliance_type=str(rule.get("compliance_type") or ""),
                exceptions=rule.get("exceptions") or [],
                related_refs=rule.get("related_refs") or [],
                overridden_by=str(rule.get("overridden_by") or ""),
                confidence=(
                    float(rule["confidence"]) if rule.get("confidence") is not None else None
                ),
                extraction_method=str(rule.get("extraction_method") or "import"),
                needs_review=bool(rule.get("needs_review", False)),
                mechanism=str(rule.get("mechanism") or top_mechanism),
                ruleset_id=ruleset_id,
                rule_category=str(rule.get("rule_category") or "property_check"),
                parameters=json.dumps(rule.get("parameters") or {}),
            )
            saved += 1
        return saved

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _norm_json(self, value: str) -> str:
        """Normalize JSON strings to a compact canonical representation."""
        raw = (value or "").strip()
        if not raw:
            return "{}"
        try:
            return json.dumps(json.loads(raw), separators=(",", ":"))
        except json.JSONDecodeError:
            return raw
