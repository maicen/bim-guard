"""Discover chat models available from configured LLM providers."""

import os

from app.modules.llm_providers import LLMProviderRegistry

_PROVIDER_KEYS = {
    "openrouter": "OPENROUTER_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


class LLMModelService:
    """Fetch provider model catalogues and return LiteLLM-compatible IDs.

    A thin wrapper over LLMProviderRegistry (app/modules/llm_providers) —
    the provider-specific HTTP calls live in each registered
    LLMProviderDriver, not here. This class only resolves the env-var
    fallback API key when the caller didn't pass one explicitly, matching
    how this service has always been called from outside a configured
    LLMProviderInstance (e.g. env-var-only deployments).
    """

    async def list_models(
        self,
        provider: str,
        *,
        api_key: str | None = None,
        api_base: str | None = None,
    ) -> list[tuple[str, str]]:
        """Return available ``(model_id, display_name)`` pairs for a provider."""
        provider = provider.strip().lower()
        try:
            driver = LLMProviderRegistry.get(provider)
        except ValueError:
            raise ValueError(f"Unsupported LLM provider: {provider}") from None
        key = api_key or os.environ.get(_PROVIDER_KEYS.get(provider, ""), "")
        if provider == "ollama":
            api_base = api_base or os.environ.get("OLLAMA_API_BASE")
        models = await driver.list_models(api_key=key, api_base=api_base)
        # Drivers return richer LLMModelInfo objects (id/name plus whatever
        # pricing/context data that provider publishes — see
        # app/modules/llm_providers/base.py); this service's own callers
        # (app/agent/cli.py) only ever consumed (id, name) pairs, so keep
        # returning that shape here rather than changing every caller.
        pairs = [(m.id, m.name) for m in models]
        return sorted(set(pairs), key=lambda item: item[1].casefold())
