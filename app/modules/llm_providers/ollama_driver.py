"""LLMProviderDriver registration for a local/self-hosted Ollama server."""

from __future__ import annotations

import httpx

from app.modules.llm_providers.base import (
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

    async def list_models(self, *, api_key: str, api_base: str | None) -> list[tuple[str, str]]:
        base = (api_base or self.default_api_base).rstrip("/")
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"{base}/api/tags")
        raise_for_provider_error(response, "Ollama")
        models = [
            (f"ollama/{item['name']}", item["name"])
            for item in response.json().get("models", [])
            if item.get("name")
        ]
        return sorted(set(models), key=lambda item: item[1].casefold())


LLMProviderRegistry.register(OllamaDriver())
