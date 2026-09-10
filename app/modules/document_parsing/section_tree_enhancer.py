"""Optional, one-shot AI cleanup pass over a deterministic section tree.

Fixes cosmetic labeling problems that the regex-based ``SectionChunker``
can produce (duplicate generic titles, truncated/garbled headings like
"Section 101.2 — , and R-4") without touching the tree's structure — see
``section_tree.build_section_tree`` for the structure itself.

Kept deliberately cheap:
  - The LLM only ever sees a compact one-line-per-node skeleton (id, depth,
    number, name) — never section body text — so the prompt size scales
    with node *count*, not document size.
  - The LLM may only return label overrides for the ids it wants to
    rename; it cannot add, remove, or reparent nodes, so a partial or
    malformed response can't corrupt the tree — unfixed labels are simply
    left as the deterministic chunker produced them.
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

_ENHANCE_PROMPT = """\
You are cleaning up the outline of a building-code/specification document \
for display as a collapsible tree. Below is a skeleton of every detected \
section: its id, outline depth (0 = top-level), reference number, and \
current heading text.

Some headings were extracted by a regex heuristic and may be garbled, \
truncated mid-sentence, cut off with a trailing "—", or duplicated across \
unrelated sections (a generic placeholder title reused verbatim). Fix ONLY \
headings that are clearly broken in one of those ways — write a short, \
accurate title from context (the surrounding depth/numbering), or leave \
ambiguous ones alone.

Do NOT invent new sections, remove sections, or change reference numbers. \
Only return entries for ids whose heading you are changing — omit anything \
you are leaving as-is.

SECTIONS (id | depth | number | name):
{skeleton}
"""


class _LabelOverride(BaseModel):
    id: str
    section_name: str


class _LabelOverrides(BaseModel):
    overrides: list[_LabelOverride] = Field(default_factory=list)


def _index_by_id(tree: list[dict]) -> dict[str, dict]:
    index: dict[str, dict] = {}

    def _walk(nodes: list[dict]) -> None:
        for node in nodes:
            index[node["id"]] = node
            _walk(node.get("children") or [])

    _walk(tree)
    return index


def _build_skeleton(flat: list[dict]) -> str:
    lines = []
    for chunk in flat:
        depth = compute_depth(chunk.get("section_number"), chunk.get("section_name"))
        number = chunk.get("section_number") or "—"
        name = (chunk.get("section_name") or "").strip() or "—"
        lines.append(f"{chunk['id']} | {depth} | {number} | {name}")
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

    # The AI pass ran and returned a valid response — mark as enhanced
    # regardless of how many labels it actually chose to change.
    return tree, True
