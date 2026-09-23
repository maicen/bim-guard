"""Build a :class:`ReportModel` from a project's compliance analysis run.

THE SOURCE OF TRUTH IS ``rule_compliance``, NOT ``audit_issues``

    ``AnalysisResultContract.audit_issues`` (the shape ``/analyze/results`` and
    ``/analyze/export`` serve) records only violations and data-quality notes --
    it has no way to say a rule *passed*. The same orchestrator run also
    produces ``rule_compliance`` (one entry per rule, carrying
    ``pass_count``/``fail_count``/``missing_count``/``total_count`` and every
    per-element failure) and ``rule_compliance_summary`` (the aggregate of
    that list) -- see ``app.modules.reporter.ComplianceReporter.render_visual_report``
    and ``app.modules.comparator.ComplianceComparator.validate_metadata``.
    ``analysis_runner._run_architecture`` now keeps both on the returned dict
    specifically so this report can cite real pass/fail/pass-rate numbers
    instead of only ever listing what went wrong.

EVERYTHING IS DETERMINISTIC

    No LLM. Every sentence is a template filled from already-computed numbers;
    every number comes from ``rule_compliance``/``rule_compliance_summary``
    or the project/model records. A field this run cannot compute (model
    hash, rule database version, engine version) is left ``None`` rather than
    guessed -- see ``ReportScopeContract``.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

from app.modules.contracts import (
    ReportCoverContract,
    ReportElementResultRowContract,
    ReportElementTypeSheetContract,
    ReportExecutiveSummaryContract,
    ReportFindingRowContract,
    ReportModel,
    ReportPriorityFindingContract,
    ReportRuleRegisterRowContract,
    ReportRulesetResultContract,
    ReportScopeContract,
    ReportTopFailedRuleContract,
    ReportUnverifiedRowContract,
)
from app.modules.rule_reliability import assess_rule
from app.services import report_charts
from app.services.analysis_runner import run_analysis
from app.services.models_service import ModelsService
from app.services.projects_service import ProjectsService
from app.services.rules_service import RuleService

#: Per-rule statuses ComplianceComparator.validate_metadata emits that are not
#: a pass and not a hard fail -- the check could not be carried out, which is
#: its own category rather than a lesser kind of failure.
_UNVERIFIED_STATUSES = frozenset({"MISSING_DATA", "PARTIAL", "NO_ELEMENTS"})

#: Deterministic "action required" sentence per rule operator. ``{property}``,
#: ``{required}``, ``{measured}`` and ``{compare_property}`` are filled per
#: finding; no ruleset or clause name ever appears in these templates --
#: see the "no hardcoded fallback thresholds" project convention.
_ACTION_TEMPLATES: dict[str, str] = {
    ">=": "Increase {property} to at least {required} (measured {measured}).",
    ">": "Increase {property} above {required} (measured {measured}).",
    "<=": "Reduce {property} to at most {required} (measured {measured}).",
    "<": "Reduce {property} below {required} (measured {measured}).",
    "==": "Set {property} to {required} (measured {measured}).",
    "!=": "Change {property} away from its current value ({measured}).",
    "between": "Bring {property} within {required} (measured {measured}).",
    "exists": "Add a value for {property}; it is missing on this element.",
    "not_exists": "Remove the value set for {property}; it should not be present.",
    "field_consistency": "Make {property} consistent with {compare_property}.",
    "unique_within_scope": "Resolve the duplicate {property} value; it must be unique within its scope.",
}

_DEFAULT_PRIORITY_LIMIT = 15
_DEFAULT_FINDINGS_LIMIT = 50

#: Per-element status (ComplianceComparator._entry) -> element-type sheet
#: result label. NOT_APPLICABLE is deliberately absent: it means the rule's
#: own scope excludes this element (e.g. a fire-door-only rule on a non-fire
#: door), so it was never evaluated and showing it as a "result" would be
#: noise, not a finding -- those rows are dropped, not mapped.
_ELEMENT_RESULT_LABELS: dict[str, str] = {
    "PASS": "pass",
    "FAIL": "fail",
    "MISSING": "unable_to_verify",
    "WAIVED": "waived",
}

#: IFC class -> friendly sheet name, covering the classes BIM Guard's
#: architecture engines actually target today (rule_reliability._SCHEMA_CLASSES
#: plus the handful of others seen in rule target_ifc_class values). Anything
#: else falls through to the CamelCase-splitting fallback in
#: ``_element_type_label`` rather than being silently dropped.
_ELEMENT_TYPE_LABELS: dict[str, str] = {
    "IfcDoor": "Doors", "IfcDoorType": "Doors",
    "IfcWindow": "Windows", "IfcWindowType": "Windows",
    "IfcWall": "Walls", "IfcWallType": "Walls", "IfcWallStandardCase": "Walls",
    "IfcCurtainWall": "Curtain Walls",
    "IfcStair": "Stairs", "IfcStairFlight": "Stairs",
    "IfcRamp": "Ramps", "IfcRampFlight": "Ramps",
    "IfcRailing": "Railings",
    "IfcRoof": "Roofs",
    "IfcSlab": "Slabs & Floors",
    "IfcColumn": "Columns",
    "IfcBeam": "Beams",
    "IfcCovering": "Coverings",
    "IfcSpace": "Spaces & Rooms",
    "IfcBuildingStorey": "Storeys",
    "IfcOpeningElement": "Openings",
    "IfcFurniture": "Furniture", "IfcFurnishingElement": "Furniture",
    "IfcSanitaryTerminal": "Sanitary Fixtures",
    "IfcBuildingElementProxy": "Other Building Elements",
}  # fmt: skip

_CAMEL_CASE_SPLIT_RE = re.compile(r"(?<!^)(?=[A-Z])")


def _element_type_label(ifc_class: Any) -> str:
    """Friendly sheet name for an IFC class, e.g. ``IfcDoor`` -> ``Doors``."""
    cls = str(ifc_class or "").strip()
    if not cls:
        return "Other"
    if cls in _ELEMENT_TYPE_LABELS:
        return _ELEMENT_TYPE_LABELS[cls]
    name = cls[3:] if cls.startswith("Ifc") else cls
    words = _CAMEL_CASE_SPLIT_RE.sub(" ", name).strip()
    if not words:
        return "Other"
    return words if words.endswith("s") else f"{words}s"


def _num(value: Any) -> Optional[float]:
    """Coerce ``value`` to a float, or ``None`` when it is not numeric."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt_value(value: Any, unit: str = "") -> str:
    """Render a scalar for display, thousands-separated, unit appended."""
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    n = _num(value)
    if n is None:
        return str(value)
    text = f"{n:,.2f}".rstrip("0").rstrip(".")
    return f"{text} {unit}".strip() if unit else text


