"""Tests for app.modules.document_parsing.pdf_page_range.slice_pdf_pages."""

import io

import pytest
from pypdf import PdfReader, PdfWriter

from app.modules.document_parsing.pdf_page_range import slice_pdf_pages


def _make_pdf(page_count: int) -> bytes:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=200, height=200)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def test_slices_the_requested_inclusive_range():
    pdf = _make_pdf(10)
    sliced = slice_pdf_pages(pdf, start_page=3, end_page=5)
    assert len(PdfReader(io.BytesIO(sliced)).pages) == 3


def test_single_page_range():
    pdf = _make_pdf(5)
    sliced = slice_pdf_pages(pdf, start_page=1, end_page=1)
    assert len(PdfReader(io.BytesIO(sliced)).pages) == 1


def test_end_page_beyond_document_is_clamped():
    pdf = _make_pdf(4)
    sliced = slice_pdf_pages(pdf, start_page=2, end_page=100)
    assert len(PdfReader(io.BytesIO(sliced)).pages) == 3


def test_rejects_start_page_below_one():
    pdf = _make_pdf(3)
    with pytest.raises(ValueError):
        slice_pdf_pages(pdf, start_page=0, end_page=1)


def test_rejects_end_before_start():
    pdf = _make_pdf(3)
    with pytest.raises(ValueError):
        slice_pdf_pages(pdf, start_page=2, end_page=1)


def test_rejects_start_page_beyond_document():
    pdf = _make_pdf(3)
    with pytest.raises(ValueError):
        slice_pdf_pages(pdf, start_page=10, end_page=12)


def test_rejects_non_pdf_content():
    with pytest.raises(ValueError):
        slice_pdf_pages(b"not a pdf", start_page=1, end_page=1)
