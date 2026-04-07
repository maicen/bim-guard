from io import BytesIO
import re

from pypdf import PdfReader


class Module1_DocReader:
    """
    Module 1: Document Reader
    Parses documents and extracts raw text/sections for rule conversion.
    """

    def parse_pdf(self, file_content: bytes) -> str:
        """Parse PDF document bytes and return extracted text."""
        if not file_content:
            return ""

        try:
            reader = PdfReader(BytesIO(file_content))
        except Exception:
            return ""

        parts = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            page_text = page_text.strip()
            if page_text:
                parts.append(page_text)

        return "\n\n".join(parts)

    def extract_text_sections(self, raw_text: str) -> list[str]:
        """Extract normalized, size-bounded text chunks from parsed document text."""
        normalized_text = self._normalize_text(raw_text)
        if not normalized_text:
            return []

        blocks = self._split_into_blocks(normalized_text)
        return self._chunk_blocks(blocks)

    def _normalize_text(self, raw_text: str) -> str:
        text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]

        normalized_lines = []
        previous_blank = False
        for line in lines:
            if not line:
                if not previous_blank:
                    normalized_lines.append("")
                previous_blank = True
                continue

            normalized_lines.append(line)
            previous_blank = False

        return "\n".join(normalized_lines).strip()

    def _split_into_blocks(self, normalized_text: str) -> list[str]:
        blocks = []
        current_lines = []
        for line in normalized_text.split("\n"):
            if not line:
                if current_lines:
                    blocks.append(" ".join(current_lines).strip())
                    current_lines = []
                continue

            if current_lines and self._starts_new_block(line):
                blocks.append(" ".join(current_lines).strip())
                current_lines = [line]
                continue

            current_lines.append(line)

        if current_lines:
            blocks.append(" ".join(current_lines).strip())

        return blocks or [normalized_text]

    def _starts_new_block(self, line: str) -> bool:
        return bool(
            re.match(r"^(?:[-*•]\s+|\d+(?:\.\d+)*[.)]\s+)", line)
            or (len(line) <= 100 and (line.isupper() or line.endswith(":")))
        )

    def _chunk_blocks(self, blocks: list[str], max_chars: int = 3500) -> list[str]:
        chunks = []
        current = []
        current_size = 0

        for block in blocks:
            oversized_blocks = self._split_large_block(block, max_chars)
            for piece in oversized_blocks:
                piece_size = len(piece)
                separator_size = 2 if current else 0
                if current and current_size + separator_size + piece_size > max_chars:
                    chunks.append("\n\n".join(current).strip())
                    current = [piece]
                    current_size = piece_size
                    continue

                current.append(piece)
                current_size += separator_size + piece_size

        if current:
            chunks.append("\n\n".join(current).strip())

        return [chunk for chunk in chunks if chunk]

    def _split_large_block(self, block: str, max_chars: int) -> list[str]:
        if len(block) <= max_chars:
            return [block]

        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", block)
            if sentence.strip()
        ]
        if len(sentences) <= 1:
            sentences = [
                segment.strip() for segment in block.split(" ") if segment.strip()
            ]

        chunks = []
        current = []
        current_size = 0
        joiner = " "

        for sentence in sentences:
            sentence_size = len(sentence)
            separator_size = len(joiner) if current else 0
            if current and current_size + separator_size + sentence_size > max_chars:
                chunks.append(joiner.join(current).strip())
                current = [sentence]
                current_size = sentence_size
                continue

            current.append(sentence)
            current_size += separator_size + sentence_size

        if current:
            chunks.append(joiner.join(current).strip())

        return chunks
