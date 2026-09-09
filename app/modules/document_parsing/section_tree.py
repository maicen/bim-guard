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

    Supports both legacy SectionChunker chunks (heuristic dot-counting depth)
    and DocLang chunks (exact hierarchy depth from ``section_path``, with
    OTSL table nodes, page numbers, and bounding boxes).

    Args:
        chunks: The list of dicts returned by ``SectionChunker.chunk()``
            or ``DocLangChunker.chunk()`` in document order.

    Returns:
        ``(tree, flat)`` ready to serialize as ``SectionTreeNode`` and ``DocumentSection``.
    """
    flat: list[dict] = []
    roots: list[dict] = []
    stack: list[tuple[int, dict]] = []  # (depth, tree_node)

    for i, chunk in enumerate(chunks):
        section_number = chunk.get("section_number")
        section_name = chunk.get("section_name")
        char_count = chunk.get("char_count", 0)
        node_type = chunk.get("node_type", "section")
        bbox = chunk.get("bbox")
        page_number = chunk.get("page_number")
        node_id = f"s{i}"

        flat_item = {
            "id": node_id,
            "section_number": section_number,
            "section_name": section_name,
            "text": chunk.get("text", ""),
            "char_count": char_count,
            "page_number": page_number,
            "node_type": node_type,
            "bbox": bbox,
        }
        flat.append(flat_item)

        # Infer depth: DocLang provides exact section_path; otherwise compute from number
        if "section_path" in chunk and chunk["section_path"]:
            base_depth = max(0, len(chunk["section_path"]) - 1)
            depth = base_depth + 1 if node_type == "table" else base_depth
        else:
            depth = compute_depth(section_number, section_name)

        tree_node = {
            "id": node_id,
            "section_number": section_number,
            "section_name": section_name,
            "char_count": char_count,
            "page_number": page_number,
            "node_type": node_type,
            "bbox": bbox,
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


def attach_page_numbers(tree: list[dict], flat: list[dict], page_numbers: list[int | None]) -> None:
    """Set ``page_number`` on every flat entry and its matching tree node.

    Pure structural helper — ``page_numbers`` must already be resolved (one
    entry per ``flat``, same order/length, e.g. via
    ``DocumentPagesService.find_best_matching_pages``) by the caller, so this
    module stays free of any DB/service dependency and independently
    testable. A page number that couldn't be resolved is ``None`` and is set
    as such — never omitted, so every node has the key.
    """
    id_to_page: dict[str, int | None] = {}
    for chunk, page_number in zip(flat, page_numbers):
        chunk["page_number"] = page_number
        id_to_page[chunk["id"]] = page_number

    def _walk(nodes: list[dict]) -> None:
        for node in nodes:
            node["page_number"] = id_to_page.get(node["id"])
            _walk(node.get("children") or [])

    _walk(tree)
