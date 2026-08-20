"""High-level settings service for runtime configuration management."""

from __future__ import annotations

from app.services.static_data_service import StaticDataService


DEFAULT_SETTINGS = [
    {
        "key": "BIM_GUARD_STORAGE_BACKEND",
        "value": "supabase",
        "value_type": "string",
        "scope": "runtime",
        "description": "Object storage backend selector: local | supabase.",
    },
    {
        "key": "BIM_GUARD_RULE_MODEL",
        "value": "gpt-4o-mini",
        "value_type": "string",
        "scope": "runtime",
        "description": "Default LiteLLM model used for rule extraction.",
    },
    {
        "key": "OPENAI_MODEL",
        "value": "gpt-4o-mini",
        "value_type": "string",
        "scope": "legacy",
        "description": "Legacy Module 3 model fallback.",
    },
    {
        "key": "GEMINI_MODEL",
        "value": "gemini-1.5-flash",
        "value_type": "string",
        "scope": "legacy",
        "description": "Legacy Gemini model fallback.",
    },
    {
        "key": "SUPABASE_STORAGE_BUCKET",
        "value": "bim-guard-artifacts",
        "value_type": "string",
        "scope": "runtime",
        "description": "Supabase bucket used for artifact uploads.",
    },
    {
        "key": "SUPABASE_STORAGE_PREFIX",
        "value": "",
        "value_type": "string",
        "scope": "runtime",
        "description": "Optional key prefix for artifacts in Supabase Storage.",
    },
    {
        "key": "BIM_GUARD_LOG_LEVEL",
        "value": "WARNING",
        "value_type": "string",
        "scope": "runtime",
        "description": "Log verbosity: 0-4 or ERROR | WARNING | INFO | DEBUG | TRACE.",
    },
]


class SettingsService:
    """Expose DB-backed application settings with seeded defaults."""

    def __init__(self) -> None:
        """Initialize settings tables and insert missing default settings."""
        self._static = StaticDataService()
        self._static.seed_default_settings(DEFAULT_SETTINGS)

    def list_settings(self) -> list[dict]:
        """Return all stored settings rows."""
        return self._static.list_settings()

    def get(self, key: str, default: str = "") -> str:
        """Return one setting value."""
        return self._static.get_setting(key, default)

    def set(self, key: str, value: str) -> None:
        """Persist one setting value while preserving metadata defaults."""
        existing = next((row for row in self.list_settings() if row.get("key") == key), None)
        if existing is None:
            self._static.upsert_setting(key=key, value=value)
            return

        self._static.upsert_setting(
            key=key,
            value=value,
            value_type=str(existing.get("value_type") or "string"),
            scope=str(existing.get("scope") or "runtime"),
            is_secret=bool(existing.get("is_secret") or 0),
            description=str(existing.get("description") or ""),
        )
