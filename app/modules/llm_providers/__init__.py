"""LLM-provider driver registry — see llm_providers/base.py for the abstraction.

Importing this package populates `LLMProviderRegistry` as a side effect of
importing each driver module below. To add a new provider kind: write a new
`driver_module.py` defining an `LLMProviderDriver` subclass that calls
`LLMProviderRegistry.register(...)` at module scope, then import that module
here. No other file needs to change.
"""

# Imported for their registration side effect (LLMProviderRegistry.register
# at module scope) — the imports themselves are otherwise unused here.
from app.modules.llm_providers import (  # noqa: F401
    anthropic_driver,
    gemini_driver,
    ollama_driver,
    openai_driver,
    openrouter_driver,
)
from app.modules.llm_providers.base import (
    EngineConnectionResult,
    LLMProviderDriver,
    LLMProviderRegistry,
)

__all__ = [
    "EngineConnectionResult",
    "LLMProviderDriver",
    "LLMProviderRegistry",
]
