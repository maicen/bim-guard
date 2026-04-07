import json
import os
from typing import Protocol

from litellm import acompletion


class RuleExtractionProvider(Protocol):
    async def extract_rules_from_text(
        self, text: str, *, chunk_index: int, total_chunks: int
    ) -> list[dict]: ...


class LiteLLMGeminiRuleExtractor:
    """LLM provider for extracting structured compliance rules from text chunks."""

    def __init__(
        self,
        *,
        model: str | None = None,
        temperature: float = 0,
    ):
        self._model = model or os.getenv(
            "BIM_GUARD_RULE_MODEL", "gemini/gemini-1.5-flash"
        )
        self._temperature = temperature

    async def extract_rules_from_text(
        self, text: str, *, chunk_index: int, total_chunks: int
    ) -> list[dict]:
        if not text.strip():
            return []

        self._ensure_api_key()

        response = await acompletion(
            model=self._model,
            messages=self._build_messages(
                text=text,
                chunk_index=chunk_index,
                total_chunks=total_chunks,
            ),
            response_format={"type": "json_object"},
            temperature=self._temperature,
        )
        payload = self._parse_response_content(response.choices[0].message.content)
        return self._normalize_rules(payload.get("rules", []))

    def _ensure_api_key(self):
        if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
            return
        raise RuntimeError(
            "Gemini API key is not configured. Set GEMINI_API_KEY or GOOGLE_API_KEY."
        )

    def _build_messages(
        self,
        *,
        text: str,
        chunk_index: int,
        total_chunks: int,
    ) -> list[dict]:
        system_prompt = (
            "You extract BIM compliance rules from regulation and specification text. "
            "Return only JSON with a top-level 'rules' array. Each rule must be an "
            "object with keys: ref, desc, target. 'ref' is a short reference id if "
            "present in the text, otherwise an empty string. 'desc' is the rule in "
            "plain language. 'target' is the IFC class the rule applies to, or "
            "'Unspecified' if not clear. Exclude commentary, examples, and duplicate rules."
        )
        user_prompt = (
            f"This is chunk {chunk_index} of {total_chunks}. Extract the explicit BIM or "
            "building compliance rules from the text below. Return JSON only.\n\n"
            f"TEXT:\n{text}"
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _parse_response_content(self, content) -> dict:
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )

        if not isinstance(content, str) or not content.strip():
            return {"rules": []}

        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()

        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            return {"rules": parsed}
        if isinstance(parsed, dict):
            return parsed
        return {"rules": []}

    def _normalize_rules(self, rules: list) -> list[dict]:
        normalized = []
        for index, rule in enumerate(rules, start=1):
            if not isinstance(rule, dict):
                continue

            ref = str(rule.get("ref") or rule.get("reference") or "").strip()
            desc = str(rule.get("desc") or rule.get("description") or "").strip()
            target = str(
                rule.get("target") or rule.get("target_ifc_class") or "Unspecified"
            ).strip()
            if not desc:
                continue

            normalized.append(
                {
                    "ref": ref or f"REQ-AI-{index:03d}",
                    "desc": desc,
                    "target": target or "Unspecified",
                }
            )

        return normalized
