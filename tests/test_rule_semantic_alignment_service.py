"""Unit tests for app.services.rule_semantic_alignment_service."""

from app.modules.contracts import BSDDClassItem, BSDDPropertyItem, RuleCreateRequest
from app.services.rule_semantic_alignment_service import RuleSemanticAlignmentService


def _class(code: str) -> BSDDClassItem:
    return BSDDClassItem(uri=f"https://x/class/{code}", code=code, name=code, dictionary_uri="https://x")


def _prop(name: str) -> BSDDPropertyItem:
    return BSDDPropertyItem(uri=f"https://x/prop/{name}", name=name)


class FakeBsddRepo:
    """Minimal stand-in exposing only the lookups RuleSemanticAlignmentService calls."""

    def __init__(
        self,
        *,
        classes: list[str] = (),
        property_names: frozenset[str] = frozenset(),
        pset_members: dict[str, frozenset[str]] | None = None,
        classes_for_property_result: list[str] = (),
    ) -> None:
        self._classes = list(classes)
        self._property_names = property_names
        self._pset_members = pset_members or {}
        self._classes_for_property_result = list(classes_for_property_result)

    def search_classes(self, query: str, limit: int = 10):
        lowered = query.strip().lower()
        return [_class(c) for c in self._classes if lowered in c.lower()][:limit]

    def known_property_names(self) -> frozenset[str]:
        return self._property_names

    def search_properties(self, query: str, limit: int = 8):
        lowered = query.strip().lower()
        return [_prop(n) for n in self._property_names if lowered in n.lower()][:limit]

    def known_property_set_members(self) -> dict[str, frozenset[str]]:
        return self._pset_members

    def classes_for_property(self, property_name: str, limit: int = 20):
        return [_class(c) for c in self._classes_for_property_result][:limit]


class FakeRuleService:
    def __init__(self, rows: list[dict] | None = None) -> None:
        self._rows = rows or []

    def rows_for_ruleset(self, ruleset_id: str) -> list[dict]:
        return self._rows


def _service(**bsdd_kwargs) -> RuleSemanticAlignmentService:
    return RuleSemanticAlignmentService(bsdd_repo=FakeBsddRepo(**bsdd_kwargs), rule_service=FakeRuleService())


# ── validate_class_and_property ─────────────────────────────────────────────


def test_unknown_target_ifc_class_is_blocking():
    service = _service(classes=["IfcDoor", "IfcWall"])

    issues = service.validate_class_and_property("IfcBanana", None, None)

    assert len(issues) == 1
    assert issues[0].field == "target_ifc_class"
    assert issues[0].severity == "blocking"


def test_known_target_ifc_class_raises_no_issue():
    service = _service(classes=["IfcDoor", "IfcWall"])

    issues = service.validate_class_and_property("IfcDoor", None, None)

    assert issues == []


def test_unknown_property_name_is_a_non_blocking_warning():
    service = _service(classes=["IfcDoor"], property_names=frozenset({"overallwidth"}))

    issues = service.validate_class_and_property("IfcDoor", None, "SomeMadeUpProperty")

    assert len(issues) == 1
    assert issues[0].field == "property_name"
    assert issues[0].severity == "warning"


def test_property_set_mismatch_is_a_warning():
    service = _service(
        classes=["IfcDoor"],
        property_names=frozenset({"firerating"}),
        # Pset_DoorCommon is known to bSDD, but not as containing FireRating.
        pset_members={"pset_doorcommon": frozenset({"someotherproperty"})},
    )

    issues = service.validate_class_and_property("IfcDoor", "Pset_DoorCommon", "FireRating")

    assert any(i.field == "property_set" and i.severity == "warning" for i in issues)


def test_property_set_match_raises_no_pset_issue():
    service = _service(
        classes=["IfcDoor"],
        property_names=frozenset({"firerating"}),
        pset_members={"pset_doorcommon": frozenset({"firerating"})},
    )

    issues = service.validate_class_and_property("IfcDoor", "Pset_DoorCommon", "FireRating")

    assert not any(i.field == "property_set" for i in issues)


