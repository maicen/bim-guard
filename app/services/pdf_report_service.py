"""Render a rule-configuration snapshot as a structured PDF spec sheet.

Configuration only — reference/target/property/operator/values/severity —
never analysis results. Uses reportlab (already a pyproject.toml
dependency; previously unused anywhere in app/).
"""

from __future__ import annotations

import io
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_COLUMNS = [
    ("reference", "Reference"),
    ("target_ifc_class", "Target IFC Class"),
    ("property_set", "Property Set"),
    ("property_name", "Property"),
    ("operator", "Operator"),
    ("check_value", "Check Value"),
    ("value_min", "Min"),
    ("value_max", "Max"),
    ("unit", "Unit"),
    ("severity", "Severity"),
]


def render_snapshot_pdf(snapshot: dict[str, Any], rules: list[dict[str, Any]]) -> bytes:
    """Return PDF bytes for one snapshot's frozen rule configuration."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=f"BIM-Guard Rule Configuration - {snapshot.get('name', '')}",
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"BIM-Guard Rule Configuration: {snapshot.get('name', '')}", styles["Title"]),
        Paragraph(
            f"Source ruleset: {snapshot.get('source_ruleset_id', '')} | "
            f"Mode: {snapshot.get('source_mode', '')} | "
            f"Category: {snapshot.get('category', '')} | "
            f"Snapshot date: {snapshot.get('created_at', '')} | "
            f"Rule count: {snapshot.get('rule_count', len(rules))}",
            styles["Normal"],
        ),
        Spacer(1, 8 * mm),
    ]

    header = [label for _, label in _COLUMNS]
    data = [header]
    for r in rules:
        row = []
        for key, _ in _COLUMNS:
            value = r.get(key)
            row.append("" if value is None else str(value))
        data.append(row)

    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0071e3")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(table)

    doc.build(story)
    return buffer.getvalue()
