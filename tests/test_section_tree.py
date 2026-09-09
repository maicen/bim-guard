"""Tests for the deterministic section outline builder and its AI cleanup pass."""

from __future__ import annotations

import asyncio

import llama_index.core.program as li_program

from app.modules.document_parsing import llamaindex_program
from app.modules.document_parsing.section_tree import build_section_tree, compute_depth
from app.modules.document_parsing.section_tree_enhancer import (
    MAX_NODES_FOR_ENHANCEMENT,
    enhance_section_tree,
)


def _chunk(number: str, name: str, text: str = "body") -> dict:
    return {"section_number": number, "section_name": name, "text": text, "char_count": len(text)}


def test_compute_depth_variants():
    assert compute_depth("4", "Stairs") == 0  # bare taxonomy number
    assert compute_depth("4.4", "SECTION 4.4") == 0  # SECTION/CHAPTER/PART always top-level
    assert compute_depth("4.4.1", "General") == 2  # two dots
    assert compute_depth("9.8.2.1", "Stair Width") == 3  # three dots
    assert compute_depth(None, None) == 0


def test_build_section_tree_nests_by_depth():
    chunks = [
        _chunk("1", "CHAPTER 1"),
        _chunk("1.1.1", "1.1.1 Scope"),
        _chunk("1.1.2", "1.1.2 Interchangeability"),
        _chunk("2", "CHAPTER 2"),
        _chunk("2.1.1", "2.1.1 Scope"),
    ]

    tree, flat = build_section_tree(chunks)

    assert [n["id"] for n in flat] == ["s0", "s1", "s2", "s3", "s4"]
    assert flat[1]["text"] == "body"
    assert flat[1]["char_count"] == 4

    assert [n["section_number"] for n in tree] == ["1", "2"]
    chapter1, chapter2 = tree
    assert [c["section_number"] for c in chapter1["children"]] == ["1.1.1", "1.1.2"]
    assert [c["section_number"] for c in chapter2["children"]] == ["2.1.1"]
    # Leaf nodes still carry an (empty) children list, never omitted.
    assert chapter1["children"][0]["children"] == []


def test_build_section_tree_skipped_intermediate_level_attaches_to_nearest_ancestor():
    # No "9.8.2" chunk exists between the chapter and the sub-clause — the
    # sub-clause should still nest one level under the nearest shallower
    # node actually present, not be dropped or mis-parented as a root.
    chunks = [
        _chunk("9", "CHAPTER 9"),
        _chunk("9.8.2.1", "Stair Width"),
    ]

    tree, _flat = build_section_tree(chunks)

    assert len(tree) == 1
    assert tree[0]["section_number"] == "9"
    assert [c["section_number"] for c in tree[0]["children"]] == ["9.8.2.1"]


def test_build_section_tree_empty_input():
    tree, flat = build_section_tree([])
    assert tree == []
    assert flat == []


class _FakeOverride:
    def __init__(self, id: str, section_name: str):
        self.id = id
        self.section_name = section_name


class _FakeOverridesResult:
    def __init__(self, overrides):
        self.overrides = overrides


class _FakeProgram:
    def __init__(self, result=None, error: Exception | None = None):
        self._result = result
        self._error = error

    async def acall(self, **_kwargs):
        if self._error:
            raise self._error
        return self._result


def _patch_program(monkeypatch, program: _FakeProgram) -> None:
    def _from_defaults(*, output_cls, prompt_template_str, llm):
        return program

    monkeypatch.setattr(
        li_program.LLMTextCompletionProgram, "from_defaults", staticmethod(_from_defaults)
    )
    monkeypatch.setattr(llamaindex_program, "build_llm", lambda model=None: None)


def test_enhance_section_tree_applies_only_known_id_overrides(monkeypatch):
    chunks = [_chunk("1", "CHAPTER 1"), _chunk("1.1.1", "garbled title fragment")]
    tree, flat = build_section_tree(chunks)

    _patch_program(
        monkeypatch,
        _FakeProgram(
            result=_FakeOverridesResult(
                overrides=[
                    _FakeOverride(id="s1", section_name="Scope"),
                    _FakeOverride(id="s-does-not-exist", section_name="Should be ignored"),
                ]
            )
        ),
    )

    new_tree, enhanced = asyncio.run(enhance_section_tree(tree, flat))

    assert enhanced is True
    assert new_tree[0]["section_name"] == "CHAPTER 1"  # untouched
    assert new_tree[0]["children"][0]["section_name"] == "Scope"  # overridden by id
    # Structure is unchanged — same number of roots/children as before.
    assert len(new_tree) == 1
    assert len(new_tree[0]["children"]) == 1


def test_enhance_section_tree_falls_back_on_llm_failure(monkeypatch):
    chunks = [_chunk("1", "CHAPTER 1")]
    tree, flat = build_section_tree(chunks)

    _patch_program(monkeypatch, _FakeProgram(error=RuntimeError("LLM unavailable")))

    new_tree, enhanced = asyncio.run(enhance_section_tree(tree, flat))

    assert enhanced is False
    assert new_tree == tree
    assert new_tree[0]["section_name"] == "CHAPTER 1"


def test_enhance_section_tree_skips_empty_and_oversized_trees(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise AssertionError("must not be called")

    monkeypatch.setattr(li_program.LLMTextCompletionProgram, "from_defaults", staticmethod(_boom))

    empty_tree, empty_enhanced = asyncio.run(enhance_section_tree([], []))
    assert empty_tree == []
    assert empty_enhanced is False

    big_chunks = [_chunk(str(i), f"Section {i}") for i in range(MAX_NODES_FOR_ENHANCEMENT + 1)]
    big_tree, big_flat = build_section_tree(big_chunks)
    result_tree, result_enhanced = asyncio.run(enhance_section_tree(big_tree, big_flat))
    assert result_enhanced is False
    assert result_tree == big_tree
