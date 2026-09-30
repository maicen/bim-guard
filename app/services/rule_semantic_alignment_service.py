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

from typing import Any, Literal, Optional

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
    """A rule or draft whose constraint is jointly unsatisfiable or in discrepancy with candidate's."""

    conflicting_rule_id: Optional[int] = None
    conflicting_draft_id: Optional[int] = None
    conflicting_reference: str
    conflict_type: Literal[
        "mutually_exclusive_range",
        "threshold_mismatch",
        "exact_value_mismatch",
        "scope_precedence_clash",
    ] = "mutually_exclusive_range"
    severity: Literal["critical", "warning", "caution"] = "warning"
    message: str
    resolution_suggestion: Optional[str] = None
    conflicting_details: Optional[dict[str, Any]] = None


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

    def detect_pair_conflict(
        self,
        candidate: dict[str, Any],
        other: dict[str, Any],
        *,
        include_threshold_discrepancies: bool = True,
    ) -> ConflictWarning | None:
        """Compare two rules or drafts and return a ConflictWarning if contradictory, else None.

        Rules in different rulesets never conflict: each ruleset is an
        independent standard, and a project is checked against only the
        ruleset selected for it.
        """
        if RuleService.normalize_ruleset_id(candidate.get("ruleset_id")) != RuleService.normalize_ruleset_id(
            other.get("ruleset_id")
        ):
            return None

        target_a = _normalize(candidate.get("target_ifc_class"))
        target_b = _normalize(other.get("target_ifc_class"))
        if not target_a or not target_b or target_a != target_b:
            return None

        prop_a = _normalize(candidate.get("property_name"))
        prop_b = _normalize(other.get("property_name"))
        if not prop_a or not prop_b or prop_a != prop_b:
            return None

        cand_id_str = str(candidate.get("rule_id") or candidate.get("id") or "")
        other_ref = str(other.get("reference") or other.get("rule_id") or other.get("id") or "")
        if _references_other(other, cand_id_str) or _references_other(candidate, other_ref):
            return None

        if not _scopes_can_overlap(candidate.get("applies_when"), other.get("applies_when")):
            return None

        other_rule_id = int(other.get("id") or 0) if not other.get("is_draft") else None
        other_draft_id = int(other.get("id") or 0) if other.get("is_draft") else None

        bounds_a = _bounds(candidate)
        bounds_b = _bounds(other)

        # 1. Numeric bounds check
        if bounds_a is not None and bounds_b is not None:
            if not _ranges_intersect(bounds_a, bounds_b):
                val_a = candidate.get("check_value") or (candidate.get("value_min"), candidate.get("value_max"))
                val_b = other.get("check_value") or (other.get("value_min"), other.get("value_max"))
                return ConflictWarning(
                    conflicting_rule_id=other_rule_id,
                    conflicting_draft_id=other_draft_id,
                    conflicting_reference=other_ref,
                    conflict_type="mutually_exclusive_range",
                    severity="critical",
                    message=(
                        f"{cand_id_str!r} requires {candidate.get('operator')} {val_a} on "
                        f"{candidate.get('target_ifc_class')}.{candidate.get('property_name')}, which cannot "
                        f"both hold with {other_ref!r}'s {other.get('operator')} {val_b}."
                    ),
                    resolution_suggestion=(
                        "Ranges are mutually exclusive and cannot be jointly satisfied. "
                        "Determine which code standard has legal precedence or scope one rule to an exception."
                    ),
                    conflicting_details={
                        "candidate_operator": str(candidate.get("operator") or ""),
                        "candidate_value": val_a,
                        "conflicting_operator": str(other.get("operator") or ""),
                        "conflicting_value": val_b,
                    },
                )
            elif include_threshold_discrepancies:
                op_a = str(candidate.get("operator") or "")
                op_b = str(other.get("operator") or "")
                val_a = candidate.get("check_value")
                val_b = other.get("check_value")
                if op_a == op_b and op_a in (">=", ">", "<=", "<") and val_a is not None and val_b is not None:
                    try:
                        fa, fb = float(val_a), float(val_b)
                        if abs(fa - fb) > 1e-6:
                            stricter_val = max(fa, fb) if op_a in (">=", ">") else min(fa, fb)
                            return ConflictWarning(
                                conflicting_rule_id=other_rule_id,
                                conflicting_draft_id=other_draft_id,
                                conflicting_reference=other_ref,
                                conflict_type="threshold_mismatch",
                                severity="warning",
                                message=(
                                    f"{cand_id_str!r} requires {op_a} {val_a} on "
                                    f"{candidate.get('target_ifc_class')}.{candidate.get('property_name')}, "
                                    f"while {other_ref!r} specifies {op_b} {val_b}. "
                                    f"The stricter threshold ({op_a} {stricter_val}) will govern unless scoped."
                                ),
                                resolution_suggestion=(
                                    f"Align differing building code thresholds between {cand_id_str} and {other_ref}, "
                                    f"or specify an `applies_when` condition to distinguish occupancy types."
                                ),
                                conflicting_details={
                                    "candidate_operator": op_a,
                                    "candidate_value": val_a,
                                    "conflicting_operator": op_b,
                                    "conflicting_value": val_b,
                                    "stricter_value": stricter_val,
                                },
                            )
                    except (TypeError, ValueError):
                        pass

        # 2. Exact equality / boolean clash
        op_a = str(candidate.get("operator") or "")
        op_b = str(other.get("operator") or "")
        if op_a in ("==", "equals") and op_b in ("==", "equals"):
            val_a = str(candidate.get("check_value") or "").strip().lower()
            val_b = str(other.get("check_value") or "").strip().lower()
            if val_a and val_b and val_a != val_b:
                return ConflictWarning(
                    conflicting_rule_id=other_rule_id,
                    conflicting_draft_id=other_draft_id,
                    conflicting_reference=other_ref,
                    conflict_type="exact_value_mismatch",
                    severity="critical",
                    message=(
                        f"{cand_id_str!r} requires {candidate.get('target_ifc_class')}.{candidate.get('property_name')} "
                        f"== {val_a!r}, which directly contradicts {other_ref!r}'s requirement of {val_b!r}."
                    ),
                    resolution_suggestion="Ensure element properties are not assigned contradictory required values across specifications.",
                    conflicting_details={"candidate_value": val_a, "conflicting_value": val_b},
                )

        return None

    def detect_conflicts(
        self,
        candidate: RuleCreateRequest,
        existing_rules: list[dict[str, Any]],
        *,
        include_threshold_discrepancies: bool = False,
    ) -> list[ConflictWarning]:
        """Flag existing rules in the ruleset whose constraint cannot be jointly satisfied with `candidate`'s.

        Always advisory: a reviewer may be deliberately overriding an older
        rule, and only a formal `exceptions`/`rase_exception` link is treated
        as "not a conflict" -- everything else is surfaced for a human to
        judge, never auto-resolved or blocked.
        """
        candidate_dict = candidate.model_dump()
        conflicts: list[ConflictWarning] = []
        for raw_row in existing_rules:
            normalized_row = rule_row_to_shacl_input(raw_row)
            normalized_row["id"] = raw_row.get("id")
            normalized_row["is_draft"] = False
            warn = self.detect_pair_conflict(
                candidate_dict,
                normalized_row,
                include_threshold_discrepancies=include_threshold_discrepancies,
            )
            if warn is not None:
                conflicts.append(warn)
        return conflicts

    def detect_conflicts_batch(
        self,
        drafts: list[dict[str, Any]],
        existing_rules: list[dict[str, Any]] | None = None,
        *,
        include_threshold_discrepancies: bool = True,
    ) -> list[dict[str, Any]]:
        """Run cross-draft and draft-vs-rule conflict detection across a batch of drafts.

        Enriches each draft dict in `drafts` with a `conflicts` list of
        serialized `ConflictWarning` dicts.
        """
        normalized_existing: list[dict[str, Any]] = []
        if existing_rules:
            for r in existing_rules:
                row_norm = rule_row_to_shacl_input(r)
                row_norm["id"] = r.get("id")
                row_norm["is_draft"] = False
                normalized_existing.append(row_norm)

        candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for draft in drafts:
            rule_data = draft.get("proposed_rule") or draft
            if hasattr(rule_data, "model_dump"):
                rule_dict = rule_data.model_dump()
            elif isinstance(rule_data, dict):
                rule_dict = dict(rule_data)
            else:
                rule_dict = {}
            rule_dict["id"] = draft.get("id")
            rule_dict["rule_id"] = rule_dict.get("rule_id") or f"Draft-{draft.get('id')}"
            rule_dict["is_draft"] = True
            candidates.append((draft, rule_dict))

        for i, (draft_a, shape_a) in enumerate(candidates):
            conflicts: list[dict[str, Any]] = []

            # 1. Draft vs Draft
            for j, (_, shape_b) in enumerate(candidates):
                if i == j:
                    continue
                warn = self.detect_pair_conflict(
                    shape_a, shape_b, include_threshold_discrepancies=include_threshold_discrepancies
                )
                if warn is not None:
                    conflicts.append(warn.model_dump())

            # 2. Draft vs Existing Rules
            for ex in normalized_existing:
                warn = self.detect_pair_conflict(
                    shape_a, ex, include_threshold_discrepancies=include_threshold_discrepancies
                )
                if warn is not None:
                    conflicts.append(warn.model_dump())

            draft_a["conflicts"] = conflicts

        return drafts

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
