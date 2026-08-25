"""
module1_doc_parser/table_rule_builder.py
------------------------------------------
Step 2 — Converts Docling table DataFrames directly into rules.db entries.
No LLM required for tables — Min/Max columns map directly to numeric_range rules.

Usage:
    from module1_doc_parser.table_rule_builder import TableRuleBuilder
    builder = TableRuleBuilder(store)
    builder.process_all_tables(tables, generator)
"""

import re

TABLE_ENTITY_MAP = {
    "stair": "IfcStairFlight",
    "riser": "IfcStairFlight",
    "tread": "IfcStairFlight",
    "rise": "IfcStairFlight",
    "run": "IfcStairFlight",
    "nosing": "IfcStairFlight",
    "door": "IfcDoor",
    "doorway": "IfcDoor",
    "window": "IfcWindow",
    "glazing": "IfcWindow",
    "ramp": "IfcRamp",
    "slope": "IfcRamp",
    "guard": "IfcRailing",
    "handrail": "IfcRailing",
    "landing": "IfcSlab",
    "floor": "IfcSlab",
    "wall": "IfcWall",
}

MIN_VARIANTS = {"min", "minimum", "min (mm)", "min. (mm)", "min.", "minimum (mm)"}
MAX_VARIANTS = {"max", "maximum", "max (mm)", "max. (mm)", "max.", "maximum (mm)"}

# Column header aliases for the one-row-per-requirement table shape, e.g.
# "Rule ID | Entity | Property | Operator | Value | Unit | Requirement".
_OPERATOR_COL_ALIASES = ("operator", "op")
_VALUE_COL_ALIASES = ("value", "check value", "check_value")
_PROPERTY_COL_ALIASES = ("property", "property name", "property_name", "attribute")
_ENTITY_COL_ALIASES = ("entity", "element", "ifc class")
_UNIT_COL_ALIASES = ("unit", "units")
_REQUIREMENT_COL_ALIASES = ("requirement", "description", "desc")
_REF_COL_ALIASES = ("rule id", "ref", "reference", "id")

# Maps an Operator cell to a Module4_Comparator-supported operator symbol.
# PDF fonts sometimes encode >=/<= with glyphs Docling can't decode cleanly
# (observed as stray characters, e.g. '‡'/'£' for one sample PDF) —
# unrecognized symbols fall back to inferring intent from the plain-English
# requirement text instead of guessing wrong silently.
_OPERATOR_SYMBOL_MAP = {
    "≥": ">=", ">=": ">=", "=>": ">=",
    "≤": "<=", "<=": "<=", "=<": "<=",
    "=": "==", "==": "==",
    "!=": "!=", "<>": "!=", "≠": "!=",
    ">": ">", "<": "<",
    "exists": "exists",
    "not_exists": "not_exists", "not exists": "not_exists",
    "matches": "matches",
    "between": "between",
}
_GE_PHRASES = ("at least", "minimum", "not less than", "no less than")
_LE_PHRASES = ("at most", "maximum", "not exceed", "not exceeding", "no more than", "not more than")

_OPERATOR_WORDS = {
    ">=": "at least",
    "<=": "at most",
    ">": "more than",
    "<": "less than",
    "==": "equal to",
    "!=": "not equal to",
}

# Strips stray trailing symbols from a Property cell — property names are
# clean IFC identifiers, so trailing junk (e.g. a corrupted operator glyph
# bleeding into the wrong cell — see _normalize_operator) is never intentional.
_TRAILING_JUNK_RE = re.compile(r"[^A-Za-z0-9_]+$")


