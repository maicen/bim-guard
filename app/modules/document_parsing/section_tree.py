"""Nests a flat, document-order chunk list into a hierarchical outline tree.

Operates purely on each chunk's detected number/heading (as produced by
``SectionChunker.chunk()``) — no LLM call, no I/O.

Depth is inferred per chunk:
  - "SECTION x" / "CHAPTER x" / "PART x" headings are always top-level
    (depth 0), regardless of what their reference number looks like.
  - A pure dotted-decimal number ("4.4.1", "9.8.2.1") nests by dot count
    ("4.4.1" -> depth 2), matching how building codes structure clauses.
  - Anything else (bare taxonomy numbers like "4", markdown-derived
    headings with no reliable numbering) is treated as depth 0.

Nesting itself uses the standard "flat headings + depth -> outline tree"
algorithm: a stack of the last-seen node at each depth. A chunk whose
depth skips an intermediate level (e.g. a "4.4.1" appears with no "4.4"
chunk of its own) still nests correctly, one level under the nearest
shallower ancestor actually present, rather than being dropped or
mis-parented.
"""

from __future__ import annotations

import re

_DOTTED = re.compile(r"^\d+(?:\.\d+)+$")
_SECTION_WORD = re.compile(r"^(SECTION|CHAPTER|PART)\b", re.IGNORECASE)


def compute_depth(section_number: str | None, section_name: str | None) -> int:
    """Return the outline depth (0 = top-level) inferred for one chunk."""
    name = (section_name or "").strip()
    if _SECTION_WORD.match(name):
        return 0

    num = (section_number or "").strip().rstrip(".")
    if _DOTTED.match(num):
        return num.count(".")

    return 0


def build_section_tree(chunks: list[dict]) -> tuple[list[dict], list[dict]]:
    """Nest a flat, document-order chunk list into a tree.

    Args:
        chunks: The list of dicts returned by ``SectionChunker.chunk()``
            (``section_number``, ``section_name``, ``text``, ``char_count``),
            in document order.

    Returns:
        ``(tree, flat)`` where ``flat`` is the same chunks with a stable
        ``id`` assigned (document order, ``"s0"``, ``"s1"``, ...) and no
        ``children`` key, and ``tree`` nests those same node dicts (by
        reference) under a ``children`` list, ready to serialize as
        ``SectionTreeNode``.
    """
    flat: list[dict] = []
    roots: list[dict] = []
    stack: list[tuple[int, dict]] = []  # (depth, tree_node)

    for i, chunk in enumerate(chunks):
        section_number = chunk.get("section_number")
        section_name = chunk.get("section_name")
        char_count = chunk.get("char_count", 0)
        node_id = f"s{i}"

        flat.append(
            {
                "id": node_id,
                "section_number": section_number,
                "section_name": section_name,
                "text": chunk.get("text", ""),
                "char_count": char_count,
            }
        )

        depth = compute_depth(section_number, section_name)
        tree_node = {
            "id": node_id,
            "section_number": section_number,
            "section_name": section_name,
            "char_count": char_count,
            "children": [],
        }

        while stack and stack[-1][0] >= depth:
            stack.pop()

        if stack:
            stack[-1][1]["children"].append(tree_node)
        else:
            roots.append(tree_node)

        stack.append((depth, tree_node))

    return roots, flat
