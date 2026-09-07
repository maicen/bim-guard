"""Generate the Module 1 stair-code test fixture PDF.

app/modules/tests/test_document_parsing.py (TestUnstructuredExtractor) and the
Module 1 setup docs (app/modules/tests/TEST_README.md) expect a real,
structured code-style PDF at app/modules/tests/fixtures/sample_obc_stairs.pdf
so the PDF-extraction tests can exercise SectionChunker's dotted-decimal
heading detection, table extraction, and the keyword_master term list against
real stair/landing/guard/handrail clauses instead of being skipped.

The clause text and table data are not hardcoded here -- they live in
app/modules/tests/fixtures/sample_obc_stairs_content.json (an original,
fictional test code -- NOT a reproduction of any real building code -- with
just the right shape: dotted-decimal Article/Sentence numbering, a dimensions
table, "shall" deontic language, and BIM-Guard's own stair/landing/guard/
handrail keyword vocabulary). This script only renders that JSON into a PDF.

Usage: uv run python scripts/generate_stair_test_fixture_pdf.py
Output: app/modules/tests/fixtures/sample_obc_stairs.pdf
"""

from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

CONTENT_PATH = Path("app/modules/tests/fixtures/sample_obc_stairs_content.json")
OUTPUT_PATH = Path("app/modules/tests/fixtures/sample_obc_stairs.pdf")

styles = getSampleStyleSheet()
heading_style = ParagraphStyle("clauseHeading", parent=styles["Normal"], fontSize=10, leading=13, spaceBefore=6, spaceAfter=2, fontName="Helvetica-Bold")
body_style = ParagraphStyle("clauseBody", parent=styles["Normal"], fontSize=9.5, leading=13)
notice_style = ParagraphStyle("notice", parent=styles["Italic"], fontSize=8, textColor=colors.HexColor("#666666"))


def render_table(header: list[str], rows: list[list[str]]) -> Table:
    data = [header] + rows
    t = Table(
        [[Paragraph(str(c), body_style) for c in row] for row in data],
        colWidths=[35 * mm, 27 * mm, 27 * mm, 27 * mm, 27 * mm],
    )
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def render_block(block: dict) -> list:
    block_type = block["type"]
    if block_type == "heading":
        return [Paragraph(f"{block['number']}.  {block['title']}", heading_style)]
    if block_type == "clause":
        return [Paragraph(block["text"], body_style)]
    if block_type == "table":
        return [Spacer(1, 2 * mm), render_table(block["header"], block["rows"]), Spacer(1, 3 * mm)]
    raise ValueError(f"Unknown content block type: {block_type!r}")


def build_pdf() -> None:
    content = json.loads(CONTENT_PATH.read_text(encoding="utf-8"))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUTPUT_PATH),
        pagesize=LETTER,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="BIM-Guard Test Fixture - Stairs, Landings, Guards and Handrails",
    )

    story = [
        Paragraph(content["title"], styles["Title"]),
        Paragraph(content["notice"], notice_style),
        Spacer(1, 6 * mm),
    ]
    for block in content["blocks"]:
        story.extend(render_block(block))

    doc.build(story)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    build_pdf()
