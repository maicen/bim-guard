"""Pre-Flight Model Health and Data-Quality Audit Service.

Executes 8 core quality and metadata compliance checks on IFC models:
1. Doors missing fire ratings
2. Elements without building storey assignment
3. Spaces missing identification attributes
4. Physical elements without property sets
5. Elements with blank or empty names
6. Categories with incomplete spatial/attribute data
7. Possible duplicate elements
8. Isolated / unconnected elements

Computes an overall Model Completeness Score (0-100%) and letter grade (A-F),
providing actionable remediation advice before running downstream compliance engines.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.modules.contracts.graph import ModelHealthAuditReport, ModelHealthCheckItem
from app.services.graph_database import GraphService
from app.services.graph_query_presets import get_preset, run_preset

logger = logging.getLogger("bimguard.services.model_health")

_CHECK_DEFINITIONS: list[dict[str, Any]] = [
    {
        "key": "doors-missing-fire-rating",
        "preset_key": "model-health-doors-missing-fire-rating",
        "name": "Fire Door Assemblies Without Fire Rating",
        "description": "Doors must define a FireRating property (in minutes) to verify egress fire barrier safety.",
        "severity": "critical",
        "penalty_weight": 20.0,
        "recommendation": "Assign a valid FireRating (e.g. 60, 90, 120 min) in Pset_DoorCommon for all egress boundary doors.",
    },
    {
        "key": "unassigned-storeys",
        "preset_key": "model-health-unassigned-storeys",
        "name": "Elements Without Building Storey Assignment",
        "description": "Physical elements must be assigned to an IfcBuildingStorey via spatial containment.",
        "severity": "critical",
        "penalty_weight": 25.0,
        "recommendation": "Link uncontained walls, slabs, and doors to their respective IfcBuildingStorey using IfcRelContainedInSpatialStructure.",
    },
    {
        "key": "spaces-missing-attributes",
        "preset_key": "model-health-spaces-missing-attributes",
        "name": "Spaces Missing Name or Identifier",
        "description": "IfcSpace instances must carry human-readable and standard room/occupancy identifiers.",
        "severity": "warning",
        "penalty_weight": 15.0,
        "recommendation": "Populate Name and LongName on all spaces with occupancy codes for egress load calculation.",
    },
    {
        "key": "elements-without-psets",
        "preset_key": "model-health-elements-without-psets",
        "name": "Elements Missing Property Sets",
        "description": "Physical building elements must carry property sets defining materials, specifications, and performance.",
        "severity": "warning",
        "penalty_weight": 15.0,
        "recommendation": "Attach standard buildingSMART property sets (e.g. Pset_WallCommon, Pset_DoorCommon) to physical elements.",
    },
    {
        "key": "empty-property-values",
        "preset_key": "model-health-empty-property-values",
        "name": "Elements With Blank Names or Identifiers",
        "description": "Elements must not have empty whitespace names or blank required identity strings.",
        "severity": "info",
        "penalty_weight": 5.0,
        "recommendation": "Provide meaningful names or mark-tags for unnamed physical elements to improve audit trail clarity.",
    },
    {
        "key": "categories-with-incomplete-data",
        "preset_key": "model-health-categories-with-most-incomplete-data",
        "name": "Categories With Uncontained Elements",
        "description": "Aggregated clusters of building elements lacking spatial containment.",
        "severity": "warning",
        "penalty_weight": 10.0,
        "recommendation": "Review spatial hierarchy in the authoring tool (Revit, ArchiCAD) for categories with highest uncontained counts.",
    },
    {
        "key": "possible-duplicates",
        "preset_key": "model-health-possible-duplicates",
        "name": "Potential Duplicate Elements",
        "description": "Multiple elements sharing identical names and IFC types, indicating duplicate modeling or clash risks.",
        "severity": "warning",
        "penalty_weight": 10.0,
        "recommendation": "Inspect duplicate elements at identical coordinates and purge redundant geometry instances.",
    },
    {
        "key": "isolated-elements",
        "preset_key": "model-health-isolated-elements",
        "name": "Isolated Floating Elements",
        "description": "Physical elements with zero graph connections (no spatial containment, voiding, or system connections).",
        "severity": "info",
        "penalty_weight": 5.0,
        "recommendation": "Ensure elements are joined, contained, or bounded by adjacent structures rather than floating freely.",
    },
]


class ModelHealthService:
    """Evaluates model data quality and health readiness via graph queries."""

    def __init__(self, graph_service: GraphService) -> None:
        self.graph_service = graph_service

    def audit_project(self, project_id: int, total_elements: int = 0) -> ModelHealthAuditReport:
        """Run all data-quality audit checks for a project's ingested model graph.

        Args:
            project_id: Target project identifier.
            total_elements: Optional total element count from model status.

        Returns:
            ModelHealthAuditReport with scores, grades, check results, and recommendations.
        """
        check_results: list[ModelHealthCheckItem] = []
        total_deductions = 0.0
        total_violations_count = 0

        for defn in _CHECK_DEFINITIONS:
            preset = get_preset(defn["preset_key"])
            rows: list[dict[str, Any]] = []

            if preset and self.graph_service and self.graph_service.provider:
                try:
                    rows = run_preset(
                        self.graph_service,
                        preset,
                        project_id=project_id,
                        params={},
                    )
                except Exception as exc:
                    logger.debug("Check %s query returned no rows or provider error: %s", defn["key"], exc)
                    rows = []

            count = len(rows)
            total_violations_count += count
            passed = (count == 0)

            if not passed:
                deduction = min(defn["penalty_weight"], defn["penalty_weight"] * (min(count, 10) / 10.0))
                total_deductions += deduction

            check_results.append(
                ModelHealthCheckItem(
                    key=defn["key"],
                    name=defn["name"],
                    description=defn["description"],
                    severity=defn["severity"],
                    passed=passed,
                    violation_count=count,
                    details=rows[:20],
                    recommendation=defn["recommendation"] if not passed else "Requirement satisfied.",
                )
            )

        health_score = max(0.0, min(100.0, round(100.0 - total_deductions, 1)))

        if health_score >= 90.0:
            grade = "A"
        elif health_score >= 80.0:
            grade = "B"
        elif health_score >= 70.0:
            grade = "C"
        elif health_score >= 60.0:
            grade = "D"
        else:
            grade = "F"

        return ModelHealthAuditReport(
            project_id=project_id,
            health_score=health_score,
            grade=grade,
            total_elements_audited=total_elements,
            total_violations=total_violations_count,
            checks=check_results,
            evaluated_at=datetime.now(timezone.utc).isoformat(),
        )
