"""Loads the clause-level bSDD grounding index built by bim-guard-evaluation.

See ../bim-guard-evaluation/kg/grounding.py for how "trusted" is defined
there: an LLM-verified, or lexically-high-confidence, candidate_class_match/
candidate_property_match edge from a document clause to a real bSDD term.

bim-guard-evaluation is the working bench where these indexes get built and
iterated against the real ontology + an LLM judge pass; a finished index is
copied here, into data/reference/clause_grounding/, once it's ready to
inform real extraction runs -- the same "R&D repo builds it, bim-guard ships
a static copy" pattern data/reference/bsdd/bsdd_ontology.duckdb already
follows for the underlying bSDD ontology itself.

Deliberately keyed and consulted by clause_id (ClauseMetadata.clause_id, via
RuleExtractionDraft.clause), which only lines up with an index's entries
when the document currently being processed is the one (or shares the
clause numbering of the one) the loaded index was built from -- on any
other document, or before any index has been promoted here, this is a
silent no-op (empty lookups), never a wrong answer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from app.logging_config import get_logger

logger = get_logger(__name__)

_DEFAULT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "reference"
    / "clause_grounding"
    / "obc_app_a_grounding_index.json"
)


class ClauseGroundingIndex:
    """In-memory clause_id -> trusted bSDD term lookup, lazily loaded once from a JSON file.

    File shape (kg.grounding.build_grounding_index's export):
        {"<clause_id>": {"classes": [{"uri": ..., "name": ..., "code": ..., "score": ...}, ...],
                          "properties": [...]}}
    """

    def __init__(self, path: Path = _DEFAULT_PATH) -> None:
        self._path = path
        self._by_clause: dict[str, dict[str, list[dict[str, Any]]]] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self._path.exists():
            logger.debug("No clause grounding index at %s -- clause-scoped grounding disabled", self._path)
            return
        try:
            with open(self._path, encoding="utf-8") as f:
                self._by_clause = json.load(f)
            logger.info("Loaded clause grounding index from %s (%d clauses)", self._path, len(self._by_clause))
        except Exception:
            logger.exception("Failed to load clause grounding index at %s", self._path)
            self._by_clause = {}

    def class_uris_for(self, clause_id: Optional[str]) -> list[str]:
        """Trusted bSDD class URIs for a clause, highest lexical score first; [] if unknown/none."""
        if not clause_id:
            return []
        self._ensure_loaded()
        entries = self._by_clause.get(clause_id, {}).get("classes", [])
        return [e["uri"] for e in entries if e.get("uri")]

    def property_hints_for(self, clause_id: Optional[str]) -> list[dict[str, Any]]:
        """Trusted bSDD property entries for a clause (uri/name/code/score).

        Advisory only: this index never carries a property_set (only a
        class's own property list does -- see rule_extraction_service.py's
        _class_properties_grounded docstring), so these are surfaced as a
        review note rather than applied as a correction.
        """
        if not clause_id:
            return []
        self._ensure_loaded()
        return self._by_clause.get(clause_id, {}).get("properties", [])

    def class_candidates_for(self, clause_id: Optional[str]) -> list[dict[str, Any]]:
        """Trusted bSDD class candidates for a clause, full entries (uri/name/code/score/source).

        Unlike class_uris_for (bare URIs, for the post-hoc correction path),
        this keeps enough detail to show a human-readable candidate list
        inside the extraction prompt itself.
        """
        if not clause_id:
            return []
        self._ensure_loaded()
        return self._by_clause.get(clause_id, {}).get("classes", [])

    def deontic_hint_for(self, clause_id: Optional[str]) -> Optional[dict[str, str]]:
        """Look up this clause's rule-based modality (kg.grounding._deontic_hint), if unambiguous.

        {"modality": "shall"|"must"|"should"|"may", "text": <clause excerpt>}
        or None when the clause isn't covered by a promoted index, or its
        deontic signal was ambiguous (negated/mixed operators) at KG-build
        time -- either way, callers should fall back to the LLM-based
        deontic extraction.
        """
        if not clause_id:
            return None
        self._ensure_loaded()
        return self._by_clause.get(clause_id, {}).get("deontic")

    def dependencies_for(self, clause_id: Optional[str]) -> list[dict[str, Any]]:
        """Look up this clause's outgoing cross_ref/depends_on edges to other clauses in the document.

        Each entry: {"edge_type", "label", "target_ref", "target_text_excerpt"}
        -- e.g. a base threshold's edge to the sprinkler exception that
        overrides it, with the exception's own text already resolved.
        """
        if not clause_id:
            return []
        self._ensure_loaded()
        return self._by_clause.get(clause_id, {}).get("dependencies", [])


_INDEX: Optional[ClauseGroundingIndex] = None


def get_clause_grounding_index() -> ClauseGroundingIndex:
    global _INDEX
    if _INDEX is None:
        _INDEX = ClauseGroundingIndex()
    return _INDEX