def _required_text(rule: dict) -> str:
    """Human-readable requirement, e.g. '>= 900 mm' or 'must be present'."""
    operator = str(rule.get("operator") or "").strip().lower()
    unit = str(rule.get("unit") or "")
    if operator == "between":
        return f"{_fmt_value(rule.get('value_min'))}–{_fmt_value(rule.get('value_max'), unit)}"
    if operator in (">=", ">", "<=", "<", "=="):
        symbol = "=" if operator == "==" else operator
        return f"{symbol} {_fmt_value(rule.get('check_value'), unit)}"
    if operator == "exists":
        return "must be present"
    if operator == "not_exists":
        return "must not be present"
    if operator == "field_consistency":
        return f"must match {rule.get('compare_property') or 'compared property'}"
    if operator == "unique_within_scope":
        return "must be unique within its scope"
    check = rule.get("check_value")
    return _fmt_value(check, unit) if check is not None else "see rule definition"


def _required_bare_value(rule: dict) -> str:
    """Target value/range with no comparison symbol, for use inside a sentence.

    ``_required_text`` prefixes the symbol (">= 900 mm") for table/tile display,
    where the reader needs it; embedding that same text in a sentence that
    already says "at least" would read "at least >= 900 mm" -- so this is the
    bare value the action-required templates below fill in instead.
    """
    operator = str(rule.get("operator") or "").strip().lower()
    unit = str(rule.get("unit") or "")
    if operator == "between":
        return f"{_fmt_value(rule.get('value_min'))}–{_fmt_value(rule.get('value_max'), unit)}"
    return _fmt_value(rule.get("check_value"), unit)


