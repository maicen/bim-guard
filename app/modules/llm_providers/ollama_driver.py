"""LLMProviderDriver registration for a local/self-hosted Ollama server."""

from __future__ import annotations

import httpx

from app.modules.llm_providers.base import (
    LLMModelInfo,
    LLMProviderDriver,
    LLMProviderRegistry,
    raise_for_provider_error,
)


class OllamaDriver(LLMProviderDriver):
    kind = "ollama"
    display_name = "Ollama (self-hosted)"
    description = "A local or self-hosted Ollama server's installed models."
    requires_api_key = False
    default_api_base = "http://localhost:11434"
    url_placeholder = "http://localhost:11434"

    async def list_models(self, *, api_key: str, api_base: str | None) -> list[LLMModelInfo]:
        base = (api_base or self.default_api_base).rstrip("/")
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"{base}/api/tags")
        raise_for_provider_error(response, "Ollama")
        # Ollama is self-hosted (no metered API), so it has no pricing to
        # publish, and /api/tags doesn't report each model's context length.
        models = [
            LLMModelInfo(id=f"ollama/{item['name']}", name=item["name"])
            for item in response.json().get("models", [])
            if item.get("name")
        ]
        return sorted(set(models), key=lambda item: item.name.casefold())


LLMProviderRegistry.register(OllamaDriver())
