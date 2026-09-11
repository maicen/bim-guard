"""Slice a PDF down to a page range before it reaches any extraction engine.

Trimming happens once, up front, on the raw upload bytes -- the resulting
(smaller) PDF is what gets stored, viewed, and handed to whichever parser
(Docling, Unstructured, or the light pypdf-only path) the caller selected, so
none of those extraction paths need their own page-range support.
"""

from __future__ import annotations

import io

from app.logging_config import get_logger

logger = get_logger(__name__)


def slice_pdf_pages(content: bytes, start_page: int, end_page: int) -> bytes:
    """Return a new PDF containing only pages `start_page..end_page` (1-based, inclusive).

    Raises ValueError if the range is invalid or the file isn't a readable PDF.
    """
    if start_page < 1:
        raise ValueError("Start page must be 1 or greater.")
    if end_page < start_page:
        raise ValueError("End page must be greater than or equal to the start page.")

    from pypdf import PdfReader, PdfWriter
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(content))
    except PdfReadError as exc:
        raise ValueError(f"Could not read this file as a PDF: {exc}") from exc

    page_count = len(reader.pages)
    if start_page > page_count:
        raise ValueError(f"Start page {start_page} is beyond this PDF's {page_count} pages.")
    clamped_end = min(end_page, page_count)

    writer = PdfWriter()
    # pypdf's `pages` bound is exclusive; end_page is inclusive in our (1-based) API.
    writer.append(reader, pages=(start_page - 1, clamped_end))

    out = io.BytesIO()
    writer.write(out)
    logger.info(
        "Sliced PDF to pages %d-%d (of %d) -- %d bytes -> %d bytes",
        start_page,
        clamped_end,
        page_count,
        len(content),
        out.tell(),
    )
    return out.getvalue()
