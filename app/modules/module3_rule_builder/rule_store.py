"""
module3_rule_builder/rule_store.py
-----------------------------------
SQLite layer for BIMGuard rules — aligned to the web app schema.

Both the CLI pipeline (RuleStore) and the web app (RuleService) write to the
same table in data/bimguard.sqlite using the same column names so rules appear
in the Rule Library regardless of which path created them.

Column mapping (old CLI names → web app names):
    rule_id   → id  (auto int)
    ref       → reference
    desc      → description
    target    → target_ifc_class
    (raw_payload removed — individual columns are the source of truth)
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd


# Web-app-compatible CREATE TABLE — matches RuleService schema exactly.
# Includes all rich columns so the CLI can write the full rule structure.
_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS rules (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    reference         TEXT,
    rule_type         TEXT,
    description       TEXT,
    target_ifc_class  TEXT,
    parameters        TEXT DEFAULT '{}',
    source_text       TEXT,
    property_set      TEXT,
    property_name     TEXT,
    fallback_property TEXT,
    operator          TEXT,
    check_value       TEXT,
    value_min         TEXT,
    value_max         TEXT,
    unit              TEXT,
    applies_when      TEXT,
    severity          TEXT DEFAULT 'mandatory',
    keyword           TEXT,
    compliance_type   TEXT,
    exceptions        TEXT,
    related_refs      TEXT,
    overridden_by     TEXT,
    confidence        TEXT,
    extraction_method TEXT DEFAULT 'llm',
    needs_review      INTEGER DEFAULT 0,
    mechanism         TEXT,
    ruleset_id        TEXT,
    rule_category     TEXT,
    created_at        TEXT,
    updated_at        TEXT
);
"""


def _row_to_dict(row, cur) -> dict:
    """Convert a sqlite3 Row (or tuple) with cursor description to a dict."""
    cols = [d[0] for d in cur.description]
    d = dict(zip(cols, row))
    # Decode JSON-encoded fields back to Python objects
    for field in ("check_value", "value_min", "value_max",
                  "applies_when", "exceptions", "related_refs"):
        raw = d.get(field)
        if raw is not None:
            try:
                d[field] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass
    return d


