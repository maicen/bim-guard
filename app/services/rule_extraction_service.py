"""LLM-only compliance rule extraction from pre-extracted document text."""

from typing import Protocol

from app.logging_config import get_logger
from app.modules import contracts
from app.modules.document_parsing.llamaindex_ingestor import LlamaIndexIngestor
from app.modules.document_parsing.section_chunker import SectionChunker
from app.modules.rule_builder.llamaindex_rule_generator import LlamaIndexRuleGenerator
from app.services.bsdd_client import DEFAULT_BSDD_CLIENT, BSDDClient

logger = get_logger(__name__)

# Comfortably under the LLM provider's ~1MB single-request part limit, so a
# document with no detected section headings (one giant chunk) or a single
# oversized section still reaches the provider instead of failing with
# "Part exceeded maximum size of 1024KB".
_MAX_CHUNK_CHARS = 400_000


def _split_oversized(text: str, max_chars: int = _MAX_CHUNK_CHARS) -> list[str]:
    """Split text too large for one LLM request into paragraph-bounded pieces."""
    if len(text) <= max_chars:
        return [text]

    pieces: list[str] = []
    current: list[str] = []
    current_len = 0
    for paragraph in text.split("\n\n"):
        piece_len = len(paragraph) + 2
        if current and current_len + piece_len > max_chars:
            pieces.append("\n\n".join(current))
            current, current_len = [], 0
        if piece_len > max_chars:
            for i in range(0, len(paragraph), max_chars):
                pieces.append(paragraph[i : i + max_chars])
            continue
        current.append(paragraph)
        current_len += piece_len
    if current:
        pieces.append("\n\n".join(current))
    return pieces


class RuleExtractionProvider(Protocol):
    """Protocol used by RuleExtractionService (Dependency Inversion)."""

    async def extract_rules_from_text(
        self, text: str, *, chunk_index: int = 1, total_chunks: int = 1, model: str | None = None
    ) -> list[dict]:
        """Extract structured rule dicts from one text chunk."""
        ...


class ExtractionResult:
    """Holds the rules list and any non-fatal warnings from the pipeline."""

    def __init__(self, rules: list[dict], warnings: list[str]):
        self.rules = rules
        self.warnings = warnings


