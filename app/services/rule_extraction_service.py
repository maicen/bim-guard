"""LLM-only compliance rule extraction from pre-extracted document text."""

from typing import Protocol

from app.logging_config import get_logger
from app.modules import contracts
from app.modules.document_parsing.llamaindex_ingestor import LlamaIndexIngestor
from app.modules.document_parsing.section_chunker import SectionChunker
from app.modules.rule_builder.llamaindex_rule_generator import LlamaIndexRuleGenerator
from app.services import pipeline_tracker

logger = get_logger(__name__)

_TRACKER_CODE = "LLAMA-INGEST"

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
        self, text: str, *, chunk_index: int = 1, total_chunks: int = 1
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
    ):
        """Initialize the extraction provider dependency."""
        self._provider = provider or LlamaIndexRuleGenerator()
        self._ingestor = ingestor or LlamaIndexIngestor()

    async def extract_rules_from_text(self, text: str) -> ExtractionResult:
        """Extract compliance rules from pre-extracted document text."""
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

        Progress is reported through the shared pipeline_tracker so
        `GET /api/events/{document_id}` shows ingestion/extraction progress
        the same way an engine run does — a no-op when no tracker is bound
        for this id (e.g. outside a `pipeline_tracker.tracking()` context).
        """
        with pipeline_tracker.tracking(document_id):
            pipeline_tracker.emit(_TRACKER_CODE, chars=len(text or ""))
            nodes = self._ingestor.nodes_from_text(text, source_document_id=document_id)
            pipeline_tracker.increment(_TRACKER_CODE, nodes=len(nodes))

            try:
                statements = await self._ingestor.extract_deontic_statements(nodes)
            except Exception:
                pipeline_tracker.fail(_TRACKER_CODE, "deontic extraction failed")
                raise
            pipeline_tracker.complete(_TRACKER_CODE, deontic_statements=len(statements))

        logger.info(
            "LlamaIndex ingestion complete document_id=%d nodes=%d deontic_statements=%d",
            document_id,
            len(nodes),
            len(statements),
        )
        return nodes

    async def extract_rule_drafts(self, document_id: int, text: str) -> list[contracts.RuleExtractionDraft]:
        """Ingest a document and generate reviewable rule drafts via LlamaIndex.

        Runs ingestion (clause-annotated nodes + deontic statements), then
        LlamaIndexRuleGenerator over each node, and persists the results as
        `pending_review` drafts via RuleDraftService — the entry point for
        `POST /api/documents/{id}/rules/extract-drafts`.
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
                    node, deontic=deontic_by_node.get(node.node_id)
                )
            except Exception as exc:  # noqa: BLE001 - one bad node must not abort the batch
                logger.warning("Rule generation failed node_id=%s error=%s", node.node_id, exc)
                continue
            drafts.extend(
                draft.model_copy(update={"source_snippet": node.text}) for draft in node_drafts
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
