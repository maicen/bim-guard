"""LLM transport layer — thin litellm wrapper decoupled from extraction logic.

Responsibilities (Single Responsibility):
    LLMClient / LiteLLMClient are concerned *only* with sending a chat-completion
    request to a provider and returning the raw text reply.  They know nothing
    about prompts, rule schemas, or JSON normalisation.

Adding a new provider (Open/Closed):
    Pass any LiteLLM model string — ``"gpt-4o"``, ``"gemini/gemini-2.0-flash"``,
    ``"anthropic/claude-3-5-sonnet-20241022"``, ``"mistral/mistral-large-latest"``,
    etc. — and litellm routes the request automatically.
"""

from typing import Protocol

from litellm import acompletion


class LLMClient(Protocol):
    """Minimal async chat-completion interface (Dependency Inversion)."""

    async def complete(
        self,
        messages: list[dict],
        *,
        response_format: dict | None = None,
    ) -> str:
        """Send *messages* and return the raw text content of the reply."""
        ...


class LiteLLMClient:
    """Concrete LLMClient backed by litellm — routes to any supported provider.

    Args:
        model: A LiteLLM model string, e.g. ``"gpt-4o-mini"`` or
            ``"gemini/gemini-2.0-flash"``.
        api_key: Provider API key.  When omitted, litellm reads the relevant
            environment variable (``OPENAI_API_KEY``, ``GEMINI_API_KEY``, etc.).
        temperature: Sampling temperature passed to the model.
    """

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        temperature: float = 0,
    ) -> None:
        """Initialise the client with model routing parameters."""
        self._model = model
        self._api_key = api_key or None
        self._temperature = temperature

    async def complete(
        self,
        messages: list[dict],
        *,
        response_format: dict | None = None,
    ) -> str:
        """Send a chat-completion request and return the raw text reply.

        Args:
            messages: OpenAI-style message list (role/content dicts).
            response_format: Optional ``{"type": "json_object"}`` constraint.

        Returns:
            Raw string content of the first choice's message.
        """
        kwargs: dict = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
        }
        if response_format:
            kwargs["response_format"] = response_format
        if self._api_key:
            kwargs["api_key"] = self._api_key

        response = await acompletion(**kwargs)
        return response.choices[0].message.content or ""
