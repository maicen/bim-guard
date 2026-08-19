"""LLM transport layer — thin litellm wrapper decoupled from extraction logic.

Responsibilities (Single Responsibility):
    LLMClient / LiteLLMClient are concerned *only* with sending a chat-completion
    request to a provider and returning the raw text reply.  They know nothing
    about prompts, rule schemas, or JSON normalisation.

Adding a new provider (Open/Closed):
    Pass any LiteLLM model string — ``"gpt-4o"``, ``"gemini/gemini-2.0-flash"``,
    ``"anthropic/claude-3-5-sonnet-20241022"``, ``"mistral/mistral-large-latest"``,
    etc. — and litellm routes the request automatically.

Retrying (Decorator):
    LiteLLMClientWithRetry wraps any LLMClient and adds exponential-backoff
    retrying without the wrapped client knowing about it.  Because it satisfies
    the same LLMClient protocol it is a drop-in substitute anywhere a client is
    accepted.

Configuration:
    Defaults for temperature, max_tokens, and retry come from
    ``app.modules.config`` (Issue #17).  That module opens a database connection
    at import time, so it is imported lazily inside ``__init__`` rather than at
    module scope — importing this module must not require a live database.
"""

import asyncio
from typing import Protocol

from litellm import acompletion
from litellm.exceptions import (
    APIConnectionError,
    InternalServerError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)

# Transient provider-side failures worth retrying. Authentication, bad-request,
# and unknown-model errors are NOT retried — they fail identically every time,
# so retrying only delays the error the caller needs to see.
_RETRYABLE = (
    APIConnectionError,
    InternalServerError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)


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
        temperature: Sampling temperature.  Defaults to
            ``config.COMPLIANCE_TEMPERATURE``, which is correct for every
            current caller since they all parse the reply as JSON.
        max_tokens: Response-length cap.  Defaults to
            ``config.MAX_TOKENS_COMPLIANCE``.

    This class does not retry.  Wrap it in LiteLLMClientWithRetry for that.
    """

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> None:
        """Initialise the client, filling unset values from the shared config."""
        if temperature is None or max_tokens is None:
            # Lazy: see module docstring — config touches the database.
            from app.modules.config import COMPLIANCE_TEMPERATURE, MAX_TOKENS_COMPLIANCE

            if temperature is None:
                temperature = COMPLIANCE_TEMPERATURE
            if max_tokens is None:
                max_tokens = MAX_TOKENS_COMPLIANCE

        self._model = model
        self._api_key = api_key or None
        self._temperature = temperature
        self._max_tokens = max_tokens

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
        if self._max_tokens is not None:
            kwargs["max_tokens"] = self._max_tokens
        if response_format:
            kwargs["response_format"] = response_format
        if self._api_key:
            kwargs["api_key"] = self._api_key

        response = await acompletion(**kwargs)
        return response.choices[0].message.content or ""


class LiteLLMClientWithRetry:
    """Adds exponential-backoff retrying to any LLMClient (Decorator).

    Satisfies the LLMClient protocol itself, so it substitutes anywhere a plain
    client is accepted::

        client = LiteLLMClientWithRetry(LiteLLMClient(model=DEFAULT_LLM_MODEL))
        extractor = LiteLLMRuleExtractor(client=client)

    Only transient provider failures are retried (see ``_RETRYABLE``).
    Authentication errors, unknown models, and malformed requests fail the same
    way on every attempt, so retrying them only delays the error the caller
    needs to see.

    Args:
        client: The LLMClient to wrap.
        max_attempts: Total attempts including the first.  Defaults to
            ``config.RETRY_MAX_ATTEMPTS``.
        initial_delay: Seconds before the second attempt.  Defaults to
            ``config.RETRY_INITIAL_DELAY_SECONDS``.
        backoff: Delay multiplier applied after each failure.  Defaults to
            ``config.RETRY_BACKOFF_MULTIPLIER``.
    """

    def __init__(
        self,
        client: LLMClient,
        *,
        max_attempts: int | None = None,
        initial_delay: float | None = None,
        backoff: float | None = None,
    ) -> None:
        """Wrap *client*, filling unset retry values from the shared config."""
        if max_attempts is None or initial_delay is None or backoff is None:
            # Lazy: see module docstring — config touches the database.
            from app.modules.config import (
                RETRY_BACKOFF_MULTIPLIER,
                RETRY_INITIAL_DELAY_SECONDS,
                RETRY_MAX_ATTEMPTS,
            )

            if max_attempts is None:
                max_attempts = RETRY_MAX_ATTEMPTS
            if initial_delay is None:
                initial_delay = RETRY_INITIAL_DELAY_SECONDS
            if backoff is None:
                backoff = RETRY_BACKOFF_MULTIPLIER

        self.client = client
        self.max_attempts = max(1, max_attempts)
        self.initial_delay = initial_delay
        self.backoff = backoff

    async def complete(
        self,
        messages: list[dict],
        *,
        response_format: dict | None = None,
    ) -> str:
        """Delegate to the wrapped client, retrying transient failures.

        Args:
            messages: OpenAI-style message list (role/content dicts).
            response_format: Optional ``{"type": "json_object"}`` constraint.

        Returns:
            Raw string content of the first choice's message.

        Raises:
            litellm.exceptions.APIError: Re-raised unchanged once the retry
                budget is exhausted, or immediately for non-transient failures.
        """
        delay = self.initial_delay
        for attempt in range(1, self.max_attempts + 1):
            try:
                return await self.client.complete(messages, response_format=response_format)
            except _RETRYABLE:
                if attempt == self.max_attempts:
                    raise
                await asyncio.sleep(delay)
                delay *= self.backoff

        # Unreachable: the loop either returns or raises on its final attempt.
        raise AssertionError("retry loop exited without returning")
