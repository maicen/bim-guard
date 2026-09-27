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
_CHAPTER_WORD = re.compile(r"^(CHAPTER|PART|DIVISION)\b", re.IGNORECASE)
_EXCEPTION_WORD = re.compile(r"^Exceptions?\b", re.IGNORECASE)
_TOP_LEVEL_TITLES = re.compile(
    r"^(PREFACE|TABLE\s+OF\s+CONTENTS|REFERENCED\s+STANDARDS|INDEX|APPENDIX(?:\s+[A-Z0-9]+)?)\b",
    re.IGNORECASE,
)


def _get_parent_prefixes(sec_num: str | None) -> list[str]:
    """Return candidate parent section numbers for a given section number in descending specificity.

    Examples:
      '2.27.3.1' -> ['2.27.3', '2.27', '2']
      '2.4'      -> ['2']
      '8.14.1'   -> ['8.14', '8']
      '2.7.7(1)' -> ['2.7.7', '2.7', '2']
    """
    if not sec_num:
        return []
    clean = sec_num.strip().split("(")[0].rstrip(".")
    parts = clean.split(".")
    candidates = []
    for i in range(len(parts) - 1, 0, -1):
        candidates.append(".".join(parts[:i]))
    return candidates


def compute_depth(section_number: str | None, section_name: str | None) -> int:
    """Return the outline depth (0 = top-level) inferred for one chunk."""
    name = (section_name or "").strip()
    if _CHAPTER_WORD.match(name) or _TOP_LEVEL_TITLES.match(name):
        return 0

    if _EXCEPTION_WORD.match(name):
        return 2  # exceptions subordinate to section/article

    num = (section_number or "").strip().rstrip(".").split("(")[0]
    if _DOTTED.match(num):
        return num.count(".")

    if "." in num and any(part.isdigit() for part in num.split(".")):
        return num.count(".")

    return 0


def build_section_tree(chunks: list[dict]) -> tuple[list[dict], list[dict]]:
    """Nest a flat, document-order chunk list into a tree.

    Supports both legacy SectionChunker chunks (heuristic dot-counting depth)
    and DocLang chunks (exact hierarchy depth from ``section_path``, with
    OTSL table nodes, page numbers, and bounding boxes).

    Uses a hybrid prefix-matching and depth-stack algorithm:
      - Numbered clauses (e.g. '2.4', '8.14.1') deterministically attach to their
        matching parent prefix ('2', '8.14') on the stack, preventing table
        captions or notes from hijacking subsequent sections.
      - Tables, paragraphs, and unnumbered notes attach subordinate to the current
        active section without popping the stack to root level.

    Args:
        chunks: The list of dicts returned by ``SectionChunker.chunk()``
            or ``DocLangChunker.chunk()`` in document order.

    Returns:
        ``(tree, flat)`` ready to serialize as ``SectionTreeNode`` and ``DocumentSection``.
    """
    flat: list[dict] = []
    roots: list[dict] = []
    # stack entry: (depth, tree_node, sec_num)
    stack: list[tuple[int, dict, str | None]] = []

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

        num_depth = compute_depth(section_number, section_name)
        if "section_path" in chunk and chunk["section_path"] and len(chunk["section_path"]) > 1:
            base_depth = max(0, len(chunk["section_path"]) - 1)
            depth = max(base_depth, num_depth)
            if node_type == "table":
                depth += 1
        elif num_depth > 0:
            depth = num_depth
        elif (section_name or "").strip().lower() == "exceptions" and stack:
            depth = stack[-1][0] + 1
        else:
            depth = num_depth

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

        # 1. Top-level Chapters/Parts/Major Divisions: always start at root
        name_str = (section_name or "").strip()
        is_major_root = bool(
            _CHAPTER_WORD.match(name_str)
            or _TOP_LEVEL_TITLES.match(name_str)
            or (not stack and depth == 0)
        )

        if is_major_root:
            stack.clear()
            roots.append(tree_node)
            stack.append((0, tree_node, section_number))
            continue

        # 2. Non-heading chunk (table, paragraph) sharing section_number with active heading
        if node_type != "heading" and stack and stack[-1][2] == section_number:
            stack[-1][1]["children"].append(tree_node)
            continue

        # 3. Numbered section/clause: check if its logical parent prefix exists on stack
        parent_matched = False
        if section_number:
            prefixes = _get_parent_prefixes(section_number)
            for pfx in prefixes:
                for idx in range(len(stack) - 1, -1, -1):
                    anc_num = stack[idx][2]
                    if anc_num and anc_num.split("(")[0].rstrip(".") == pfx:
                        # Pop everything above this ancestor
                        while len(stack) > idx + 1:
                            stack.pop()
                        stack[idx][1]["children"].append(tree_node)
                        stack.append((stack[idx][0] + 1, tree_node, section_number))
                        parent_matched = True
                        break
                if parent_matched:
                    break

        if parent_matched:
            continue

        # 3. Unnumbered chunks (tables, notes, footnotes, paragraphs, unnumbered sub-clauses)
        # When an active section exists on stack, nest inside it rather than resetting to root!
        if not section_number and stack:
            # Subordinate to current top of stack
            stack[-1][1]["children"].append(tree_node)
            # If it's a heading with substantial depth, track it so sub-items can nest under it
            if node_type == "heading":
                stack.append((stack[-1][0] + 1, tree_node, None))
            continue

        # 4. Fallback depth-based stack resolution
        while stack and stack[-1][0] >= depth:
            stack.pop()

        if stack:
            stack[-1][1]["children"].append(tree_node)
        else:
            roots.append(tree_node)

        stack.append((depth, tree_node, section_number))

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
