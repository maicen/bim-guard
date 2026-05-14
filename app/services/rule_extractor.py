"""Rule extraction: prompt construction, response parsing, and rule normalisation.

Responsibilities (Single Responsibility):
    LiteLLMRuleExtractor is concerned only with *what to ask* (the prompt) and
    *how to interpret the answer* (JSON parsing + schema normalisation).
    It delegates all HTTP/LLM transport to an injected LLMClient, so swapping
    providers requires no changes here.

Interface segregation:
    RuleExtractionProvider exposes a single focussed method used by the pipeline.

Dependency inversion:
    LiteLLMRuleExtractor depends on the LLMClient *abstraction*, not on litellm
    or any provider SDK directly.
"""

import json
from typing import Protocol

from app.services.llm_client import LLMClient


class RuleExtractionProvider(Protocol):
    """Protocol used by RuleExtractionService (Dependency Inversion)."""

    async def extract_rules_from_text(
        self, text: str, *, chunk_index: int = 1, total_chunks: int = 1
    ) -> list[dict]:
        """Extract structured rule dicts from one text chunk."""
        ...


# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a BIM compliance rule extraction engine for building regulations (e.g. OBC Part 9).

Extract every discrete, checkable requirement from the text and return a JSON object with
a top-level "rules" array. Each rule MUST have ALL of the following fields:

{
  "ref":               "section reference e.g. 9.8.2.1.(1), or empty string",
  "desc":              "short plain-English rule description",
  "source_text":       "exact quote or close paraphrase from the regulation",

  "target":            "IFC class the rule applies to e.g. IfcStairFlight",
  "property_set":      "Pset name e.g. Pset_StairFlightCommon, or null",
  "property_name":     "IFC property to measure e.g. TreadLength, or null",
  "fallback_property": "alternative property name if primary missing, or null",

  "rule_type":         "numeric_range | exists_check | regex_match | classification",
  "operator":          ">= | <= | == | != | between | exists | matches",
  "value":             860,
  "value_min":         null,
  "value_max":         null,
  "unit":              "mm | m | m2 | deg | ratio | null",

  "applies_when": {
    "building_use":  "residential | commercial | any",
    "max_storeys":   null,
    "location":      "exit | interior | exterior | any"
  },

  "severity":          "mandatory | recommended | informational",
  "keyword":           "shall | must | should | may",
  "compliance_type":   "prescriptive | performance | descriptive",

  "exceptions":        ["list of exception strings, or empty array"],
  "related_refs":      ["related section numbers, or empty array"],
  "overridden_by":     null,

  "confidence":        0.9,
  "extraction_method": "llm",
  "needs_review":      false
}

RULES:
- Output ONLY valid JSON — no markdown, no prose, no code fences.
- Use "between" operator + value_min/value_max for min-and-max requirements; set "value" to null.
- Use "exists" operator + value null for presence-only checks.
- Set confidence < 0.7 and needs_review true when the text is ambiguous.
- Skip commentary, examples, definitions, and duplicate rules.
- Exclude requirements that cannot be expressed as a discrete checkable rule.\
"""


# ── Extractor ─────────────────────────────────────────────────────────────────


class LiteLLMRuleExtractor:
    """Extracts structured BIM compliance rules from text using a chat LLM.

    Implements RuleExtractionProvider.  Depends on LLMClient for transport so
    any LiteLLM-supported provider can be used without modifying this class.

    Args:
        client: An LLMClient instance (e.g. LiteLLMClient) that handles
            routing to the actual provider.

    Example::

        from app.services.llm_client import LiteLLMClient
        from app.services.rule_extractor import LiteLLMRuleExtractor

        client = LiteLLMClient(model="gpt-4o-mini")
        extractor = LiteLLMRuleExtractor(client=client)
        rules = await extractor.extract_rules_from_text(text)
    """

    def __init__(self, client: LLMClient) -> None:
        """Initialise with an LLMClient for transport."""
        self._client = client

    async def extract_rules_from_text(
        self, text: str, *, chunk_index: int = 1, total_chunks: int = 1
    ) -> list[dict]:
        """Call the LLM and return normalised rule dicts for one text chunk.

        Args:
            text: The regulation text to analyse.
            chunk_index: 1-based index of this chunk (reported in the prompt).
            total_chunks: Total number of chunks in this extraction run.

        Returns:
            List of normalised rule dicts conforming to the BIM rule schema.
        """
        if not text.strip():
            return []

        user_prompt = (
            f"This is chunk {chunk_index} of {total_chunks}. "
            "Extract all BIM compliance rules from the text below. "
            "Return JSON only.\n\nTEXT:\n" + text
        )

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        raw = await self._client.complete(messages, response_format={"type": "json_object"})
        payload = _parse(raw)
        return _normalize(payload.get("rules", []))


# ── Private helpers (pure functions — no state) ───────────────────────────────


def _parse(content) -> dict:
    """Parse raw LLM output into a Python dict.

    Handles both string responses and Gemini-style list responses.
    """
    # Gemini may return a list of content parts
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    if not isinstance(content, str) or not content.strip():
        return {"rules": []}

    cleaned = content.strip().lstrip("`")
    if cleaned.startswith("json"):
        cleaned = cleaned[4:].strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return {"rules": []}

    if isinstance(parsed, list):
        return {"rules": parsed}
    if isinstance(parsed, dict):
        return parsed
    return {"rules": []}


def _normalize(rules: list) -> list[dict]:
    """Normalise a raw list of LLM-returned rule dicts to the BIM rule schema."""
    normalized = []
    for idx, rule in enumerate(rules, start=1):
        if not isinstance(rule, dict):
            continue

        desc = str(rule.get("desc") or rule.get("description") or "").strip()
        if not desc:
            continue

        ref = str(rule.get("ref") or rule.get("reference") or "").strip()
        applies_when = rule.get("applies_when") or {}
        if not isinstance(applies_when, dict):
            applies_when = {}

        # LLM may return "value" or "check_value" — normalise to both so the
        # web UI and Module 3 / RuleGenerator can each find what they need.
        check_value = (
            rule.get("value") if rule.get("value") is not None else rule.get("check_value")
        )

        normalized.append(
            {
                "ref": ref or f"REQ-AI-{idx:03d}",
                "desc": desc,
                "source_text": str(rule.get("source_text") or "").strip(),
                "target": str(
                    rule.get("target") or rule.get("target_ifc_class") or "Unspecified"
                ).strip(),
                "property_set": str(rule.get("property_set") or "").strip(),
                "property_name": str(rule.get("property_name") or "").strip(),
                "fallback_property": str(rule.get("fallback_property") or "").strip(),
                "rule_type": str(rule.get("rule_type") or "numeric_range").strip(),
                "operator": str(rule.get("operator") or ">=").strip(),
                "value": check_value,  # display / UI key
                "check_value": check_value,  # Module 3 / RuleGenerator key
                "value_min": rule.get("value_min"),
                "value_max": rule.get("value_max"),
                "unit": str(rule.get("unit") or "").strip(),
                "applies_when": applies_when,
                "severity": str(rule.get("severity") or "mandatory").strip(),
                "keyword": str(rule.get("keyword") or "shall").strip(),
                "compliance_type": str(rule.get("compliance_type") or "prescriptive").strip(),
                "exceptions": rule.get("exceptions") or [],
                "related_refs": rule.get("related_refs") or [],
                "overridden_by": rule.get("overridden_by"),
                "confidence": float(rule.get("confidence") or 0.8),
                "extraction_method": "llm",
                "needs_review": bool(rule.get("needs_review", False)),
            }
        )

    return normalized
