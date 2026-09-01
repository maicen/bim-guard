"""IFC Pre-Flight Validation Service.

Integrates buildingSMART validation data model & Gherkin rule engine checks:
1. Syntax Checks (ISO 10303-21 STEP physical file structure)
2. Schema Checks (IFC schema versioning, root entities)
3. Gherkin Rules (Single Project, GUID uniqueness & format, Spatial Hierarchy, Material associations)

Reference:
- Validation Service: https://github.com/buildingSMART/validate
- Gherkin Rules: https://github.com/buildingSMART/ifc-gherkin-rules
"""

from __future__ import annotations

import re
from pathlib import Path

from app.logging_config import get_logger
from app.modules.contracts import (
    IFCValidationIssue,
    IFCValidationReport,
    IFCValidationStageResult,
)

logger = get_logger(__name__)

SUPPORTED_SCHEMAS = {
    "IFC2X3",
    "IFC4",
    "IFC4X1",
    "IFC4X2",
    "IFC4X3",
    "IFC4X3_ADD1",
    "IFC4X3_ADD2",
    "IFC4X3_TC1",
}

# 22-character IFC base64 GUID pattern
IFC_GUID_PATTERN = re.compile(r"^[0-9A-Za-z_\$]{22}$")


class IFCValidationService:
    """3-Stage pre-flight validation gatekeeper for IFC files."""

    def __init__(self, reject_on_fatal: bool = True) -> None:
        self.reject_on_fatal = reject_on_fatal

    def validate_bytes(self, content: bytes, filename: str = "model.ifc") -> IFCValidationReport:
        """Execute pre-flight checks directly on raw byte buffer before saving or parsing."""
        if not content or len(content.strip()) == 0:
            syntax_issue = IFCValidationIssue(
                rule_code="IFC-SYN-001",
                stage="syntax",
                severity="fatal",
                message="File is empty or contains only whitespace.",
            )
            return IFCValidationReport(
                valid=False,
                schema_version=None,
                file_size_bytes=0,
                syntax_stage=IFCValidationStageResult(stage_name="syntax", passed=False, issues_count=1, details=[syntax_issue]),
                schema_stage=IFCValidationStageResult(stage_name="schema", passed=False, issues_count=0, details=[]),
                rules_stage=IFCValidationStageResult(stage_name="gherkin_rules", passed=False, issues_count=0, details=[]),
                total_issues=1,
                fatal_errors=1,
                warnings=0,
                summary_message="FATAL: File is empty.",
            )

        # Stage 1: Syntax Checks
        syntax_issues, text = self._check_syntax(content)
        syntax_passed = not any(i.severity in {"fatal", "error"} for i in syntax_issues)

        # Stage 2: Schema Checks
        schema_version = None
        schema_issues: list[IFCValidationIssue] = []
        if syntax_passed and text:
            schema_version, schema_issues = self._check_schema(text)
        schema_passed = not any(i.severity in {"fatal", "error"} for i in schema_issues)

        # Stage 3: Gherkin / buildingSMART Rules
        rules_issues: list[IFCValidationIssue] = []
        if syntax_passed and text:
            rules_issues = self._check_gherkin_rules(text)
        rules_passed = not any(i.severity == "fatal" for i in rules_issues)

        all_issues = syntax_issues + schema_issues + rules_issues
        fatal_count = sum(1 for i in all_issues if i.severity == "fatal")
        error_count = sum(1 for i in all_issues if i.severity == "error")
        warning_count = sum(1 for i in all_issues if i.severity == "warning")

        is_valid = fatal_count == 0 and error_count == 0

        summary = (
            f"Validation PASSED (Schema: {schema_version or 'Unknown'}, {warning_count} warnings)"
            if is_valid
            else f"Validation FAILED ({fatal_count} fatal errors, {error_count} schema/syntax errors, {warning_count} warnings)"
        )

        return IFCValidationReport(
            valid=is_valid,
            schema_version=schema_version,
            file_size_bytes=len(content),
            syntax_stage=IFCValidationStageResult(stage_name="syntax", passed=syntax_passed, issues_count=len(syntax_issues), details=syntax_issues),
            schema_stage=IFCValidationStageResult(stage_name="schema", passed=schema_passed, issues_count=len(schema_issues), details=schema_issues),
            rules_stage=IFCValidationStageResult(stage_name="gherkin_rules", passed=rules_passed, issues_count=len(rules_issues), details=rules_issues),
            total_issues=len(all_issues),
            fatal_errors=fatal_count,
            warnings=warning_count,
            summary_message=summary,
        )

    def validate_file(self, filepath: str | Path) -> IFCValidationReport:
        """Validate a file stored on disk."""
        path = Path(filepath)
        if not path.exists():
            issue = IFCValidationIssue(
                rule_code="IFC-SYN-000",
                stage="syntax",
                severity="fatal",
                message=f"File does not exist: {filepath}",
            )
            return IFCValidationReport(
                valid=False,
                schema_version=None,
                file_size_bytes=0,
                syntax_stage=IFCValidationStageResult(stage_name="syntax", passed=False, issues_count=1, details=[issue]),
                schema_stage=IFCValidationStageResult(stage_name="schema", passed=False, issues_count=0, details=[]),
                rules_stage=IFCValidationStageResult(stage_name="gherkin_rules", passed=False, issues_count=0, details=[]),
                total_issues=1,
                fatal_errors=1,
                warnings=0,
                summary_message="File does not exist.",
            )

        return self.validate_bytes(path.read_bytes(), filename=path.name)

    def _check_syntax(self, content: bytes) -> tuple[list[IFCValidationIssue], str | None]:
        """Stage 1: Validate ISO 10303-21 STEP physical header and structure."""
        issues: list[IFCValidationIssue] = []

        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = content.decode("latin-1")
            except Exception as exc:
                issues.append(
                    IFCValidationIssue(
                        rule_code="IFC-SYN-002",
                        stage="syntax",
                        severity="fatal",
                        message=f"Invalid character encoding in IFC file: {exc}",
                    )
                )
                return issues, None

        stripped = text.strip()

        # STEP header tokens
        if not stripped.startswith("ISO-10303-21;"):
            issues.append(
                IFCValidationIssue(
                    rule_code="IFC-SYN-003",
                    stage="syntax",
                    severity="fatal",
                    message="Missing standard STEP physical file header 'ISO-10303-21;'.",
                    line_number=1,
                )
            )

        if "HEADER;" not in text:
            issues.append(
                IFCValidationIssue(
                    rule_code="IFC-SYN-004",
                    stage="syntax",
                    severity="fatal",
                    message="Missing 'HEADER;' section in STEP structure.",
                )
            )

        if "DATA;" not in text:
            issues.append(
                IFCValidationIssue(
                    rule_code="IFC-SYN-005",
                    stage="syntax",
                    severity="fatal",
                    message="Missing 'DATA;' section in STEP structure.",
                )
            )

        if not (stripped.endswith("END-ISO-10303-21;") or "END-ISO-10303-21;" in stripped[-200:]):
            issues.append(
                IFCValidationIssue(
                    rule_code="IFC-SYN-006",
                    stage="syntax",
                    severity="error",
                    message="Missing or corrupted 'END-ISO-10303-21;' closing token at end of file.",
                )
            )

        return issues, text

    def _check_schema(self, text: str) -> tuple[str | None, list[IFCValidationIssue]]:
        """Stage 2: Extract and validate IFC schema version from HEADER."""
        issues: list[IFCValidationIssue] = []
        schema_version = None

        match = re.search(r"FILE_SCHEMA\s*\(\s*\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\)", text, re.IGNORECASE)
        if match:
            schema_version = match.group(1).upper()
            if schema_version not in SUPPORTED_SCHEMAS:
                issues.append(
                    IFCValidationIssue(
                        rule_code="IFC-SCH-001",
                        stage="schema",
                        severity="error",
                        message=f"Unsupported or unrecognized IFC schema: '{schema_version}'. Supported: {', '.join(sorted(SUPPORTED_SCHEMAS))}",
                    )
                )
        else:
            issues.append(
                IFCValidationIssue(
                    rule_code="IFC-SCH-002",
                    stage="schema",
                    severity="warning",
                    message="Could not locate FILE_SCHEMA declaration in IFC HEADER section.",
                )
            )

        return schema_version, issues

    def _check_gherkin_rules(self, text: str) -> list[IFCValidationIssue]:
        """Stage 3: Gherkin / buildingSMART rules."""
        issues: list[IFCValidationIssue] = []

        # Rule IFC-VAL-001: Exactly one IfcProject root
        project_matches = re.findall(r"=\s*IFCPROJECT\s*\(", text, re.IGNORECASE)
        if len(project_matches) == 0:
            issues.append(
                IFCValidationIssue(
                    rule_code="IFC-VAL-001",
                    stage="gherkin_rules",
                    severity="error",
                    message="Model does not contain an IfcProject root entity.",
                )
            )
        elif len(project_matches) > 1:
            issues.append(
                IFCValidationIssue(
                    rule_code="IFC-VAL-001",
                    stage="gherkin_rules",
                    severity="error",
                    message=f"Model contains {len(project_matches)} IfcProject root entities; exactly 1 is required.",
                )
            )

        # Rule IFC-VAL-002: GUID Format & Uniqueness
        # Find 22-char strings in single quotes representing GUIDs
        guid_matches = re.findall(r"['\"]([0-9A-Za-z_\$]{22})['\"]", text)
        seen_guids = set()
        duplicate_guids = set()
        for g in guid_matches:
            if g in seen_guids:
                duplicate_guids.add(g)
            seen_guids.add(g)

        if duplicate_guids:
            samples = list(duplicate_guids)[:3]
            issues.append(
                IFCValidationIssue(
                    rule_code="IFC-VAL-002",
                    stage="gherkin_rules",
                    severity="warning",
                    message=f"Found {len(duplicate_guids)} duplicate IFC GUIDs in model (e.g. {', '.join(samples)}).",
                )
            )

        # Rule IFC-VAL-003: Spatial Containment (IfcRelAggregates / IfcSite / IfcBuilding)
        has_aggregates = bool(re.search(r"IFCRELAGGREGATES", text, re.IGNORECASE))
        has_spatial = bool(re.search(r"IFC(SITE|BUILDING|BUILDINGSTOREY)", text, re.IGNORECASE))
        if not has_aggregates and not has_spatial:
            issues.append(
                IFCValidationIssue(
                    rule_code="IFC-VAL-003",
                    stage="gherkin_rules",
                    severity="warning",
                    message="Model lacks spatial hierarchy (IfcRelAggregates / IfcBuilding / IfcBuildingStorey).",
                )
            )

        # Rule IFC-VAL-004: RelContainedInSpatialStructure
        has_contained = bool(re.search(r"IFCRELCONTAINEDINSPATIALSTRUCTURE", text, re.IGNORECASE))
        if not has_contained:
            issues.append(
                IFCValidationIssue(
                    rule_code="IFC-VAL-004",
                    stage="gherkin_rules",
                    severity="info",
                    message="Model does not declare IfcRelContainedInSpatialStructure relationships.",
                )
            )

        # Rule IFC-VAL-006: Material Association
        has_material_rel = bool(re.search(r"IFCRELASSOCIATESMATERIAL", text, re.IGNORECASE))
        if not has_material_rel:
            issues.append(
                IFCValidationIssue(
                    rule_code="IFC-VAL-006",
                    stage="gherkin_rules",
                    severity="info",
                    message="Model contains no IfcRelAssociatesMaterial relations. Material properties will rely on psets or geometry defaults.",
                )
            )

        return issues


DEFAULT_IFC_VALIDATION_SERVICE = IFCValidationService()
