"""Discover chat models available from configured LLM providers."""

import os

import httpx

_PROVIDER_KEYS = {
    "openrouter": "OPENROUTER_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


class LLMModelService:
    """Fetch provider model catalogues and return LiteLLM-compatible IDs."""

    async def list_models(
        self,
        provider: str,
        *,
        api_key: str | None = None,
        api_base: str | None = None,
    ) -> list[tuple[str, str]]:
        """Return available ``(model_id, display_name)`` pairs for a provider."""
        provider = provider.strip().lower()
        key = api_key or os.environ.get(_PROVIDER_KEYS.get(provider, ""), "")

        async with httpx.AsyncClient(timeout=15.0) as client:
            if provider == "ollama":
                models = await self._list_ollama(client, api_base)
            elif provider == "gemini":
                models = await self._list_gemini(client, key, api_base)
            elif provider == "anthropic":
                models = await self._list_anthropic(client, key, api_base)
            elif provider in {"openai", "openrouter"}:
                models = await self._list_openai_compatible(
                    client, provider, key, api_base
                )
            else:
                raise ValueError(f"Unsupported LLM provider: {provider}")

        return sorted(set(models), key=lambda item: item[1].casefold())

    async def _list_ollama(
        self, client: httpx.AsyncClient, api_base: str | None
    ) -> list[tuple[str, str]]:
        base = api_base or os.environ.get("OLLAMA_API_BASE", "http://localhost:11434")
        response = await client.get(f"{base.rstrip('/')}/api/tags")
        self._ensure_success(response, "Ollama")
        return [
            (f"ollama/{item['name']}", item["name"])
            for item in response.json().get("models", [])
            if item.get("name")
        ]

    async def _list_gemini(
        self, client: httpx.AsyncClient, api_key: str, api_base: str | None
    ) -> list[tuple[str, str]]:
        if not api_key:
            raise RuntimeError("Gemini API key is required to load models.")
        base = api_base or "https://generativelanguage.googleapis.com/v1beta"
        models = []
        page_token = ""
        while True:
            params = {"key": api_key, "pageSize": 1000}
            if page_token:
                params["pageToken"] = page_token
            response = await client.get(f"{base.rstrip('/')}/models", params=params)
            self._ensure_success(response, "Gemini")
            payload = response.json()
            for item in payload.get("models", []):
                if "generateContent" not in item.get("supportedGenerationMethods", []):
                    continue
                model_id = str(item.get("name") or "").removeprefix("models/")
                if model_id:
                    models.append(
                        (f"gemini/{model_id}", item.get("displayName") or model_id)
                    )
            page_token = payload.get("nextPageToken") or ""
            if not page_token:
                break
        return models

    async def _list_anthropic(
        self, client: httpx.AsyncClient, api_key: str, api_base: str | None
    ) -> list[tuple[str, str]]:
        if not api_key:
            raise RuntimeError("Anthropic API key is required to load models.")
        base = api_base or "https://api.anthropic.com/v1"
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        models = []
        after_id = ""
        while True:
            params = {"limit": 1000}
            if after_id:
                params["after_id"] = after_id
            response = await client.get(
                f"{base.rstrip('/')}/models", params=params, headers=headers
            )
            self._ensure_success(response, "Anthropic")
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
        return models

    async def _list_openai_compatible(
        self,
        client: httpx.AsyncClient,
        provider: str,
        api_key: str,
        api_base: str | None,
    ) -> list[tuple[str, str]]:
        if provider == "openai" and not api_key:
            raise RuntimeError("OpenAI API key is required to load models.")
        default_base = (
            "https://openrouter.ai/api/v1"
            if provider == "openrouter"
            else "https://api.openai.com/v1"
        )
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        response = await client.get(
            f"{(api_base or default_base).rstrip('/')}/models", headers=headers
        )
        self._ensure_success(response, provider.title())
        models = []
        for item in response.json().get("data", []):
            model_id = item.get("id")
            if not model_id:
                continue
            litellm_id = model_id
            if provider == "openrouter" and not model_id.startswith("openrouter/"):
                litellm_id = f"openrouter/{model_id}"
            models.append((litellm_id, item.get("name") or model_id))
        return models

    @staticmethod
    def _ensure_success(response: httpx.Response, provider: str) -> None:
        """Raise a credential-safe error for an unsuccessful provider response."""
        if response.is_error:
            raise RuntimeError(
                f"{provider} model request failed with HTTP {response.status_code}."
            )