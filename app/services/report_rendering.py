"""Render a :class:`ReportModel` to HTML and PDF.

RENDERING ENGINE: PLAYWRIGHT (HEADLESS CHROMIUM), NOT WEASYPRINT

    WeasyPrint needs native Pango/Cairo libraries -- real friction on Windows
    dev machines and in the Dockerfile. Chromium has none of that friction
    (``playwright install chromium``, no GTK) and gives better CSS fidelity.
    Gotenberg was rejected: it needs a ~1GB sidecar container, more than this
    warrants. Typst was rejected: it can't share the same HTML the in-app
    preview uses.

COVER PAGE, SPLIT AND MERGED

    Chromium's ``page.pdf()`` header/footer template API has no way to skip
    the header/footer on just page 1. The cover is rendered as its own
    single-page PDF with no header/footer and no margins, the body (every
    other section) as a second PDF with the header/footer and page numbers,
    and the two are merged with :mod:`pypdf` -- already a direct dependency.
"""

from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pypdf import PdfReader, PdfWriter

from app.modules.contracts import ReportModel

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_TEMPLATE_NAME = "report.html.j2"

#: Raised when Chromium is not installed locally -- points at the exact fix
#: rather than surfacing Playwright's own raw stack trace to a report download.
CHROMIUM_SETUP_HINT = (
    "The PDF report engine (Playwright/Chromium) is not installed on this "
    "server. Run `uv run playwright install chromium` and retry."
)


@lru_cache(maxsize=1)
def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
    )


def render_report_html(model: ReportModel, *, render_target: str = "full") -> str:
    """Render ``model`` to an HTML string.

    Args:
        render_target: ``"full"`` (cover + body, for the in-app preview),
            ``"cover"`` (cover page only) or ``"body"`` (every other section
            only) -- the latter two are what :func:`render_report_pdf` renders
            separately before merging them back into one PDF.
    """
    template = _environment().get_template(_TEMPLATE_NAME)
    return template.render(render_target=render_target, **model.model_dump())


#: Chromium print margins for the body pages, leaving room for the header/footer.
_BODY_MARGIN = {"top": "18mm", "bottom": "16mm", "left": "0mm", "right": "0mm"}
_COVER_MARGIN = {"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"}

_HEADER_TEMPLATE = """
<div style="font-size:8px; width:100%; padding:0 18mm; color:#64748b;
  font-family: Inter, 'Segoe UI', system-ui, sans-serif; display:flex; justify-content:space-between;">
  <span class="title"></span>
  <span>BIM Guard Compliance Report</span>
</div>
"""

_FOOTER_TEMPLATE = """
<div style="font-size:8px; width:100%; padding:0 18mm; color:#64748b;
  font-family: Inter, 'Segoe UI', system-ui, sans-serif; display:flex; justify-content:space-between;">
  <span class="date"></span>
  <span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>
</div>
"""


def render_report_pdf(model: ReportModel) -> bytes:
    """Render ``model`` to a merged, paginated PDF (cover + body).

    Raises:
        RuntimeError: Chromium is not installed locally (see
            :data:`CHROMIUM_SETUP_HINT`) or Playwright otherwise failed to launch.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - dependency always declared
        raise RuntimeError(CHROMIUM_SETUP_HINT) from exc

    cover_html = render_report_html(model, render_target="cover")
    body_html = render_report_html(model, render_target="body")

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                cover_page = browser.new_page()
                cover_page.set_content(cover_html, wait_until="networkidle")
                cover_pdf = cover_page.pdf(
                    format="A4",
                    print_background=True,
                    margin=_COVER_MARGIN,
                    display_header_footer=False,
                )
                cover_page.close()

                body_page = browser.new_page()
                body_page.set_content(body_html, wait_until="networkidle")
                body_pdf = body_page.pdf(
                    format="A4",
                    print_background=True,
                    margin=_BODY_MARGIN,
                    display_header_footer=True,
                    header_template=_HEADER_TEMPLATE,
                    footer_template=_FOOTER_TEMPLATE,
                )
                body_page.close()
            finally:
                browser.close()
    except Exception as exc:  # noqa: BLE001 - Playwright raises its own broad Error type
        if "Executable doesn't exist" in str(exc):
            raise RuntimeError(CHROMIUM_SETUP_HINT) from exc
        raise

    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(cover_pdf)))
    writer.append(PdfReader(io.BytesIO(body_pdf)))
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
