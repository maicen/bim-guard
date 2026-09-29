"""Splits extracted markdown or plain text into section chunks.

document_parsing/section_chunker.py
-----------------------------------
Step 3 — Splits extracted markdown/plain text into section chunks.

Recognises headings in this priority order (every section keeps the heading's
own text as its name):
  1. Top-level numbered headings ("4 Stairs", "01 Core Dimensions").
  2. Real dotted-decimal numbering ("9.8.2.1.  Stair Width") — the actual
     Article/Sentence numbering scheme building codes use, independent of
     markdown. This is what
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

# ── 1. Top-level numbered headings: "4 Stairs", "01 Core Dimensions",
# "12 Units ...". A 1-2 digit number (zero-padded or not) followed by
# whitespace and a capitalised title. Requiring whitespace straight after the
# number keeps a numbered table row ("1.  Private stairs(1) 200 125...") from
# matching.
_TOP_LEVEL_HEADING = re.compile(r"^(\d{1,2})\s+[A-Z].+")

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

        m = _TOP_LEVEL_HEADING.match(s)
        if m:
            return m.group(1), s[:100]

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
        if re.match(r"^TABLE\s+OF\s+(CONTENTS|TABLES|FIGURES)\b", heading_text, re.IGNORECASE):
            return None, heading_text.strip()
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
        preamble_lines = []

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
            else:
                preamble_lines.append(line.strip())

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

        # Text before the first recognised heading is kept as its own chunk
        # rather than dropped -- an unrecognised heading style would otherwise
        # silently discard everything above the first one that does match.
        preamble = "\n".join(preamble_lines).strip()
        if preamble and chunks:
            chunks.insert(
                0,
                {
                    "section_number": None,
                    "section_name": None,
                    "text": preamble,
                    "char_count": len(preamble),
                },
            )

        print(f"[SectionChunker] {len(chunks)} sections detected")
        for c in chunks:
            print(f"  {c['section_number'] or '-':<6} {c['section_name'] or '(preamble)':<40} {c['char_count']:>8,} chars")

        return chunks
