"""LLMProviderDriver registration for Google Gemini."""

from __future__ import annotations

import httpx

from app.modules.llm_providers.base import (
    LLMProviderDriver,
    LLMProviderRegistry,
    raise_for_provider_error,
)


class GeminiDriver(LLMProviderDriver):
    kind = "gemini"
    display_name = "Google Gemini"
    description = "Gemini models via the Generative Language API."
    requires_api_key = True
    default_api_base = "https://generativelanguage.googleapis.com/v1beta"
    url_placeholder = "https://generativelanguage.googleapis.com/v1beta"

    async def list_models(self, *, api_key: str, api_base: str | None) -> list[tuple[str, str]]:
        if not api_key:
            raise RuntimeError("Gemini API key is required to load models.")
        base = (api_base or self.default_api_base).rstrip("/")
        models: list[tuple[str, str]] = []
        page_token = ""
        async with httpx.AsyncClient(timeout=15.0) as client:
            while True:
                params: dict[str, str | int] = {"key": api_key, "pageSize": 1000}
                if page_token:
                    params["pageToken"] = page_token
                response = await client.get(f"{base}/models", params=params)
                raise_for_provider_error(response, "Gemini")
                payload = response.json()
                for item in payload.get("models", []):
                    if "generateContent" not in item.get("supportedGenerationMethods", []):
                        continue
                    model_id = str(item.get("name") or "").removeprefix("models/")
                    if model_id:
                        models.append((f"gemini/{model_id}", item.get("displayName") or model_id))
                page_token = payload.get("nextPageToken") or ""
                if not page_token:
                    break
        return sorted(set(models), key=lambda item: item[1].casefold())


LLMProviderRegistry.register(GeminiDriver())
