"""Resolves which API key an LLM call should use.

The org's configured DB instance first, falling back to the provider's env
var. Kept separate from `LLMModelService` (app/services/llm_model_service.py),
which only resolves env-var fallbacks for the "list available models" UI
call and never consults `llm_provider_instances`.
"""

from __future__ import annotations

import os

#: Mirrors app/services/llm_model_service.py's _PROVIDER_KEYS -- the env var
#: each provider's key falls back to when no DB instance is configured.
_PROVIDER_ENV_VARS = {
    "openrouter": "OPENROUTER_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


def resolve_api_key(provider: str, organization_id: int | None) -> str | None:
    """Return the API key to use for *provider*, or None if none is configured.

    Precedence: the organization's enabled `llm_provider_instances` row for
    this provider kind (its default instance if more than one is enabled),
    then the provider's env var (e.g. `OPENROUTER_API_KEY`).
    """
    provider = provider.strip().lower()

    if organization_id is not None:
        from app.bootstrap import get_container

        service = get_container().llm_provider_instances_service
        candidates = [
            row
            for row in service.list_instances(organization_id)
            if str(row.get("kind", "")).strip().lower() == provider and row.get("is_enabled", True)
        ]
        candidates.sort(key=lambda row: not row.get("is_default"))
        for row in candidates:
            key = str(row.get("api_key") or "").strip()
            if key:
                return key

    return os.environ.get(_PROVIDER_ENV_VARS.get(provider, ""), "") or None
