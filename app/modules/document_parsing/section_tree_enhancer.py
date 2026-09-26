"""Optional, one-shot AI cleanup pass over a deterministic section tree.

Fixes cosmetic labeling problems that the regex-based ``SectionChunker``
can produce (duplicate generic titles, truncated/garbled headings like
"Section 101.2 — , and R-4"), and disambiguates generic-but-legitimate
labels that repeat verbatim across the document (e.g. many "Exceptions:"
or "GENERAL" nodes) by folding in parent context — see
``section_tree.build_section_tree`` for the tree structure itself.

The LLM may also request a small, constrained structural edit: merging a
node with negligible content into its parent, to cut down on trivial
one-line entries cluttering the outline. This is the only way the tree's
*shape* can change; renames never touch structure.

Kept deliberately cheap:
  - The LLM only ever sees a compact one-line-per-node skeleton (id, depth,
    number, page, a short extractive snippet, and name) — never the full
    section body — so the prompt size scales with node *count*, not
    document size. The snippet is a hard-capped prefix of text already
    parsed and held in memory (see ``SNIPPET_CHARS``); no extra parsing,
    model, or network call is needed to produce it.
  - The LLM may only return label overrides for the ids it wants to
    rename, plus a list of ids to merge into their parent. It cannot add
    nodes, reparent arbitrary subtrees, or rename/merge an id that doesn't
    exist, so a partial or malformed response can't corrupt the tree —
    unfixed labels are simply left as the deterministic chunker produced
    them, and unresolvable merge ids are silently skipped.
  - Callers are expected to cache the result (see the ``/sections-tree``
    endpoint), so this runs once per document rather than once per view.

Any failure (LLM error, validation failure, oversized tree) falls back to
returning the input tree unchanged with ``enhanced=False`` — the tree is
always usable without this step.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.logging_config import get_logger
from app.modules.document_parsing.section_tree import compute_depth

logger = get_logger(__name__)

# Above this many nodes, skip the AI pass rather than send an oversized
# prompt — the deterministic tree is still fully usable on its own.
MAX_NODES_FOR_ENHANCEMENT = 4000

# Hard cap on the extractive snippet shown per node — keeps the prompt
# bounded per node regardless of how long the underlying section body is.
SNIPPET_CHARS = 60

_ENHANCE_PROMPT = """\
You are cleaning up the outline of a building-code/specification document \
for display as a collapsible tree. Below is a skeleton of every detected \
section: its id, outline depth (0 = top-level), reference number, page \
number, a short snippet of its opening body text (may be cut off \
mid-word — that's expected, it's only a hint), and current heading text, \
in document order (so each node's context is the lines immediately \
around it). Page numbers are a strong signal — two nodes with the same \
generic label but far-apart page numbers are almost certainly distinct \
sections, not duplicates. The snippet is your main source for what a \
generic-labeled node is actually about — use it to write the disambiguated \
label, not just the ancestor's own heading.

Two kinds of fixes are allowed:

1. RELABEL — fix a heading that is clearly broken, OR disambiguate a \
generic label that repeats verbatim across unrelated parts of the \
document (e.g. many separate "Exceptions:" or "GENERAL" nodes). For a \
repeated generic label, prefer using the node's own snippet to write a \
short topical suffix, e.g. "Exceptions: (fire-rated corridor walls)"; \
fall back to its nearest ancestor's number/name only when the snippet \
isn't informative enough, e.g. "GENERAL (Section 2.1)". Keep it short — a \
few words — and leave a heading alone if you are not reasonably confident \
what to add.

2. MERGE — if a node's content is negligible (near-empty, a stray \
fragment, a table continuation, or otherwise not worth its own outline \
entry) and it would read fine folded into its parent, list its id to \
merge. A merged node is removed from the tree and its own children (if \
any) are reattached to its former parent in its place; nothing is \
deleted from the document. Only merge nodes with a parent (depth > 0 or \
a shallower sibling exists above them) and be conservative — most nodes \
should stay as their own entry.

Do NOT invent new sections, change reference numbers, or merge a node \
into anything other than its immediate parent. Only return entries for \
ids you are actually changing — omit anything you are leaving as-is.

SECTIONS (id | depth | number | page | snippet | name):
{skeleton}
"""


class _LabelOverride(BaseModel):
    id: str
    section_name: str


class _LabelOverrides(BaseModel):
    overrides: list[_LabelOverride] = Field(default_factory=list)
    merges: list[str] = Field(default_factory=list)


def _index_by_id(tree: list[dict]) -> dict[str, dict]:
    index: dict[str, dict] = {}

    def _walk(nodes: list[dict]) -> None:
        for node in nodes:
            index[node["id"]] = node
            _walk(node.get("children") or [])

    _walk(tree)
    return index


def _find_container(tree: list[dict], node_id: str) -> list[dict] | None:
    """Return the list (root list or some node's ``children``) holding ``node_id``."""

    def _walk(nodes: list[dict]) -> list[dict] | None:
        for node in nodes:
            if node["id"] == node_id:
                return nodes
            found = _walk(node.get("children") or [])
            if found is not None:
                return found
        return None

    return _walk(tree)


def _apply_merges(tree: list[dict], merge_ids: list[str]) -> None:
    """Remove each listed node from the tree, splicing its children in place.

    Children are reattached to the former parent's children list (or the
    root list, for a top-level node) at the same position. Unknown ids are
    silently skipped — the tree is always left in a valid state.
    """
    for node_id in merge_ids:
        container = _find_container(tree, node_id)
        if container is None:
            continue
        index = next((i for i, n in enumerate(container) if n["id"] == node_id), None)
        if index is None:
            continue
        node = container[index]
        container[index : index + 1] = node.get("children") or []


def _snippet(text: str | None) -> str:
    """Hard-capped, single-line extractive snippet of a chunk's body text."""
    collapsed = " ".join((text or "").split()).replace("|", "/")
    if not collapsed:
        return "—"
    if len(collapsed) <= SNIPPET_CHARS:
        return collapsed
    return collapsed[:SNIPPET_CHARS].rstrip() + "…"


def _build_skeleton(flat: list[dict]) -> str:
    lines = []
    for chunk in flat:
        depth = compute_depth(chunk.get("section_number"), chunk.get("section_name"))
        number = chunk.get("section_number") or "—"
        name = (chunk.get("section_name") or "").strip() or "—"
        page = chunk.get("page_number")
        page_str = str(page) if page is not None else "—"
        snippet = _snippet(chunk.get("text"))
        lines.append(f"{chunk['id']} | {depth} | {number} | {page_str} | {snippet} | {name}")
    return "\n".join(lines)


async def enhance_section_tree(
    tree: list[dict],
    flat: list[dict],
    *,
    model: str | None = None,
    organization_id: int | None = None,
) -> tuple[list[dict], bool]:
    """Apply an optional AI label-cleanup pass to a deterministic tree.

    Returns ``(tree, enhanced)``. On any failure, or when the document has
    no sections or too many to enhance cheaply, returns the input tree
    unchanged with ``enhanced=False``.
    """
    if not flat:
        return tree, False

    if len(flat) > MAX_NODES_FOR_ENHANCEMENT:
        logger.info(
            "section_tree_enhancer: skipping AI cleanup for %d sections (over the %d cap)",
            len(flat),
            MAX_NODES_FOR_ENHANCEMENT,
        )
        return tree, False

    try:
        from llama_index.core.program import LLMTextCompletionProgram

        from app.modules.document_parsing.llamaindex_program import build_llm

        program = LLMTextCompletionProgram.from_defaults(
            output_cls=_LabelOverrides,
            prompt_template_str=_ENHANCE_PROMPT,
            llm=build_llm(model, organization_id=organization_id),
        )
        result: _LabelOverrides = await program.acall(skeleton=_build_skeleton(flat))
    except Exception:
        logger.exception("section_tree_enhancer: AI cleanup pass failed, using deterministic tree")
        return tree, False

    index = _index_by_id(tree)
    for override in result.overrides:
        node = index.get(override.id)
        new_name = (override.section_name or "").strip()
        if node is not None and new_name:
            node["section_name"] = new_name

    if result.merges:
        _apply_merges(tree, result.merges)

    # The AI pass ran and returned a valid response — mark as enhanced
    # regardless of how many labels it actually chose to change.
    return tree, True
