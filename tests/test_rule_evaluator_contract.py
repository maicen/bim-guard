import pytest

from app.modules.comparator.engine_registry import RuleEngineRegistry


class DummyRuleEvaluator:
    rule_type = "GC-001"

    def evaluate(self, element, *, context=None):
        return {"rule_type": self.rule_type, "element": element["id"], "context": context.rule_type if context else None}


def test_rule_registry_uses_explicit_evaluator_contract():
    registry = RuleEngineRegistry()
    evaluator = DummyRuleEvaluator()

    registry.register("GC-001", evaluator)

    assert registry.get("GC-001").rule_type == "GC-001"
    assert registry.evaluate("GC-001", {"id": "E-1"}) == {
        "rule_type": "GC-001",
        "element": "E-1",
        "context": "GC-001",
    }

    with pytest.raises(KeyError):
        registry.get("MC-001")
