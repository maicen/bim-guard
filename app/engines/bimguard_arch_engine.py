"""BIMGUARD AI — Architectural Compliance Compute Engines.

Implements the RuleEvaluator protocol directly for complex architectural,
topological circulation, and spatial daylighting evaluations that buildingSMART IDS
cannot express.

Engines:
1. EgressAnalysisEngine (ARCH-EGRESS-001):
   NetworkX space-connectivity graph egress travel distance & storey exit counts.
2. SpatialDaylightEngine (ARCH-SPATIAL-001):
   IfcRelSpaceBoundary spatial daylighting window glazing-to-floor area ratios.
"""

from __future__ import annotations

from typing import Any

from app.logging_config import get_logger
from app.modules.contracts import RuleEvaluationRequest, RuleEvaluationResult
from app.modules.comparator.engine_registry import RuleEvaluationContext, RuleEvaluator
from app.services.rules_service import RuleService

logger = get_logger(__name__)


class EgressAnalysisEngine(RuleEvaluator):
    """Egress travel distance and exit count evaluation engine conforming to RuleEvaluator."""

    def __init__(self, *, rules_service: RuleService | None = None) -> None:
        """Initialize with optional rules_service dependency."""
        self.rule_type = "ARCH-EGRESS-001"
        self._rules_service = rules_service

    def _get_max_travel_distance(self) -> float | None:
        """Resolve maximum permissible travel distance from DB rules.

        None means no BUILDING-CODE-PART9 rule is configured for reference
        9.9.10.1 -- evaluate() must treat that as NOT_ASSESSED, not silently
        check against a residential-default distance.
        """
        try:
            svc = self._rules_service or RuleService()
            for r in svc.list_by_ruleset("BUILDING-CODE-PART9"):
                if "9.9.10.1" in str(r.get("reference") or ""):
                    val = r.get("check_value")
                    if val is not None:
                        return float(val)
        except Exception:
            pass
        return None

    def _get_min_exits_per_floor(self) -> int | None:
        """Resolve minimum required exits per storey from DB rules.

        None means no BUILDING-CODE-PART9 rule is configured for reference
        9.9.4.1 -- evaluate() must treat that as NOT_ASSESSED, not silently
        check against a residential-default count.
        """
        try:
            svc = self._rules_service or RuleService()
            for r in svc.list_by_ruleset("BUILDING-CODE-PART9"):
                if "9.9.4.1" in str(r.get("reference") or ""):
                    val = r.get("check_value")
                    if val is not None:
                        return int(float(val))
        except Exception:
            pass
        return None

    def evaluate(
        self,
        element: Any,
        *,
        context: RuleEvaluationContext | RuleEvaluationRequest | None = None,
    ) -> RuleEvaluationResult:
        """Evaluate an egress check candidate (space or storey record) against building code limits."""
        data = element if isinstance(element, dict) else getattr(element, "__dict__", {})
        max_dist = self._get_max_travel_distance()
        min_exits = self._get_min_exits_per_floor()

        guid = str(data.get("space_guid") or data.get("guid") or data.get("id") or "UNKNOWN")
        space_name = str(data.get("space_name") or data.get("name") or "Unnamed Space")
        storey_name = str(data.get("storey_name") or data.get("storey") or "—")

        # Check if evaluating an exit count record
        if "exit_count" in data:
            count = int(data.get("exit_count", 0))
            if min_exits is None:
                return RuleEvaluationResult(
                    rule_type=self.rule_type,
                    band=None,
                    score=0.0,
                    details={
                        "check_type": "exit_count",
                        "storey": storey_name,
                        "exit_count": count,
                        "required_min": None,
                        "passes": None,
                        "code_reference": "CODE 9.9.4.1",
                    },
                    status="NOT_ASSESSED",
                    element_id=guid,
                    action="No rule was found for minimum exits per storey",
                )
            passes = count >= min_exits
            band = "Low" if passes else "High"
            score = 0.0 if passes else 0.8
            status = "PASS" if passes else "FAIL"
            return RuleEvaluationResult(
                rule_type=self.rule_type,
                band=band,
                score=score,
                details={
                    "check_type": "exit_count",
                    "storey": storey_name,
                    "exit_count": count,
                    "required_min": min_exits,
                    "passes": passes,
                    "code_reference": "CODE 9.9.4.1",
                },
                status=status,
                element_id=guid,
                action="Provide at least one compliant exterior exit" if not passes else "Compliant",
            )

        # Evaluating a travel distance record
        travel_m = data.get("travel_distance_m")
        no_path = bool(data.get("no_path", False)) or travel_m is None

        if max_dist is None:
            return RuleEvaluationResult(
                rule_type=self.rule_type,
                band=None,
                score=0.0,
                details={
                    "check_type": "travel_distance",
                    "space_name": space_name,
                    "storey": storey_name,
                    "travel_distance_m": travel_m,
                    "required_max_m": None,
                    "nearest_exit": data.get("nearest_exit"),
                    "no_path": no_path,
                    "passes": None,
                    "code_reference": "CODE 9.9.10.1",
                },
                status="NOT_ASSESSED",
                element_id=guid,
                action="No rule was found for maximum egress travel distance",
            )
        elif no_path:
            passes = False
            band = "Critical"
            score = 1.0
            status = "FAIL"
            action = "No path from space to exterior exit; verify door boundaries and egress corridors"
        else:
            travel_val = float(travel_m)
            passes = travel_val <= max_dist
            if passes:
                band = "Low"
                score = round(travel_val / max_dist * 0.25, 3)
                status = "PASS"
                action = "Compliant"
            else:
                band = "High"
                score = round(min(1.0, 0.5 + (travel_val - max_dist) / max_dist), 3)
                status = "FAIL"
                action = f"Travel distance ({travel_val:.1f} m) exceeds maximum allowable limit ({max_dist:.1f} m)"

        return RuleEvaluationResult(
            rule_type=self.rule_type,
            band=band,
            score=score,
            details={
                "check_type": "travel_distance",
                "space_name": space_name,
                "storey": storey_name,
                "travel_distance_m": travel_m,
                "required_max_m": max_dist,
                "nearest_exit": data.get("nearest_exit"),
                "no_path": no_path,
                "passes": passes,
                "code_reference": "CODE 9.9.10.1",
            },
            status=status,
            element_id=guid,
            action=action,
        )


