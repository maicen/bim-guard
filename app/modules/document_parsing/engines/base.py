"""Parsing-engine driver abstraction.

Adding a new document-parsing engine — a new backend, or a new deployment
mode of an existing backend (local vs. hosted) — means writing one
`ParsingEngineDriver` subclass and registering it with `ParsingEngineRegistry`
(see engines/unstructured_driver.py and engines/docling_driver.py for the
pattern). Nothing else needs editing: document_extractor.py, the parsing
engines API router, and ParsingEngineInstancesService all depend on this
module's `ParsingEngine` protocol and `ParsingEngineRegistry`, never on a
concrete extractor class or a hardcoded kind string — Dependency Inversion
and Open/Closed in the same move.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, Protocol, runtime_checkable


@runtime_checkable
class ParsingEngine(Protocol):
    """What document_extractor.py needs from any structured-extraction engine.

    Deliberately minimal (Interface Segregation) — an engine's own richer
    API (e.g. UnstructuredExtractor.extract for on-disk files) lives on the
    concrete class; callers that only extract from in-memory bytes never
    need to know it exists.
    """

    def extract_bytes(self, content: bytes, filename: str) -> tuple[str, list[dict], list[dict]]: ...


@dataclass(frozen=True)
class EngineConnectionResult:
    """Outcome of a driver's connectivity check (ParsingEngineDriver.test_connection)."""

    ok: bool
    detail: str = ""


class ParsingEngineDriver(ABC):
    """Describes one selectable parsing-engine kind and builds/tests instances of it.

    A subclass is the single place its kind's behavior lives — how to build
    an extractor for it, how to check it's reachable, whether it needs an
    API key, whether "strategy" means anything to it. Every other module
    works purely against this interface plus the registry, so registering a
    new kind never means touching an if/elif chain elsewhere (Single
    Responsibility: this class owns exactly one kind's behavior; Liskov:
    any driver is substitutable for another through this same interface).
    """

    kind: ClassVar[str]
    """Stable, persisted discriminator stored in the database (e.g. "docling-local")."""

    family: ClassVar[str]
    """Groups kinds sharing an underlying backend (e.g. "unstructured", "docling")."""

    display_name: ClassVar[str]
    """Human-readable label for the Settings UI's kind selector."""

    description: ClassVar[str] = ""
    requires_api_key: ClassVar[bool] = False
    supports_strategy: ClassVar[bool] = False
    url_placeholder: ClassVar[str] = ""

    @abstractmethod
    def build(self, *, api_key: str, api_url: str, strategy: str, name: str) -> ParsingEngine:
        """Construct the concrete extractor for a configured instance of this kind."""

    @abstractmethod
    def test_connection(self, *, api_key: str, api_url: str) -> EngineConnectionResult:
        """Best-effort reachability/auth check against a configured instance."""


class ParsingEngineRegistry:
    """Process-wide catalog of registered ParsingEngineDriver kinds.

    A plain class-level dict rather than a DI-injected singleton: engine
    kinds are a build-time property of the codebase (which drivers are
    importable), not a runtime configuration choice, so a module-global
    registry populated by import-time `register()` calls (see
    engines/__init__.py) is the right shape here.
    """

    _drivers: dict[str, ParsingEngineDriver] = {}

    @classmethod
    def register(cls, driver: ParsingEngineDriver) -> None:
        cls._drivers[driver.kind] = driver

    @classmethod
    def get(cls, kind: str) -> ParsingEngineDriver:
        try:
            return cls._drivers[kind]
        except KeyError:
            raise ValueError(
                f"Unknown parsing engine kind '{kind}'. Registered kinds: {sorted(cls._drivers)}."
            ) from None

    @classmethod
    def all(cls) -> list[ParsingEngineDriver]:
        return list(cls._drivers.values())

    @classmethod
    def valid_kinds(cls) -> set[str]:
        return set(cls._drivers)
