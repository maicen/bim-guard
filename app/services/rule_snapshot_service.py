"""Persistence for frozen, timestamped rule-configuration snapshots.

A snapshot freezes a copy of a ruleset's rules at save time into rules_json
so it survives later edits/deletes to the live public.rules / rule-folder
rows — the live folder is mutable, a snapshot is not. This is what the
"export as structured PDF for future use" feature reads from
(app/services/pdf_report_service.py), so the exported spec sheet always
reflects the rules exactly as they were when the snapshot was taken.
"""

from __future__ import annotations

import json
from typing import Any

from app.logging_config import get_logger
from app.services.persistence import PersistenceService
from app.services.rules_service import RuleService
from app.utils import now_iso_utc

logger = get_logger(__name__)

_VALID_SOURCE_MODES = {"pdf", "ids", "manual", "mixed"}

_SNAPSHOT_SCHEMA = {
    "id": int,
    "name": str,
    "source_ruleset_id": str,
    "source_mode": str,
    "category": str,
    "rules_json": list,
    "rule_count": int,
    "notes": str,
    "created_at": str,
    "created_by": str,
}


class RuleSnapshotService:
    """CRUD for `rule_snapshots` — create/list/get/delete frozen rule configs."""

    def __init__(
        self,
        *,
        snapshots_repo=None,
        rule_service: RuleService | None = None,
        db=None,
    ) -> None:
        self._snapshots = (
            snapshots_repo
            if snapshots_repo is not None
            else PersistenceService.get_table("rule_snapshots", _SNAPSHOT_SCHEMA, db=db)
        )
        self._rule_service = rule_service if rule_service is not None else RuleService()

    def create_snapshot(
        self,
        *,
        ruleset_id: str,
        name: str = "",
        source_mode: str = "manual",
        notes: str = "",
        created_by: str = "",
    ) -> dict[str, Any]:
        """Freeze the current rules of `ruleset_id` into a new snapshot row."""
        rules = self._rule_service.list_by_ruleset(ruleset_id)
        if not rules:
            raise ValueError(f"Ruleset '{ruleset_id}' has no rules to snapshot.")

        folder = self._rule_service.get_folder(ruleset_id)
        category = (folder or {}).get("category") or rules[0].get("category") or "Arch"

        row = self._snapshots.insert(
            {
                "name": (name or ruleset_id).strip(),
                "source_ruleset_id": ruleset_id,
                "source_mode": source_mode if source_mode in _VALID_SOURCE_MODES else "manual",
                "category": category,
                "rules_json": rules,
                "rule_count": len(rules),
                "notes": notes or "",
                "created_at": now_iso_utc(),
                "created_by": created_by or "",
            }
        )
        logger.info(
            "Created rule snapshot id=%s ruleset_id=%s rules=%d",
            row.get("id"),
            ruleset_id,
            len(rules),
        )
        return row

    def list_snapshots(self) -> list[dict[str, Any]]:
        """Return all snapshots, newest first."""
        return sorted(self._snapshots.rows, key=lambda r: int(r.get("id") or 0), reverse=True)

    def get_snapshot(self, snapshot_id: int) -> dict[str, Any] | None:
        """Return one snapshot row, or None if it doesn't exist."""
        return self._snapshots.get(snapshot_id)

    def get_snapshot_rules(self, snapshot_id: int) -> list[dict[str, Any]]:
        """Return the frozen rule list for one snapshot.

        rules_json round-trips differently by backend: the SQLite adapter
        (fastlite) auto-encodes a list on insert but returns it as a raw
        JSON string on read, while Supabase/PostgREST decodes JSONB columns
        back into native Python objects. Handle both.
        """
        row = self.get_snapshot(snapshot_id)
        raw = (row or {}).get("rules_json") or []
        if isinstance(raw, str):
            try:
                return json.loads(raw) or []
            except (ValueError, TypeError):
                return []
        return raw

    def delete_snapshot(self, snapshot_id: int) -> bool:
        """Delete one snapshot. Returns False if it didn't exist."""
        if self.get_snapshot(snapshot_id) is None:
            return False
        self._snapshots.delete(snapshot_id)
        return True
