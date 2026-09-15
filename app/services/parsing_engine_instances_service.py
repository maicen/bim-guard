"""Service layer for managing configured document-parsing engine instances.

Two tiers, one table: `organization_id is None` is the platform-wide tier
(superadmin-managed; the historical shape of this service before org
scoping was added) and a non-null `organization_id` is an org-scoped tier
an org's own owner/admin can manage, mirroring LLMProviderInstancesService
(app/services/llm_provider_instances_service.py). `get_effective_default`
prefers an org's own default and falls back to the platform default,
matching the fallback idiom documents.py already uses when resolving which
engine to extract with.

Each row names one addressable parsing engine — which "kind" (a registered
ParsingEngineDriver — see app/modules/document_parsing/engines) it is, and
its connection details. This service owns persistence, per-scope
uniqueness, and per-scope single-default enforcement only; it validates a
`kind` by asking ParsingEngineRegistry whether it's registered, and asks the
matching driver whether an API key is required — it never hardcodes the set
of valid kinds itself, so a new engine kind never requires editing this file
(Open/Closed). See app/modules/document_parsing/document_extractor.py for
how a resolved instance dict is turned into an extractor via the same
registry.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.modules.document_parsing.engines import ParsingEngineRegistry
from app.services.db_adapters import DatabaseAdapter


class ParsingEngineInstancesService:
    """Domain service for CRUD and default-selection of parsing-engine instances, per scope."""

    def __init__(self, instances_repo: DatabaseAdapter):
        self._repo = instances_repo

    def list_instances(self, organization_id: int | None) -> list[dict[str, Any]]:
        """Retrieve every instance configured for *organization_id* (None = platform tier), oldest first."""
        rows = [r for r in self._repo.rows if r.get("organization_id") == organization_id]
        return sorted(rows, key=lambda r: int(r.get("id") or 0))

    def get_instance(self, organization_id: int | None, instance_id: int) -> dict[str, Any] | None:
        """Retrieve a configured instance by primary key, scoped to its tier."""
        row = self._repo.get(instance_id)
        if not row or row.get("organization_id") != organization_id:
            return None
        return row

    def get_by_name(self, organization_id: int | None, name: str) -> dict[str, Any] | None:
        """Retrieve a configured instance by its (case-insensitive) name within a scope."""
        clean = name.strip().lower()
        for row in self.list_instances(organization_id):
            if str(row.get("name", "")).strip().lower() == clean:
                return row
        return None

    def get_default(self, organization_id: int | None) -> dict[str, Any] | None:
        """Return the scope's enabled default instance, or its first enabled instance."""
        enabled = [row for row in self.list_instances(organization_id) if row.get("is_enabled", True)]
        for row in enabled:
            if row.get("is_default"):
                return row
        return enabled[0] if enabled else None

    def get_effective_default(self, organization_id: int) -> dict[str, Any] | None:
        """Return the org's own enabled default if configured, else the platform default."""
        return self.get_default(organization_id) or self.get_default(None)

    def create_instance(
        self,
        organization_id: int | None,
        name: str,
        kind: str,
        api_url: str,
        api_key: Optional[str] = None,
        strategy: str = "auto",
        is_default: bool = False,
        is_enabled: bool = True,
        notes: str = "",
    ) -> dict[str, Any]:
        """Register a new parsing-engine instance in the given scope."""
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
        if self.get_by_name(organization_id, clean_name):
            scope = f"organization {organization_id}" if organization_id is not None else "the platform tier"
            raise ValueError(f"An instance named '{clean_name}' already exists in {scope}.")

        clean_is_default = bool(is_default)
        if clean_is_default:
            self._clear_all_defaults(organization_id)

        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "organization_id": organization_id,
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
        organization_id: int | None,
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
        existing = self.get_instance(organization_id, instance_id)
        if not existing:
            return None

        updates: dict[str, Any] = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if name is not None:
            clean_name = name.strip()
            if not clean_name:
                raise ValueError("Instance name cannot be empty.")
            other = self.get_by_name(organization_id, clean_name)
            if other and int(other.get("id", -1)) != instance_id:
                scope = f"organization {organization_id}" if organization_id is not None else "the platform tier"
                raise ValueError(f"An instance named '{clean_name}' already exists in {scope}.")
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
            self._clear_all_defaults(organization_id)
            updates["is_default"] = True
        elif is_default is False:
            updates["is_default"] = False

        self._repo.update(updates=updates, pk_values=instance_id)
        return self.get_instance(organization_id, instance_id)

    def delete_instance(self, organization_id: int | None, instance_id: int) -> None:
        """Delete a configured instance by primary key, scoped to its tier."""
        if self.get_instance(organization_id, instance_id):
            self._repo.delete(instance_id)

    @staticmethod
    def _require_driver(kind: str):
        try:
            return ParsingEngineRegistry.get(kind)
        except ValueError:
            valid = sorted(ParsingEngineRegistry.valid_kinds())
            raise ValueError(f"kind must be one of {valid}.") from None

    def _clear_all_defaults(self, organization_id: int | None) -> None:
        """Unset is_default on every row in this scope so a single new default can be set.

        Cleared before the new default is written (not in the same call) so
        the database's per-scope single-default partial unique indexes never
        see two rows for the same scope with is_default=true at once.
        """
        for row in self.list_instances(organization_id):
            if row.get("is_default"):
                self._repo.update(updates={"is_default": False}, pk_values=row["id"])