class SpatialDaylightEngine(RuleEvaluator):
    """Spatial daylighting and boundary evaluation engine conforming to RuleEvaluator."""

    def __init__(self, *, rules_service: RuleService | None = None) -> None:
        """Initialize with optional rules_service dependency."""
        self.rule_type = "ARCH-SPATIAL-001"
        self._rules_service = rules_service

    def _get_min_daylight_ratio(self) -> float | None:
        """Resolve minimum daylight ratio from DB rules.

        None means no BUILDING-CODE-PART9 rule is configured for reference
        9.7.2.3 -- evaluate() must treat that as NOT_ASSESSED, not silently
        check against a residential-default ratio.
        """
        try:
            svc = self._rules_service or RuleService()
            for r in svc.list_by_ruleset("BUILDING-CODE-PART9"):
                ref = str(r.get("reference") or "")
                prop = str(r.get("property_name") or "")
                unit = str(r.get("unit") or "").lower()
                if "9.7.2.3" in ref or prop == "DaylightRatio" or (unit == "ratio" and "9.7.2" in ref):
                    val = r.get("check_value")
                    if val is not None and 0.0 < float(val) <= 1.0:
                        return float(val)
        except Exception:
            pass
        return None

    def _get_min_fire_rating(self) -> float | None:
        """Resolve party-wall fire separation rating from DB rules.

        None means no BUILDING-CODE-PART9 rule is configured for reference
        9.10.9 on IfcWall -- evaluate() must treat that as NOT_ASSESSED, not
        silently check against a residential-default rating.
        """
        try:
            svc = self._rules_service or RuleService()
            for r in svc.list_by_ruleset("BUILDING-CODE-PART9"):
                if "9.10.9" in str(r.get("reference") or "") and str(r.get("target_ifc_class") or "") == "IfcWall":
                    val = r.get("check_value")
                    if val is not None and float(val) > 1.0:
                        return float(val)
        except Exception:
            pass
        return None

    def evaluate(
        self,
        element: Any,
        *,
        context: RuleEvaluationContext | RuleEvaluationRequest | None = None,
    ) -> RuleEvaluationResult:
        """Evaluate a spatial daylight or party-wall record against building code limits."""
        data = element if isinstance(element, dict) else getattr(element, "__dict__", {})
        min_ratio = self._get_min_daylight_ratio()
        min_fire = self._get_min_fire_rating()

        guid = str(data.get("space_guid") or data.get("wall_guid") or data.get("guid") or "UNKNOWN")

        # Check if evaluating party wall fire separation
        if "fire_rating_min" in data or "wall_guid" in data:
            wall_name = str(data.get("wall_name") or "Unnamed Party Wall")
            numeric_rating = data.get("fire_rating_min")
            missing = data.get("missing_rating") or numeric_rating is None

            if missing:
                passes = False
                band = "High"
                score = 0.75
                status = "FAIL"
                action = "Declare FireRating property on party wall"
            elif min_fire is None:
                passes = None
                band = None
                score = 0.0
                status = "NOT_ASSESSED"
                action = "No rule was found for party-wall fire rating"
            else:
                rating_val = float(numeric_rating)
                passes = rating_val >= min_fire
                band = "Low" if passes else "High"
                score = 0.0 if passes else 0.75
                status = "PASS" if passes else "FAIL"
                action = "Compliant" if passes else f"Party wall fire rating ({rating_val} min) below {min_fire} min"

            return RuleEvaluationResult(
                rule_type=self.rule_type,
                band=band,
                score=score,
                details={
                    "check_type": "fire_separation",
                    "wall_name": wall_name,
                    "adjacent_spaces": data.get("adjacent_spaces", []),
                    "fire_rating_min": numeric_rating,
                    "required_min": min_fire,
                    "missing_rating": missing,
                    "passes": passes,
                    "code_reference": "CODE 9.10.9",
                },
                status=status,
                element_id=guid,
                action=action,
            )

        # Evaluating daylight ratio
        space_name = str(data.get("space_name") or "Unnamed Space")
        storey_name = str(data.get("storey_name") or "—")
        floor_area = float(data.get("floor_area_m2") or 0.0)
        window_area = float(data.get("total_window_area_m2") or 0.0)

        ratio = (window_area / floor_area) if floor_area > 0 else float(data.get("daylight_ratio") or 0.0)

        if min_ratio is None:
            passes = None
            band = None
            score = 0.0
            status = "NOT_ASSESSED"
            action = "No rule was found for daylight ratio"
        else:
            passes = ratio >= min_ratio
            if passes:
                band = "Low"
                score = 0.1
                status = "PASS"
                action = "Compliant"
            else:
                band = "Medium"
                score = round(min(1.0, 0.4 + (min_ratio - ratio) * 5), 3)
                status = "FAIL"
                action = f"Daylight ratio ({ratio:.3f}) below required minimum 1/{int(round(1 / min_ratio))} ({min_ratio:.2f})"

        return RuleEvaluationResult(
            rule_type=self.rule_type,
            band=band,
            score=score,
            details={
                "check_type": "daylight_ratio",
                "space_name": space_name,
                "storey": storey_name,
                "floor_area_m2": floor_area,
                "total_window_area_m2": window_area,
                "daylight_ratio": round(ratio, 4),
                "required_ratio": min_ratio,
                "passes": passes,
                "code_reference": "CODE 9.7.2",
            },
            status=status,
            element_id=guid,
            action=action,
        )
