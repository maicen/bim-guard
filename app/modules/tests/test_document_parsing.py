"""
tests/test_document_parsing.py
----------------------
Unit tests for Module 1 — SectionChunker and regression snapshots.

Run with: pytest tests/test_document_parsing.py -v
"""

import json
import os

import pytest
from document_parsing.keywords.keyword_master import ALL_KEYWORDS, BIGRAM_PHRASES, KEYWORD_WEIGHTS
from document_parsing.section_chunker import SectionChunker

TEST_DB = "tests/test_rules_m1.db"
SNAPSHOTS_DIR = os.path.join(os.path.dirname(__file__), "snapshots")


# ═══════════════════════════════════════════════════════════════════════════════
# Keyword master tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_keyword_total_count():
    assert len(ALL_KEYWORDS) >= 193, "Should have at least 193 keywords"


def test_keyword_weights_assigned():
    for kw in ALL_KEYWORDS:
        assert kw in KEYWORD_WEIGHTS, f"No weight for keyword: '{kw}'"


def test_bigrams_sorted_longest_first():
    for i in range(len(BIGRAM_PHRASES) - 1):
        assert len(BIGRAM_PHRASES[i]) >= len(BIGRAM_PHRASES[i + 1]), (
            "Bigrams must be sorted longest-first for correct matching"
        )


def test_critical_keywords_present():
    flat = [kw.lower() for kw in ALL_KEYWORDS]
    for expected in [
        "shall",
        "must",
        "minimum",
        "maximum",
        "need not",
        "deemed to comply",
        "prohibited",
        "fire-resistance rating",
        "means of egress",
    ]:
        assert expected in flat, f"Critical keyword missing: '{expected}'"


def test_keyword_weights_are_positive_integers():
    """Every weight must be a positive int — catches typos like 0 or -1."""
    for kw, weight in KEYWORD_WEIGHTS.items():
        assert isinstance(weight, int) and weight > 0, f"Invalid weight for '{kw}': {weight}"


# ═══════════════════════════════════════════════════════════════════════════════
# SectionChunker tests
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def chunker():
    return SectionChunker()


def test_chunker_detects_markdown_headings(chunker):
    text = """# 4 Stairs
Every stair shall have a clear width of not less than 860 mm.

# 6 Guards and Handrails
Guards shall not be less than 900 mm in height.
"""
    chunks = chunker.chunk(text)
    nums = [c["section_number"] for c in chunks]
    assert "4" in nums
    assert "6" in nums


def test_chunker_detects_plain_headings(chunker):
    text = """4 Stairs
Every stair shall have a clear width of not less than 860 mm.

6 Guards and Handrails
Guards shall not be less than 900 mm in height.
"""
    chunks = chunker.chunk(text)
    nums = [c["section_number"] for c in chunks]
    assert "4" in nums
    assert "6" in nums


def test_chunker_names_sections_from_their_own_heading(chunker):
    text = "# 4 Stairs\nEvery stair shall have a clear width.\n\n12 Units and Global IDs\nEvery window has a GlobalId."
    chunks = chunker.chunk(text)
    assert [c["section_name"] for c in chunks] == ["4 Stairs", "12 Units and Global IDs"]


def test_chunker_empty_text(chunker):
    chunks = chunker.chunk("")
    assert chunks == []


def test_chunker_text_goes_to_right_section(chunker):
    text = """# 4 Stairs
Stair width shall be not less than 860 mm.

# 7 Windows and Glazing
Windows shall provide egress opening area of 0.35 m2.
"""
    chunks = chunker.chunk(text)
    stair_chunk = next(c for c in chunks if c["section_number"] == "4")
    window_chunk = next(c for c in chunks if c["section_number"] == "7")
    assert "860" in stair_chunk["text"]
    assert "0.35" in window_chunk["text"]


def test_chunker_preserves_all_content(chunker):
    """No text should be silently dropped between sections."""
    text = """# 4 Stairs
Line A about stairs.
Line B about stairs.

# 6 Guards and Handrails
Line C about guards.
"""
    chunks = chunker.chunk(text)
    all_text = " ".join(c["text"] for c in chunks)
    for phrase in ["Line A", "Line B", "Line C"]:
        assert phrase in all_text, f"Content silently dropped: '{phrase}'"


def test_chunker_detects_zero_padded_headings(chunker):
    text = """01 Core Dimensions | 6 rules
WR-001 Width must be at least 800 mm.

02 Fire and Smoke Protection | 1 rule
WR-068 FireRating must be at least 60 min.
"""
    chunks = chunker.chunk(text)
    by_num = {c["section_number"]: c for c in chunks}
    assert "WR-001" in by_num["01"]["text"]
    assert "WR-068" in by_num["02"]["text"]
    assert by_num["01"]["section_name"].startswith("01 Core Dimensions")


def test_chunker_keeps_text_before_first_heading(chunker):
    """Content above the first recognised heading must not be dropped."""
    text = """Intro requirement that sits before any heading.

# 4 Stairs
Stair width shall be not less than 860 mm.
"""
    chunks = chunker.chunk(text)
    assert chunks[0]["section_number"] is None
    assert "Intro requirement" in chunks[0]["text"]
    assert any(c["section_number"] == "4" for c in chunks)


def test_chunker_char_count_field(chunker):
    """Each chunk should have a char_count that matches the actual text length."""
    text = "# 4 Stairs\nEvery stair shall have a clear width of 860 mm."
    chunks = chunker.chunk(text)
    for c in chunks:
        if "char_count" in c:
            assert c["char_count"] == len(c["text"]), "char_count doesn't match actual text length"


# ═══════════════════════════════════════════════════════════════════════════════
# Regression snapshot tests
# ═══════════════════════════════════════════════════════════════════════════════
#
# First run: saves output as snapshot.  Subsequent runs: compares against it.
# To update snapshots: delete the file in tests/snapshots/ and re-run.


class TestSnapshots:
    def _snapshot_path(self, name):
        os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
        return os.path.join(SNAPSHOTS_DIR, f"{name}.json")

    def test_chunker_snapshot(self, chunker):
        text = """# 4 Stairs
Every stair shall have a clear width of not less than 860 mm.

# 6 Guards and Handrails
Guards shall not be less than 900 mm in height.
"""
        chunks = chunker.chunk(text)
        snap_file = self._snapshot_path("chunker_basic")

        if not os.path.exists(snap_file):
            with open(snap_file, "w") as f:
                json.dump(chunks, f, indent=2)
            pytest.skip("Snapshot created — re-run to verify")

        with open(snap_file) as f:
            expected = json.load(f)

        assert len(chunks) == len(expected), f"Chunk count changed: {len(expected)} → {len(chunks)}"
        for got, exp in zip(chunks, expected):
            assert got["section_number"] == exp["section_number"]
            assert got["section_name"] == exp["section_name"]
