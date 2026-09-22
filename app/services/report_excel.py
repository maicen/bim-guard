"""Render a :class:`ReportModel` to an Excel workbook.

WHY THIS EXISTS ALONGSIDE THE PDF

    The PDF's Findings Register is deliberately capped (see
    ``ReportModel.findings_register_truncated``) -- a report meant to be read
    has no room for hundreds of rows. This workbook is the uncapped, working
    counterpart: every failed finding, one row each, filterable and sortable
    in Excel, with blank Status/Assigned To/Resolved Date/Notes columns so it
    can double as a live punch-list rather than a read-only snapshot.

SHEET LAYOUT

    Summary            -- cover/scope identity, executive KPIs, results by
                           ruleset, top failed rules: the same numbers the
                           PDF's first two pages show, laid out as tables.
    Findings Register   -- every failed finding, ruleset-tagged, plus the
                           tracking columns above. The main working sheet.
    Rule Register       -- every rule executed, for finding -> rule -> clause
                           traceability, same as the PDF's rule register.
    Unable to Verify     -- rules that could not be evaluated against this
                           model; kept separate so they are never read as
                           failures.
"""

from __future__ import annotations

import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet

from app.modules.contracts import ReportModel

#: Literal light-mode hex values mirrored from frontend/src/app.css, same
#: source ``report_charts.py`` draws from -- the workbook, the PDF and the
#: in-app preview all read the same palette rather than three different ones.
_FG_PRIMARY = "0F172A"
_HEADER_FILL = "0066CC"
_HEADER_FONT = "FFFFFF"
_SUBHEAD_FILL = "F1F5F9"

_SEVERITY_FILL = {"mandatory": "FFE4E6", "recommended": "E0E7FF"}
_SEVERITY_FONT = {"mandatory": "BE123C", "recommended": "4338CA"}
_RELIABILITY_FILL = {"high": "D1FAE5", "medium": "FEF3C7", "low": "F1F5F9"}
_RELIABILITY_FONT = {"high": "047857", "medium": "B45309", "low": "64748B"}

_STATUS_OPTIONS = ("Open", "In Progress", "Resolved", "Won't Fix")

_FINDINGS_HEADERS = (
    "Element Name", "Element GUID", "Storey", "Ruleset", "Rule Reference",
    "Rule Description", "Severity", "Measured", "Required", "Difference",
    "Reliability", "IFC Property", "Citation", "Action Required", "Assignee Role",
    "Status", "Assigned To", "Resolved Date", "Notes",
)  # fmt: skip

_RULE_REGISTER_HEADERS = (
    "Rule Reference", "Rule Description", "Ruleset", "Citation", "IFC Property",
    "Reliability", "Evaluation Status", "Fail Count", "Total Count",
)  # fmt: skip

_UNVERIFIED_HEADERS = ("Rule Reference", "Rule Description", "Reason", "Affected Count")


def _header_font() -> Font:
    return Font(bold=True, color=_HEADER_FONT, size=10)


def _header_fill() -> PatternFill:
    return PatternFill(start_color=_HEADER_FILL, end_color=_HEADER_FILL, fill_type="solid")


def _write_header_row(ws: Worksheet, row: int, headers: tuple[str, ...]) -> None:
    for col, text in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=col, value=text)
        cell.font = _header_font()
        cell.fill = _header_fill()
        cell.alignment = Alignment(vertical="center", wrap_text=False)
    ws.freeze_panes = ws.cell(row=row + 1, column=1).coordinate
    ws.auto_filter.ref = f"A{row}:{get_column_letter(len(headers))}{row}"


def _fill_badge(cell, value: str, fill_map: dict[str, str], font_map: dict[str, str]) -> None:
    key = str(value or "").strip().lower()
    if key in fill_map:
        cell.fill = PatternFill(start_color=fill_map[key], end_color=fill_map[key], fill_type="solid")
        cell.font = Font(color=font_map[key], bold=True, size=9)


def _autosize(ws: Worksheet, widths: dict[int, int]) -> None:
    for col, width in widths.items():
        ws.column_dimensions[get_column_letter(col)].width = width


def _kv_block(ws: Worksheet, start_row: int, title: str, rows: list[tuple[str, object]]) -> int:
    """Write a titled key/value block starting at ``start_row``; return the next free row."""
    title_cell = ws.cell(row=start_row, column=1, value=title)
    title_cell.font = Font(bold=True, size=12, color=_FG_PRIMARY)
    row = start_row + 1
    for label, value in rows:
        ws.cell(row=row, column=1, value=label).font = Font(color="64748B", size=10)
        ws.cell(row=row, column=2, value=value if value not in (None, "") else "—").font = Font(size=10)
        row += 1
    return row + 1


