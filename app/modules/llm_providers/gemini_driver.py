"""LLMProviderDriver registration for Google Gemini."""

from __future__ import annotations

import httpx

from app.modules.llm_providers.base import (
    LLMModelInfo,
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

    async def list_models(self, *, api_key: str, api_base: str | None) -> list[LLMModelInfo]:
        if not api_key:
            raise RuntimeError("Gemini API key is required to load models.")
        base = (api_base or self.default_api_base).rstrip("/")
        models: list[LLMModelInfo] = []
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
                        # Gemini's /models endpoint publishes neither pricing
                        # nor context length, unlike OpenRouter's — but it
                        # does report a token input limit; surface that as
                        # context_length since it plays the same role.
                        models.append(
                            LLMModelInfo(
                                id=f"gemini/{model_id}",
                                name=item.get("displayName") or model_id,
                                context_length=item.get("inputTokenLimit"),
                            )
                        )
                page_token = payload.get("nextPageToken") or ""
                if not page_token:
                    break
        return sorted(set(models), key=lambda item: item.name.casefold())


LLMProviderRegistry.register(GeminiDriver())
