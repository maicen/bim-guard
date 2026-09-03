"""
document_parsing/section_chunker.py
---------------------------------------
Step 3 — Splits extracted markdown/plain text into section chunks.

Recognises headings in this priority order:
  1. The original 13-topic code taxonomy ("# 4 Stairs", "4 Stairs...")
     — exact match required, preserved for backward compatibility.
  2. Real dotted-decimal numbering ("9.8.2.1.  Stair Width") — the actual
     Article/Sentence numbering scheme building codes use, independent of
     markdown and independent of the 13-topic taxonomy above. This is what
      pypdf's plain-text extraction of a real code PDF looks like, so it's the
     pattern the live document-upload -> extract-rules flow actually needs.
  3. Any markdown heading, any level ("## SECTION 8.14 ...") — the extractor's
     own structural markers, independent of numbering scheme.
  4. "SECTION 8.14 ...", "CHAPTER 3 ...", "PART II ..." style plain-text
     headings, for documents whose PDF backend didn't preserve markdown "#".

Documents whose PDF extraction collapses to too few line breaks for any of
the above to find (e.g. a single undifferentiated block of text) yield zero
chunks here; callers should fall back to a generic size-bounded chunker
(see DocumentReader.extract_text_sections) rather than sending nothing
downstream.

Usage:
    from document_parsing.section_chunker import SectionChunker
    chunker = SectionChunker()
    chunks  = chunker.chunk(extracted_text)
"""

import re

CODE_SECTION_HEADINGS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13"]

CODE_SECTION_NAMES = {
    "1": "Building Basics",
    "2": "Means of Egress and Exit Paths",
    "3": "Doors (Detailed)",
    "4": "Stairs (Detailed - Part 9)",
    "5": "Ramps",
    "6": "Guards and Handrails",
    "7": "Windows and Glazing",
    "8": "Washrooms and Basic Accessibility",
    "9": "Plumbing Fixture Counts",
    "10": "Fire Protection",
    "11": "Garage and Carport",
    "12": "Spatial Separation to Property Line",
    "13": "Model QA",
}

# ── 1. Original 13-topic taxonomy — unchanged, exact match only ──────────────
_CODE_MD_HEADING = re.compile(r"^#{1,3}\s+(1[0-3]|[1-9])\s+.+")
_CODE_TXT_HEADING = re.compile(r"^(1[0-3]|[1-9])[\s\.].+")

# ── 2. Real dotted-decimal Article numbering, e.g. "9.8.2.1.  Stair Width"
# or "9.8.2.  Stair Dimensions" — 3 to 5 dot-separated components. Requires
# >=2 dots so a bare decimal mid-prose ("3.7 m") can't false-match, and a
# capitalised title after the number so a numbered clause ("(1) Except...",
# which starts with "(" anyway) or a table data row ("1.  Private stairs(1)
# 200 125...", which has no further dotted digits after "1.") can't either.
_CODE_DOTTED_HEADING = re.compile(r"^(\d+(?:\.\d+){2,4})\.?\s+[A-Z].+")

# ── 3. Any markdown heading, any level, any numbering scheme ─────────────────
_MD_ANY_HEADING = re.compile(r"^(#{1,6})\s+(.+)$")

# ── 4. "SECTION 8.14 ...", "CHAPTER 3 ...", "PART II ..." plain-text headings.
# Requires the line to start with the keyword — real prose essentially never
# opens a line this way, so this is a low false-positive-risk pattern.
_SECTION_WORD_HEADING = re.compile(
    r"^(SECTION|Section|CHAPTER|Chapter|PART|Part)\s+([\w.]+)\.?\s*(.*)$"
)

_TRAILING_NUMBER = re.compile(r"\d+(?:\.\d+)*")


class SectionChunker:
    def _detect_section(self, line: str):
        """Return (section_number, section_name) for a heading line, else None."""
        s = line.strip()
        if not s:
            return None

        if _CODE_MD_HEADING.match(s):
            m = re.search(r"(1[0-3]|[1-9])", s)
            if m:
                num = m.group(1)
                return num, CODE_SECTION_NAMES.get(num, "Unknown")

        if _CODE_TXT_HEADING.match(s):
            m = re.match(r"^(1[0-3]|[1-9])", s)
            if m:
                candidate = m.group(1)
                if s[len(candidate) : len(candidate) + 1] == " ":
                    return candidate, CODE_SECTION_NAMES.get(candidate, "Unknown")

        m = _CODE_DOTTED_HEADING.match(s)
        if m:
            return m.group(1), s[:100]

        m = _MD_ANY_HEADING.match(s)
        if m:
            return self._derive_number_and_name(m.group(2).strip())

        m = _SECTION_WORD_HEADING.match(s)
        if m:
            keyword, ref, rest = m.group(1), m.group(2), m.group(3).strip()
            name = f"{keyword} {ref}" + (f" — {rest[:80]}" if rest else "")
            return ref, name[:100]

        return None

    @staticmethod
    def _derive_number_and_name(heading_text: str):
        """Build a (number, name) pair from an arbitrary heading string."""
        m = _TRAILING_NUMBER.search(heading_text)
        number = m.group(0) if m else heading_text[:20] or "?"
        name = heading_text[:100] or number
        return number, name

    def chunk(self, full_text: str) -> list:
        lines = full_text.split("\n")
        chunks = []
        current_num = None
        current_name = None
        current_lines = []

        for line in lines:
            detected = self._detect_section(line)
            if detected:
                num, name = detected
                if current_num and current_lines:
                    text = "\n".join(current_lines).strip()
                    chunks.append(
                        {
                            "section_number": current_num,
                            "section_name": current_name,
                            "text": text,
                            "char_count": len(text),
                        }
                    )
                current_num, current_name = num, name
                current_lines = [line.strip()]
            elif current_num:
                current_lines.append(line.strip())

        if current_num and current_lines:
            text = "\n".join(current_lines).strip()
            chunks.append(
                {
                    "section_number": current_num,
                    "section_name": current_name,
                    "text": text,
                    "char_count": len(text),
                }
            )

        print(f"[SectionChunker] {len(chunks)} sections detected")
        for c in chunks:
            print(f"  {c['section_number']:<6} {c['section_name']:<40} {c['char_count']:>8,} chars")

        return chunks
