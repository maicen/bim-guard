"""
module3_rule_builder/rule_store.py
-----------------------------------
SQLite database layer for BIMGuard rules.
All standalone CLI modules read from and write to this store.

Responsibilities:
    - Create and manage the rules table
    - Save individual rule dicts
    - Query rules by target IFC class, severity, section ref
    - Return rules as DataFrames for inspection
    - Support RAG by returning sample rules as examples

Usage:
    from module3_rule_builder.rule_store import RuleStore
    from config import DB_PATH

    store = RuleStore(DB_PATH)
    store.save_rule({...})
    rules = store.fetch_rules_for_target("IfcStairFlight")
"""

import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
import pandas as pd


class RuleStore:
    """
    Handles all SQLite read/write operations for the BIMGuard Rule Database.
    This is the central hub — all CLI modules read from and write to here.
    """

    CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS rules (
        rule_id          TEXT PRIMARY KEY,
        source_doc       TEXT,
        ref              TEXT,
        rule_type        TEXT,
        target           TEXT,
        property_set     TEXT,
        property_name    TEXT,
        fallback_property TEXT,
        operator         TEXT,
        check_value      TEXT,
        value_min        TEXT,
        value_max        TEXT,
        unit             TEXT,
        severity         TEXT DEFAULT 'mandatory',
        desc             TEXT,
        source_text      TEXT,
        applies_when     TEXT,
        keyword          TEXT,
        compliance_type  TEXT,
        exceptions       TEXT,
        related_refs     TEXT,
        overridden_by    TEXT,
        confidence       REAL DEFAULT 0.8,
        extraction_method TEXT DEFAULT 'llm',
        needs_review     INTEGER DEFAULT 0,
        raw_payload      TEXT,
        created_at       TEXT
    );
    """

    def __init__(self, db_path):
        """
        Initialise the RuleStore and create the rules table if it doesn't exist.

        Args:
            db_path (str | Path): path to the SQLite database file
        """
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.execute(self.CREATE_TABLE)
        self.conn.commit()
        print(f"[RuleStore] Connected — {self.count()} existing rules in '{self.db_path.name}'")

    # ── WRITE ─────────────────────────────────────────────────────────────────

    def save_rule(self, rule: dict) -> str:
        """
        Save a single validated rule dict to the database.

        Args:
            rule (dict): rule dict matching the rich schema in rule_generator.py

        Returns:
            str: the new rule_id (UUID)
        """
        rule_id = str(uuid.uuid4())
        now     = datetime.utcnow().isoformat()

        self.conn.execute(
            """INSERT INTO rules (
                rule_id, source_doc, ref, rule_type, target,
                property_set, property_name, fallback_property,
                operator, check_value, value_min, value_max, unit,
                severity, desc, source_text, applies_when,
                keyword, compliance_type, exceptions, related_refs,
                overridden_by, confidence, extraction_method, needs_review,
                raw_payload, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                rule_id,
                rule.get("source_doc"),
                rule.get("ref"),
                rule.get("rule_type"),
                rule.get("target"),
                rule.get("property_set"),
                rule.get("property_name"),
                rule.get("fallback_property"),
                rule.get("operator"),
                json.dumps(rule.get("check_value")),
                json.dumps(rule.get("value_min")),
                json.dumps(rule.get("value_max")),
                rule.get("unit"),
                rule.get("severity", "mandatory"),
                rule.get("desc"),
                rule.get("source_text"),
                json.dumps(rule.get("applies_when") or {}),
                rule.get("keyword"),
                rule.get("compliance_type"),
                json.dumps(rule.get("exceptions") or []),
                json.dumps(rule.get("related_refs") or []),
                rule.get("overridden_by"),
                float(rule.get("confidence") or 0.8),
                rule.get("extraction_method", "llm"),
                int(rule.get("needs_review", False)),
                json.dumps(rule),
                now,
            ),
        )
        self.conn.commit()
        return rule_id

    def clear_all_rules(self):
        """Delete all rules from the database. Use carefully — primarily for testing."""
        self.conn.execute("DELETE FROM rules")
        self.conn.commit()
        print("[RuleStore] All rules deleted")

    # ── READ ──────────────────────────────────────────────────────────────────

    def get_all_rules(self) -> list:
        """
        Return all rules as a list of dicts (from raw_payload).

        Returns:
            list[dict]
        """
        cur = self.conn.execute("SELECT raw_payload FROM rules")
        return [json.loads(row[0]) for row in cur.fetchall()]

    def fetch_rules_for_target(self, target: str) -> list:
        """
        Get all rules for a specific IFC target class.

        Args:
            target (str): e.g. "IfcStairFlight", "IfcDoor"

        Returns:
            list[dict]: list of rule dicts
        """
        cur = self.conn.execute(
            "SELECT raw_payload FROM rules WHERE target = ?",
            (target,),
        )
        return [json.loads(row[0]) for row in cur.fetchall()]

    # Keep old name as alias for backward compatibility with any existing callers
    def fetch_rules_for_entity(self, target: str) -> list:
        return self.fetch_rules_for_target(target)

    def fetch_mandatory_rules(self) -> list:
        """
        Get all rules with severity = 'mandatory'.

        Returns:
            list[dict]: list of rule dicts
        """
        cur = self.conn.execute(
            "SELECT raw_payload FROM rules WHERE severity = 'mandatory'"
        )
        return [json.loads(row[0]) for row in cur.fetchall()]

    def fetch_rules_by_ref(self, ref: str) -> list:
        """
        Get all rules for a specific OBC section reference.

        Args:
            ref (str): e.g. "9.8.2.1"

        Returns:
            list[dict]
        """
        cur = self.conn.execute(
            "SELECT raw_payload FROM rules WHERE ref LIKE ?",
            (f"%{ref}%",),
        )
        return [json.loads(row[0]) for row in cur.fetchall()]

    def fetch_needs_review(self) -> list:
        """Return all rules flagged as needing human review."""
        cur = self.conn.execute(
            "SELECT raw_payload FROM rules WHERE needs_review = 1"
        )
        return [json.loads(row[0]) for row in cur.fetchall()]

    def get_existing_entity_types(self) -> list:
        """
        Returns list of distinct IFC target classes already in the DB.
        Used by the NLP Engine to avoid extracting duplicate rules.

        Returns:
            list[str]: e.g. ["IfcStairFlight", "IfcDoor", "IfcRailing"]
        """
        cur = self.conn.execute("SELECT DISTINCT target FROM rules")
        return [row[0] for row in cur.fetchall() if row[0]]

    def get_rules_sample(self, limit: int = 3) -> list:
        """
        Returns a sample of mandatory rules as RAG examples.
        Injected into the NLP Engine prompt so the LLM sees
        the exact schema in action before extracting new rules.

        Args:
            limit (int): number of examples to return

        Returns:
            list[dict]
        """
        cur = self.conn.execute(
            "SELECT raw_payload FROM rules WHERE severity = 'mandatory' LIMIT ?",
            (limit,),
        )
        return [json.loads(row[0]) for row in cur.fetchall()]

    def fetch_all_as_dataframe(self) -> pd.DataFrame:
        """
        Return all rules as a pandas DataFrame for inspection.

        Returns:
            pd.DataFrame
        """
        return pd.read_sql_query(
            """SELECT ref, rule_type, target, property_name,
               operator, check_value, value_min, value_max,
               unit, severity, desc
               FROM rules""",
            self.conn,
        )

    def count(self) -> int:
        """Return total number of rules in the database."""
        return self.conn.execute(
            "SELECT COUNT(*) FROM rules"
        ).fetchone()[0]

    def summary(self) -> dict:
        """
        Return a summary dict of the current DB state.

        Returns:
            dict: {total, mandatory_count, by_entity, by_source}
        """
        total = self.count()

        by_entity = {}
        for row in self.conn.execute(
            "SELECT target, COUNT(*) FROM rules GROUP BY target"
        ):
            by_entity[row[0]] = row[1]

        by_source = {}
        for row in self.conn.execute(
            "SELECT source_doc, COUNT(*) FROM rules GROUP BY source_doc"
        ):
            by_source[row[0]] = row[1]

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
        """Close the database connection."""
        self.conn.close()