class RuleStore:
    """
    SQLite access for the rules table — uses web-app column names so CLI and
    web app share a single consistent table.
    """

    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.execute(_CREATE_TABLE)
        self.conn.commit()
        print(f"[RuleStore] Connected — {self.count()} rules in '{self.db_path.name}'")

    # ── WRITE ─────────────────────────────────────────────────────────────────

    def save_rule(self, rule: dict) -> str:
        """
        Save one rule dict. Accepts the Module 1 / RuleGenerator field names
        (ref, desc, target, check_value …) and maps them to web-app columns.

        Returns:
            str: str(id) of the inserted row
        """
        now = datetime.utcnow().isoformat()
        cur = self.conn.execute(
            """INSERT INTO rules (
                reference, rule_type, description, target_ifc_class,
                parameters, source_text, property_set, property_name,
                fallback_property, operator, check_value, value_min, value_max,
                unit, applies_when, severity, keyword, compliance_type,
                exceptions, related_refs, overridden_by, confidence,
                extraction_method, needs_review,
                mechanism, ruleset_id, rule_category,
                created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                str(rule.get("ref") or ""),
                str(rule.get("rule_type") or "numeric_range"),
                str(rule.get("desc") or rule.get("description") or ""),
                str(rule.get("target") or rule.get("target_ifc_class") or "Unspecified"),
                "{}",
                str(rule.get("source_text") or ""),
                str(rule.get("property_set") or ""),
                str(rule.get("property_name") or ""),
                str(rule.get("fallback_property") or ""),
                str(rule.get("operator") or ""),
                json.dumps(rule.get("check_value")),
                json.dumps(rule.get("value_min")),
                json.dumps(rule.get("value_max")),
                str(rule.get("unit") or ""),
                json.dumps(rule.get("applies_when") or {}),
                str(rule.get("severity") or "mandatory"),
                str(rule.get("keyword") or ""),
                str(rule.get("compliance_type") or ""),
                json.dumps(rule.get("exceptions") or []),
                json.dumps(rule.get("related_refs") or []),
                str(rule.get("overridden_by") or ""),
                str(rule.get("confidence") or 0.8),
                str(rule.get("extraction_method") or "llm"),
                int(bool(rule.get("needs_review", False))),
                str(rule.get("mechanism") or ""),
                str(rule.get("ruleset_id") or ""),
                str(rule.get("rule_category") or ""),
                now,
                now,
            ),
        )
        self.conn.commit()
        return str(cur.lastrowid)

    def clear_all_rules(self):
        """Delete all rules. Use carefully — primarily for testing/re-seeding."""
        self.conn.execute("DELETE FROM rules")
        self.conn.commit()
        print("[RuleStore] All rules deleted")

    # ── READ ──────────────────────────────────────────────────────────────────

    def get_all_rules(self) -> list[dict]:
        cur = self.conn.execute("SELECT * FROM rules")
        return [_row_to_dict(r, cur) for r in cur.fetchall()]

    def fetch_rules_for_target(self, target: str) -> list[dict]:
        cur = self.conn.execute(
            "SELECT * FROM rules WHERE target_ifc_class = ?", (target,)
        )
        return [_row_to_dict(r, cur) for r in cur.fetchall()]

    # Backward-compat alias
    def fetch_rules_for_entity(self, target: str) -> list[dict]:
        return self.fetch_rules_for_target(target)

    def fetch_mandatory_rules(self) -> list[dict]:
        cur = self.conn.execute(
            "SELECT * FROM rules WHERE severity = 'mandatory'"
        )
        return [_row_to_dict(r, cur) for r in cur.fetchall()]

    def fetch_rules_by_ref(self, ref: str) -> list[dict]:
        cur = self.conn.execute(
            "SELECT * FROM rules WHERE reference LIKE ?", (f"%{ref}%",)
        )
        return [_row_to_dict(r, cur) for r in cur.fetchall()]

    def fetch_needs_review(self) -> list[dict]:
        cur = self.conn.execute(
            "SELECT * FROM rules WHERE needs_review = 1"
        )
        return [_row_to_dict(r, cur) for r in cur.fetchall()]

    def get_existing_entity_types(self) -> list[str]:
        cur = self.conn.execute(
            "SELECT DISTINCT target_ifc_class FROM rules"
        )
        return [row[0] for row in cur.fetchall() if row[0]]

    def get_rules_sample(self, limit: int = 3) -> list[dict]:
        """Return a small sample of mandatory rules for RAG prompting."""
        cur = self.conn.execute(
            "SELECT * FROM rules WHERE severity = 'mandatory' LIMIT ?", (limit,)
        )
        return [_row_to_dict(r, cur) for r in cur.fetchall()]

    def fetch_all_as_dataframe(self) -> pd.DataFrame:
        return pd.read_sql_query(
            """SELECT reference, rule_type, target_ifc_class, property_name,
                      operator, check_value, value_min, value_max,
                      unit, severity, description
               FROM rules""",
            self.conn,
        )

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM rules").fetchone()[0]

    def summary(self) -> dict:
        total = self.count()
        by_entity = {
            r[0]: r[1]
            for r in self.conn.execute(
                "SELECT target_ifc_class, COUNT(*) FROM rules GROUP BY target_ifc_class"
            )
        }
        by_source = {
            r[0]: r[1]
            for r in self.conn.execute(
                "SELECT extraction_method, COUNT(*) FROM rules GROUP BY extraction_method"
            )
        }
        mandatory_count = self.conn.execute(
            "SELECT COUNT(*) FROM rules WHERE severity = 'mandatory'"
        ).fetchone()[0]
        return {
            "total":           total,
            "mandatory_count": mandatory_count,
            "by_entity":       by_entity,
            "by_source":       by_source,
        }

    def close(self):
        self.conn.close()