class TableRuleBuilder:
    def __init__(self, rule_store=None):
        self.store = rule_store

    def _detect_target(self, text: str) -> str:
        text_lower = str(text).lower()
        for kw, ifc in TABLE_ENTITY_MAP.items():
            if kw in text_lower:
                return ifc
        return "IfcBuildingElement"

    def _detect_unit(self, text: str) -> str:
        t = str(text).lower()
        if "m2" in t or "area" in t:
            return "m2"
        if "deg" in t or "angle" in t:
            return "deg"
        return "mm"

    def _build_rule_dicts(self, table_dict: dict) -> list[dict]:
        """Build rule dicts from a table DataFrame without saving to any store.

        Tries the Min/Max range format first (e.g. building-code dimension tables), then
        falls back to a one-row-per-requirement Operator/Value format (e.g.
        "Entity | Property | Operator | Value | Unit | Requirement")."""
        rules = self._build_minmax_rule_dicts(table_dict)
        if rules:
            return rules
        return self._build_operator_value_rule_dicts(table_dict)

    def _build_minmax_rule_dicts(self, table_dict: dict) -> list[dict]:
        """Build rule dicts from a table whose columns include a Min and Max pair."""
        df = table_dict["dataframe"].copy()
        idx = table_dict["table_index"]
        df.columns = [str(c).strip().lower() for c in df.columns]

        min_col = next((c for c in df.columns if c in MIN_VARIANTS), None)
        max_col = next((c for c in df.columns if c in MAX_VARIANTS), None)
        if not min_col or not max_col:
            return []

        prop_col = df.columns[0]
        rules = []

        for _, row in df.iterrows():
            name = str(row.get(prop_col, "")).strip()
            if not name or name.lower() == "nan":
                continue
            try:
                min_val = float(str(row[min_col]).replace(",", "").strip())
                max_val = float(str(row[max_col]).replace(",", "").strip())
            except (ValueError, TypeError):
                continue

            rules.append(
                {
                    "ref": f"CODE_Table_{idx + 1}",
                    "desc": f"{name} must be between {min_val} and {max_val}",
                    "source_text": "",
                    "target": self._detect_target(name),
                    "property_set": "",
                    "property_name": name.replace(" ", "_").title(),
                    "fallback_property": "",
                    "rule_type": "numeric_range",
                    "operator": "between",
                    "value": None,  # table rules use value_min/value_max
                    "check_value": None,  # Module 3 compatibility
                    "value_min": min_val,
                    "value_max": max_val,
                    "unit": self._detect_unit(name),
                    "applies_when": {},
                    "severity": "mandatory",
                    "keyword": "shall",
                    "compliance_type": "prescriptive",
                    "exceptions": [],
                    "related_refs": [],
                    "overridden_by": None,
                    "confidence": 1.0,
                    "extraction_method": "table",
                    "needs_review": False,
                }
            )

        return rules

    @staticmethod
    def _first_col(columns, aliases) -> str | None:
        return next((c for c in aliases if c in columns), None)

    @staticmethod
    def _cell(row, col) -> str:
        if not col:
            return ""
        value = str(row.get(col, "")).strip()
        return "" if value.lower() == "nan" else value

    @staticmethod
    def _parse_value(raw: str):
        if not raw:
            return None
        try:
            return float(raw.replace(",", ""))
        except ValueError:
            return raw

    @staticmethod
    def _clean_property_name(name: str) -> str:
        return _TRAILING_JUNK_RE.sub("", name).strip()

    def _normalize_operator(
        self, raw_op: str, property_name: str, requirement_text: str
    ) -> tuple[str, bool, float]:
        """Resolve a table 'Operator' cell to a Module4_Comparator operator symbol.

        Returns (operator, needs_review, confidence). Falls back to inferring
        intent from the plain-English requirement text when the cell holds an
        unrecognized or corrupted symbol, or repeats the property cell's text
        (both observed from Docling table parsing of PDF-embedded symbol fonts).
        """
        key = raw_op.strip()
        if key and key.lower() == (property_name or "").strip().lower():
            key = ""  # duplicated-cell glitch: operator cell repeats the property cell

        if key.lower() in _OPERATOR_SYMBOL_MAP:
            return _OPERATOR_SYMBOL_MAP[key.lower()], False, 1.0

        lowered = requirement_text.lower()
        if any(phrase in lowered for phrase in _GE_PHRASES):
            return ">=", True, 0.9
        if any(phrase in lowered for phrase in _LE_PHRASES):
            return "<=", True, 0.9

        return key, True, 0.5

    def _describe(
        self, requirement_text: str, property_name: str, operator: str, value, unit: str
    ) -> str:
        """Prefer the source requirement sentence; fall back to a synthesized
        description when it looks truncated (no closing punctuation) — Docling
        sometimes only captures the first line of a wrapped table cell."""
        text = requirement_text.strip()
        if text and text[-1] in ".!?":
            return text

        if operator == "exists":
            return f"{property_name} must be specified"
        if operator == "not_exists":
            return f"{property_name} must not be specified"

        unit_suffix = f" {unit}" if unit else ""
        word = _OPERATOR_WORDS.get(operator, operator)
        return f"{property_name} must be {word} {value}{unit_suffix}".strip()

    def _build_operator_value_rule_dicts(self, table_dict: dict) -> list[dict]:
        """Build rule dicts from a one-row-per-requirement table, e.g.
        "Rule ID | Entity | Property | Operator | Value | Unit | Requirement".
        Each row becomes its own rule instead of relying on a Min/Max pair."""
        df = table_dict["dataframe"].copy()
        idx = table_dict["table_index"]
        df.columns = [str(c).strip().lower() for c in df.columns]

        operator_col = self._first_col(df.columns, _OPERATOR_COL_ALIASES)
        value_col = self._first_col(df.columns, _VALUE_COL_ALIASES)
        property_col = self._first_col(df.columns, _PROPERTY_COL_ALIASES)
        if not operator_col or not value_col or not property_col:
            return []

        entity_col = self._first_col(df.columns, _ENTITY_COL_ALIASES)
        unit_col = self._first_col(df.columns, _UNIT_COL_ALIASES)
        requirement_col = self._first_col(df.columns, _REQUIREMENT_COL_ALIASES)
        ref_col = self._first_col(df.columns, _REF_COL_ALIASES)

        rules = []
        for row_idx, row in df.iterrows():
            raw_property_name = self._cell(row, property_col)
            property_name = self._clean_property_name(raw_property_name)
            if not property_name:
                continue

            entity_text = self._cell(row, entity_col)
            target = self._detect_target(entity_text or property_name)
            requirement_text = self._cell(row, requirement_col)
            raw_op = self._cell(row, operator_col)

            operator, needs_review, confidence = self._normalize_operator(
                raw_op, raw_property_name, requirement_text
            )
            if not operator:
                continue

            value = self._parse_value(self._cell(row, value_col))
            unit = self._cell(row, unit_col)
            ref = self._cell(row, ref_col) or f"CODE_Table_{idx + 1}_{row_idx + 1}"
            is_value_operator = operator in ("exists", "not_exists")

            rules.append(
                {
                    "ref": ref,
                    "desc": self._describe(requirement_text, property_name, operator, value, unit),
                    "source_text": requirement_text,
                    "target": target,
                    "property_set": "",
                    "property_name": property_name,
                    "fallback_property": "",
                    "rule_type": "numeric_comparison",
                    "operator": operator,
                    "value": None if is_value_operator else value,
                    "check_value": None if is_value_operator else value,
                    "value_min": None,
                    "value_max": None,
                    "unit": unit,
                    "applies_when": {},
                    "severity": "mandatory",
                    "keyword": "shall",
                    "compliance_type": "prescriptive",
                    "exceptions": [],
                    "related_refs": [],
                    "overridden_by": None,
                    "confidence": confidence,
                    "extraction_method": "table",
                    "needs_review": needs_review,
                }
            )

        return rules

    def extract_all_as_dicts(self, tables: list) -> list[dict]:
        """Return all table rules as dicts without saving to any store."""
        all_rules: list[dict] = []
        for t in tables:
            all_rules.extend(self._build_rule_dicts(t))
        if all_rules:
            print(
                f"[TableRuleBuilder] {len(all_rules)} table rules built from {len(tables)} tables"
            )
        return all_rules

    def _extract_from_table(self, table_dict: dict, generator, ruleset_id: str = "") -> int:
        rules = self._build_rule_dicts(table_dict)
        if ruleset_id:
            for rule in rules:
                rule["ruleset_id"] = ruleset_id
        if rules:
            saved = generator.save_batch(rules, source_doc="Code_Table_Direct")
            return len(saved)
        return 0

    def process_all_tables(self, tables: list, generator, ruleset_id: str = "") -> int:
        if not tables:
            print("[TableRuleBuilder] No tables found")
            return 0

        print(f"[TableRuleBuilder] Processing {len(tables)} tables...")
        total = 0
        for t in tables:
            saved = self._extract_from_table(t, generator, ruleset_id)
            idx = t["table_index"]
            if saved:
                print(f"  Table {idx + 1}: {saved} rules saved (no LLM)")
            else:
                print(f"  Table {idx + 1}: no recognized rule columns — skipped")
            total += saved

        print(f"[TableRuleBuilder] Done — {total} rules saved")
        return total