def _build_summary_sheet(wb: Workbook, model: ReportModel) -> None:
    ws = wb.create_sheet("Summary")
    _autosize(ws, {1: 26, 2: 46})

    row = _kv_block(
        ws,
        1,
        "Report",
        [
            ("Project name", model.cover.project_name),
            ("Project code", model.cover.project_code),
            ("Model file", model.cover.model_file_name),
            ("Report ID", model.cover.report_id),
            ("Analysis date", model.cover.analysis_date),
            ("Discipline", model.cover.discipline),
            ("IFC schema", model.cover.ifc_schema),
            ("Suitability code", model.cover.suitability_code),
            ("Revision code", model.cover.revision_code),
            ("CDE state", model.cover.cde_state),
            ("ISO 19650 document ID", model.cover.document_id),
        ],
    )

    es = model.executive_summary
    row = _kv_block(
        ws,
        row,
        "Executive Summary",
        [
            ("Elements evaluated", es.unique_elements_evaluated),
            ("Rules executed", es.rules_executed),
            ("Rules with matching elements", es.rules_with_elements),
            ("Checks run", es.checks_run),
            ("Passed", es.passed),
            ("Failed", es.failed),
            ("Unable to verify", es.unable_to_verify),
            ("Verified pass rate", f"{es.pass_rate:.1f}%"),
            ("Mandatory failures", es.mandatory_failed),
            ("Narrative", es.narrative),
        ],
    )

    row = _kv_block(
        ws,
        row,
        "Scope & Document Control",
        [
            ("Model file", model.scope.model_file_name),
            ("IFC schema", model.scope.ifc_schema),
            ("Element count", model.scope.element_count),
            ("Storey count", model.scope.storey_count),
            ("Rulesets applied", ", ".join(model.scope.ruleset_names) or "—"),
            ("Model hash", model.scope.model_hash or "Pending — not yet recorded per analysis run"),
            ("Rule database version", model.scope.rule_database_version or "Pending — not yet recorded per analysis run"),
            ("Engine version", model.scope.engine_version or "Pending — not yet recorded per analysis run"),
            ("Generated at", model.scope.generated_at),
            ("Generated by", model.scope.generated_by),
        ],
    )

    ws.cell(row=row, column=1, value="Results by Ruleset").font = Font(bold=True, size=12, color=_FG_PRIMARY)
    row += 1
    headers = ("Ruleset", "Source", "Rule Count", "Passed", "Failed", "Unable to Verify", "Pass Rate")
    for col, text in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=col, value=text)
        cell.font = _header_font()
        cell.fill = _header_fill()
    row += 1
    for r in model.results_by_ruleset:
        ws.cell(row=row, column=1, value=r.ruleset_name)
        ws.cell(row=row, column=2, value=r.source_citation or "—")
        ws.cell(row=row, column=3, value=r.rule_count)
        ws.cell(row=row, column=4, value=r.passed)
        ws.cell(row=row, column=5, value=r.failed)
        ws.cell(row=row, column=6, value=r.unable_to_verify)
        ws.cell(row=row, column=7, value=f"{r.pass_rate:.1f}%")
        row += 1
    row += 2

    ws.cell(row=row, column=1, value="Top Failed Rules").font = Font(bold=True, size=12, color=_FG_PRIMARY)
    row += 1
    for col, text in enumerate(("Rule Reference", "Description", "Fail Count"), start=1):
        cell = ws.cell(row=row, column=col, value=text)
        cell.font = _header_font()
        cell.fill = _header_fill()
    row += 1
    for tf in es.top_failed_rules:
        ws.cell(row=row, column=1, value=tf.rule_reference)
        ws.cell(row=row, column=2, value=tf.rule_description)
        ws.cell(row=row, column=3, value=tf.fail_count)
        row += 1


