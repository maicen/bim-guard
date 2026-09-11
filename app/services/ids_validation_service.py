"""ISO 19650-4 Tier 2 exchange verification: buildingSMART IDS 1.0 execution.

Executes a ruleset's IDS-exportable rows against a project's IFC model via
``ifctester.ids`` -- the same buildingSMART IDS 1.0 implementation
``app/modules/rule_builder/ids_exporter.py`` already uses to author and parse
IDS documents. Closes the gap where ``ids_check_passed`` was hardcoded
``True`` everywhere ``CDEStateMachine`` consulted it, because nothing
actually ran an IDS document against a model.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import ifcopenshell
import ifctester.ids as ifctester_ids

from app.logging_config import get_logger
from app.modules.rule_builder.ids_exporter import build_ids_document
from app.services.projects_service import ProjectsService
from app.services.rules_service import RuleService

logger = get_logger(__name__)


@dataclass
class IDSSpecificationResult:
    """Outcome of one IDS `<specification>` evaluated against the model."""

    name: str
    status: bool | None
    applicable_count: int
    failed_count: int


@dataclass
class IDSValidationResult:
    """Aggregate Tier 2 (IDS) verification outcome for one ruleset."""

    ruleset_id: str
    passed: bool
    specifications: list[IDSSpecificationResult] = field(default_factory=list)
    error: str | None = None

    @property
    def failed_specifications(self) -> list[IDSSpecificationResult]:
        """Return only the specifications that had applicable entities fail."""
        return [spec for spec in self.specifications if spec.status is False]

    def to_dict(self) -> dict[str, Any]:
        """JSON-serialisable summary, for surfacing in API responses/logs."""
        return {
            "ruleset_id": self.ruleset_id,
            "passed": self.passed,
            "error": self.error,
            "specifications": [
                {
                    "name": spec.name,
                    "status": spec.status,
                    "applicable_count": spec.applicable_count,
                    "failed_count": spec.failed_count,
                }
                for spec in self.specifications
            ],
        }


class IDSValidationService:
    """Runs Tier 2 (buildingSMART IDS 1.0) verification for a project."""

    def __init__(
        self,
        *,
        projects_service: ProjectsService | None = None,
        rules_service: RuleService | None = None,
    ) -> None:
        """Initialize with injected collaborators, defaulting to real instances."""
        self._projects = projects_service if projects_service is not None else ProjectsService()
        self._rules = rules_service if rules_service is not None else RuleService()

    def validate_project(self, project_id: int, ruleset_id: str) -> IDSValidationResult:
        """Validate a project's IFC model against one ruleset's IDS-exportable rules.

        A ruleset with no IDS-exportable rows (no property_check rules with
        both a target IFC class and property name) has nothing to check, so
        this returns ``passed=True`` rather than treating "no rules" as a
        failure. A specification with applicable entities that all fail its
        requirements makes the whole result ``passed=False``.
        """
        rows = self._rules.list_by_ruleset(ruleset_id)
        try:
            xml = build_ids_document(rows, export_identifier=ruleset_id)
        except ValueError:
            return IDSValidationResult(ruleset_id=ruleset_id, passed=True)

        ifc_path = self._projects.resolve_ifc_file(project_id)
        if ifc_path is None:
            return IDSValidationResult(
                ruleset_id=ruleset_id,
                passed=False,
                error="Project has no IFC model to validate.",
            )

        document = self._parse_ids_document(xml)
        if document is None:
            return IDSValidationResult(
                ruleset_id=ruleset_id,
                passed=False,
                error="Generated IDS document could not be parsed.",
            )

        try:
            ifc_file = ifcopenshell.open(str(ifc_path))
        except Exception as exc:
            logger.warning(
                "Failed to open IFC model for IDS validation project_id=%d", project_id, exc_info=True
            )
            return IDSValidationResult(
                ruleset_id=ruleset_id, passed=False, error=f"Could not open IFC model: {exc}"
            )

        document.validate(ifc_file)

        specs = [
            IDSSpecificationResult(
                name=spec.name,
                status=spec.status,
                applicable_count=len(spec.applicable_entities),
                failed_count=len(spec.failed_entities),
            )
            for spec in document.specifications
        ]
        passed = all(spec.status is not False for spec in specs)
        return IDSValidationResult(ruleset_id=ruleset_id, passed=passed, specifications=specs)

    @staticmethod
    def _parse_ids_document(xml_text: str) -> "ifctester_ids.Ids | None":
        """Parse a generated IDS XML string via the strict `ifctester.ids` parser."""
        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".ids", encoding="utf-8", delete=False
            ) as tmp_file:
                tmp_file.write(xml_text)
                tmp_path = tmp_file.name
            return ifctester_ids.open(tmp_path, validate=False)
        except Exception:
            logger.warning("Failed to parse generated IDS document", exc_info=True)
            return None
        finally:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)
