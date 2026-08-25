"""LLM-only compliance rule extraction from pre-extracted document text."""

from app.logging_config import get_logger
from app.modules.config import (
    COMPLIANCE_TEMPERATURE,
    DEFAULT_LLM_MODEL,
    MAX_TOKENS_RULE_EXTRACTION,
)
from app.modules.module1_doc_parser.section_chunker import SectionChunker
from app.services.llm_client import LiteLLMClient, LiteLLMClientWithRetry
from app.services.rule_extractor import LiteLLMRuleExtractor, RuleExtractionProvider

logger = get_logger(__name__)

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
