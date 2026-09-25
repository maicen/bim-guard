"""Ontology-informed semantic alignment for rules being promoted into `public.rules`.

Closes a gap between BIM-Guard's LLM-based extraction pipeline
(app.modules.rule_builder.llamaindex_rule_generator) and its ontology/SHACL
layer (app.modules.rule_builder.shacl_generator): nothing today validates
that a promoted rule's `target_ifc_class`/`property_name` are real ontology
terms, and nothing checks a newly promoted rule against the rules already in
its ruleset for a direct numeric contradiction. Both checks reuse
`BSDDOntologyRepository`'s existing local-first lookups (no new dependency,
no network call, no database round trip beyond the ruleset row read the
caller already has to do for duplicate-detection).

Informed by Zheng, Zhou, Lu & Lin (2022), "Knowledge-informed semantic
alignment and rule interpretation for automated compliance checking",
Automation in Construction 142.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from app.logging_config import get_logger
from app.modules.contracts import RuleCreateRequest
from app.modules.rule_builder.shacl_generator import rule_row_to_shacl_input
from app.services.bsdd_ontology_repository import (
    BSDDOntologyRepository,
    get_bsdd_ontology_repository,
)
from app.services.rules_service import RuleService

logger = get_logger(__name__)


def _normalize(value: Any) -> str:
    """Lower-case, letters-and-digits-only form used for tolerant name comparisons."""
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


class AlignmentIssue(BaseModel):
    """One ontology-vocabulary mismatch found on a rule's target class/property."""

    field: str  # "target_ifc_class" | "property_name" | "property_set"
    severity: str  # "blocking" | "warning"
    message: str
    suggestion: Optional[str] = None


class ConflictWarning(BaseModel):
    """A rule already in the ruleset whose constraint is jointly unsatisfiable with the candidate's."""

    conflicting_rule_id: int
    conflicting_reference: str
    message: str


class AlignmentResult(BaseModel):
    issues: list[AlignmentIssue] = []
    conflicts: list[ConflictWarning] = []

    @property
    def blocks_promotion(self) -> bool:
        return any(issue.severity == "blocking" for issue in self.issues)


#: Numeric-range operators `detect_conflicts` knows how to intersect. Anything
#: else (exists/matches/field_consistency/...) has no simple range semantics,
#: so a rule pair involving it is left alone rather than risk a wrong verdict.
_RANGE_OPERATORS = {">=", "<=", ">", "<", "==", "between"}


def _bounds(rule: dict[str, Any]) -> Optional[tuple[float, float]]:
    """Return the rule's feasible numeric range as (low, high), or None if not range-shaped."""
    operator = str(rule.get("operator") or "")
    if operator not in _RANGE_OPERATORS:
        return None
    try:
        if operator == "between":
            value_min = rule.get("value_min")
            value_max = rule.get("value_max")
            low = float(value_min) if value_min is not None else float("-inf")
            high = float(value_max) if value_max is not None else float("inf")
            return (low, high)
        check_value = float(rule.get("check_value"))
    except (TypeError, ValueError):
        return None
    if operator == ">=":
        return (check_value, float("inf"))
    if operator == ">":
        return (check_value + 1e-9, float("inf"))
    if operator == "<=":
        return (float("-inf"), check_value)
    if operator == "<":
        return (float("-inf"), check_value - 1e-9)
    if operator == "==":
        return (check_value, check_value)
    return None


