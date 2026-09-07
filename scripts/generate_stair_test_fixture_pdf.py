"""Generate the Module 1 stair-code test fixture PDF.

app/modules/tests/test_document_parsing.py (TestUnstructuredExtractor) and the
Module 1 setup docs (app/modules/tests/TEST_README.md) expect a real,
structured code-style PDF at app/modules/tests/fixtures/sample_obc_stairs.pdf
so the PDF-extraction tests can exercise SectionChunker's dotted-decimal
heading detection, table extraction, and the keyword_master term list against
real stair/landing/guard/handrail clauses instead of being skipped.

The content here is an original, fictional test code -- NOT a reproduction of
any real building code -- written only to have the right shape (dotted-decimal
Article/Sentence numbering, a dimensions table, "shall" deontic language, and
BIM-Guard's own stair/landing/guard/handrail keyword vocabulary).

Usage: uv run python scripts/generate_stair_test_fixture_pdf.py
Output: app/modules/tests/fixtures/sample_obc_stairs.pdf
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUTPUT_PATH = Path("app/modules/tests/fixtures/sample_obc_stairs.pdf")

styles = getSampleStyleSheet()
heading_style = ParagraphStyle("clauseHeading", parent=styles["Normal"], fontSize=10, leading=13, spaceBefore=6, spaceAfter=2, fontName="Helvetica-Bold")
body_style = ParagraphStyle("clauseBody", parent=styles["Normal"], fontSize=9.5, leading=13)
notice_style = ParagraphStyle("notice", parent=styles["Italic"], fontSize=8, textColor=colors.HexColor("#666666"))

DIMENSION_TABLE_ROWS = [
    ["Stair Type", "Max. Rise (mm)", "Min. Rise (mm)", "Max. Run (mm)", "Min. Run (mm)"],
    ["Private stairs", "200", "125", "355", "255"],
    ["Public stairs", "180", "125", "no limit", "280"],
    ["Service stairs", "no limit", "125", "355", "no limit"],
]


def make_table() -> Table:
    t = Table([[Paragraph(c, body_style) for c in row] for row in DIMENSION_TABLE_ROWS], colWidths=[35 * mm, 27 * mm, 27 * mm, 27 * mm, 27 * mm])
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


def H(number: str, title: str) -> Paragraph:
    return Paragraph(f"{number}.  {title}", heading_style)


def B(text: str) -> Paragraph:
    return Paragraph(text, body_style)


def build_pdf() -> None:
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
        Paragraph("9.8  STAIRS, LANDINGS, GUARDS AND HANDRAILS", styles["Title"]),
        Paragraph(
            "FICTIONAL TEST CODE -- generated for BIM-Guard's automated test suite only. "
            "This document is not a reproduction of, and carries no authority under, any "
            "real building code; every clause number, dimension and requirement below is "
            "invented purely to exercise document parsing and rule extraction.",
            notice_style,
        ),
        Spacer(1, 6 * mm),
        H("9.8.1", "Scope"),
        B(
            "9.8.1.1.  This Subsection applies to interior and exterior stairs, ramps, "
            "landings, guards and handrails serving as part of a required means of egress "
            "or public stairway within a building."
        ),
        Spacer(1, 4 * mm),
        H("9.8.2", "Stair Width and Headroom Clearance"),
        B(
            "9.8.2.1.  Except as provided in Sentence 9.8.2.1.(2), the clear width of a "
            "required exit stair, measured between wall faces or guards, shall not be "
            "less than 900 mm."
        ),
        B(
            "9.8.2.1.(2)  A stair serving a single dwelling unit shall have a clear width "
            "of not less than 860 mm."
        ),
        B(
            "9.8.2.2.  Headroom clearance over a stairway shall be measured vertically "
            "from a straight line tangent to the tread and landing nosings to the lowest "
            "point of any obstruction above, and shall not be less than 2 050 mm."
        ),
        Spacer(1, 4 * mm),
        H("9.8.3", "Riser and Tread Dimensions"),
        B(
            "9.8.3.1.  The rise and run of a stair, measured as the vertical nosing-to-"
            "nosing distance for rise and the horizontal nosing-to-nosing distance for "
            "run, shall conform to Table 9.8.3.1."
        ),
        Spacer(1, 2 * mm),
        make_table(),
        Spacer(1, 3 * mm),
        B(
            "9.8.3.2.  Except as permitted by Sentence 9.8.3.2.(2), risers in any one "
            "flight shall be of uniform height, with a maximum tolerance of 10 mm between "
            "the tallest and shortest riser in the flight."
        ),
        B(
            "9.8.3.2.(2)  Treads shall have a uniform run with a maximum tolerance of "
            "10 mm between the deepest and shallowest tread in a flight."
        ),
        B(
            "9.8.3.3.  A nosing shall project not more than 25 mm beyond the face of the "
            "riser below it, and every open riser shall be deemed non-compliant unless "
            "the flight serves an unoccupied service space."
        ),
        Spacer(1, 4 * mm),
        H("9.8.4", "Landings"),
        B(
            "9.8.4.1.  A landing provided at the top or bottom of a flight shall have a "
            "clear length, measured in the direction of travel, of not less than the "
            "required width of the stair, and need not exceed 1 100 mm."
        ),
        B(
            "9.8.4.2.  The clear width of a landing shall not be less than the clear "
            "width of the stair it serves."
        ),
        B(
            "9.8.4.3.  A flight shall not rise more than 3.7 m between landings without "
            "an intermediate landing being provided."
        ),
        B(
            "9.8.4.4.  The slope of a landing's walking surface shall not exceed 1 in 50."
        ),
        Spacer(1, 4 * mm),
        H("9.8.5", "Guards and Handrails"),
        B(
            "9.8.5.1.  A guard protecting the open side of a stair, landing or ramp shall "
            "have a height of not less than 900 mm, measured vertically from the tread "
            "nosing or landing surface to the top of the guard."
        ),
        B(
            "9.8.5.2.  A guard shall be constructed so that no opening within it permits "
            "the passage of a sphere having a diameter of more than 100 mm, except that "
            "the triangular opening formed by a stair, a riser and the bottom rail of a "
            "guard is permitted to admit a sphere having a diameter of not more than "
            "200 mm."
        ),
        B(
            "9.8.5.3.  At least one handrail shall be provided on every required exit "
            "stair, and shall be located not less than 865 mm and not more than 965 mm "
            "above the line of the tread nosings."
        ),
        B(
            "9.8.5.4.  A handrail shall be continuous throughout the length of a flight, "
            "without interruption by newel posts or other obstructions, and shall extend "
            "horizontally not less than 300 mm beyond the top and bottom risers of the "
            "flight it serves."
        ),
        Spacer(1, 4 * mm),
        H("9.8.6", "Winders and Curved Flights"),
        B(
            "9.8.6.1.  Winders forming part of a flight shall turn through an angle of "
            "not more than 90 degrees between adjacent floor levels, and individual "
            "winder treads shall turn through an angle of not less than 30 degrees."
        ),
        B(
            "9.8.6.2.  The run of a winder tread, measured at a point 300 mm from the "
            "centre line of the inside handrail, shall conform to the minimum run "
            "specified in Table 9.8.3.1. for the applicable stair type."
        ),
    ]

    doc.build(story)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    build_pdf()
