"""BIMGUARD AI — Compliance Assessment Engines.

ARCH: Egress & daylight architectural checks (bimguard_arch_engine)

This is the stable, documented programmatic surface for the engines --
``from app.engines import EgressAnalysisEngine`` (etc.) is the supported
import path for any script or external project (see the "Programmatic API"
section of docs/architecture.md) that wants to run an assessment without
going through the REST API. Route handlers under ``app/api/`` call the same
functions, so both access modes always produce identical results.
"""

from app.engines.bimguard_arch_engine import EgressAnalysisEngine, SpatialDaylightEngine

__all__ = [
    "EgressAnalysisEngine",
    "SpatialDaylightEngine",
]