def _ranges_intersect(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return a[0] <= b[1] and b[0] <= a[1]


def _references_other(rule: dict[str, Any], other_rule_id: str) -> bool:
    """Return True when `rule` names `other_rule_id` as a waiver/exception -- a deliberate override, not a conflict."""
    if not other_rule_id:
        return False
    for field in ("exceptions", "rase_exception"):
        value = rule.get(field)
        blob = str(value or "")
        if other_rule_id in blob:
            return True
    return False


def _scopes_can_overlap(a: dict[str, Any] | None, b: dict[str, Any] | None) -> bool:
    """Return True unless `a` and `b` (each an `applies_when` dict) are provably disjoint.

    Matches the "an unresolvable or absent scope predicate never narrows"
    semantics already established by app.modules.comparator and mirrored in
    app.modules.rule_builder.shacl_generator._apply_scope_target: only a
    shared key whose value *lists* share no element rules out overlap, since
    that is the one case both rules definitely disagree on which elements
    they cover.
    """
    if not a or not b:
        return True
    for key, values in a.items():
        if key in b and isinstance(values, list) and isinstance(b[key], list):
            if not (set(values) & set(b[key])):
                return False
    return True


class RuleSemanticAlignmentService:
    """Validates a candidate rule's ontology vocabulary and checks it for cross-rule conflicts.

    Keyword-only, optional constructor args each defaulting to a real
    instance when omitted (matches ModelsService.__init__'s established
    shape) -- this service is not container-managed, matching
    RuleDraftService, its only caller, which is instantiated per-request the
    same way.
    """

    def __init__(
        self,
        *,
        bsdd_repo: BSDDOntologyRepository | None = None,
        rule_service: RuleService | None = None,
    ) -> None:
        self._bsdd = bsdd_repo if bsdd_repo is not None else get_bsdd_ontology_repository()
        self._rule_service = rule_service if rule_service is not None else RuleService()

    # ── Ontology vocabulary validation ──────────────────────────────────────

    def validate_class_and_property(
        self,
        target_ifc_class: str | None,
        property_set: str | None,
        property_name: str | None,
    ) -> list[AlignmentIssue]:
        """Check `target_ifc_class`/`property_set`/`property_name` against the local bSDD ontology.

        Only an unrecognized `target_ifc_class` is blocking: bSDD's IFC
        dictionary is a closed, well-known entity vocabulary, so a class that
        matches nothing in it is almost certainly a typo or hallucination.
        Property/pset checks stay advisory -- plenty of legitimate
        project-specific Psets are never going to appear in bSDD.
        """
        issues: list[AlignmentIssue] = []

        target_ifc_class = (target_ifc_class or "").strip()
        if target_ifc_class:
            issues.extend(self._validate_class(target_ifc_class))

        property_name = (property_name or "").strip()
        property_set = (property_set or "").strip()
        if property_name:
            issues.extend(self._validate_property(target_ifc_class, property_set, property_name))

        return issues

    def _validate_class(self, target_ifc_class: str) -> list[AlignmentIssue]:
        hits = self._bsdd.search_classes(target_ifc_class, limit=5)
        exact = next((h for h in hits if _normalize(h.code) == _normalize(target_ifc_class)), None)
        if exact is not None:
            return []
        suggestion = hits[0].code if hits else None
        return [
            AlignmentIssue(
                field="target_ifc_class",
                severity="blocking",
                message=(
                    f"{target_ifc_class!r} does not match any known IFC entity in the bSDD ontology "
                    "-- likely a typo or hallucinated class name."
                ),
                suggestion=suggestion,
            )
        ]

    def _validate_property(
        self, target_ifc_class: str, property_set: str, property_name: str
    ) -> list[AlignmentIssue]:
        issues: list[AlignmentIssue] = []
        known_names = self._bsdd.known_property_names()
        normalized_property = _normalize(property_name)
        property_known = normalized_property in known_names

        if not property_known:
            suggestions = self._bsdd.search_properties(property_name, limit=1)
            issues.append(
                AlignmentIssue(
                    field="property_name",
                    severity="warning",
                    message=(
                        f"{property_name!r} is not a property bSDD knows about -- fine for a "
                        "legitimate custom Pset, but worth a second look."
                    ),
                    suggestion=suggestions[0].name if suggestions else None,
                )
            )

        if property_known and property_set:
            # known_property_set_members() keys are the raw (lower-cased) pset
            # name, not the alnum-only normalization used elsewhere here --
            # match that exactly rather than re-normalizing the key away.
            pset_members = self._bsdd.known_property_set_members().get(property_set.strip().lower())
            if pset_members is not None and normalized_property not in pset_members:
                issues.append(
                    AlignmentIssue(
                        field="property_set",
                        severity="warning",
                        message=(
                            f"bSDD does not list {property_name!r} as a member of {property_set!r} "
                            "-- double-check the property set."
                        ),
                    )
                )

        if property_known and target_ifc_class:
            classes = self._bsdd.classes_for_property(property_name)
            if classes and not any(_normalize(c.code) == _normalize(target_ifc_class) for c in classes):
                issues.append(
                    AlignmentIssue(
                        field="property_name",
                        severity="warning",
                        message=(
                            f"bSDD associates {property_name!r} with "
                            f"{', '.join(c.code for c in classes[:3])}, not {target_ifc_class!r} "
                            "-- possible class/property mismatch."
                        ),
                    )
                )

        return issues

    # ── Cross-rule conflict detection ───────────────────────────────────────

    def detect_conflicts(
        self, candidate: RuleCreateRequest, existing_rules: list[dict[str, Any]]
    ) -> list[ConflictWarning]:
        """Flag existing rules in the ruleset whose constraint cannot be jointly satisfied with `candidate`'s.

        Always advisory: a reviewer may be deliberately overriding an older
        rule, and only a formal `exceptions`/`rase_exception` link is treated
        as "not a conflict" -- everything else is surfaced for a human to
        judge, never auto-resolved or blocked.

        `existing_rules` are raw `rules` table rows, not `RuleCreateRequest`
        shapes -- normalized through `rule_row_to_shacl_input` (the same
        decode `shacl_generator` uses) since `check_value`/`value_min`/
        `value_max`/`applies_when` are stored JSON-encoded as TEXT.
        """
        existing_rules = [rule_row_to_shacl_input(row) for row in existing_rules]
        candidate_bounds = _bounds(candidate.model_dump())
        if candidate_bounds is None:
            return []

        candidate_target = _normalize(candidate.target_ifc_class)
        candidate_property = _normalize(candidate.property_name)
        candidate_scope = candidate.applies_when

        conflicts: list[ConflictWarning] = []
        for row in existing_rules:
            if _normalize(row.get("target_ifc_class")) != candidate_target:
                continue
            if _normalize(row.get("property_name")) != candidate_property:
                continue

            other_bounds = _bounds(row)
            if other_bounds is None:
                continue
            if _ranges_intersect(candidate_bounds, other_bounds):
                continue

            other_reference = str(row.get("reference") or row.get("rule_id") or "")
            if _references_other(row, candidate.rule_id) or _references_other(
                candidate.model_dump(), other_reference
            ):
                continue
            if not _scopes_can_overlap(candidate_scope, row.get("applies_when")):
                continue

            conflicts.append(
                ConflictWarning(
                    conflicting_rule_id=int(row.get("id") or 0),
                    conflicting_reference=other_reference,
                    message=(
                        f"{candidate.rule_id!r} requires {candidate.operator} "
                        f"{candidate.check_value or (candidate.value_min, candidate.value_max)} on "
                        f"{candidate.target_ifc_class}.{candidate.property_name}, which cannot "
                        f"both hold with {other_reference!r}'s {row.get('operator')} "
                        f"{row.get('check_value') or (row.get('value_min'), row.get('value_max'))}."
                    ),
                )
            )

        return conflicts

    def check(self, candidate: RuleCreateRequest) -> AlignmentResult:
        """Run both checks for a candidate about to be promoted."""
        issues = self.validate_class_and_property(
            candidate.target_ifc_class, candidate.property_set, candidate.property_name
        )
        conflicts: list[ConflictWarning] = []
        ruleset_id = (candidate.ruleset_id or "").strip()
        if ruleset_id:
            existing_rules = self._rule_service.rows_for_ruleset(ruleset_id)
            conflicts = self.detect_conflicts(candidate, existing_rules)
        return AlignmentResult(issues=issues, conflicts=conflicts)
