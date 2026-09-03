"""Service layer for managing configured document-parsing engine instances.

Each row names one addressable parsing engine — which "kind" (a registered
ParsingEngineDriver — see app/modules/document_parsing/engines) it is, and
its connection details. This service owns persistence, uniqueness, and
single-default enforcement only; it validates a `kind` by asking
ParsingEngineRegistry whether it's registered, and asks the matching driver
whether an API key is required — it never hardcodes the set of valid kinds
itself, so a new engine kind never requires editing this file (Open/Closed).
See app/modules/document_parsing/document_extractor.py for how a resolved
instance dict is turned into an extractor via the same registry.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.modules.document_parsing.engines import ParsingEngineRegistry
from app.services.db_adapters import DatabaseAdapter


class ParsingEngineInstancesService:
    """Domain service for CRUD and default-selection of parsing-engine instances."""

    def __init__(self, instances_repo: DatabaseAdapter):
        self._repo = instances_repo

    def list_instances(self) -> list[dict[str, Any]]:
        """Retrieve all configured instances, oldest first."""
        rows = list(self._repo.rows)
        return sorted(rows, key=lambda r: int(r.get("id") or 0))

    def get_instance(self, instance_id: int) -> dict[str, Any] | None:
        """Retrieve a configured instance by primary key."""
        return self._repo.get(instance_id)

    def get_by_name(self, name: str) -> dict[str, Any] | None:
        """Retrieve a configured instance by its (case-insensitive) name."""
        clean = name.strip().lower()
        for row in self.list_instances():
            if str(row.get("name", "")).strip().lower() == clean:
                return row
        return None

    def get_default(self) -> dict[str, Any] | None:
        """Return the enabled default instance, or the first enabled instance."""
        enabled = [row for row in self.list_instances() if row.get("is_enabled", True)]
        for row in enabled:
            if row.get("is_default"):
                return row
        return enabled[0] if enabled else None

    def create_instance(
        self,
        name: str,
        kind: str,
        api_url: str,
        api_key: Optional[str] = None,
        strategy: str = "auto",
        is_default: bool = False,
        is_enabled: bool = True,
        notes: str = "",
    ) -> dict[str, Any]:
        """Register a new parsing-engine instance."""
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Instance name is required.")
        clean_kind = kind.strip().lower()
        driver = self._require_driver(clean_kind)
        clean_url = api_url.strip().rstrip("/")
        if not clean_url:
            raise ValueError("api_url is required.")
        if driver.requires_api_key and not (api_key or "").strip():
            raise ValueError(f"api_key is required for '{clean_kind}' instances.")
        if self.get_by_name(clean_name):
            raise ValueError(f"An instance named '{clean_name}' already exists.")

        clean_is_default = bool(is_default)
        if clean_is_default:
            self._clear_all_defaults()

        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "name": clean_name,
            "kind": clean_kind,
            "api_url": clean_url,
            "api_key": (api_key or "").strip(),
            "strategy": (strategy or "auto").strip().lower(),
            "is_default": clean_is_default,
            "is_enabled": bool(is_enabled),
            "notes": (notes or "").strip(),
            "created_at": now,
            "updated_at": now,
        }
        return self._repo.insert(payload)

    def update_instance(
        self,
        instance_id: int,
        name: Optional[str] = None,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        strategy: Optional[str] = None,
        is_default: Optional[bool] = None,
        is_enabled: Optional[bool] = None,
        notes: Optional[str] = None,
    ) -> dict[str, Any] | None:
        """Update metadata for an existing configured instance.

        `kind` is intentionally not updatable — it identifies which driver
        built the instance and is immutable after creation; register a new
        instance instead of repurposing one.
        """
        existing = self.get_instance(instance_id)
        if not existing:
            return None

        updates: dict[str, Any] = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if name is not None:
            clean_name = name.strip()
            if not clean_name:
                raise ValueError("Instance name cannot be empty.")
            other = self.get_by_name(clean_name)
            if other and int(other.get("id", -1)) != instance_id:
                raise ValueError(f"An instance named '{clean_name}' already exists.")
            updates["name"] = clean_name
        if api_url is not None:
            clean_url = api_url.strip().rstrip("/")
            if not clean_url:
                raise ValueError("api_url cannot be empty.")
            updates["api_url"] = clean_url
        if api_key is not None:
            updates["api_key"] = api_key.strip()
        if strategy is not None:
            updates["strategy"] = strategy.strip().lower()
        if is_enabled is not None:
            updates["is_enabled"] = bool(is_enabled)
        if notes is not None:
            updates["notes"] = notes.strip()

        if is_default is True:
            self._clear_all_defaults()
            updates["is_default"] = True
        elif is_default is False:
            updates["is_default"] = False

        self._repo.update(updates=updates, pk_values=instance_id)
        return self.get_instance(instance_id)

    def delete_instance(self, instance_id: int) -> None:
        """Delete a configured instance by primary key."""
        self._repo.delete(instance_id)

    @staticmethod
    def _require_driver(kind: str):
        try:
            return ParsingEngineRegistry.get(kind)
        except ValueError:
            valid = sorted(ParsingEngineRegistry.valid_kinds())
            raise ValueError(f"kind must be one of {valid}.") from None

    def _clear_all_defaults(self) -> None:
        """Unset is_default on every row so a single new default can be set.

        Cleared before the new default is written (not in the same call) so
        the database's `parsing_engine_instances_single_default` partial
        unique index never sees two rows with is_default=true at once.
        """
        for row in self.list_instances():
            if row.get("is_default"):
                self._repo.update(updates={"is_default": False}, pk_values=row["id"])
