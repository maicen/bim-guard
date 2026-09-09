"""LLMProviderDriver registration for OpenAI."""

from __future__ import annotations

import httpx

from app.modules.llm_providers.base import (
    LLMModelInfo,
    LLMProviderDriver,
    LLMProviderRegistry,
    raise_for_provider_error,
)


class OpenAIDriver(LLMProviderDriver):
    kind = "openai"
    display_name = "OpenAI"
    description = "OpenAI's Chat Completions models (gpt-4o, gpt-4.1, ...)."
    requires_api_key = True
    default_api_base = "https://api.openai.com/v1"
    url_placeholder = "https://api.openai.com/v1"

    async def list_models(self, *, api_key: str, api_base: str | None) -> list[LLMModelInfo]:
        if not api_key:
            raise RuntimeError("OpenAI API key is required to load models.")
        base = (api_base or self.default_api_base).rstrip("/")
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"{base}/models", headers={"Authorization": f"Bearer {api_key}"})
        raise_for_provider_error(response, "OpenAI")
        models = []
        for item in response.json().get("data", []):
            model_id = item.get("id")
            # OpenAI's /models endpoint publishes neither pricing nor
            # context length, unlike OpenRouter's — see LLMModelInfo.
            if model_id:
                models.append(LLMModelInfo(id=model_id, name=item.get("name") or model_id))
        return sorted(set(models), key=lambda item: item.name.casefold())


LLMProviderRegistry.register(OpenAIDriver())