def test_class_property_cross_check_flags_mismatch():
    service = _service(
        classes=["IfcDoor", "IfcStairFlight"],
        property_names=frozenset({"treadlength"}),
        classes_for_property_result=["IfcStairFlight"],
    )

    issues = service.validate_class_and_property("IfcDoor", None, "TreadLength")

    assert any(i.field == "property_name" and "IfcStairFlight" in i.message for i in issues)


def test_class_property_cross_check_silent_when_bsdd_has_no_opinion():
    service = _service(
        classes=["IfcDoor"],
        property_names=frozenset({"customprop"}),
        classes_for_property_result=[],
    )

    issues = service.validate_class_and_property("IfcDoor", None, "CustomProp")

    assert issues == []


def test_blocks_promotion_true_only_with_a_blocking_issue():
    service = _service(classes=["IfcDoor"], property_names=frozenset({"overallwidth"}))

    blocked = service.validate_class_and_property("IfcBanana", None, None)
    warned = service.validate_class_and_property("IfcDoor", None, "Unknown")

    from app.services.rule_semantic_alignment_service import AlignmentResult

    assert AlignmentResult(issues=blocked).blocks_promotion is True
    assert AlignmentResult(issues=warned).blocks_promotion is False


# ── detect_conflicts ─────────────────────────────────────────────────────────


def _rule(rule_id: str, **overrides) -> RuleCreateRequest:
    base = dict(
        rule_id=rule_id,
        target_ifc_class="IfcDoor",
        property_name="OverallWidth",
        operator=">=",
        check_value="900",
    )
    base.update(overrides)
    return RuleCreateRequest(**base)


def test_detect_conflicts_flags_infeasible_overlapping_ranges():
    service = _service()
    candidate = _rule("NEW-1", operator=">=", check_value="900")
    existing = [
        {
            "id": 7,
            "rule_id": "OLD-1",
            "reference": "OLD-1",
            "target_ifc_class": "IfcDoor",
            "property_name": "OverallWidth",
            "operator": "<=",
            "check_value": "800",
        }
    ]

    conflicts = service.detect_conflicts(candidate, existing)

    assert len(conflicts) == 1
    assert conflicts[0].conflicting_rule_id == 7


def test_detect_conflicts_ignores_different_target_or_property():
    service = _service()
    candidate = _rule("NEW-1", operator=">=", check_value="900")
    existing = [
        {"id": 1, "target_ifc_class": "IfcWindow", "property_name": "OverallWidth", "operator": "<=", "check_value": "800"},
        {"id": 2, "target_ifc_class": "IfcDoor", "property_name": "OverallHeight", "operator": "<=", "check_value": "800"},
    ]

    assert service.detect_conflicts(candidate, existing) == []


def test_detect_conflicts_ignores_compatible_ranges():
    service = _service()
    candidate = _rule("NEW-1", operator=">=", check_value="900")
    existing = [
        {"id": 1, "target_ifc_class": "IfcDoor", "property_name": "OverallWidth", "operator": ">=", "check_value": "800"}
    ]

    assert service.detect_conflicts(candidate, existing) == []


def test_detect_conflicts_skips_a_rule_that_is_a_declared_exception():
    service = _service()
    candidate = _rule("NEW-1", operator=">=", check_value="900")
    existing = [
        {
            "id": 7,
            "rule_id": "OLD-1",
            "reference": "OLD-1",
            "target_ifc_class": "IfcDoor",
            "property_name": "OverallWidth",
            "operator": "<=",
            "check_value": "800",
            "exceptions": '[{"reference": "NEW-1", "predicate": {}}]',
        }
    ]

    assert service.detect_conflicts(candidate, existing) == []


def test_detect_conflicts_skips_non_range_operators():
    service = _service()
    candidate = _rule("NEW-1", operator="exists", check_value=None)
    existing = [
        {"id": 1, "target_ifc_class": "IfcDoor", "property_name": "OverallWidth", "operator": "<=", "check_value": "800"}
    ]

    assert service.detect_conflicts(candidate, existing) == []


def test_check_skips_conflict_detection_without_ruleset_id():
    service = _service()
    candidate = _rule("NEW-1", operator=">=", check_value="900", ruleset_id=None)

    result = service.check(candidate)

    assert result.conflicts == []
