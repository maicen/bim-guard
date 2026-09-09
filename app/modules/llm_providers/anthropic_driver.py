"""LLMProviderDriver registration for Anthropic."""

from __future__ import annotations

import httpx

from app.modules.llm_providers.base import (
    LLMProviderDriver,
    LLMProviderRegistry,
    raise_for_provider_error,
)


class AnthropicDriver(LLMProviderDriver):
    kind = "anthropic"
    display_name = "Anthropic"
    description = "Claude models, called directly against the Anthropic API."
    requires_api_key = True
    default_api_base = "https://api.anthropic.com/v1"
    url_placeholder = "https://api.anthropic.com/v1"

    async def list_models(self, *, api_key: str, api_base: str | None) -> list[tuple[str, str]]:
        if not api_key:
            raise RuntimeError("Anthropic API key is required to load models.")
        base = (api_base or self.default_api_base).rstrip("/")
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        models: list[tuple[str, str]] = []
        after_id = ""
        async with httpx.AsyncClient(timeout=15.0) as client:
            while True:
                params: dict[str, str | int] = {"limit": 1000}
                if after_id:
                    params["after_id"] = after_id
                response = await client.get(f"{base}/models", params=params, headers=headers)
                raise_for_provider_error(response, "Anthropic")
                payload = response.json()
                models.extend(
                    (f"anthropic/{item['id']}", item.get("display_name") or item["id"])
                    for item in payload.get("data", [])
                    if item.get("id")
                )
                if not payload.get("has_more"):
                    break
                after_id = payload.get("last_id") or ""
                if not after_id:
                    break
        return sorted(set(models), key=lambda item: item[1].casefold())


LLMProviderRegistry.register(AnthropicDriver())
