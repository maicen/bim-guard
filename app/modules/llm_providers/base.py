"""LLM-provider driver abstraction.

Mirrors app/modules/document_parsing/engines/base.py: adding a new LLM
provider means writing one `LLMProviderDriver` subclass and registering it
with `LLMProviderRegistry` (see openai_driver.py, anthropic_driver.py,
gemini_driver.py, openrouter_driver.py, ollama_driver.py for the pattern).
Nothing else needs editing — LLMModelService, the LLM providers API router,
and LLMProviderInstancesService all depend on this module's registry, never
on a concrete provider class or a hardcoded kind string.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class EngineConnectionResult:
    """Outcome of a driver's connectivity check (LLMProviderDriver.test_connection)."""

    ok: bool
    detail: str = ""


@dataclass(frozen=True)
class LLMModelInfo:
    """One model available from a provider.

    Carries whatever pricing/capability metadata that provider's own
    model-listing API publishes. Only OpenRouter's `/models` endpoint
    documents pricing and context
    length (https://openrouter.ai/docs/guides/community/for-providers#3-pricing),
    so those fields are `None` for every other driver — an honest gap, not a
    guess, since OpenAI/Anthropic/Gemini/Ollama's own `/models` endpoints
    don't publish this data.
    """

    id: str
    name: str
    context_length: int | None = None
    input_price_per_million: float | None = None
    """USD per 1,000,000 input tokens."""
    output_price_per_million: float | None = None
    """USD per 1,000,000 output tokens."""
    capabilities: tuple[str, ...] = ()


class LLMProviderDriver(ABC):
    """Describes one selectable LLM provider kind.

    How to list its models and check connectivity. Every other module works
    purely against this interface plus the registry, so registering a new
    kind never means touching an if/elif chain elsewhere.
    """

    kind: ClassVar[str]
    """Stable, persisted discriminator stored in the database (e.g. "openrouter")."""

    display_name: ClassVar[str]
    """Human-readable label for the External Providers UI's kind selector."""

    description: ClassVar[str] = ""
    requires_api_key: ClassVar[bool] = False
    supports_api_base: ClassVar[bool] = True
    default_api_base: ClassVar[str] = ""
    url_placeholder: ClassVar[str] = ""

    @abstractmethod
    async def list_models(self, *, api_key: str, api_base: str | None) -> list[LLMModelInfo]:
        """Return available models for this provider, with pricing/context data where published."""

    async def test_connection(self, *, api_key: str, api_base: str | None) -> EngineConnectionResult:
        """Best-effort reachability/auth check for a configured instance of this kind.

        The default implementation just calls list_models() and reports
        success/failure from that — sufficient for every provider here since
        listing models already exercises auth and connectivity. A driver can
        override this if a cheaper dedicated check exists.
        """
        try:
            models = await self.list_models(api_key=api_key, api_base=api_base)
            return EngineConnectionResult(ok=True, detail=f"{len(models)} model(s) available.")
        except Exception as exc:
            return EngineConnectionResult(ok=False, detail=str(exc))


class LLMProviderRegistry:
    """Process-wide catalog of registered LLMProviderDriver kinds.

    A plain class-level dict rather than a DI-injected singleton: provider
    kinds are a build-time property of the codebase (which drivers are
    importable), not a runtime configuration choice, so a module-global
    registry populated by import-time `register()` calls (see __init__.py)
    is the right shape here.
    """

    _drivers: dict[str, LLMProviderDriver] = {}

    @classmethod
    def register(cls, driver: LLMProviderDriver) -> None:
        cls._drivers[driver.kind] = driver

    @classmethod
    def get(cls, kind: str) -> LLMProviderDriver:
        try:
            return cls._drivers[kind]
        except KeyError:
            raise ValueError(
                f"Unknown LLM provider kind '{kind}'. Registered kinds: {sorted(cls._drivers)}."
            ) from None

    @classmethod
    def all(cls) -> list[LLMProviderDriver]:
        return list(cls._drivers.values())

    @classmethod
    def valid_kinds(cls) -> set[str]:
        return set(cls._drivers)


def raise_for_provider_error(response, provider: str) -> None:
    """Raise a credential-safe error for an unsuccessful provider HTTP response.

    Shared by every driver's list_models() so a failed request never leaks
    response body content (which may echo back request headers/params) into
    the error surfaced to the UI.
    """
    if response.is_error:
        raise RuntimeError(f"{provider} model request failed with HTTP {response.status_code}.")
