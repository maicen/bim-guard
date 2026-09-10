"""BIMGUARD AI — SHACL-based semantic compliance engine.

Implements the RuleEvaluator protocol for DB-authored rules that are more
naturally expressed as W3C SHACL shapes (`app.modules.rule_builder.shacl_generator`)
run against a BOT graph (`app.modules.ifc_reader.bot_graph`) than as the
existing per-element operator/threshold comparator path. This is the
"hybrid" bridge from the ontology-integration proposal: geometry stays
computed by the existing pure-Python engines (`ifc_geometry.py`,
`ifc_egress.py`, `ifc_stair.py`, `blue_halo/`) and is written onto the graph
as literals (`bot_graph.enrich_literal`); this engine only validates the
resulting graph.

Unlike the single-element engines in `bimguard_arch_engine.py`, `element`
here is the whole model's BOT data graph -- SHACL validates a graph, not one
element at a time -- matching the whole-graph style `EgressAnalysisEngine`
already uses for building-wide checks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pyshacl import validate as pyshacl_validate
from rdflib import Graph

from app.logging_config import get_logger
from app.modules.comparator.engine_registry import RuleEvaluationContext, RuleEvaluator
from app.modules.contracts import RuleEvaluationRequest, RuleEvaluationResult
from app.modules.rule_builder.shacl_generator import compile_shapes

if TYPE_CHECKING:
    from app.services.rules_service import RuleService

logger = get_logger(__name__)


class ShaclComplianceEngine(RuleEvaluator):
    """Validates a BOT data graph against DB-compiled SHACL shapes."""

    def __init__(self, *, rules_service: RuleService | None = None) -> None:
        self.rule_type = "CODE-SHACL"
        self._rules_service = rules_service

    def compile_shapes_for_ruleset(self, ruleset_id: str) -> Graph:
        """Compile every SHACL-eligible rule in a ruleset into a shapes graph."""
        from app.services.rules_service import RuleService

        svc = self._rules_service or RuleService()
        rules = svc.list_by_ruleset(ruleset_id)
        return compile_shapes(rules)

    def evaluate(
        self,
        element: Any,
        *,
        context: RuleEvaluationContext | RuleEvaluationRequest | None = None,
    ) -> RuleEvaluationResult:
        """Validate `element` (a BOT `rdflib.Graph`) against SHACL shapes.

        `context.metadata` (or `context` itself when a `RuleEvaluationRequest`)
        may carry a precompiled `shapes_graph`, or a `ruleset_id` to compile
        one from the DB. Neither present means there is nothing to check --
        that is NOT_ASSESSED, never a silent PASS.
        """
        data_graph = element
        metadata: dict = {}
        if isinstance(context, (RuleEvaluationRequest, RuleEvaluationContext)):
            metadata = context.metadata or {}

        shapes_graph = metadata.get("shapes_graph")
        ruleset_id = metadata.get("ruleset_id")

        if shapes_graph is None:
            if not ruleset_id:
                return RuleEvaluationResult(
                    rule_type=self.rule_type,
                    status="NOT_ASSESSED",
                    details={"reason": "No shapes_graph or ruleset_id supplied"},
                    action="Provide a compiled SHACL shapes graph or a ruleset_id to compile one",
                )
            shapes_graph = self.compile_shapes_for_ruleset(ruleset_id)

        if len(shapes_graph) == 0:
            return RuleEvaluationResult(
                rule_type=self.rule_type,
                status="NOT_ASSESSED",
                details={"reason": "No SHACL-eligible rules compiled for this ruleset", "ruleset_id": ruleset_id},
                action="No rule in this ruleset compiles to a SHACL shape",
            )

        conforms, results_graph, results_text = pyshacl_validate(
            data_graph,
            shacl_graph=shapes_graph,
            advanced=True,
            inference="none",
        )

        return RuleEvaluationResult(
            rule_type=self.rule_type,
            status="PASS" if conforms else "FAIL",
            band=None if conforms else "High",
            score=0.0 if conforms else 1.0,
            details={"conforms": conforms, "results_text": results_text, "ruleset_id": ruleset_id},
            raw_result=results_graph,
        )
