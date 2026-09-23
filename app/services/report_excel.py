"""Render a :class:`ReportModel` to an Excel workbook.

WHY THIS EXISTS ALONGSIDE THE PDF

    The PDF's findings/rule sections are deliberately capped or flattened for
    a document meant to be read. This workbook is the uncapped, working
    counterpart, organized the way an engineer actually works: one sheet per
    IFC element type (Doors, Windows, Stairs, Walls, ...), each listing every
    rule's full result for that type -- pass, fail, or unable to verify, not
    just what failed -- with blank Status/Assigned To/Resolved Date/Notes
    columns so it can double as a live punch-list.

SHEET LAYOUT

    Summary            -- cover/scope identity, executive KPIs, results by
                           ruleset, top failed rules.
    <Element type>      -- one sheet per ``ReportModel.element_type_sheets``
                           entry (Doors, Windows, Stairs, Walls, Spaces, ...),
                           every rule x element result for that type.
"""

from __future__ import annotations

import io
import re

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet

from app.modules.contracts import ReportElementTypeSheetContract, ReportModel

#: Literal light-mode hex values mirrored from frontend/src/app.css, same
#: source ``report_charts.py`` draws from -- the workbook, the PDF and the
#: in-app preview all read the same palette rather than three different ones.
_FG_PRIMARY = "0F172A"
_HEADER_FILL = "0066CC"
_HEADER_FONT = "FFFFFF"

_SEVERITY_FILL = {"mandatory": "FFE4E6", "recommended": "E0E7FF"}
_SEVERITY_FONT = {"mandatory": "BE123C", "recommended": "4338CA"}
_RELIABILITY_FILL = {"high": "D1FAE5", "medium": "FEF3C7", "low": "F1F5F9"}
_RELIABILITY_FONT = {"high": "047857", "medium": "B45309", "low": "64748B"}
_RESULT_FILL = {"pass": "D1FAE5", "fail": "FFE4E6", "unable_to_verify": "F1F5F9", "waived": "FEF3C7"}
_RESULT_FONT = {"pass": "047857", "fail": "BE123C", "unable_to_verify": "64748B", "waived": "B45309"}
_RESULT_LABEL = {"pass": "Pass", "fail": "Fail", "unable_to_verify": "Unable to Verify", "waived": "Waived"}

_STATUS_OPTIONS = ("Open", "In Progress", "Resolved", "Won't Fix")

_ELEMENT_SHEET_HEADERS = (
    "Element Name", "Element GUID", "Storey", "Rule Reference", "Rule Description",
    "Ruleset", "IFC Property", "Measured", "Required", "Difference", "Result",
    "Severity", "Reliability", "Citation", "Action Required", "Assignee Role",
    "Status", "Assigned To", "Resolved Date", "Notes",
)  # fmt: skip

_INVALID_SHEET_NAME_CHARS = re.compile(r"[:\\/?*\[\]]")


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


def _safe_sheet_name(name: str, used: set[str]) -> str:
    r"""Excel sheet names: <=31 chars, no ``: \ / ? * [ ]``, unique within the workbook."""
    cleaned = _INVALID_SHEET_NAME_CHARS.sub("-", name).strip() or "Sheet"
    base = cleaned[:31]
    candidate = base
    suffix = 2
    while candidate.casefold() in used:
        trimmed = base[: 31 - len(f" ({suffix})")]
        candidate = f"{trimmed} ({suffix})"
        suffix += 1
    used.add(candidate.casefold())
    return candidate


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

    ws.cell(row=row, column=1, value="Element Types in This Workbook").font = Font(
        bold=True, size=12, color=_FG_PRIMARY
    )
    row += 1
    for col, text in enumerate(("Sheet", "Passed", "Failed", "Unable to Verify", "Waived"), start=1):
        cell = ws.cell(row=row, column=col, value=text)
        cell.font = _header_font()
        cell.fill = _header_fill()
    row += 1
    for sheet in model.element_type_sheets:
        ws.cell(row=row, column=1, value=sheet.type_label)
        ws.cell(row=row, column=2, value=sheet.passed)
        ws.cell(row=row, column=3, value=sheet.failed)
        ws.cell(row=row, column=4, value=sheet.unable_to_verify)
        ws.cell(row=row, column=5, value=sheet.waived)
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


def _build_element_type_sheet(
    wb: Workbook, sheet_model: ReportElementTypeSheetContract, used_names: set[str]
) -> None:
    ws = wb.create_sheet(_safe_sheet_name(sheet_model.type_label, used_names))
    _write_header_row(ws, 1, _ELEMENT_SHEET_HEADERS)
    _autosize(
        ws,
        {
            1: 20, 2: 16, 3: 14, 4: 20, 5: 30, 6: 18, 7: 26, 8: 14, 9: 16, 10: 12,
            11: 16, 12: 12, 13: 12, 14: 40, 15: 40, 16: 16, 17: 16, 18: 16, 19: 16, 20: 30,
        },
    )

    status_col = _ELEMENT_SHEET_HEADERS.index("Status") + 1
    dv = DataValidation(
        type="list",
        formula1=f'"{",".join(_STATUS_OPTIONS)}"',
        allow_blank=True,
        showDropDown=False,
    )
    ws.add_data_validation(dv)

    row = 2
    for r in sheet_model.rows:
        ws.cell(row=row, column=1, value=r.element_name)
        ws.cell(row=row, column=2, value=r.element_guid)
        ws.cell(row=row, column=3, value=r.storey)
        ws.cell(row=row, column=4, value=r.rule_reference)
        ws.cell(row=row, column=5, value=r.rule_description)
        ws.cell(row=row, column=6, value=r.ruleset_name)
        ws.cell(row=row, column=7, value=r.ifc_property)
        ws.cell(row=row, column=8, value=r.measured)
        ws.cell(row=row, column=9, value=r.required)
        ws.cell(row=row, column=10, value=r.difference)
        result_cell = ws.cell(row=row, column=11, value=_RESULT_LABEL.get(r.result, r.result))
        _fill_badge(result_cell, r.result, _RESULT_FILL, _RESULT_FONT)
        sev_cell = ws.cell(row=row, column=12, value=r.severity)
        _fill_badge(sev_cell, r.severity, _SEVERITY_FILL, _SEVERITY_FONT)
        rel_cell = ws.cell(row=row, column=13, value=r.reliability)
        _fill_badge(rel_cell, r.reliability, _RELIABILITY_FILL, _RELIABILITY_FONT)
        ws.cell(row=row, column=14, value=r.citation)
        ws.cell(row=row, column=15, value=r.action_required)
        ws.cell(row=row, column=16, value=r.assignee_role)
        status_cell = ws.cell(row=row, column=status_col, value="Open" if r.result == "fail" else "")
        dv.add(status_cell)
        # Assigned To / Resolved Date / Notes are left blank for the user.
        row += 1

    if not sheet_model.rows:
        ws.cell(row=2, column=1, value="No rules were evaluated against this element type.")


def render_report_excel(model: ReportModel) -> bytes:
    """Render ``model`` to an .xlsx workbook: Summary, then one sheet per IFC element type."""
    wb = Workbook()
    # The default sheet Workbook() creates is replaced by the sheets built
    # below, in display order, so "Summary" opens first rather than a blank
    # "Sheet".
    wb.remove(wb.active)

    _build_summary_sheet(wb, model)
    used_names = {"summary"}
    for sheet_model in model.element_type_sheets:
        _build_element_type_sheet(wb, sheet_model, used_names)

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
