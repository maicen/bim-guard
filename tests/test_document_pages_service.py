"""DocumentPagesService.find_best_matching_page — shared by rule/draft source lookup."""

from app.services.document_pages_service import DocumentPagesService

PAGES = [
    {"page_number": 1, "text": "Introduction. This document covers exit access doorways."},
    {"page_number": 2, "text": "Section 8.14.1 Exit or exit access doorways required. Two exits shall be provided."},
    {"page_number": 3, "text": "Appendix A: definitions and abbreviations used throughout."},
]


def test_exact_substring_match_wins():
    page = DocumentPagesService.find_best_matching_page(
        PAGES, "Two exits shall be provided."
    )
    assert page == 2


def test_whitespace_and_case_are_normalized():
    page = DocumentPagesService.find_best_matching_page(
        PAGES, "TWO   EXITS\nshall be provided."
    )
    assert page == 2


def test_falls_back_to_best_word_overlap_when_no_exact_match():
    page = DocumentPagesService.find_best_matching_page(
        PAGES, "exit access doorways required for every storey"
    )
    assert page == 2


def test_returns_none_when_overlap_too_weak():
    page = DocumentPagesService.find_best_matching_page(
        PAGES, "completely unrelated text about plumbing fixtures"
    )
    assert page is None


def test_returns_none_for_empty_snippet_or_pages():
    assert DocumentPagesService.find_best_matching_page(PAGES, "") is None
    assert DocumentPagesService.find_best_matching_page([], "Two exits shall be provided.") is None
