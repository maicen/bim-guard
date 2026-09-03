"""Rule engine registry for Module 4 comparator checks.

This keeps the compliance runner open for extension without hard-coding a new
conditional branch for every rule family. Each evaluator is registered under its
rule code (for example "GC-001") and resolved through an explicit evaluator
contract rather than an ad hoc callable assumption.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, runtime_checkable

from app.modules.contracts import RuleEvaluationRequest, RuleEvaluationResult


@dataclass(frozen=True)
class RuleEvaluationContext:
    """Explicit evaluation context passed to a rule evaluator."""

    rule_type: str
    element: Any
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class RuleEvaluator(Protocol):
    """Explicit Module 4 evaluator contract.

    Any evaluator registered in the registry must expose a stable rule type and
    an evaluate() method that accepts both the element and an optional context.
    """

    rule_type: str

    def evaluate(
        self,
        element: Any,
        *,
        context: RuleEvaluationContext | RuleEvaluationRequest | None = None,
    ) -> RuleEvaluationResult | dict[str, Any]:
        ...


class CallableRuleEvaluator:
    """Adapter that converts a legacy callable into the explicit rule contract."""

    def __init__(
        self,
        rule_type: str,
        evaluator: Callable[[Any], dict[str, Any] | RuleEvaluationResult],
    ) -> None:
        self.rule_type = str(rule_type)
        self._evaluator = evaluator

    def evaluate(
        self,
        element: Any,
        *,
        context: RuleEvaluationContext | RuleEvaluationRequest | None = None,
    ) -> RuleEvaluationResult | dict[str, Any]:
        return self._evaluator(element)


class RuleEngineRegistry:
    """Central registry for Module 4 rule engines."""

    def __init__(
        self,
        *,
        evaluators: dict[str, RuleEvaluator | Callable[[Any], dict[str, Any] | RuleEvaluationResult]]
        | None = None,
    ) -> None:
        self._evaluators: dict[str, RuleEvaluator] = {}
        if evaluators:
            for rule_type, evaluator in evaluators.items():
                self.register(rule_type, evaluator)

    def register(
        self,
        rule_type: str,
        evaluator: RuleEvaluator | Callable[[Any], dict[str, Any] | RuleEvaluationResult],
    ) -> RuleEvaluator:
        """Register an evaluator for a rule family using the explicit contract."""
        key = str(rule_type)

        if callable(evaluator) and not hasattr(evaluator, "evaluate"):
            wrapped = CallableRuleEvaluator(key, evaluator)
            self._evaluators[key] = wrapped
            return wrapped

        if hasattr(evaluator, "evaluate"):
            instance = evaluator
            try:
                instance.rule_type = key
            except Exception:
                pass
            self._evaluators[key] = instance
            return instance

        raise TypeError(f"Evaluator for '{rule_type}' does not implement the RuleEvaluator contract")

    def get(self, rule_type: str) -> RuleEvaluator:
        """Return the evaluator for a rule family."""
        try:
            return self._evaluators[str(rule_type)]
        except KeyError as exc:
            raise KeyError(f"No evaluator registered for rule type '{rule_type}'") from exc

    def supports(self, rule_type: str) -> bool:
        """Return True when a rule type is registered."""
        return str(rule_type) in self._evaluators

    def registered_rule_types(self) -> list[str]:
        """Return the registered rule codes in deterministic order."""
        return sorted(self._evaluators)

    def evaluate(
        self,
        rule_type: str,
        element: Any,
        *,
        context: RuleEvaluationContext | RuleEvaluationRequest | None = None,
    ) -> RuleEvaluationResult | dict[str, Any]:
        """Execute the evaluator for a rule family against one element."""
        evaluator = self.get(rule_type)
        effective_context = context or RuleEvaluationContext(
            rule_type=str(rule_type),
            element=element,
        )
        return evaluator.evaluate(element, context=effective_context)


DEFAULT_ENGINE_REGISTRY = RuleEngineRegistry()


def register_default_engines(registry: RuleEngineRegistry | None = None) -> RuleEngineRegistry:
    """Register the built-in corrosion and architectural engines directly into the registry.

    Directly registers GalvanicCorrosionEngine, CreviceCorrosionEngine,
    MICEngine, EgressAnalysisEngine, and SpatialDaylightEngine instances which
    implement the RuleEvaluator protocol directly.
    """
    target = registry or DEFAULT_ENGINE_REGISTRY
    from app.engines.bimguard_arch_engine import EgressAnalysisEngine, SpatialDaylightEngine
    from app.engines.bimguard_corrosion_engine import GalvanicCorrosionEngine
    from app.engines.bimguard_crevice_engine import CreviceCorrosionEngine
    from app.engines.bimguard_mic_engine import MICEngine

    target.register("GC-001", GalvanicCorrosionEngine())
    target.register("CC-001", CreviceCorrosionEngine())
    target.register("MC-001", MICEngine())
    target.register("ARCH-EGRESS-001", EgressAnalysisEngine())
    target.register("ARCH-SPATIAL-001", SpatialDaylightEngine())
    return target
