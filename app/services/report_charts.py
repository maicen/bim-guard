"""Small, dependency-free inline-SVG chart builders for the compliance PDF report.

No charting library: every chart in the report is a handful of ``<rect>``/``<text>``
elements computed from already-aggregated counts, so there is nothing here a library
would meaningfully simplify. Colors are the literal light-mode hex values from
``frontend/src/app.css``'s ``html.light`` block -- the report is always rendered in
light mode regardless of the viewer's app theme, since a printed page has no dark-mode
reader to serve and this keeps the two color systems from drifting into two different
truths about what "critical" looks like.
"""

from __future__ import annotations

from html import escape

#: Literal light-mode hex values mirrored from frontend/src/app.css (html.light block).
FG_PRIMARY = "#0f172a"
FG_MUTED = "#64748b"
BORDER_SUBTLE = "#f1f5f9"
ACCENT = "#0066cc"
SUCCESS = "#047857"
CRITICAL = "#be123c"
WARNING = "#b45309"

_FONT = "Inter, 'Segoe UI', system-ui, sans-serif"


def horizontal_bar_chart_svg(
    rows: list[tuple[str, int]],
    *,
    width: int = 640,
    bar_color: str = ACCENT,
    max_rows: int = 8,
) -> str:
    """Render a horizontal bar chart as a self-contained inline SVG string.

    Args:
        rows: ``(label, value)`` pairs, already in the order they should render.
        width: Total SVG width in px.
        bar_color: Fill color for every bar.
        max_rows: Rows beyond this are dropped -- a report page has no room for
            a 40-row chart, and the findings register table is where the long
            tail belongs.

    Returns:
        Empty string when ``rows`` is empty, so a template can test truthiness
        rather than render an axis with nothing on it.
    """
    rows = rows[:max_rows]
    if not rows:
        return ""

    row_height = 28
    label_width = 200
    chart_width = width - label_width - 60
    height = len(rows) * row_height + 10
    max_value = max((v for _, v in rows), default=0) or 1

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">']
    for i, (label, value) in enumerate(rows):
        y = i * row_height
        bar_w = round((value / max_value) * chart_width) if max_value else 0
        parts.append(
            f'<text x="{label_width - 8}" y="{y + 18}" text-anchor="end" '
            f'font-family="{_FONT}" font-size="11" fill="{FG_PRIMARY}">{escape(str(label))[:28]}</text>'
        )
        parts.append(
            f'<rect x="{label_width}" y="{y + 4}" width="{max(bar_w, 2)}" height="16" rx="3" fill="{bar_color}" />'
        )
        parts.append(
            f'<text x="{label_width + bar_w + 6}" y="{y + 16}" '
            f'font-family="{_FONT}" font-size="11" fill="{FG_MUTED}">{value:,}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def stacked_bar_chart_svg(
    rows: list[tuple[str, int, int, int]],
    *,
    width: int = 640,
    max_rows: int = 8,
) -> str:
    """Render a passed/failed/unable-to-verify stacked horizontal bar chart.

    Args:
        rows: ``(label, passed, failed, unable_to_verify)`` tuples.
        width: Total SVG width in px.
        max_rows: Rows beyond this are dropped.

    Returns:
        Empty string when ``rows`` is empty.
    """
    rows = rows[:max_rows]
    if not rows:
        return ""

    row_height = 30
    label_width = 200
    chart_width = width - label_width - 20
    height = len(rows) * row_height + 26
    max_total = max((p + f + u for _, p, f, u in rows), default=0) or 1

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">']
    for i, (label, passed, failed, unverified) in enumerate(rows):
        y = i * row_height
        total = passed + failed + unverified
        x = label_width
        parts.append(
            f'<text x="{label_width - 8}" y="{y + 18}" text-anchor="end" '
            f'font-family="{_FONT}" font-size="11" fill="{FG_PRIMARY}">{escape(str(label))[:28]}</text>'
        )
        for value, color in ((passed, SUCCESS), (failed, CRITICAL), (unverified, FG_MUTED)):
            seg_w = round((value / max_total) * chart_width) if total and max_total else 0
            if seg_w > 0:
                parts.append(f'<rect x="{x}" y="{y + 4}" width="{seg_w}" height="16" fill="{color}" />')
                x += seg_w
        parts.append(
            f'<text x="{label_width + chart_width + 6}" y="{y + 16}" '
            f'font-family="{_FONT}" font-size="10" fill="{FG_MUTED}">{total:,}</text>'
        )
    legend_y = height - 14
    legend = [("Passed", SUCCESS), ("Failed", CRITICAL), ("Unable to verify", FG_MUTED)]
    lx = label_width
    for text, color in legend:
        parts.append(f'<rect x="{lx}" y="{legend_y}" width="10" height="10" rx="2" fill="{color}" />')
        parts.append(
            f'<text x="{lx + 14}" y="{legend_y + 9}" font-family="{_FONT}" '
            f'font-size="10" fill="{FG_MUTED}">{text}</text>'
        )
        lx += 22 + 8 * len(text)
    parts.append("</svg>")
    return "".join(parts)
