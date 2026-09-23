"""Render a :class:`ReportModel` to a flat, uncapped CSV.

The CSV twin of ``report_excel.py``'s per-element-type sheets: one row per
(element, rule) result -- pass, fail, or unable to verify, not just
failures -- with the same blank Status/Assigned To/Resolved Date/Notes
columns so it can double as a working punch-list. Unlike the workbook, which
splits rows across one sheet per IFC element type, this is a single flat
file, so it carries an added "Element Type" column to keep that context.

This is deliberately not the same export as ``/api/analyze/export?fmt=csv``
(``app.modules.pipeline_io.analysis_result_exporter``), which serves an
unscoped, whole-project asset register built from ``audit_issues``. This one
is built from the same ``ReportModel`` as the PDF/XLSX report, so it can be
ruleset-scoped the same way they are.
"""

from __future__ import annotations

import csv
import io

from app.modules.contracts import ReportModel

_HEADERS = (
    "Element Type", "Element Name", "Element GUID", "Storey", "Rule Reference",
    "Rule Description", "Ruleset", "IFC Property", "Measured", "Required",
    "Difference", "Result", "Severity", "Reliability", "Citation",
    "Action Required", "Assignee Role", "Status", "Assigned To",
    "Resolved Date", "Notes",
)  # fmt: skip

_RESULT_LABEL = {"pass": "Pass", "fail": "Fail", "unable_to_verify": "Unable to Verify", "waived": "Waived"}


def render_report_csv(model: ReportModel) -> bytes:
    """Render every element-type sheet's rows into one flat, uncapped CSV."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_HEADERS)

    for sheet in model.element_type_sheets:
        for row in sheet.rows:
            writer.writerow(
                [
                    sheet.type_label,
                    row.element_name,
                    row.element_guid,
                    row.storey,
                    row.rule_reference,
                    row.rule_description,
                    row.ruleset_name,
                    row.ifc_property,
                    row.measured,
                    row.required,
                    row.difference,
                    _RESULT_LABEL.get(row.result, row.result),
                    row.severity,
                    row.reliability,
                    row.citation,
                    row.action_required,
                    row.assignee_role,
                    "Open" if row.result == "fail" else "",
                    "",
                    "",
                    "",
                ]
            )

    return buffer.getvalue().encode("utf-8-sig")
