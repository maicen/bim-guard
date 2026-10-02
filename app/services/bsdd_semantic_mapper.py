"""LLM-backed semantic matching against the local bSDD ontology.

`BSDDOntologyRepository`'s own search (`search_classes`/`search_properties`)
is pure substring matching -- a query like "Fire_Resistance_Rating" finds
nothing useful against bSDD's "FireRating" beyond the shared word "Fire".
No embeddings/vector-similarity infrastructure exists anywhere in this
codebase (confirmed), so this stays LLM-completion-based, reusing the same
`build_llm` binding and "known-good candidates shown to the model, it picks
or declines" discipline `llamaindex_rule_generator.py` already established --
not a second grounding mechanism, just this one applied to an on-demand
lookup instead of extraction-time context.

Deliberately NOT wired into `RuleSemanticAlignmentService.check()`: that path
is synchronous (as is `RuleDraftService.promote_draft`), while every LLM call
in this codebase is async. Making an optional suggestion-quality improvement
force the whole promotion path async was judged not worth the ripple: this is
instead a separate, explicitly-triggered lookup a reviewer calls when they
want a better suggestion, not something that runs silently on every
promotion.
"""

from __future__ import annotations

import asyncio

from typing import Optional

from pydantic import BaseModel, Field

from app.logging_config import get_logger
from app.modules.contracts import BSDDClassItem, BSDDPropertyItem
from app.services.bsdd_ontology_repository import (
    BSDDOntologyRepository,
    get_bsdd_ontology_repository,
)

logger = get_logger(__name__)

_MIN_WORD_LEN = 3
_MAX_CANDIDATES = 25

_SYSTEM_PROMPT = """\
You are matching a non-standard, locally-authored BIM property or IFC class
name to the correct entry in the buildingSMART Data Dictionary (bSDD).

You will be shown a QUERY (the local name) and a list of CANDIDATES already
retrieved from bSDD. Pick the candidate that means the same thing as the
query, even if the wording, casing, or word order differs (e.g. "Fire
Resistance Rating" and "FireRating" are the same concept). Only pick a
candidate that is actually a correct semantic match -- if none of the
candidates mean the same thing as the query, say so; never invent a code or
uri that isn't in the candidate list.
"""

_MATCH_PROMPT = """\
QUERY: {query}

CANDIDATES:
{candidates}

Respond with the uri of the best matching candidate (matched_uri), that
candidate's code (matched_code), your confidence (0.0-1.0), and a one-line
reasoning. If nothing in the list is a correct match, set matched_uri and
matched_code to "" and confidence to 0.0.
"""


class SemanticMatch(BaseModel):
    """The LLM's best pick from a candidate shortlist, or an explicit non-match."""

    matched_uri: str = ""
    matched_code: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: str = ""

    @property
    def matched(self) -> bool:
        return bool(self.matched_uri.strip())


def _query_words(query: str) -> list[str]:
    """Split *query* into lower-case words at least `_MIN_WORD_LEN` chars, deduplicated in order."""
    seen: dict[str, None] = {}
    for raw in query.replace("_", " ").replace("-", " ").split():
        word = raw.strip().lower()
        if len(word) >= _MIN_WORD_LEN:
            seen.setdefault(word, None)
    return list(seen)


class BsddSemanticMapper:
    """Resolves a non-standard local name to a bSDD class/property via LLM disambiguation.

    Keyword-only, optional constructor args each defaulting to a real
    instance when omitted -- matches ModelsService's established shape, the
    same convention RuleSemanticAlignmentService follows.
    """

    def __init__(self, *, bsdd_repo: BSDDOntologyRepository | None = None) -> None:
        self._bsdd = bsdd_repo if bsdd_repo is not None else get_bsdd_ontology_repository()

    # ── Candidate retrieval (pure, no LLM) ──────────────────────────────────

    def _candidate_classes(self, query: str) -> list[BSDDClassItem]:
        by_uri: dict[str, BSDDClassItem] = {}
        for word in _query_words(query) or [query]:
            for item in self._bsdd.search_classes(word, limit=10):
                by_uri.setdefault(item.uri, item)
        return list(by_uri.values())[:_MAX_CANDIDATES]

    def _candidate_properties(self, query: str) -> list[BSDDPropertyItem]:
        by_uri: dict[str, BSDDPropertyItem] = {}
        for word in _query_words(query) or [query]:
            for item in self._bsdd.search_properties(word, limit=10):
                by_uri.setdefault(item.uri, item)
        return list(by_uri.values())[:_MAX_CANDIDATES]

    # ── LLM disambiguation ───────────────────────────────────────────────────

    async def suggest_class(
        self, query: str, *, model: Optional[str] = None, organization_id: Optional[int] = None
    ) -> SemanticMatch | None:
        """Return the best bSDD class match for *query*, or None on no candidates/LLM failure."""
        # The local ontology lookup is a CPU-bound scan; keep it off the loop.
        candidates = await asyncio.to_thread(self._candidate_classes, query)
        if not candidates:
            return None
        lines = [f"- {c.name} (code={c.code}, uri={c.uri})" for c in candidates]
        return await self._ask(query, lines, model=model, organization_id=organization_id)

    async def suggest_property(
        self,
        query: str,
        target_ifc_class: Optional[str] = None,
        *,
        model: Optional[str] = None,
        organization_id: Optional[int] = None,
    ) -> SemanticMatch | None:
        """Return the best bSDD property match for *query*, or None on no candidates/LLM failure.

        `target_ifc_class` is advisory context only (shown in the prompt when
        given) -- candidates themselves are not filtered by it, since a
        property can be legitimately shared across many classes.
        """
        candidates = await asyncio.to_thread(self._candidate_properties, query)
        if not candidates:
            return None
        lines = [f"- {p.name} (code={p.code or ''}, uri={p.uri})" for p in candidates]
        query_text = f"{query} (property of {target_ifc_class})" if target_ifc_class else query
        return await self._ask(query_text, lines, model=model, organization_id=organization_id)

    async def _ask(
        self,
        query: str,
        candidate_lines: list[str],
        *,
        model: Optional[str],
        organization_id: Optional[int],
    ) -> SemanticMatch | None:
        try:
            from llama_index.core.llms import ChatMessage, MessageRole
            from llama_index.core.program import LLMTextCompletionProgram
            from llama_index.core.prompts import ChatPromptTemplate

            from app.modules.document_parsing.llamaindex_program import build_llm

            chat_prompt = ChatPromptTemplate(
                message_templates=[
                    ChatMessage(role=MessageRole.SYSTEM, content=_SYSTEM_PROMPT),
                    ChatMessage(role=MessageRole.USER, content=_MATCH_PROMPT),
                ]
            )
            # build_llm resolves the API key with a synchronous DB query.
            llm = await asyncio.to_thread(build_llm, model, organization_id=organization_id)
            program = LLMTextCompletionProgram.from_defaults(
                output_cls=SemanticMatch,
                prompt=chat_prompt,
                llm=llm,
            )
            return await program.acall(query=query, candidates="\n".join(candidate_lines))
        except Exception:
            logger.exception("BsddSemanticMapper LLM call failed for query=%r -- returning no suggestion", query)
            return None
