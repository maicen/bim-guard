"""BIMGUARD AI — Topology & Graph Compute Engine.

Implements the RuleEvaluator protocol for theme-agnostic structural graph
checks that sit underneath every discipline (Architecture, Piping, Seismic)
rather than inside one of them -- see ``app.modules.ifc_reader.ifc_graph`` for
the NetworkX relationship graph this evaluates records from.

Engines:
1. GraphTopologyEngine (GRAPH-TOPOLOGY-001):
   Flags IFC products with no spatial, connection, or material relationship
   anywhere in the model (``ifc_graph.find_orphan_elements``).
"""

from __future__ import annotations

from typing import Any

from app.logging_config import get_logger
from app.modules.comparator.engine_registry import RuleEvaluationContext, RuleEvaluator
from app.modules.contracts import RuleEvaluationRequest, RuleEvaluationResult

logger = get_logger(__name__)

_SPATIAL_ROOT_TYPES = {"IfcProject", "IfcSite", "IfcBuilding", "IfcBuildingStorey", "IfcSpace"}


class GraphTopologyEngine(RuleEvaluator):
    """Orphan/disconnected element detection engine conforming to RuleEvaluator.

    Unlike the discipline engines in ``bimguard_arch_engine.py``, this check
    has no numeric threshold to resolve from the DB rules table: an element
    with zero relationships in the model graph is a structural defect
    regardless of ruleset, the same way a missing FireRating property is an
    unconditional fail in ``SpatialDaylightEngine``.
    """

    def __init__(self) -> None:
        """Initialize the engine. No DI seam needed -- no DB thresholds to resolve."""
        self.rule_type = "GRAPH-TOPOLOGY-001"

    def evaluate(
        self,
        element: Any,
        *,
        context: RuleEvaluationContext | RuleEvaluationRequest | None = None,
    ) -> RuleEvaluationResult:
        """Evaluate one graph-node record (``guid``/``label``/``ifc_type``/``degree``)."""
        data = element if isinstance(element, dict) else getattr(element, "__dict__", {})
        guid = str(data.get("guid") or data.get("id") or "UNKNOWN")
        label = str(data.get("label") or guid)
        ifc_type = str(data.get("ifc_type") or "Unknown")
        degree = int(data.get("degree") or 0)

        is_orphan = degree == 0 and ifc_type not in _SPATIAL_ROOT_TYPES

        if is_orphan:
            band, score, status = "Medium", 0.5, "FAIL"
            action = (
                f"{ifc_type} '{label}' has no spatial containment, connection, or "
                "material relationship anywhere in the model; verify placement and "
                "connectivity"
            )
        else:
            band, score, status, action = "Low", 0.0, "PASS", "Compliant"

        return RuleEvaluationResult(
            rule_type=self.rule_type,
            band=band,
            score=score,
            details={
                "check_type": "orphan_element",
                "label": label,
                "ifc_type": ifc_type,
                "degree": degree,
                "passes": not is_orphan,
                "code_reference": "GRAPH-TOPOLOGY-001",
            },
            status=status,
            element_id=guid,
            action=action,
        )
