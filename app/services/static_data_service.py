"""Database-backed storage for static assets and runtime settings."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.services.persistence import PersistenceService
from app.utils import now_iso_utc

_STATIC_ASSET_SCHEMA = {
    "id": int,
    "asset_key": str,
    "source_path": str,
    "format": str,
    "content_json": str,
    "content_text": str,
    "content_sha256": str,
    "migrated_at": str,
    "active": int,
}

_SETTINGS_SCHEMA = {
    "key": str,
    "value": str,
    "value_type": str,
    "scope": str,
    "is_secret": int,
    "description": str,
    "updated_at": str,
}


class StaticDataService:
    """Persist static payloads and app settings inside the shared database."""

    def __init__(self, *, assets_repo=None, settings_repo=None) -> None:
        """Initialize storage tables used for static payload migration with dependency injection."""
        self._assets = (
            assets_repo
            if assets_repo is not None
            else PersistenceService.get_table("static_data_assets", _STATIC_ASSET_SCHEMA)
        )
        self._settings = (
            settings_repo
            if settings_repo is not None
            else PersistenceService.get_table("app_settings", _SETTINGS_SCHEMA, pk="key")
        )

    @staticmethod
    def _json_text(payload: Any) -> str:
        """Serialize a payload as stable JSON text."""
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _sha256(value: str) -> str:
        """Return SHA-256 hash for a UTF-8 string value."""
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def upsert_asset(
        self,
        *,
        asset_key: str,
        source_path: str,
        format_name: str,
        payload: Any,
        content_text: str = "",
    ) -> dict:
        """Insert or update a static asset payload by unique key."""
        normalized_key = asset_key.strip()
        if not normalized_key:
            raise ValueError("asset_key is required")

        json_text = self._json_text(payload)
        now = now_iso_utc()
        record = {
            "asset_key": normalized_key,
            "source_path": source_path,
            "format": format_name,
            "content_json": json_text,
            "content_text": content_text,
            "content_sha256": self._sha256(json_text + "\n" + content_text),
            "migrated_at": now,
            "active": 1,
        }

        existing = self._assets.rows_where("asset_key = ?", [normalized_key], limit=1)
        if existing:
            row = existing[0]
            self._assets.update(updates=record, pk_values=row["id"])
            record["id"] = row["id"]
            return record

        return self._assets.insert(record)

    def get_asset(self, asset_key: str) -> dict | None:
        """Return a static asset row by key."""
        key = asset_key.strip()
        if not key:
            return None
        rows = self._assets.rows_where("asset_key = ?", [key], limit=1)
        return rows[0] if rows else None

    def get_asset_json(self, asset_key: str) -> dict | list | None:
        """Return decoded JSON payload for an asset key."""
        row = self.get_asset(asset_key)
        if row is None:
            return None
        raw = row.get("content_json") or ""
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        if isinstance(payload, (dict, list)):
            return payload
        return None

    def list_assets(self) -> list[dict]:
        """Return all static asset rows, newest first."""
        rows = list(self._assets.rows)
        return sorted(rows, key=lambda row: row.get("asset_key", ""))

    def upsert_setting(
        self,
        *,
        key: str,
        value: str,
        value_type: str = "string",
        scope: str = "runtime",
        is_secret: bool = False,
        description: str = "",
    ) -> dict:
        """Insert or update one application setting."""
        normalized_key = key.strip()
        if not normalized_key:
            raise ValueError("setting key is required")

        existing = self._settings.get(normalized_key)
        payload = {
            "value": value,
            "value_type": value_type,
            "scope": scope,
            "is_secret": int(bool(is_secret)),
            "description": description,
            "updated_at": now_iso_utc(),
        }

        if existing is None:
            return self._settings.insert({"key": normalized_key, **payload})

        self._settings.update(updates=payload, pk_values=normalized_key)
        return {"key": normalized_key, **payload}

    def get_setting(self, key: str, default: str = "") -> str:
        """Return a setting value by key or provided default."""
        row = self._settings.get(key.strip())
        if row is None:
            return default
        return str(row.get("value") or default)

    def list_settings(self) -> list[dict]:
        """Return all settings rows sorted by key."""
        rows = list(self._settings.rows)
        return sorted(rows, key=lambda row: str(row.get("key") or ""))

    def seed_default_settings_with_snapshot(self, defaults: list[dict[str, Any]]) -> dict[str, str]:
        """Ensure defaults exist and return a key/value snapshot with one initial read."""
        rows = self.list_settings()
        existing_values: dict[str, str] = {
            str(row.get("key") or "").strip(): str(row.get("value") or "")
            for row in rows
            if str(row.get("key") or "").strip()
        }

        for item in defaults:
            key = str(item.get("key") or "").strip()
            if not key or key in existing_values:
                continue
            value = str(item.get("value") or "")
            self._settings.insert(
                {
                    "key": key,
                    "value": value,
                    "value_type": str(item.get("value_type") or "string"),
                    "scope": str(item.get("scope") or "runtime"),
                    "is_secret": int(bool(item.get("is_secret") or False)),
                    "description": str(item.get("description") or ""),
                    "updated_at": now_iso_utc(),
                }
            )
            existing_values[key] = value

        return existing_values

    def seed_default_settings(self, defaults: list[dict[str, Any]]) -> int:
        """Insert missing settings from defaults without overwriting values."""
        existing_keys = {
            str(row.get("key") or "").strip()
            for row in self.list_settings()
            if str(row.get("key") or "").strip()
        }
        inserted = 0
        for item in defaults:
            key = str(item.get("key") or "").strip()
            if not key:
                continue
            if key in existing_keys:
                continue
            self._settings.insert(
                {
                    "key": key,
                    "value": str(item.get("value") or ""),
                    "value_type": str(item.get("value_type") or "string"),
                    "scope": str(item.get("scope") or "runtime"),
                    "is_secret": int(bool(item.get("is_secret") or False)),
                    "description": str(item.get("description") or ""),
                    "updated_at": now_iso_utc(),
                }
            )
            existing_keys.add(key)
            inserted += 1
        return inserted
