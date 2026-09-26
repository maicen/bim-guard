"""Persistence for page-tagged document text (document viewer / rule-source annotation)."""

import re
from typing import Optional

from app.logging_config import get_logger
from app.services.persistence import PersistenceService

logger = get_logger(__name__)


def _normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


# Minimum overlap score for a fuzzy (non-substring) match to advance the
# sequential cursor — stricter than the 0.3 floor used to accept a match at
# all, since a weak match must not be trusted to bound every later lookup.
_MIN_OVERLAP_TO_ADVANCE_CURSOR = 0.6


class DocumentPagesService:
    """CRUD for `document_pages` — independent of clause/section chunking."""

    def __init__(self, *, pages_repo=None):
        """Initialize the document_pages table adapter with dependency injection."""
        self._pages = (
            pages_repo
            if pages_repo is not None
            else PersistenceService.get_table(
                "document_pages",
                {
                    "id": int,
                    "document_id": int,
                    "page_number": int,
                    "text": str,
                    "char_count": int,
                },
            )
        )

    def save_pages(self, document_id: int, pages: list[dict]) -> None:
        """Persist a document's page-tagged text, replacing any existing rows."""
        if not pages:
            return
        existing_ids = [
            row["id"] for row in self._pages.rows if int(row.get("document_id") or 0) == document_id
        ]
        if existing_ids:
            self._pages.delete_many(existing_ids)
        rows = [
            {
                "document_id": document_id,
                "page_number": int(page["page_number"]),
                "text": page.get("text") or "",
                "char_count": len(page.get("text") or ""),
            }
            for page in pages
        ]
        if hasattr(self._pages, "insert_many"):
            self._pages.insert_many(rows)
        else:
            for row in rows:
                self._pages.insert(row)
        logger.info("Document pages stored document_id=%d pages=%d", document_id, len(rows))

    def get_pages(self, document_id: int) -> list[dict]:
        """Return all page rows for a document, ordered by page number."""
        rows = [row for row in self._pages.rows if int(row.get("document_id") or 0) == document_id]
        return sorted(rows, key=lambda row: int(row.get("page_number") or 0))

    @staticmethod
    def find_best_matching_page(pages: list[dict], snippet: str) -> Optional[int]:
        """Resolve which page's text a source snippet lives on.

        Whitespace-normalized substring match first (the common case — the
        snippet is a contiguous quote from one page); falls back to the page
        with the highest word-overlap ratio when no page contains it verbatim
        (e.g. the snippet spans a page break, or minor OCR/whitespace drift).

        Shared by both a promoted rule's `/rules/{id}/source` lookup
        (`source_text`) and a pre-promotion draft's `/rules/drafts/{id}/source`
        lookup (`source_snippet`) — same matching problem either way. For more
        than one snippet against the same `pages`, prefer
        `find_best_matching_pages` — this normalizes every page's text fresh
        on every call, which is fine once but wasteful in a loop.
        """
        return DocumentPagesService.find_best_matching_pages(pages, [snippet])[0]

    @staticmethod
    def find_best_matching_pages(
        pages: list[dict],
        snippets: list[str],
        *,
        sequential: bool = False,
    ) -> list[Optional[int]]:
        """Batch form of `find_best_matching_page` — one page-normalization pass.

        Used when resolving many snippets against the same document (e.g. one
        per detected section), so normalizing `pages` isn't repeated once per
        snippet.

        `sequential=True` asserts `snippets` are given in document order (e.g.
        one per detected section, walked top to bottom). A snippet made of a
        short, generic, recurring heading like "Exceptions:" has no unique
        text to match on, so a plain substring search returns the *first*
        page anywhere in the document containing that string — always the
        same page, no matter which occurrence is being resolved. With
        `sequential=True`, each snippet's search is bounded to pages at or
        after the previously matched page, since later snippets can't
        legitimately resolve earlier than earlier ones did; only widens back
        to the full document when nothing matches within that bound.
        """
        normalized_pages = [
            (page.get("page_number"), _normalize_for_match(page.get("text", ""))) for page in pages
        ]

        results: list[Optional[int]] = []
        cursor: Optional[int] = None
        for snippet in snippets:
            norm_snippet = _normalize_for_match(snippet)
            if not norm_snippet or not normalized_pages:
                results.append(None)
                continue

            snippet_words = norm_snippet.split()
            candidates = normalized_pages
            if sequential and cursor is not None:
                bounded = [(n, t) for n, t in normalized_pages if n is not None and n > cursor]
                if bounded:
                    candidates = bounded

            matched = next((number for number, text in candidates if norm_snippet in text), None)
            if matched is None and candidates is not normalized_pages:
                matched = next(
                    (number for number, text in normalized_pages if norm_snippet in text),
                    None,
                )
            if matched is not None:
                results.append(matched)
                if sequential:
                    cursor = matched
                continue

            if not snippet_words:
                results.append(None)
                continue

            snippet_word_set = set(snippet_words)
            best_page, best_score = DocumentPagesService._best_overlap(candidates, snippet_word_set)
            if candidates is not normalized_pages:
                # A weak bounded match must never beat a stronger match that
                # exists earlier in the document (outside the bound) — and
                # if it's the better one, that's also a sign the bound
                # itself was already wrong.
                full_page, full_score = DocumentPagesService._best_overlap(
                    normalized_pages, snippet_word_set
                )
                if full_score > best_score:
                    best_page, best_score = full_page, full_score

            matched_page = best_page if best_score > 0.3 else None
            results.append(matched_page)
            if sequential and matched_page is not None and best_score >= _MIN_OVERLAP_TO_ADVANCE_CURSOR:
                cursor = matched_page

        return results

    @staticmethod
    def _best_overlap(
        normalized_pages: list[tuple[Optional[int], str]], snippet_words: set[str]
    ) -> tuple[Optional[int], float]:
        best_page, best_score = None, 0.0
        for number, text in normalized_pages:
            page_words = set(text.split())
            if not page_words:
                continue
            overlap = len(snippet_words & page_words) / len(snippet_words)
            if overlap > best_score:
                best_score, best_page = overlap, number
        return best_page, best_score
