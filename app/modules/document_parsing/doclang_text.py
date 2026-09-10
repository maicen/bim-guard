"""Plain text derivation from DocLang XML.

Replaces the retired ``documents.extracted_text`` column: DocLang is now the
only persisted text representation, so any caller that previously read
``extracted_text`` derives its plain text from DocLang on demand instead.
"""

from __future__ import annotations

from app.modules.document_parsing.doclang_chunker import DocLangChunker


def doclang_to_text(doclang_xml: str) -> str:
    """Flatten DocLang XML into plain text by joining its section/paragraph chunks."""
    if not doclang_xml or not doclang_xml.strip():
        return ""
    chunks = DocLangChunker().chunk(doclang_xml)
    return "\n\n".join(chunk["text"] for chunk in chunks if chunk.get("text"))