def _measured_text(rule: dict, actual: Any) -> str:
    """Human-readable measured value, matching the rule's own vocabulary."""
    operator = str(rule.get("operator") or "").strip().lower()
    if operator in ("exists", "not_exists"):
        return "present" if actual is not None else "missing"
    return _fmt_value(actual, str(rule.get("unit") or ""))


def _difference_text(rule: dict, actual: Any) -> str:
    """Signed distance from the measured value to the nearer threshold edge.

    Returns '—' whenever the operator has no numeric notion of distance
    (exists/not_exists, field_consistency, unique_within_scope) or the
    measured value is not itself numeric -- a dash, not a fabricated zero.
    """
    operator = str(rule.get("operator") or "").strip().lower()
    unit = str(rule.get("unit") or "")
    measured = _num(actual)
    if measured is None:
        return "—"
    if operator in (">=", ">"):
        target = _num(rule.get("check_value"))
        return _fmt_value(target - measured, unit) if target is not None else "—"
    if operator in ("<=", "<"):
        target = _num(rule.get("check_value"))
        return _fmt_value(measured - target, unit) if target is not None else "—"
    if operator == "==":
        target = _num(rule.get("check_value"))
        return _fmt_value(abs(measured - target), unit) if target is not None else "—"
    if operator == "between":
        vmin, vmax = _num(rule.get("value_min")), _num(rule.get("value_max"))
        if vmin is not None and measured < vmin:
            return _fmt_value(vmin - measured, unit)
        if vmax is not None and measured > vmax:
            return _fmt_value(measured - vmax, unit)
        return "—"
    return "—"


def _action_required(rule: dict, actual: Any) -> str:
    """Deterministic remediation sentence for one failure, templated by operator."""
    operator = str(rule.get("operator") or "").strip().lower()
    property_name = rule.get("property_name") or "the checked property"
    template = _ACTION_TEMPLATES.get(operator)
    if not template:
        return f"Review {property_name} against the rule's requirement."
    return template.format(
        property=property_name,
        required=_required_bare_value(rule),
        measured=_measured_text(rule, actual),
        compare_property=rule.get("compare_property") or "the compared property",
    )


def _ifc_property(rule: dict) -> str:
    pset = str(rule.get("property_set") or "").strip()
    prop = str(rule.get("property_name") or "").strip()
    if pset and prop:
        return f"{pset}.{prop}"
    return prop or pset or "—"


def _rule_reference(rule: dict) -> str:
    return str(rule.get("rule_ref") or rule.get("rule_id") or "Unreferenced rule")


def _citation_for(rule: dict) -> str:
    """Quoted source text with its document/page, or the bare rule reference."""
    source_text = str(rule.get("source_text") or "").strip()
    if not source_text:
        return _rule_reference(rule)
    quoted = source_text if len(source_text) <= 220 else source_text[:217] + "..."
    page = rule.get("source_page_number")
    suffix = f" (p. {page})" if page else ""
    return f'"{quoted}"{suffix}'