class RuleExtractionService:
    """Extract and deduplicate rules using only an LLM provider."""

    def __init__(
        self,
        *,
        provider: RuleExtractionProvider | None = None,
        ingestor: LlamaIndexIngestor | None = None,
        bsdd_client: BSDDClient | None = None,
    ):
        """Initialize the extraction provider dependency."""
        self._provider = provider or LlamaIndexRuleGenerator()
        self._ingestor = ingestor or LlamaIndexIngestor()
        self._bsdd_client = bsdd_client or DEFAULT_BSDD_CLIENT

    def _ground_draft_with_bsdd(self, draft: contracts.RuleExtractionDraft) -> contracts.RuleExtractionDraft:
        """Correct an extracted rule's property_set/property_name against bSDD.

        The LLM frequently invents or misnames property sets (e.g.
        "Pset_Door" instead of the real "Pset_DoorCommon", or "DoorWidth"
        instead of "OverallWidth"). When bSDD's own property search has an
        exact case-insensitive name match carrying a property_set, that
        canonical pairing replaces whatever the LLM produced, and a note of
        the correction is attached so a reviewer can see why it changed.
        Silently leaves the draft untouched when nothing resolves against
        bSDD — that is not itself evidence the property is wrong, only that
        it could not be confirmed offline/against this dictionary.
        """
        rule = draft.proposed_rule
        prop_name = (rule.property_name or "").strip()
        if not prop_name:
            return draft

        try:
            matches = self._bsdd_client.search_properties(prop_name, limit=5)
        except Exception as exc:  # noqa: BLE001 - a lookup failure must not block extraction
            logger.warning("bSDD grounding lookup failed property_name=%s error=%s", prop_name, exc)
            return draft

        match = next((m for m in matches if m.name.strip().lower() == prop_name.lower()), None)
        if match is None or not match.property_set:
            return draft
        if rule.property_set == match.property_set and rule.property_name == match.name:
            return draft

        corrected_rule = rule.model_copy(
            update={"property_set": match.property_set, "property_name": match.name}
        )
        note = (
            f"bSDD grounding: corrected property to {match.property_set}.{match.name} "
            f"(was {rule.property_set or '—'}.{rule.property_name or '—'})."
        )
        return draft.model_copy(update={"proposed_rule": corrected_rule, "review_notes": note})

    async def extract_rules_from_text(self, text: str, *, model: str | None = None) -> ExtractionResult:
        """Extract compliance rules from pre-extracted document text.

        Args:
            model: Extraction LLM override, threaded down to the provider
                (e.g. from the Rule Extraction UI's model selector).
        """
        if not text or not text.strip():
            logger.warning("Skipped rule extraction for empty extracted text")
            return ExtractionResult(rules=[], warnings=[])

        logger.info("Starting rule extraction from text chars=%d", len(text))
        structured_chunks = SectionChunker().chunk(text)
        chunks = structured_chunks or [{"text": text}]
        extracted_rules: list[dict] = []
        total = len(chunks)

        for idx, chunk in enumerate(chunks, start=1):
            chunk_text = chunk.get("text", "").strip()
            if not chunk_text:
                continue
            for sub_text in _split_oversized(chunk_text):
                chunk_rules = await self._provider.extract_rules_from_text(
                    sub_text,
                    chunk_index=idx,
                    total_chunks=total,
                    model=model,
                )
                extracted_rules.extend(chunk_rules)

        rules = self._deduplicate(extracted_rules)
        logger.info(
            "LLM rule extraction complete chunks=%d extracted_rules=%d unique_rules=%d",
            len(chunks),
            len(extracted_rules),
            len(rules),
        )
        return ExtractionResult(rules=rules, warnings=[])

    async def ingest_with_llamaindex(
        self, document_id: int, text: str
    ) -> list[contracts.DocumentNodeContract]:
        """Ingest document text into clause-annotated nodes with deontic statements.

        Does not report through the shared pipeline_tracker: that tracker is
        keyed by project_id against a fixed corrosion-engine registry
        (GC-001/CC-001/...), so binding it here under a document_id would
        either collide with an in-flight corrosion run that happens to share
        the same id, or raise on an engine code ("LLAMA-INGEST") the registry
        does not know. Document ingestion has no engine-progress contract of
        its own yet, so this stays plain (unstreamed) for now.
        """
        nodes = self._ingestor.nodes_from_text(text, source_document_id=document_id)
        statements = await self._ingestor.extract_deontic_statements(nodes)

        logger.info(
            "LlamaIndex ingestion complete document_id=%d nodes=%d deontic_statements=%d",
            document_id,
            len(nodes),
            len(statements),
        )
        return nodes

    async def extract_rule_drafts(
        self, document_id: int, text: str, *, model: str | None = None
    ) -> list[contracts.RuleExtractionDraft]:
        """Ingest a document and generate reviewable rule drafts via LlamaIndex.

        Runs ingestion (clause-annotated nodes + deontic statements), then
        LlamaIndexRuleGenerator over each node, and persists the results as
        `pending_review` drafts via RuleDraftService — the entry point for
        `POST /api/documents/{id}/rules/extract-drafts`.

        Args:
            model: Extraction LLM override (e.g. from the UI's model
                selector), applied to every node in this document.
        """
        from app.services.rule_draft_service import RuleDraftService

        nodes = await self.ingest_with_llamaindex(document_id, text)
        deontic_by_node = {
            node.node_id: (node.deontic_statements[0] if node.deontic_statements else None)
            for node in nodes
        }

        generator = LlamaIndexRuleGenerator()
        drafts: list[contracts.RuleExtractionDraft] = []
        for node in nodes:
            try:
                node_drafts = await generator.generate_drafts_from_node(
                    node, deontic=deontic_by_node.get(node.node_id), model=model
                )
            except Exception as exc:  # noqa: BLE001 - one bad node must not abort the batch
                logger.warning("Rule generation failed node_id=%s error=%s", node.node_id, exc)
                continue
            drafts.extend(
                self._ground_draft_with_bsdd(draft.model_copy(update={"source_snippet": node.text}))
                for draft in node_drafts
            )

        saved_drafts = RuleDraftService().save_drafts(drafts)
        logger.info(
            "LlamaIndex rule-draft extraction complete document_id=%d nodes=%d drafts=%d",
            document_id,
            len(nodes),
            len(saved_drafts),
        )
        return saved_drafts

    # ── Private: deduplication ────────────────────────────────────────────────

    def _deduplicate(self, rules: list[dict]) -> list[dict]:
        deduplicated: list[dict] = []
        seen: set[tuple] = set()

        for rule in rules:
            desc = str(rule.get("desc") or "").strip()
            target = str(rule.get("target") or "Unspecified").strip()
            if not desc:
                continue

            key = (desc.casefold(), target.casefold())
            if key in seen:
                continue
            seen.add(key)

            ref = str(rule.get("ref") or "").strip()
            deduplicated.append(
                {
                    **rule,
                    "ref": ref or f"REQ-AI-{len(deduplicated) + 1:03d}",
                    "target": target,
                }
            )

        return deduplicated
