"""
Rule extraction pipeline wiring Module 1 → Module 3 (Gemini) → web app DB.

Pipeline:
    PDF bytes
        ↓  Module1_DocReader.parse_pdf()       — pypdf text extraction
        ↓  SectionChunker.chunk()              — split into OBC-structured sections
        ↓  LiteLLMGeminiRuleExtractor          — Gemini extracts rules per section
        ↓  _deduplicate_rules()                — remove duplicates
        → list[dict] returned to route for display + "Save to Library" per rule
"""

from app.modules.module1_doc_parser import Module1_DocReader
from app.modules.module1_doc_parser.section_chunker import SectionChunker
from app.services.gemini_rule_extractor import (
    LiteLLMGeminiRuleExtractor,
    RuleExtractionProvider,
)


class RuleExtractionService:
    """Encapsulates the Module 1 → Module 3 rule extraction pipeline."""

    def __init__(
        self,
        *,
        doc_reader: Module1_DocReader | None = None,
        provider: RuleExtractionProvider | None = None,
    ):
        self._doc_reader = doc_reader or Module1_DocReader()
        self._provider = provider or LiteLLMGeminiRuleExtractor()

    async def extract_rules(self, file_content: bytes) -> list[dict]:
        # ── Module 1 Step 1: PDF text extraction ─────────────────────────────
        if not file_content:
            return []

        try:
            raw_text = self._doc_reader.parse_pdf(file_content)
        except Exception as exc:
            raise RuntimeError(f"PDF parsing failed: {exc}") from exc

        if not raw_text.strip():
            raise RuntimeError(
                "No text could be extracted from this PDF. "
                "The file may be scanned (image-only) or encrypted. "
                "Please upload a text-based PDF."
            )

        # ── Module 1 Step 3: Section chunking ────────────────────────────────
        # SectionChunker detects OBC Part 9 section headings (1–13).
        # If it finds sections, each is sent to Gemini individually so the LLM
        # has focused context per topic (stairs, doors, windows, etc.).
        # For non-OBC documents with no recognized headings, fall back to
        # the generic size-based chunker built into Module1_DocReader.
        obc_chunks = SectionChunker().chunk(raw_text)

        if obc_chunks:
            text_chunks = [
                (c["section_name"], c["text"]) for c in obc_chunks if c.get("text", "").strip()
            ]
        else:
            # Fall back: generic size-bounded chunking
            generic_chunks = self._doc_reader.extract_text_sections(raw_text)
            text_chunks = [(f"Section {i + 1}", t) for i, t in enumerate(generic_chunks)]

        if not text_chunks:
            raise RuntimeError(
                "Could not split the document into processable sections. "
                "Make sure the document contains readable text."
            )

        # ── Module 3 (Gemini): extract rules per section ──────────────────────
        # Gemini acts as the rule converter — equivalent to module3's RuleConverter
        # but using the configured Gemini key instead of OpenAI.
        extracted_rules: list[dict] = []
        total = len(text_chunks)

        for index, (section_name, section_text) in enumerate(text_chunks, start=1):
            if not section_text.strip():
                continue
            chunk_rules = await self._provider.extract_rules_from_text(
                section_text,
                chunk_index=index,
                total_chunks=total,
            )
            extracted_rules.extend(chunk_rules)

        return self._deduplicate_rules(extracted_rules)

    def _deduplicate_rules(self, rules: list[dict]) -> list[dict]:
        deduplicated = []
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
                    "ref": ref or f"REQ-AI-{len(deduplicated) + 1:03d}",
                    "desc": desc,
                    "target": target or "Unspecified",
                }
            )

        return deduplicated
