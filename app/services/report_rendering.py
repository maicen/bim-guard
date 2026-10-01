"""Render a :class:`ReportModel` to HTML and PDF.

RENDERING ENGINES:
    - HTML: Jinja2 template (`app/services/templates/report.html.j2`) for fast in-app web preview.
    - PDF: ReportLab (`SimpleDocTemplate`, `Table`, `Paragraph`) for fast, deterministic,
      zero-browser PDF generation without Chromium, Node, or Playwright dependencies.
"""

from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from jinja2 import Environment, FileSystemLoader, select_autoescape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.modules.contracts import ReportModel

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_TEMPLATE_NAME = "report.html.j2"


@lru_cache(maxsize=1)
def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
    )


def render_report_html(model: ReportModel, *, render_target: str = "full") -> str:
    """Render ``model`` to an HTML string for the in-app browser preview.

    Args:
        render_target: ``"full"`` (cover + body), ``"cover"``, or ``"body"``.
    """
    template = _environment().get_template(_TEMPLATE_NAME)
    return template.render(render_target=render_target, **model.model_dump())


# ---------------------------------------------------------------------------
# ReportLab Canvas with Running Header & Two-Pass Dynamic Page Numbers
# ---------------------------------------------------------------------------


class _NumberedReportCanvas(canvas.Canvas):
    """Canvas that computes total page count dynamically and paints header/footer."""

    _doc_title: str = "BIM Guard Compliance Report"
    _analysis_date: str = ""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict[str, Any]] = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_decorations(num_pages)
            super().showPage()
        super().save()

    def _draw_decorations(self, total_pages: int) -> None:
        # Page 1 is the cover page -- omit running header and footer
        if self._pageNumber == 1:
            return

        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        page_width, page_height = A4

        # Header
        self.drawString(18 * mm, page_height - 12 * mm, self._doc_title)
        self.drawRightString(page_width - 18 * mm, page_height - 12 * mm, "BIM Guard Compliance Report")
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.5)
        self.line(18 * mm, page_height - 14 * mm, page_width - 18 * mm, page_height - 14 * mm)

        # Footer
        self.line(18 * mm, 14 * mm, page_width - 18 * mm, 14 * mm)
        self.drawString(18 * mm, 9 * mm, self._analysis_date)
        page_label = f"Page {self._pageNumber} of {total_pages}"
        self.drawRightString(page_width - 18 * mm, 9 * mm, page_label)
        self.restoreState()


def _make_canvas_factory(doc_title: str, analysis_date: str):
    class _ConfiguredCanvas(_NumberedReportCanvas):
        _doc_title = doc_title
        _analysis_date = analysis_date

    return _ConfiguredCanvas


# ---------------------------------------------------------------------------
# ReportLab PDF Report Generator
# ---------------------------------------------------------------------------


