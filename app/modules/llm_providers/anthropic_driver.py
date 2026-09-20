"""LLMProviderDriver registration for Anthropic."""

from __future__ import annotations

import httpx

from app.modules.llm_providers.base import (
    LLMModelInfo,
    LLMProviderDriver,
    LLMProviderRegistry,
)


def _anthropic_error_summary(response: httpx.Response, api_key: str) -> str:
    """Describe a failed Anthropic request, including Anthropic's own reason.

    The shared ``raise_for_provider_error`` reports only the status code, which
    leaves a bare "HTTP 400" with no way to tell a billing problem from a bad
    parameter. Anthropic's structured error body (``error.message``) is that
    reason and does not echo credentials, so it is surfaced here -- unless it
    ever contains the key, in which case only the status is reported.
    """
    summary = f"Anthropic model request failed with HTTP {response.status_code}."
    try:
        payload = response.json()
    except ValueError:
        return summary
    error = payload.get("error") if isinstance(payload, dict) else None
    message = error.get("message") if isinstance(error, dict) else None
    if not isinstance(message, str) or not message.strip():
        return summary
    if api_key and api_key in message:
        return summary
    return f"{summary} {message.strip()[:300]}"


class AnthropicDriver(LLMProviderDriver):
    kind = "anthropic"
    display_name = "Anthropic"
    description = "Claude models, called directly against the Anthropic API."
    requires_api_key = True
    default_api_base = "https://api.anthropic.com/v1"
    url_placeholder = "https://api.anthropic.com/v1"

    async def list_models(self, *, api_key: str, api_base: str | None) -> list[LLMModelInfo]:
        if not api_key:
            raise RuntimeError("Anthropic API key is required to load models.")
        base = (api_base or self.default_api_base).rstrip("/")
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        models: list[LLMModelInfo] = []
        after_id = ""
        async with httpx.AsyncClient(timeout=15.0) as client:
            while True:
                params: dict[str, str | int] = {"limit": 1000}
                if after_id:
                    params["after_id"] = after_id
                response = await client.get(f"{base}/models", params=params, headers=headers)
                if response.is_error:
                    raise RuntimeError(_anthropic_error_summary(response, api_key))
                payload = response.json()
                # Anthropic's /models endpoint publishes neither pricing nor
                # context length, unlike OpenRouter's — see LLMModelInfo.
                models.extend(
                    LLMModelInfo(id=f"anthropic/{item['id']}", name=item.get("display_name") or item["id"])
                    for item in payload.get("data", [])
                    if item.get("id")
                )
                if not payload.get("has_more"):
                    break
                after_id = payload.get("last_id") or ""
                if not after_id:
                    break
        return sorted(set(models), key=lambda item: item.name.casefold())


LLMProviderRegistry.register(AnthropicDriver())