def _build_findings_sheet(wb: Workbook, model: ReportModel) -> None:
    ws = wb.create_sheet("Findings Register")
    _write_header_row(ws, 1, _FINDINGS_HEADERS)
    _autosize(
        ws,
        {
            1: 20, 2: 16, 3: 14, 4: 18, 5: 20, 6: 30, 7: 12, 8: 14, 9: 16, 10: 12,
            11: 12, 12: 26, 13: 40, 14: 40, 15: 16, 16: 14, 17: 16, 18: 16, 19: 30,
        },
    )

    status_col = _FINDINGS_HEADERS.index("Status") + 1
    dv = DataValidation(
        type="list",
        formula1=f'"{",".join(_STATUS_OPTIONS)}"',
        allow_blank=True,
        showDropDown=False,
    )
    ws.add_data_validation(dv)

    row = 2
    for f in model.all_findings:
        ws.cell(row=row, column=1, value=f.element_name)
        ws.cell(row=row, column=2, value=f.element_guid)
        ws.cell(row=row, column=3, value=f.storey)
        ws.cell(row=row, column=4, value=f.ruleset_name)
        ws.cell(row=row, column=5, value=f.rule_reference)
        ws.cell(row=row, column=6, value=f.rule_description)
        sev_cell = ws.cell(row=row, column=7, value=f.severity)
        _fill_badge(sev_cell, f.severity, _SEVERITY_FILL, _SEVERITY_FONT)
        ws.cell(row=row, column=8, value=f.measured)
        ws.cell(row=row, column=9, value=f.required)
        ws.cell(row=row, column=10, value=f.difference)
        rel_cell = ws.cell(row=row, column=11, value=f.reliability)
        _fill_badge(rel_cell, f.reliability, _RELIABILITY_FILL, _RELIABILITY_FONT)
        ws.cell(row=row, column=12, value=f.ifc_property)
        ws.cell(row=row, column=13, value=f.citation)
        ws.cell(row=row, column=14, value=f.action_required)
        ws.cell(row=row, column=15, value=f.assignee_role)
        status_cell = ws.cell(row=row, column=status_col, value="Open")
        dv.add(status_cell)
        # Assigned To / Resolved Date / Notes are left blank for the user.
        row += 1

    if not model.all_findings:
        ws.cell(row=2, column=1, value="No failed findings in this analysis run.")


def _build_rule_register_sheet(wb: Workbook, model: ReportModel) -> None:
    ws = wb.create_sheet("Rule Register")
    _write_header_row(ws, 1, _RULE_REGISTER_HEADERS)
    _autosize(ws, {1: 20, 2: 30, 3: 18, 4: 40, 5: 26, 6: 12, 7: 16, 8: 12, 9: 12})

    row = 2
    for r in model.rule_register:
        ws.cell(row=row, column=1, value=r.rule_reference)
        ws.cell(row=row, column=2, value=r.rule_description)
        ws.cell(row=row, column=3, value=r.ruleset_name)
        ws.cell(row=row, column=4, value=r.citation)
        ws.cell(row=row, column=5, value=r.ifc_property)
        rel_cell = ws.cell(row=row, column=6, value=r.reliability)
        _fill_badge(rel_cell, r.reliability, _RELIABILITY_FILL, _RELIABILITY_FONT)
        ws.cell(row=row, column=7, value=r.status)
        ws.cell(row=row, column=8, value=r.fail_count)
        ws.cell(row=row, column=9, value=r.total_count)
        row += 1

    if not model.rule_register:
        ws.cell(row=2, column=1, value="No rules were executed in this run.")


def _build_unverified_sheet(wb: Workbook, model: ReportModel) -> None:
    ws = wb.create_sheet("Unable to Verify")
    _write_header_row(ws, 1, _UNVERIFIED_HEADERS)
    _autosize(ws, {1: 20, 2: 30, 3: 46, 4: 12})

    row = 2
    for u in model.unable_to_verify:
        ws.cell(row=row, column=1, value=u.rule_reference)
        ws.cell(row=row, column=2, value=u.rule_description)
        ws.cell(row=row, column=3, value=u.reason)
        ws.cell(row=row, column=4, value=u.affected_count)
        row += 1

    if not model.unable_to_verify:
        ws.cell(row=2, column=1, value="Every rule could be verified against this model.")


def render_report_excel(model: ReportModel) -> bytes:
    """Render ``model`` to an .xlsx workbook: Summary, Findings Register, Rule Register, Unable to Verify."""
    wb = Workbook()
    # The default sheet Workbook() creates is replaced by the four built below,
    # in display order, so "Summary" opens first rather than a blank "Sheet".
    wb.remove(wb.active)

    _build_summary_sheet(wb, model)
    _build_findings_sheet(wb, model)
    _build_rule_register_sheet(wb, model)
    _build_unverified_sheet(wb, model)

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
