"""BIMGUARD AI — Compliance Assessment Engines.

GC-001: Galvanic corrosion (bimguard_corrosion_engine)
CC-001: Crevice corrosion  (bimguard_crevice_engine)
MC-001: Microbial influence (bimguard_mic_engine)
ARCH:   Egress & daylight architectural checks (bimguard_arch_engine)

This is the stable, documented programmatic surface for the engines --
``from app.engines import GalvanicCorrosionEngine`` (etc.) is the supported
import path for any script or external project (see the "Programmatic API"
section of docs/architecture.md) that wants to run an assessment without
going through the REST API. Route handlers under ``app/api/`` call the same
functions, so both access modes always produce identical results.
"""

from app.engines.bimguard_arch_engine import EgressAnalysisEngine, SpatialDaylightEngine
from app.engines.bimguard_corrosion_engine import (
    GalvanicCorrosionEngine,
    GCElement,
    GCResult,
    assess_galvanic_risk,
)
from app.engines.bimguard_crevice_engine import (
    CCElement,
    CCResult,
    CreviceCorrosionEngine,
    assess_crevice_risk,
)
from app.engines.bimguard_mic_engine import (
    MICElement,
    MICEngine,
    MICResult,
    assess_mic_risk,
)

__all__ = [
    "EgressAnalysisEngine",
    "SpatialDaylightEngine",
    "GalvanicCorrosionEngine",
    "GCElement",
    "GCResult",
    "assess_galvanic_risk",
    "CreviceCorrosionEngine",
    "CCElement",
    "CCResult",
    "assess_crevice_risk",
    "MICEngine",
    "MICElement",
    "MICResult",
    "assess_mic_risk",
]
