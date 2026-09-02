"""LLM-only compliance rule extraction from pre-extracted document text."""

from app.logging_config import get_logger
from app.modules import contracts
from app.modules.config import (
    COMPLIANCE_TEMPERATURE,
    DEFAULT_LLM_MODEL,
    MAX_TOKENS_RULE_EXTRACTION,
)
from app.modules.module1_doc_parser.llamaindex_ingestor import LlamaIndexIngestor
from app.modules.module1_doc_parser.section_chunker import SectionChunker
from app.services import pipeline_tracker
from app.services.llm_client import LiteLLMClient, LiteLLMClientWithRetry
from app.services.rule_extractor import LiteLLMRuleExtractor, RuleExtractionProvider

logger = get_logger(__name__)

_TRACKER_CODE = "LLAMA-INGEST"

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
        self._provider = provider or LiteLLMRuleExtractor(
            client=LiteLLMClientWithRetry(
                LiteLLMClient(
                    model=DEFAULT_LLM_MODEL,
                    temperature=COMPLIANCE_TEMPERATURE,
                    max_tokens=MAX_TOKENS_RULE_EXTRACTION,
                )
            )
        )
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
            chunk_rules = await self._provider.extract_rules_from_text(
                chunk_text,
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
        from app.modules.module3_rule_builder.llamaindex_rule_generator import (
            LlamaIndexRuleGenerator,
        )
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
                draft = await generator.generate_draft_from_node(
                    node, deontic=deontic_by_node.get(node.node_id)
                )
            except Exception as exc:  # noqa: BLE001 - one bad node must not abort the batch
                logger.warning("Rule generation failed node_id=%s error=%s", node.node_id, exc)
                continue
            if draft is not None:
                drafts.append(draft)

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
