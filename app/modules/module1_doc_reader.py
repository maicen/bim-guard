from io import BytesIO

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
        """Extract text sections from parsed document text."""
        if not raw_text.strip():
            return []
        return [
            section.strip() for section in raw_text.split("\n\n") if section.strip()
        ]
