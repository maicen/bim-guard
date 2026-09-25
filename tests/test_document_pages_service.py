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


def test_batch_matches_agree_with_singular_lookup_per_snippet():
    snippets = [
        "Two exits shall be provided.",
        "exit access doorways required for every storey",
        "completely unrelated text about plumbing fixtures",
        "",
    ]

    batch = DocumentPagesService.find_best_matching_pages(PAGES, snippets)

    assert batch == [DocumentPagesService.find_best_matching_page(PAGES, s) for s in snippets]
    assert batch == [2, 2, None, None]


def test_batch_returns_all_none_for_empty_pages():
    assert DocumentPagesService.find_best_matching_pages([], ["Two exits shall be provided.", "x"]) == [
        None,
        None,
    ]


def test_batch_returns_empty_list_for_no_snippets():
    assert DocumentPagesService.find_best_matching_pages(PAGES, []) == []


RECURRING_HEADING_PAGES = [
    {"page_number": 1, "text": "Chapter 2. Exceptions: none apply to this section."},
    {"page_number": 5, "text": "Section 8.14.1 doorways required. Exceptions: see 8.14.2."},
    {"page_number": 9, "text": "Section 8.15 travel distance. Exceptions: sprinklered spaces only."},
]


def test_non_sequential_batch_collapses_recurring_headings_to_first_occurrence():
    # Without sequential=True, every "Exceptions:" snippet resolves to the
    # same (first) page, regardless of which occurrence it actually is.
    snippets = ["Exceptions:", "Exceptions:", "Exceptions:"]
    batch = DocumentPagesService.find_best_matching_pages(RECURRING_HEADING_PAGES, snippets)
    assert batch == [1, 1, 1]


def test_sequential_batch_resolves_recurring_headings_in_document_order():
    snippets = ["Exceptions:", "Exceptions:", "Exceptions:"]
    batch = DocumentPagesService.find_best_matching_pages(
        RECURRING_HEADING_PAGES, snippets, sequential=True
    )
    assert batch == [1, 5, 9]


def test_sequential_batch_widens_back_to_full_document_when_bound_has_no_match():
    # A snippet unique to page 1 shouldn't be lost just because the running
    # cursor has already advanced past page 1 from an earlier match.
    pages = [
        {"page_number": 1, "text": "Unique introductory text about scope."},
        {"page_number": 5, "text": "Exceptions: see 8.14.2."},
    ]
    snippets = ["Exceptions:", "Unique introductory text about scope."]
    batch = DocumentPagesService.find_best_matching_pages(pages, snippets, sequential=True)
    assert batch == [5, 1]
