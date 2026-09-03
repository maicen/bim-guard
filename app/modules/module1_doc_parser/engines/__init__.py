"""Parsing-engine driver registry — see engines/base.py for the abstraction.

Importing this package populates `ParsingEngineRegistry` as a side effect of
importing each driver module below. To add a new engine kind: write a new
`driver_module.py` defining a `ParsingEngineDriver` subclass that calls
`ParsingEngineRegistry.register(...)` at module scope, then import that
module here. No other file needs to change.
"""

# Imported for their registration side effect (ParsingEngineRegistry.register
# at module scope) — the imports themselves are otherwise unused here.
from app.modules.module1_doc_parser.engines import (  # noqa: F401
    docling_driver,
    unstructured_driver,
)
from app.modules.module1_doc_parser.engines.base import (
    EngineConnectionResult,
    ParsingEngine,
    ParsingEngineDriver,
    ParsingEngineRegistry,
)

__all__ = [
    "EngineConnectionResult",
    "ParsingEngine",
    "ParsingEngineDriver",
    "ParsingEngineRegistry",
]
