"""LLMProviderDriver registration for OpenRouter."""

from __future__ import annotations

import httpx

from app.modules.llm_providers.base import (
    LLMModelInfo,
    LLMProviderDriver,
    LLMProviderRegistry,
    raise_for_provider_error,
)


def _price_per_million(pricing: dict, key: str) -> float | None:
    """Convert OpenRouter's per-token decimal-string price to USD per 1M tokens.

    See https://openrouter.ai/docs/guides/community/for-providers#3-pricing —
    `pricing.prompt`/`pricing.completion` are cost-per-token strings (e.g.
    "0.000003"); "0" is a genuine free price, not a missing one.
    """
    raw = pricing.get(key)
    if raw is None:
        return None
    try:
        return float(raw) * 1_000_000
    except (TypeError, ValueError):
        return None


class OpenRouterDriver(LLMProviderDriver):
    kind = "openrouter"
    display_name = "OpenRouter"
    description = "Aggregates many hosted model providers behind one API."
    requires_api_key = True
    default_api_base = "https://openrouter.ai/api/v1"
    url_placeholder = "https://openrouter.ai/api/v1"

    async def list_models(self, *, api_key: str, api_base: str | None) -> list[LLMModelInfo]:
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
        models: list[LLMModelInfo] = []
        for item in response.json().get("data", []):
            model_id = item.get("id")
            if not model_id:
                continue
            litellm_id = model_id if model_id.startswith("openrouter/") else f"openrouter/{model_id}"
            pricing = item.get("pricing") or {}
            architecture = item.get("architecture") or {}
            capabilities = tuple(architecture.get("input_modalities") or ()) + ("structured_outputs",)
            models.append(
                LLMModelInfo(
                    id=litellm_id,
                    name=item.get("name") or model_id,
                    context_length=item.get("context_length"),
                    input_price_per_million=_price_per_million(pricing, "prompt"),
                    output_price_per_million=_price_per_million(pricing, "completion"),
                    capabilities=capabilities,
                )
            )
        return sorted(set(models), key=lambda item: item.name.casefold())


LLMProviderRegistry.register(OpenRouterDriver())
