"""Rule engine registry for Module 4 comparator checks.

This keeps the compliance runner open for extension without hard-coding a new
conditional branch for every rule family. Each evaluator is registered under its
rule code (for example "GC-001") and can be resolved by the orchestrator or
future rule families.
"""

from __future__ import annotations

from typing import Any, Protocol


class RuleEvaluator(Protocol):
    """Callable protocol for a Module 4 evaluator.

    The returned payload is the same shape returned by the runner helpers used by
    the current compliance pipeline.
    """

    def __call__(self, element: Any) -> dict[str, Any]:
        ...


class RuleEngineRegistry:
    """Central registry for Module 4 rule engines."""

    def __init__(self, *, evaluators: dict[str, RuleEvaluator] | None = None) -> None:
        self._evaluators: dict[str, RuleEvaluator] = {}
        if evaluators:
            for rule_type, evaluator in evaluators.items():
                self.register(rule_type, evaluator)

    def register(self, rule_type: str, evaluator: RuleEvaluator) -> None:
        """Register a callable evaluator for a rule family."""
        self._evaluators[str(rule_type)] = evaluator

    def get(self, rule_type: str) -> RuleEvaluator:
        """Return the evaluator for a rule family."""
        try:
            return self._evaluators[str(rule_type)]
        except KeyError as exc:
            raise KeyError(f"No evaluator registered for rule type '{rule_type}'") from exc

    def registered_rule_types(self) -> list[str]:
        """Return the registered rule codes in deterministic order."""
        return sorted(self._evaluators)

    def evaluate(self, rule_type: str, element: Any) -> dict[str, Any]:
        """Execute the evaluator for a rule family against one element."""
        return self.get(rule_type)(element)


DEFAULT_ENGINE_REGISTRY = RuleEngineRegistry()


def register_default_engines(registry: RuleEngineRegistry | None = None) -> RuleEngineRegistry:
    """Register the built-in Module 4 engine functions into the default registry.

    This is intentionally deferred until the runner module has finished defining
    the evaluator functions, avoiding circular import issues during package load.
    """
    target = registry or DEFAULT_ENGINE_REGISTRY
    from app.modules.module4_comparator.compliance_runner import (
        run_crevice_compliance_check,
        run_galvanic_compliance_check,
        run_mic_compliance_check,
    )

    target.register("GC-001", run_galvanic_compliance_check)
    target.register("CC-001", run_crevice_compliance_check)
    target.register("MC-001", run_mic_compliance_check)
    return target
