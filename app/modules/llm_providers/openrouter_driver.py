"""LLMProviderDriver registration for OpenRouter."""

from __future__ import annotations

import httpx

from app.modules.llm_providers.base import (
    LLMProviderDriver,
    LLMProviderRegistry,
    raise_for_provider_error,
)


class OpenRouterDriver(LLMProviderDriver):
    kind = "openrouter"
    display_name = "OpenRouter"
    description = "Aggregates many hosted model providers behind one API."
    requires_api_key = True
    default_api_base = "https://openrouter.ai/api/v1"
    url_placeholder = "https://openrouter.ai/api/v1"

    async def list_models(self, *, api_key: str, api_base: str | None) -> list[tuple[str, str]]:
        base = (api_base or self.default_api_base).rstrip("/")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        # Every LLM call in this app that needs typed output goes through
        # LlamaIndex's LLMTextCompletionProgram (deontic extraction, rule
        # generation, the section-tree AI cleanup pass), so only surface
        # models OpenRouter reports as supporting structured outputs —
        # anything else is liable to return unparseable text.
        params = {"supported_parameters": "structured_outputs"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"{base}/models", headers=headers, params=params)
        raise_for_provider_error(response, "OpenRouter")
        models = []
        for item in response.json().get("data", []):
            model_id = item.get("id")
            if not model_id:
                continue
            litellm_id = model_id if model_id.startswith("openrouter/") else f"openrouter/{model_id}"
            models.append((litellm_id, item.get("name") or model_id))
        return sorted(set(models), key=lambda item: item[1].casefold())


LLMProviderRegistry.register(OpenRouterDriver())
