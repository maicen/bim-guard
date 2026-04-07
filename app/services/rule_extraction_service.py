from app.modules.module1_doc_reader import Module1_DocReader
from app.services.gemini_rule_extractor import (
    LiteLLMGeminiRuleExtractor,
    RuleExtractionProvider,
)


class RuleExtractionService:
    """Encapsulates rule extraction workflow from uploaded documents."""

    def __init__(
        self,
        *,
        doc_reader: Module1_DocReader | None = None,
        provider: RuleExtractionProvider | None = None,
    ):
        self._doc_reader = doc_reader or Module1_DocReader()
        self._provider = provider or LiteLLMGeminiRuleExtractor()

    async def extract_rules(self, file_content: bytes) -> list[dict]:
        if not file_content:
            return []

        raw_text = self._doc_reader.parse_pdf(file_content)
        if not raw_text.strip():
            return []

        chunks = self._doc_reader.extract_text_sections(raw_text)
        if not chunks:
            return []

        extracted_rules = []
        for index, chunk in enumerate(chunks, start=1):
            chunk_rules = await self._provider.extract_rules_from_text(
                chunk,
                chunk_index=index,
                total_chunks=len(chunks),
            )
            extracted_rules.extend(chunk_rules)

        return self._deduplicate_rules(extracted_rules)

    def _deduplicate_rules(self, rules: list[dict]) -> list[dict]:
        deduplicated = []
        seen = set()

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