class ReportService:
    """Build a :class:`ReportModel` for one project's latest compliance analysis.

    Every collaborator is optional and defaults to a real instance when
    omitted, per this repo's DI convention (see ``ModelsService.__init__``).
    """

    def __init__(
        self,
        *,
        projects_service: ProjectsService | None = None,
        models_service: ModelsService | None = None,
        rules_service: RuleService | None = None,
    ) -> None:
        """Wire collaborators, defaulting each to a real instance."""
        self._projects = projects_service if projects_service is not None else ProjectsService()
        self._models = models_service if models_service is not None else ModelsService(
            project_mirror=self._projects
        )
        self._rules = rules_service if rules_service is not None else RuleService()

    def build_report_model(
        self,
        project_id: int,
        slug: str = "architecture",
        *,
        use_cache: bool = True,
        priority_limit: int = _DEFAULT_PRIORITY_LIMIT,
        findings_limit: int = _DEFAULT_FINDINGS_LIMIT,
    ) -> ReportModel:
        """Return the fully-computed :class:`ReportModel` for ``project_id``.

        Raises:
            ValueError: The analysis could not be produced (no model, unreadable
                file, engine error) -- callers translate this into an HTTP error;
                a report is never rendered over a run that did not happen.
        """
        raw = run_analysis(slug, project_id, use_cache=use_cache)
        if raw.get("compliance_error"):
            raise ValueError(str(raw["compliance_error"]))

        project = self._projects.get_project(project_id) or {}
        primary_model = self._models.get_primary(project_id) or {}
        rule_compliance: list[dict] = list(raw.get("rule_compliance") or [])
        summary: dict = dict(raw.get("rule_compliance_summary") or {})

        cover = self._build_cover(project, primary_model)
        executive_summary = self._build_executive_summary(summary, rule_compliance)
        scope = self._build_scope(project, primary_model, rule_compliance)
        results_by_ruleset = self._build_results_by_ruleset(rule_compliance)
        priority_findings = self._build_priority_findings(rule_compliance, priority_limit)
        findings_register, findings_total = self._build_findings_register(rule_compliance, findings_limit)
        unable_to_verify = self._build_unable_to_verify(rule_compliance)
        rule_register = self._build_rule_register(rule_compliance)
        element_type_sheets = self._build_element_type_sheets(rule_compliance)

        return ReportModel(
            cover=cover,
            executive_summary=executive_summary,
            scope=scope,
            results_by_ruleset=results_by_ruleset,
            priority_findings=priority_findings,
            findings_register=findings_register,
            findings_register_total=findings_total,
            findings_register_truncated=findings_total > len(findings_register),
            unable_to_verify=unable_to_verify,
            rule_register=rule_register,
            element_type_sheets=element_type_sheets,
        )

    # -- Section builders --------------------------------------------------

    def _build_cover(self, project: dict, model: dict) -> ReportCoverContract:
        project_id = project.get("id")
        now = datetime.now(timezone.utc)
        report_id = f"BGR-{project_id}-{now.strftime('%Y%m%d%H%M%S')}"
        project_code = str(project.get("project_code") or "")
        volume_system = str(model.get("volume_system") or "")
        doc_number = str(model.get("number") or "")
        document_id = "-".join(p for p in (project_code, volume_system, doc_number, "RPT") if p)
        return ReportCoverContract(
            project_name=str(project.get("name") or f"Project {project_id}"),
            project_code=project_code,
            model_file_name=str(model.get("file_name") or ""),
            report_id=report_id,
            analysis_date=now.strftime("%Y-%m-%d"),
            discipline="Architecture",
            ifc_schema=str(model.get("ifc_schema") or ""),
            suitability_code=str(model.get("suitability_code") or ""),
            revision_code=str(model.get("revision_code") or ""),
            cde_state=str(model.get("cde_state") or ""),
            document_id=document_id,
        )

    def _build_executive_summary(
        self, summary: dict, rule_compliance: list[dict]
    ) -> ReportExecutiveSummaryContract:
        total_rules = int(summary.get("total_rules") or 0)
        passed = int(summary.get("passed") or 0)
        failed = int(summary.get("failed") or 0)
        unable_to_verify = int(summary.get("missing_data") or 0) + int(summary.get("no_elements") or 0)
        checks_run = sum(int(r.get("total_count") or 0) for r in rule_compliance)
        pass_rate = float(summary.get("pass_rate") or 0.0)
        elements_evaluated = int(summary.get("elements_evaluated") or 0)
        unique_elements = int(summary.get("unique_elements_evaluated") or 0)

        narrative = (
            f"{failed:,} of {checks_run:,} checks failed across {total_rules:,} rules "
            f"evaluated against {unique_elements:,} elements. {passed:,} checks passed "
            f"({pass_rate:.1f}% verified pass rate), and {unable_to_verify:,} rules could "
            "not be verified against this model."
            if checks_run
            else "No checks could be run against this model for the selected ruleset."
        )

        by_ruleset = self._build_results_by_ruleset(rule_compliance)
        ruleset_chart = report_charts.stacked_bar_chart_svg(
            [(r.ruleset_name, r.passed, r.failed, r.unable_to_verify) for r in by_ruleset]
        )

        storey_counts: dict[str, int] = {}
        for rule in rule_compliance:
            for failure in rule.get("failures") or []:
                storey = str(failure.get("storey") or "Unassigned")
                storey_counts[storey] = storey_counts.get(storey, 0) + 1
        storey_rows = sorted(storey_counts.items(), key=lambda kv: kv[1], reverse=True)
        storey_chart = report_charts.horizontal_bar_chart_svg(storey_rows, bar_color=report_charts.CRITICAL)

        top_failed = sorted(
            rule_compliance, key=lambda r: int(r.get("fail_count") or 0), reverse=True
        )[:5]
        top_failed_rules = [
            ReportTopFailedRuleContract(
                rule_reference=_rule_reference(r),
                rule_description=str(r.get("rule_desc") or ""),
                fail_count=int(r.get("fail_count") or 0),
            )
            for r in top_failed
            if int(r.get("fail_count") or 0) > 0
        ]

        return ReportExecutiveSummaryContract(
            elements_evaluated=elements_evaluated,
            unique_elements_evaluated=unique_elements,
            rules_executed=total_rules,
            rules_with_elements=int(summary.get("rules_with_elements") or 0),
            checks_run=checks_run,
            passed=passed,
            failed=failed,
            unable_to_verify=unable_to_verify,
            pass_rate=pass_rate,
            mandatory_failed=int(summary.get("mandatory_failed") or 0),
            narrative=narrative,
            ruleset_chart_svg=ruleset_chart,
            storey_chart_svg=storey_chart,
            top_failed_rules=top_failed_rules,
        )

    def _build_scope(
        self, project: dict, model: dict, rule_compliance: list[dict]
    ) -> ReportScopeContract:
        ruleset_ids = sorted({str(r.get("ruleset_id") or "") for r in rule_compliance if r.get("ruleset_id")})
        ruleset_names = [self._ruleset_name(rid) for rid in ruleset_ids]
        now = datetime.now(timezone.utc)
        return ReportScopeContract(
            model_file_name=str(model.get("file_name") or ""),
            ifc_schema=str(model.get("ifc_schema") or ""),
            element_count=int(model.get("element_count") or 0),
            storey_count=model.get("storey_count"),
            ruleset_names=ruleset_names,
            model_hash=None,
            rule_database_version=None,
            engine_version=None,
            generated_at=now.strftime("%Y-%m-%d %H:%M UTC"),
            generated_by="BIM Guard",
        )

    def _ruleset_name(self, ruleset_id: str) -> str:
        folder = self._rules.get_folder(ruleset_id) if ruleset_id else None
        if folder:
            return str(folder.get("display_name") or ruleset_id)
        return ruleset_id or "Unspecified ruleset"

    def _ruleset_citation(self, ruleset_id: str) -> str:
        folder = self._rules.get_folder(ruleset_id) if ruleset_id else None
        if folder and folder.get("description"):
            return str(folder["description"])
        return ""

    def _build_results_by_ruleset(self, rule_compliance: list[dict]) -> list[ReportRulesetResultContract]:
        groups: dict[str, list[dict]] = {}
        for rule in rule_compliance:
            ruleset_id = str(rule.get("ruleset_id") or "")
            groups.setdefault(ruleset_id, []).append(rule)

        rows: list[ReportRulesetResultContract] = []
        for ruleset_id, rules in sorted(groups.items(), key=lambda kv: self._ruleset_name(kv[0])):
            passed = sum(1 for r in rules if r.get("status") == "PASS")
            failed = sum(1 for r in rules if r.get("status") == "FAIL")
            unable = sum(1 for r in rules if r.get("status") in _UNVERIFIED_STATUSES)
            rule_count = len(rules)
            rows.append(
                ReportRulesetResultContract(
                    ruleset_id=ruleset_id,
                    ruleset_name=self._ruleset_name(ruleset_id),
                    source_citation=self._ruleset_citation(ruleset_id),
                    rule_count=rule_count,
                    passed=passed,
                    failed=failed,
                    unable_to_verify=unable,
                    pass_rate=round(100 * passed / rule_count, 1) if rule_count else 0.0,
                )
            )
        return rows

    def _flatten_failures(self, rule_compliance: list[dict]) -> list[tuple[dict, dict]]:
        """Every (rule, failure) pair across all rules, rule dict repeated per failure."""
        pairs: list[tuple[dict, dict]] = []
        for rule in rule_compliance:
            for failure in rule.get("failures") or []:
                pairs.append((rule, failure))
        return pairs

    def _priority_rank(self, rule: dict) -> tuple[int, int]:
        """Sort key: mandatory-severity first, then by the rule's own fail_count."""
        is_mandatory = 0 if str(rule.get("severity") or "mandatory") == "mandatory" else 1
        return (is_mandatory, -int(rule.get("fail_count") or 0))

    def _finding_contract(self, rule: dict, failure: dict) -> ReportPriorityFindingContract:
        """Build one finding row for the PDF's priority-finding cards."""
        actual = failure.get("actual")
        assessment = assess_rule(rule)
        ruleset_id = str(rule.get("ruleset_id") or "")
        return ReportPriorityFindingContract(
            rule_reference=_rule_reference(rule),
            rule_description=str(rule.get("rule_desc") or ""),
            ruleset_id=ruleset_id,
            ruleset_name=self._ruleset_name(ruleset_id),
            element_name=str(failure.get("element_name") or failure.get("guid") or ""),
            element_guid=str(failure.get("guid") or ""),
            storey=str(failure.get("storey") or "—"),
            measured=_measured_text(rule, actual),
            required=_required_text(rule),
            difference=_difference_text(rule, actual),
            citation=_citation_for(rule),
            ifc_property=_ifc_property(rule),
            reliability=assessment.level if assessment else "low",
            reliability_reason=assessment.reason if assessment else "No specific IFC property recorded for this rule.",
            action_required=_action_required(rule, actual),
            assignee_role="BIM coordinator",
            severity=str(rule.get("severity") or "mandatory"),
        )

    def _build_priority_findings(
        self, rule_compliance: list[dict], limit: int
    ) -> list[ReportPriorityFindingContract]:
        pairs = self._flatten_failures(rule_compliance)
        pairs.sort(key=lambda pair: self._priority_rank(pair[0]))
        return [self._finding_contract(rule, failure) for rule, failure in pairs[:limit]]

    def _build_element_type_sheets(self, rule_compliance: list[dict]) -> list[ReportElementTypeSheetContract]:
        """Group every rule's full per-element result by IFC element type.

        Unlike ``_flatten_failures`` (failures only), this walks each rule's
        ``all_elements`` -- every element the rule actually evaluated, whatever
        the outcome -- so a sheet shows the whole picture for its element type,
        not just what went wrong. A rule that matched no elements at all still
        gets one "unable to verify" row, so it isn't silently absent from the
        type it targets.
        """
        groups: dict[str, list[dict]] = {}
        for rule in rule_compliance:
            groups.setdefault(_element_type_label(rule.get("target")), []).append(rule)

        sheets: list[ReportElementTypeSheetContract] = []
        for label in sorted(groups, key=lambda name: (name == "Other", name)):
            rules = groups[label]
            rows: list[ReportElementResultRowContract] = []
            for rule in rules:
                ruleset_id = str(rule.get("ruleset_id") or "")
                ruleset_name = self._ruleset_name(ruleset_id)
                assessment = assess_rule(rule)
                reliability = assessment.level if assessment else "low"
                all_elements = rule.get("all_elements") or []

                if not all_elements:
                    rows.append(
                        ReportElementResultRowContract(
                            element_name="—",
                            rule_reference=_rule_reference(rule),
                            rule_description=str(rule.get("rule_desc") or ""),
                            ruleset_id=ruleset_id,
                            ruleset_name=ruleset_name,
                            ifc_property=_ifc_property(rule),
                            required=_required_text(rule),
                            difference="—",
                            result="unable_to_verify",
                            severity=str(rule.get("severity") or "mandatory"),
                            reliability=reliability,
                            citation=_citation_for(rule),
                            assignee_role="BIM coordinator",
                        )
                    )
                    continue

                for el in all_elements:
                    status = str(el.get("status") or "")
                    if status == "NOT_APPLICABLE":
                        continue
                    result = _ELEMENT_RESULT_LABELS.get(status, "unable_to_verify")
                    actual = el.get("actual")
                    rows.append(
                        ReportElementResultRowContract(
                            element_name=str(el.get("element_name") or el.get("guid") or ""),
                            element_guid=str(el.get("guid") or ""),
                            storey=str(el.get("storey") or "—"),
                            rule_reference=_rule_reference(rule),
                            rule_description=str(rule.get("rule_desc") or ""),
                            ruleset_id=ruleset_id,
                            ruleset_name=ruleset_name,
                            ifc_property=_ifc_property(rule),
                            measured=_measured_text(rule, actual),
                            required=_required_text(rule),
                            difference=_difference_text(rule, actual) if result == "fail" else "—",
                            result=result,
                            severity=str(rule.get("severity") or "mandatory"),
                            reliability=reliability,
                            citation=_citation_for(rule),
                            action_required=_action_required(rule, actual) if result == "fail" else "",
                            assignee_role="BIM coordinator",
                        )
                    )

            sheets.append(
                ReportElementTypeSheetContract(
                    type_label=label,
                    ifc_class=str(rules[0].get("target") or ""),
                    rows=rows,
                    passed=sum(1 for r in rows if r.result == "pass"),
                    failed=sum(1 for r in rows if r.result == "fail"),
                    unable_to_verify=sum(1 for r in rows if r.result == "unable_to_verify"),
                    waived=sum(1 for r in rows if r.result == "waived"),
                )
            )
        return sheets

    def _build_findings_register(
        self, rule_compliance: list[dict], limit: int
    ) -> tuple[list[ReportFindingRowContract], int]:
        pairs = self._flatten_failures(rule_compliance)
        pairs.sort(key=lambda pair: self._priority_rank(pair[0]))
        total = len(pairs)

        rows = [
            ReportFindingRowContract(
                element_name=str(failure.get("element_name") or failure.get("guid") or ""),
                element_guid=str(failure.get("guid") or ""),
                storey=str(failure.get("storey") or "—"),
                rule_reference=_rule_reference(rule),
                measured=_measured_text(rule, failure.get("actual")),
                required=_required_text(rule),
                difference=_difference_text(rule, failure.get("actual")),
                severity=str(rule.get("severity") or "mandatory"),
            )
            for rule, failure in pairs[:limit]
        ]
        return rows, total

    def _build_unable_to_verify(self, rule_compliance: list[dict]) -> list[ReportUnverifiedRowContract]:
        rows: list[ReportUnverifiedRowContract] = []
        for rule in rule_compliance:
            status = rule.get("status")
            if status not in _UNVERIFIED_STATUSES:
                continue
            reason = {
                "NO_ELEMENTS": "No matching elements were found in this model.",
                "MISSING_DATA": "The required property was not found on the matched elements.",
                "PARTIAL": "The required property was found on some, but not all, matched elements.",
            }.get(str(status), "Could not be verified against this model.")
            affected = int(rule.get("missing_count") or rule.get("total_count") or 0)
            rows.append(
                ReportUnverifiedRowContract(
                    rule_reference=_rule_reference(rule),
                    rule_description=str(rule.get("rule_desc") or ""),
                    reason=reason,
                    affected_count=affected,
                )
            )
        return rows

    def _build_rule_register(self, rule_compliance: list[dict]) -> list[ReportRuleRegisterRowContract]:
        rows: list[ReportRuleRegisterRowContract] = []
        for rule in rule_compliance:
            assessment = assess_rule(rule)
            ruleset_id = str(rule.get("ruleset_id") or "")
            rows.append(
                ReportRuleRegisterRowContract(
                    rule_reference=_rule_reference(rule),
                    rule_description=str(rule.get("rule_desc") or ""),
                    ruleset_id=ruleset_id,
                    ruleset_name=self._ruleset_name(ruleset_id),
                    citation=_citation_for(rule),
                    ifc_property=_ifc_property(rule),
                    reliability=assessment.level if assessment else "low",
                    status=str(rule.get("status") or ""),
                    fail_count=int(rule.get("fail_count") or 0),
                    total_count=int(rule.get("total_count") or 0),
                )
            )
        return rows
