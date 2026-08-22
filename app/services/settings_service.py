"""High-level settings service for runtime configuration management."""

from __future__ import annotations

from app.services.static_data_service import StaticDataService

DEFAULT_SETTINGS = [
    {
        "key": "BIM_GUARD_LOG_LEVEL",
        "value": "WARNING",
        "value_type": "string",
        "scope": "runtime",
        "description": "Log verbosity: 0-4 or ERROR | WARNING | INFO | DEBUG | TRACE.",
    },
]
_MANAGED_SETTING_KEYS = {item["key"] for item in DEFAULT_SETTINGS}


class SettingsService:
    """Expose DB-backed application settings with seeded defaults."""

    _defaults_seeded = False
    _values_cache: dict[str, str] | None = None

    def __init__(self) -> None:
        """Initialize settings tables and insert missing default settings."""
        self._static = StaticDataService()
        if not self.__class__._defaults_seeded:
            self.__class__._values_cache = self._static.seed_default_settings_with_snapshot(
                DEFAULT_SETTINGS
            )
            self.__class__._defaults_seeded = True
        elif self.__class__._values_cache is None:
            self.__class__._values_cache = {
                str(row.get("key") or "").strip(): str(row.get("value") or "")
                for row in self._static.list_settings()
                if str(row.get("key") or "").strip()
            }

    @classmethod
    def _cache(cls) -> dict[str, str]:
        """Return the in-process settings cache, loading from DB on first read."""
        if cls._values_cache is None:
            svc = StaticDataService()
            cls._values_cache = {
                str(row.get("key") or "").strip(): str(row.get("value") or "")
                for row in svc.list_settings()
                if str(row.get("key") or "").strip()
            }
        return cls._values_cache

    @classmethod
    def _refresh_cache(cls) -> None:
        """Refresh the in-process settings cache from persistent storage."""
        cls._values_cache = None
        cls._cache()

    def list_settings(self) -> list[dict]:
        """Return database-managed settings, excluding environment-owned values."""
        return [
            row
            for row in self._static.list_settings()
            if row.get("key") in _MANAGED_SETTING_KEYS
        ]

    def get(self, key: str, default: str = "") -> str:
        """Return one setting value."""
        normalized = key.strip()
        if not normalized:
            return default
        return self._cache().get(normalized, default)

    def set(self, key: str, value: str) -> None:
        """Persist one setting value while preserving metadata defaults."""
        existing = next((row for row in self.list_settings() if row.get("key") == key), None)
        if existing is None:
            self._static.upsert_setting(key=key, value=value)
            self._cache()[key] = value
            return

        self._static.upsert_setting(
            key=key,
            value=value,
            value_type=str(existing.get("value_type") or "string"),
            scope=str(existing.get("scope") or "runtime"),
            is_secret=bool(existing.get("is_secret") or 0),
            description=str(existing.get("description") or ""),
        )
        self._cache()[key] = value
