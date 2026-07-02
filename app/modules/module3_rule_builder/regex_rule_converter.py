"""
module3_rule_builder/regex_rule_converter.py
------------------------------------------------
Free, offline alternative to rule_converter.py (GPT-4o). Same public
interface (extract_rules(chunk) -> list[dict]) so orchestrator.py can
swap between the two via the USE_GPT4O flag with no other changes.

Pattern-matches the common OBC prose phrasings ("shall be at least
X mm", "between X and Y mm", "shall not...") instead of calling an LLM.
Trades recall for zero cost: anything it can't confidently parse is
simply skipped rather than guessed at.

Usage:
    from module3_rule_builder.regex_rule_converter import RegexRuleConverter
    converter = RegexRuleConverter()
    rules = converter.extract_rules(chunk)
"""

import re

try:
    from config import OBC_TO_IFC_MAP
except ImportError:
    from app.modules.config import OBC_TO_IFC_MAP


# ── Property name keywords ───────────────────────────────────────────────────
# Checked longest-phrase-first against the paragraph text to pick property_name.
PROPERTY_KEYWORDS = [
    ("riser height", "RiserHeight"),
    ("riser", "RiserHeight"),
    ("tread depth", "TreadDepth"),
    ("tread", "TreadDepth"),
    ("headroom", "HeadroomClearance"),
    ("clear width", "Width"),
    ("clearance", "Clearance"),
    ("width", "Width"),
    ("height", "Height"),
    ("slope", "Slope"),
    ("area", "Area"),
    ("depth", "Depth"),
    ("length", "Length"),
    ("thickness", "Thickness"),
]

UNIT_ALIASES = {
    "millimetres": "mm",
    "millimetre": "mm",
    "millimeters": "mm",
    "millimeter": "mm",
    "degrees": "deg",
    "degree": "deg",
    "metres": "m",
    "metre": "m",
    "meters": "m",
    "meter": "m",
    "mm": "mm",
    "m2": "m2",
    "m²": "m2",
    "deg": "deg",
    "°": "deg",
    "%": "ratio",
    "m": "m",
}
# Longest alias first so "mm" / "millimetres" win over a bare "m" at the same position.
_UNIT_PATTERN = "|".join(re.escape(u) for u in sorted(UNIT_ALIASES, key=len, reverse=True))
_NUM = r"(\d+(?:\.\d+)?)"

# (regex, operator, rule_type). Checked in order; first match wins.
_PATTERNS = [
    (
        re.compile(
            rf"\bbetween\s+{_NUM}\s*(?:{_UNIT_PATTERN})?\s+and\s+{_NUM}\s*({_UNIT_PATTERN})\b",
            re.IGNORECASE,
        ),
        "between",
        "numeric_range",
    ),
    (
        re.compile(
            rf"\b(?:not less than|no less than|minimum(?: of)?|at least)\s+{_NUM}\s*({_UNIT_PATTERN})\b",
            re.IGNORECASE,
        ),
        ">=",
        "numeric_comparison",
    ),
    (
        re.compile(
            rf"\b(?:not more than|no more than|maximum(?: of)?|at most)\s+{_NUM}\s*({_UNIT_PATTERN})\b",
            re.IGNORECASE,
        ),
        "<=",
        "numeric_comparison",
    ),
    (
        re.compile(
            rf"\bshall be\s+{_NUM}\s*({_UNIT_PATTERN})\b",
            re.IGNORECASE,
        ),
        "==",
        "numeric_comparison",
    ),
]

_PROHIBITION_PATTERN = re.compile(
    r"\b(?:shall not|must not|is prohibited|are prohibited|not permitted)\b",
    re.IGNORECASE,
)

# OBC-style section references, e.g. "9.8.2.1.(2)"
_REF_PATTERN = re.compile(r"\b\d+(?:\.\d+){2,}(?:\.\(\d+\))?\b")


class RegexRuleConverter:
    """
    Free, offline rule extraction using keyword + regex pattern matching.
    Drop-in replacement for RuleConverter (rule_converter.py) when
    USE_GPT4O is False — no API key, no network call.
    """

    def _detect_target(self, text: str) -> str | None:
        lowered = text.lower()
        for keyword, ifc_class in OBC_TO_IFC_MAP.items():
            if keyword in lowered:
                return ifc_class
        return None

    def _detect_property(self, text: str) -> str | None:
        lowered = text.lower()
        for keyword, property_name in PROPERTY_KEYWORDS:
            if keyword in lowered:
                return property_name
        return None

    def _detect_ref(self, text: str, fallback: str) -> str:
        match = _REF_PATTERN.search(text)
        return match.group(0) if match else fallback

    def _build_rule(self, paragraph: dict, chunk: dict) -> dict | None:
        text = paragraph["text"]
        target = self._detect_target(text)
        if not target:
            return None  # can't tell what IFC element this paragraph applies to

        ref = self._detect_ref(text, chunk.get("section_number", ""))

        if _PROHIBITION_PATTERN.search(text):
            return {
                "ref": ref,
                "desc": text[:200],
                "source_text": text,
                "target": target,
                "rule_type": "prohibition",
                "operator": "not_exists",
                "severity": "mandatory",
                "keyword": "shall not",
                "confidence": 0.5,
                "extraction_method": "regex",
                "needs_review": True,
            }

        for pattern, operator, rule_type in _PATTERNS:
            match = pattern.search(text)
            if not match:
                continue

            property_name = self._detect_property(text)
            if not property_name:
                continue  # numeric threshold found but no property to attach it to

            rule = {
                "ref": ref,
                "desc": text[:200],
                "source_text": text,
                "target": target,
                "property_name": property_name,
                "rule_type": rule_type,
                "operator": operator,
                "severity": "mandatory",
                "keyword": "shall",
                "confidence": 0.5,
                "extraction_method": "regex",
                "needs_review": True,
            }

            if operator == "between":
                value_min, value_max, unit = match.groups()
                rule["value_min"] = float(value_min)
                rule["value_max"] = float(value_max)
                rule["unit"] = UNIT_ALIASES.get(unit.lower(), unit.lower())
            else:
                value, unit = match.groups()
                rule["check_value"] = float(value)
                rule["unit"] = UNIT_ALIASES.get(unit.lower(), unit.lower())

            return rule

        return None

    # ── PUBLIC API ────────────────────────────────────────────────────────────

    def extract_rules(self, chunk: dict) -> list:
        """
        Scan one scored section chunk for regex-matchable compliance rules.
        Only looks at HIGH/MEDIUM confidence paragraphs — LOW_CONFIDENCE text
        is too noisy for pattern matching to be reliable without an LLM.

        Args:
            chunk (dict): scored section chunk from keyword_filter.py.
                          Must have key: scored_paragraphs (list of
                          {text, score, matched, confidence}).

        Returns:
            list[dict]: raw rule dicts ready for RuleGenerator.save_batch()
        """
        section = chunk.get("section_number", "?")
        paragraphs = chunk.get("scored_paragraphs", [])
        rules = []

        for paragraph in paragraphs:
            if paragraph["confidence"] == "LOW_CONFIDENCE":
                continue

            rule = self._build_rule(paragraph, chunk)
            if rule:
                rule["obc_section_number"] = chunk.get("section_number")
                rule["obc_section_name"] = chunk.get("section_name")
                rules.append(rule)

        print(f"  [RegexRuleConverter] Section {section}: extracted {len(rules)} rules")
        return rules