def render_report_pdf(model: ReportModel) -> bytes:
    """Render ``model`` to a structured, paginated PDF report using ReportLab.

    Returns:
        Generated PDF content as bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"BIM Guard Compliance Report - {model.cover.project_name}",
        author="BIM Guard",
    )

    base_styles = getSampleStyleSheet()

    # Custom semantic typographic styles
    style_cover_brand = ParagraphStyle(
        "CoverBrand",
        parent=base_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#0066cc"),
    )
    style_cover_title = ParagraphStyle(
        "CoverTitle",
        parent=base_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        textColor=colors.HexColor("#0f172a"),
    )
    style_cover_subtitle = ParagraphStyle(
        "CoverSubtitle",
        parent=base_styles["Normal"],
        fontName="Helvetica",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#64748b"),
    )
    style_h1 = ParagraphStyle(
        "ReportH1",
        parent=base_styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=6,
    )
    style_h2 = ParagraphStyle(
        "ReportH2",
        parent=base_styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=8,
        spaceAfter=4,
    )
    style_body = ParagraphStyle(
        "ReportBody",
        parent=base_styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
    )
    style_body_muted = ParagraphStyle(
        "ReportBodyMuted",
        parent=base_styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#64748b"),
    )
    style_table_cell = ParagraphStyle(
        "ReportTableCell",
        parent=base_styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#334155"),
    )
    style_table_header = ParagraphStyle(
        "ReportTableHeader",
        parent=base_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#475569"),
    )
    style_kpi_value = ParagraphStyle(
        "KpiValue",
        parent=base_styles["Normal"],
        alignment=1,  # Center
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#0f172a"),
    )
    style_kpi_label = ParagraphStyle(
        "KpiLabel",
        parent=base_styles["Normal"],
        alignment=1,  # Center
        fontName="Helvetica",
        fontSize=6.5,
        leading=9,
        textColor=colors.HexColor("#64748b"),
    )
    style_citation = ParagraphStyle(
        "ReportCitation",
        parent=base_styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#64748b"),
    )

    story: list[Any] = []

    # =========================================================================
    # 1. COVER PAGE
    # =========================================================================
    story.append(Paragraph("BIM GUARD", style_cover_brand))
    story.append(Spacer(1, 35 * mm))
    story.append(Paragraph(escape(model.cover.project_name or "Compliance Report"), style_cover_title))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Architectural Compliance Report", style_cover_subtitle))
    story.append(Spacer(1, 15 * mm))

    cover_meta = [
        ("Project code", model.cover.project_code or "—"),
        ("Model file", model.cover.model_file_name or "—"),
        ("Report ID", model.cover.report_id or "—"),
        ("Analysis date", model.cover.analysis_date or "—"),
        ("Discipline", model.cover.discipline or "Architecture"),
        ("IFC schema", model.cover.ifc_schema or "—"),
        ("Suitability code", model.cover.suitability_code or "—"),
        ("Revision / CDE state", f"{model.cover.revision_code or '—'} / {model.cover.cde_state or '—'}"),
        ("ISO 19650 document ID", model.cover.document_id or "—"),
    ]
    cover_table_data = [
        [
            Paragraph(f"<font color='#64748b'>{escape(k)}</font>", style_table_cell),
            Paragraph(f"<b>{escape(v)}</b>", style_table_cell),
        ]
        for k, v in cover_meta
    ]
    cover_table = Table(cover_table_data, colWidths=[55 * mm, 115 * mm])
    cover_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(cover_table)

    story.append(Spacer(1, 35 * mm))
    story.append(
        Paragraph(
            "Generated by BIM Guard · Deterministic, database-driven compliance analysis · "
            "Not a certification of compliance",
            style_body_muted,
        )
    )
    story.append(PageBreak())

    # =========================================================================
    # 2. EXECUTIVE SUMMARY
    # =========================================================================
    story.append(Paragraph("Executive Summary", style_h1))
    if model.executive_summary.narrative:
        story.append(Paragraph(escape(model.executive_summary.narrative), style_body))
        story.append(Spacer(1, 4 * mm))

    # KPI Summary Cards (2 rows x 4 columns)
    kpis = [
        ("ELEMENTS EVALUATED", str(model.executive_summary.unique_elements_evaluated)),
        ("RULES EXECUTED", str(model.executive_summary.rules_executed)),
        ("CHECKS RUN", str(model.executive_summary.checks_run)),
        ("VERIFIED PASS RATE", f"{model.executive_summary.pass_rate:.1f}%"),
        ("PASSED", str(model.executive_summary.passed)),
        ("FAILED", str(model.executive_summary.failed)),
        ("UNABLE TO VERIFY", str(model.executive_summary.unable_to_verify)),
        ("MANDATORY FAILED", str(model.executive_summary.mandatory_failed)),
    ]
    kpi_cells: list[list[Any]] = [[], []]
    for idx, (label, val) in enumerate(kpis):
        row = idx // 4
        cell_content = [
            Spacer(1, 2 * mm),
            Paragraph(escape(val), style_kpi_value),
            Spacer(1, 1 * mm),
            Paragraph(escape(label), style_kpi_label),
            Spacer(1, 2 * mm),
        ]
        kpi_cells[row].append(cell_content)

    kpi_table = Table(kpi_cells, colWidths=[42.5 * mm] * 4)
    kpi_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(kpi_table)
    story.append(Spacer(1, 5 * mm))

    # Top 5 failed rules
    story.append(Paragraph("Top Failed Rules", style_h2))
    if model.executive_summary.top_failed_rules:
        top_rules_data = [
            [
                Paragraph("<b>RULE</b>", style_table_header),
                Paragraph("<b>DESCRIPTION</b>", style_table_header),
                Paragraph("<b>FAILURES</b>", style_table_header),
            ]
        ]
        for tr in model.executive_summary.top_failed_rules:
            top_rules_data.append(
                [
                    Paragraph(escape(tr.rule_reference), style_table_cell),
                    Paragraph(escape(tr.rule_description), style_table_cell),
                    Paragraph(str(tr.fail_count), style_table_cell),
                ]
            )
        top_rules_table = Table(top_rules_data, colWidths=[35 * mm, 115 * mm, 20 * mm], repeatRows=1)
        top_rules_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#cbd5e1")),
                    ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor("#f1f5f9")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(top_rules_table)
    else:
        story.append(Paragraph("<i>No failed rules.</i>", style_body_muted))

    story.append(PageBreak())

    # =========================================================================
    # 3. SCOPE & DOCUMENT CONTROL
    # =========================================================================
    story.append(Paragraph("Scope & Document Control", style_h1))
    story.append(Paragraph("Model & Analysis Scope", style_h2))

    scope_meta = [
        ("Model file", model.scope.model_file_name or "—"),
        ("IFC schema", model.scope.ifc_schema or "—"),
        ("Element count", str(model.scope.element_count)),
        ("Storey count", str(model.scope.storey_count) if model.scope.storey_count is not None else "—"),
        ("Rulesets applied", ", ".join(model.scope.ruleset_names) if model.scope.ruleset_names else "—"),
    ]
    scope_table_data = [
        [
            Paragraph(f"<font color='#64748b'>{escape(k)}</font>", style_table_cell),
            Paragraph(escape(v), style_table_cell),
        ]
        for k, v in scope_meta
    ]
    scope_table = Table(scope_table_data, colWidths=[55 * mm, 115 * mm])
    scope_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#f1f5f9")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(scope_table)
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Document Control", style_h2))
    doc_control_meta = [
        ("Model hash", model.scope.model_hash or "Pending — not yet recorded per analysis run"),
        ("Rule database version", model.scope.rule_database_version or "Pending — not yet recorded per analysis run"),
        ("Engine version", model.scope.engine_version or "Pending — not yet recorded per analysis run"),
        ("Generated at", model.scope.generated_at or "—"),
        ("Generated by", model.scope.generated_by or "—"),
    ]
    doc_control_data = [
        [
            Paragraph(f"<font color='#64748b'>{escape(k)}</font>", style_table_cell),
            Paragraph(escape(v), style_table_cell),
        ]
        for k, v in doc_control_meta
    ]
    doc_control_table = Table(doc_control_data, colWidths=[55 * mm, 115 * mm])
    doc_control_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#f1f5f9")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(doc_control_table)
    story.append(PageBreak())

    # =========================================================================
    # 4. RESULTS BY RULESET
    # =========================================================================
    story.append(Paragraph("Results by Ruleset", style_h1))
    if model.results_by_ruleset:
        ruleset_headers = [
            Paragraph("<b>RULESET</b>", style_table_header),
            Paragraph("<b>SOURCE</b>", style_table_header),
            Paragraph("<b>RULES</b>", style_table_header),
            Paragraph("<b>PASSED</b>", style_table_header),
            Paragraph("<b>FAILED</b>", style_table_header),
            Paragraph("<b>UNVERIFIED</b>", style_table_header),
            Paragraph("<b>PASS RATE</b>", style_table_header),
        ]
        ruleset_data = [ruleset_headers]
        for rs in model.results_by_ruleset:
            ruleset_data.append(
                [
                    Paragraph(f"<b>{escape(rs.ruleset_name)}</b>", style_table_cell),
                    Paragraph(escape(rs.source_citation or "—"), style_table_cell),
                    Paragraph(str(rs.rule_count), style_table_cell),
                    Paragraph(str(rs.passed), style_table_cell),
                    Paragraph(str(rs.failed), style_table_cell),
                    Paragraph(str(rs.unable_to_verify), style_table_cell),
                    Paragraph(f"{rs.pass_rate:.1f}%", style_table_cell),
                ]
            )
        ruleset_table = Table(
            ruleset_data,
            colWidths=[40 * mm, 45 * mm, 15 * mm, 18 * mm, 18 * mm, 18 * mm, 16 * mm],
            repeatRows=1,
        )
        ruleset_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#cbd5e1")),
                    ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(ruleset_table)
    else:
        story.append(Paragraph("<i>No rulesets were evaluated in this run.</i>", style_body_muted))

    story.append(PageBreak())

    # =========================================================================
    # 5. PRIORITY FINDINGS
    # =========================================================================
    story.append(Paragraph("Priority Findings", style_h1))
    if model.priority_findings:
        for pf in model.priority_findings:
            finding_flowables: list[Any] = []

            # Card Title & Badges
            title_text = f"<b>{escape(pf.rule_reference)} — {escape(pf.element_name)}</b>"
            badge_text = f"<font color='#be123c'><b>{escape(pf.severity.upper())}</b></font> · <font color='#64748b'>{escape(pf.reliability)} reliability</font>"
            head_table = Table(
                [[Paragraph(title_text, style_h2), Paragraph(badge_text, style_table_cell)]],
                colWidths=[120 * mm, 50 * mm],
            )
            head_table.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ]
                )
            )
            finding_flowables.append(head_table)

            if pf.rule_description:
                finding_flowables.append(Paragraph(escape(pf.rule_description), style_body))
                finding_flowables.append(Spacer(1, 2 * mm))

            # Metric tiles (Measured, Required, Difference, Storey)
            metric_data = [
                [
                    Paragraph(f"<font size='6.5' color='#64748b'>MEASURED</font><br/><b>{escape(pf.measured or '—')}</b>", style_table_cell),
                    Paragraph(f"<font size='6.5' color='#64748b'>REQUIRED</font><br/><b>{escape(pf.required or '—')}</b>", style_table_cell),
                    Paragraph(f"<font size='6.5' color='#64748b'>DIFFERENCE</font><br/><b>{escape(pf.difference or '—')}</b>", style_table_cell),
                    Paragraph(f"<font size='6.5' color='#64748b'>STOREY</font><br/><b>{escape(pf.storey or '—')}</b>", style_table_cell),
                ]
            ]
            metric_table = Table(metric_data, colWidths=[42.5 * mm] * 4)
            metric_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ]
                )
            )
            finding_flowables.append(metric_table)
            finding_flowables.append(Spacer(1, 2 * mm))

            if pf.citation:
                finding_flowables.append(Paragraph(f"Citation: {escape(pf.citation)}", style_citation))

            prop_line = f"IFC property: {escape(pf.ifc_property or '—')}"
            if pf.reliability_reason:
                prop_line += f" — {escape(pf.reliability_reason)}"
            finding_flowables.append(Paragraph(prop_line, style_body_muted))
            finding_flowables.append(Spacer(1, 1 * mm))

            if pf.action_required:
                action_text = (
                    f"<b>Action required:</b> {escape(pf.action_required)} "
                    f"<font color='#64748b'>(assignee: {escape(pf.assignee_role or 'BIM coordinator')})</font>"
                )
                action_table = Table([[Paragraph(action_text, style_table_cell)]], colWidths=[170 * mm])
                action_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
                            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                            ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ]
                    )
                )
                finding_flowables.append(action_table)

            finding_flowables.append(Spacer(1, 5 * mm))
            finding_flowables.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0"), spaceAfter=5 * mm))
            story.append(KeepTogether(finding_flowables))
    else:
        story.append(
            Paragraph(
                "<i>No failures to prioritize — every checked rule passed or could not be evaluated.</i>",
                style_body_muted,
            )
        )

    story.append(PageBreak())

    # =========================================================================
    # 6. FINDINGS REGISTER
    # =========================================================================
    story.append(Paragraph("Findings Register", style_h1))
    reg_subtitle = f"Showing {len(model.findings_register)} of {model.findings_register_total} failed findings, most severe first."
    if model.findings_register_truncated:
        reg_subtitle += " Full register is available in the CSV/Excel export."
    story.append(Paragraph(reg_subtitle, style_body_muted))
    story.append(Spacer(1, 3 * mm))

    if model.findings_register:
        reg_headers = [
            Paragraph("<b>ELEMENT</b>", style_table_header),
            Paragraph("<b>STOREY</b>", style_table_header),
            Paragraph("<b>RULE</b>", style_table_header),
            Paragraph("<b>MEASURED</b>", style_table_header),
            Paragraph("<b>REQUIRED</b>", style_table_header),
            Paragraph("<b>DIFF</b>", style_table_header),
            Paragraph("<b>SEVERITY</b>", style_table_header),
        ]
        reg_data = [reg_headers]
        for fr in model.findings_register:
            sev_color = "#be123c" if fr.severity == "mandatory" else "#b45309"
            sev_badge = f"<font color='{sev_color}'><b>{escape(fr.severity)}</b></font>"
            reg_data.append(
                [
                    Paragraph(escape(fr.element_name), style_table_cell),
                    Paragraph(escape(fr.storey or "—"), style_table_cell),
                    Paragraph(escape(fr.rule_reference), style_table_cell),
                    Paragraph(escape(fr.measured), style_table_cell),
                    Paragraph(escape(fr.required), style_table_cell),
                    Paragraph(escape(fr.difference), style_table_cell),
                    Paragraph(sev_badge, style_table_cell),
                ]
            )
        reg_table = Table(
            reg_data,
            colWidths=[35 * mm, 20 * mm, 25 * mm, 25 * mm, 25 * mm, 20 * mm, 20 * mm],
            repeatRows=1,
        )
        reg_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#cbd5e1")),
                    ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor("#f1f5f9")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(reg_table)
    else:
        story.append(Paragraph("<i>No failed findings.</i>", style_body_muted))

    story.append(PageBreak())

    # =========================================================================
    # 7. CHECKS THAT COULD NOT BE VERIFIED
    # =========================================================================
    story.append(Paragraph("Checks That Could Not Be Verified", style_h1))
    story.append(
        Paragraph(
            "These rules are not counted as failures — the model did not carry enough data to evaluate them.",
            style_body_muted,
        )
    )
    story.append(Spacer(1, 3 * mm))

    if model.unable_to_verify:
        uv_headers = [
            Paragraph("<b>RULE</b>", style_table_header),
            Paragraph("<b>DESCRIPTION</b>", style_table_header),
            Paragraph("<b>REASON</b>", style_table_header),
            Paragraph("<b>AFFECTED</b>", style_table_header),
        ]
        uv_data = [uv_headers]
        for uv in model.unable_to_verify:
            uv_data.append(
                [
                    Paragraph(escape(uv.rule_reference), style_table_cell),
                    Paragraph(escape(uv.rule_description), style_table_cell),
                    Paragraph(escape(uv.reason), style_table_cell),
                    Paragraph(str(uv.affected_count), style_table_cell),
                ]
            )
        uv_table = Table(uv_data, colWidths=[30 * mm, 70 * mm, 50 * mm, 20 * mm], repeatRows=1)
        uv_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#cbd5e1")),
                    ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor("#f1f5f9")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(uv_table)
    else:
        story.append(Paragraph("<i>Every rule could be verified against this model.</i>", style_body_muted))

    story.append(PageBreak())

    # =========================================================================
    # 8. RULE REGISTER
    # =========================================================================
    story.append(Paragraph("Rule Register", style_h1))
    story.append(
        Paragraph("Full traceability: finding → rule → clause → IFC property.", style_body_muted)
    )
    story.append(Spacer(1, 3 * mm))

    if model.rule_register:
        rr_headers = [
            Paragraph("<b>RULE &amp; DESCRIPTION</b>", style_table_header),
            Paragraph("<b>CITATION</b>", style_table_header),
            Paragraph("<b>IFC PROPERTY</b>", style_table_header),
            Paragraph("<b>RELIABILITY</b>", style_table_header),
            Paragraph("<b>STATUS</b>", style_table_header),
            Paragraph("<b>FAIL / TOTAL</b>", style_table_header),
        ]
        rr_data = [rr_headers]
        for rr in model.rule_register:
            status_color = "#be123c" if rr.status == "FAIL" else ("#047857" if rr.status == "PASS" else "#64748b")
            status_text = f"<font color='{status_color}'><b>{escape(rr.status)}</b></font>"
            rr_data.append(
                [
                    Paragraph(f"<b>{escape(rr.rule_reference)}</b><br/><font size='7' color='#64748b'>{escape(rr.rule_description)}</font>", style_table_cell),
                    Paragraph(escape(rr.citation), style_table_cell),
                    Paragraph(escape(rr.ifc_property), style_table_cell),
                    Paragraph(escape(rr.reliability), style_table_cell),
                    Paragraph(status_text, style_table_cell),
                    Paragraph(f"{rr.fail_count} / {rr.total_count}", style_table_cell),
                ]
            )
        rr_table = Table(
            rr_data,
            colWidths=[45 * mm, 35 * mm, 30 * mm, 20 * mm, 20 * mm, 20 * mm],
            repeatRows=1,
        )
        rr_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#cbd5e1")),
                    ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor("#f1f5f9")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(rr_table)
    else:
        story.append(Paragraph("<i>No rules were executed in this run.</i>", style_body_muted))

    story.append(PageBreak())

    # =========================================================================
    # 9. METHODOLOGY & LIMITATIONS
    # =========================================================================
    story.append(Paragraph("Methodology & Limitations", style_h1))
    story.append(
        Paragraph(
            "This report is produced entirely deterministically: every number is read directly from the "
            "compliance analysis run, and every sentence is filled from a fixed template — no language model "
            "is used to generate, summarize, or interpret any result in this document.",
            style_body,
        )
    )
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Reliability Tiers", style_h2))
    tiers_data = [
        [
            Paragraph("<b>TIER</b>", style_table_header),
            Paragraph("<b>MEANING</b>", style_table_header),
        ],
        [
            Paragraph("<font color='#047857'><b>high</b></font>", style_table_cell),
            Paragraph(
                "Read from an IFC schema attribute, the element's own type, or an explicit stored relationship — "
                "authored data BIM Guard cannot get wrong.",
                style_table_cell,
            ),
        ],
        [
            Paragraph("<font color='#b45309'><b>medium</b></font>", style_table_cell),
            Paragraph(
                "Read from a standard property set — true if found, but depends on the authoring tool having exported it.",
                style_table_cell,
            ),
        ],
        [
            Paragraph("<font color='#64748b'><b>low</b></font>", style_table_cell),
            Paragraph(
                "Estimated by BIM Guard's own geometry engine, or not standard IFC data at all (a project-specific "
                "or manufacturer field) — can be wrong even when it looks plausible.",
                style_table_cell,
            ),
        ],
    ]
    tiers_table = Table(tiers_data, colWidths=[25 * mm, 145 * mm])
    tiers_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#cbd5e1")),
                ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor("#f1f5f9")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(tiers_table)
    story.append(Spacer(1, 6 * mm))

    disclaimer_text = (
        "<b>Important Disclaimer:</b> This report is a compliance <i>analysis</i>, not a certification. "
        "It reflects what the supplied IFC model contains at the time of analysis, checked against the rulesets "
        "selected for this project. It does not constitute regulatory approval, and a professional review remains "
        "required before any finding here is treated as a basis for design or construction decisions."
    )
    disclaimer_table = Table([[Paragraph(disclaimer_text, style_body_muted)]], colWidths=[170 * mm])
    disclaimer_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(disclaimer_table)

    # Build PDF with dynamic header/footer canvas
    canvas_maker = _make_canvas_factory(
        doc_title=model.cover.project_name or "BIM Guard Compliance Report",
        analysis_date=model.cover.analysis_date or "",
    )
    doc.build(story, canvasmaker=canvas_maker)
    return buffer.getvalue()

