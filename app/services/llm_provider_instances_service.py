"""Service layer for managing an organization's configured LLM provider instances.

Each row names one addressable LLM provider — which "kind" (a registered
LLMProviderDriver — see app/modules/llm_providers) it is, and its
credentials — scoped to one organization_id. This service owns persistence,
per-org uniqueness, and per-org single-default enforcement only; it
validates a `kind` by asking LLMProviderRegistry whether it's registered, and
asks the matching driver whether an API key is required — it never
hardcodes the set of valid kinds itself, so a new provider kind never
requires editing this file (Open/Closed). Mirrors
ParsingEngineInstancesService (app/services/parsing_engine_instances_service.py),
the platform-wide equivalent for document parsing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.modules.llm_providers import LLMProviderRegistry
from app.services.db_adapters import DatabaseAdapter


class LLMProviderInstancesService:
    """Domain service for CRUD and default-selection of LLM provider instances, per org."""

    def __init__(self, instances_repo: DatabaseAdapter):
        self._repo = instances_repo

    def list_instances(self, organization_id: int) -> list[dict[str, Any]]:
        """Retrieve every instance configured for *organization_id*, oldest first."""
        rows = [r for r in self._repo.rows if int(r.get("organization_id") or 0) == organization_id]
        return sorted(rows, key=lambda r: int(r.get("id") or 0))

    def get_instance(self, organization_id: int, instance_id: int) -> dict[str, Any] | None:
        """Retrieve a configured instance by primary key, scoped to its organization."""
        row = self._repo.get(instance_id)
        if not row or int(row.get("organization_id") or 0) != organization_id:
            return None
        return row

    def get_by_name(self, organization_id: int, name: str) -> dict[str, Any] | None:
        """Retrieve a configured instance by its (case-insensitive) name within an org."""
        clean = name.strip().lower()
        for row in self.list_instances(organization_id):
            if str(row.get("name", "")).strip().lower() == clean:
                return row
        return None

    def get_default(self, organization_id: int) -> dict[str, Any] | None:
        """Return the org's enabled default instance, or its first enabled instance."""
        enabled = [row for row in self.list_instances(organization_id) if row.get("is_enabled", True)]
        for row in enabled:
            if row.get("is_default"):
                return row
        return enabled[0] if enabled else None

    def create_instance(
        self,
        organization_id: int,
        name: str,
        kind: str,
        api_key: Optional[str] = None,
        api_base: str = "",
        is_default: bool = False,
        is_enabled: bool = True,
        notes: str = "",
    ) -> dict[str, Any]:
        """Register a new LLM provider instance for *organization_id*."""
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Instance name is required.")
        clean_kind = kind.strip().lower()
        driver = self._require_driver(clean_kind)
        if driver.requires_api_key and not (api_key or "").strip():
            raise ValueError(f"api_key is required for '{clean_kind}' instances.")
        if self.get_by_name(organization_id, clean_name):
            raise ValueError(f"An instance named '{clean_name}' already exists in this organization.")

        clean_is_default = bool(is_default)
        if clean_is_default:
            self._clear_all_defaults(organization_id)

        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "organization_id": organization_id,
            "name": clean_name,
            "kind": clean_kind,
            "api_key": (api_key or "").strip(),
            "api_base": (api_base or "").strip().rstrip("/"),
            "is_default": clean_is_default,
            "is_enabled": bool(is_enabled),
            "notes": (notes or "").strip(),
            "created_at": now,
            "updated_at": now,
        }
        return self._repo.insert(payload)

    def update_instance(
        self,
        organization_id: int,
        instance_id: int,
        name: Optional[str] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
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
                raise ValueError(f"An instance named '{clean_name}' already exists in this organization.")
            updates["name"] = clean_name
        if api_key is not None:
            updates["api_key"] = api_key.strip()
        if api_base is not None:
            updates["api_base"] = api_base.strip().rstrip("/")
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

    def delete_instance(self, organization_id: int, instance_id: int) -> None:
        """Delete a configured instance by primary key, scoped to its organization."""
        if self.get_instance(organization_id, instance_id):
            self._repo.delete(instance_id)

    async def list_models(self, organization_id: int, instance_id: int) -> list[tuple[str, str]]:
        """Fetch the live model catalogue for one configured instance."""
        row = self.get_instance(organization_id, instance_id)
        if not row:
            raise ValueError(f"LLM provider instance {instance_id} not found.")
        driver = self._require_driver(row.get("kind", ""))
        return await driver.list_models(api_key=row.get("api_key") or "", api_base=row.get("api_base") or None)

    async def test_instance(self, organization_id: int, instance_id: int):
        """Check connectivity/auth for one configured instance."""
        row = self.get_instance(organization_id, instance_id)
        if not row:
            raise ValueError(f"LLM provider instance {instance_id} not found.")
        driver = self._require_driver(row.get("kind", ""))
        return await driver.test_connection(api_key=row.get("api_key") or "", api_base=row.get("api_base") or None)

    async def test_connection(
        self,
        kind: str,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
    ):
        """Check connectivity/auth for candidate credentials before creation."""
        clean_kind = (kind or "").strip().lower()
        driver = self._require_driver(clean_kind)
        clean_key = (api_key or "").strip()
        if driver.requires_api_key and not clean_key:
            raise ValueError(f"api_key is required for '{clean_kind}' instances.")
        clean_base = (api_base or "").strip().rstrip("/")
        return await driver.test_connection(api_key=clean_key, api_base=clean_base or None)

    @staticmethod
    def _require_driver(kind: str):
        try:
            return LLMProviderRegistry.get(kind)
        except ValueError:
            valid = sorted(LLMProviderRegistry.valid_kinds())
            raise ValueError(f"kind must be one of {valid}.") from None

    def _clear_all_defaults(self, organization_id: int) -> None:
        """Unset is_default on every row in this org so a single new default can be set.

        Cleared before the new default is written (not in the same call) so
        the database's `llm_provider_instances_single_default_per_org`
        partial unique index never sees two rows for the same org with
        is_default=true at once.
        """
        for row in self.list_instances(organization_id):
            if row.get("is_default"):
                self._repo.update(updates={"is_default": False}, pk_values=row["id"])
