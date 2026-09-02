"""
module1_doc_parser/document_extractor.py
-------------------------------------------
Unified document-text extraction entry point used by both the web upload
flow (documents_service.py) and the CLI/enhanced pipelines (orchestrator.py,
enhanced_orchestrator.py).

Two engines:
  - UnstructuredExtractor (primary) — Unstructured's Workflow/Jobs API.
    Best quality (layout-aware text + real tables), but uploads the file,
    needs UNSTRUCTURED_API_KEY, and takes several-to-tens of seconds per
    document (it's an async job under the hood, not a synchronous call).
  - LightExtractor (fallback) — plain per-format readers (pypdf, python-docx,
    openpyxl, csv), no upload, no API key, no tables, effectively instant.

Usage:
    from module1_doc_parser.document_extractor import extract_document_text
    text, tables = extract_document_text("code.pdf", file_bytes)                # auto
    text, tables = extract_document_text("code.pdf", file_bytes, parser="light")
"""

from app.logging_config import get_logger

logger = get_logger(__name__)

PARSER_AUTO = "auto"
PARSER_UNSTRUCTURED = "unstructured"
PARSER_LIGHT = "light"
VALID_PARSERS = {PARSER_AUTO, PARSER_UNSTRUCTURED, PARSER_LIGHT}


def extract_document_text(
    filename: str, content: bytes, parser: str = PARSER_AUTO
) -> tuple:
    """
    Extract text (and tables, when available) from an uploaded document.

    Args:
        filename (str):   original filename, used to pick the format reader
        content  (bytes):  raw file bytes
        parser   (str):   "auto" (default)  — Unstructured if a key is
                                              configured, else LightExtractor;
                                              also falls back automatically on
                                              a failed or empty extraction
                          "unstructured"    — force the hosted API; raises if
                                              the key is missing or the call fails
                          "light"           — force the local, dependency-light
                                              extractor

    Returns:
        text   (str)
        tables (list[dict])
    """
    if parser not in VALID_PARSERS:
        raise ValueError(f"Unknown parser '{parser}'. Expected one of {sorted(VALID_PARSERS)}.")

    from app.modules.config import UNSTRUCTURED_API_KEY
    from app.modules.module1_doc_parser.light_extractor import LightExtractor

    if parser == PARSER_LIGHT:
        return LightExtractor().extract(filename, content), []

    if parser == PARSER_UNSTRUCTURED and not UNSTRUCTURED_API_KEY:
        raise RuntimeError(
            "UNSTRUCTURED_API_KEY is not set; cannot force the 'unstructured' parser."
        )

    if UNSTRUCTURED_API_KEY:
        from app.modules.module1_doc_parser.unstructured_extractor import UnstructuredExtractor

        try:
            text, tables = UnstructuredExtractor().extract_bytes(content, filename)
            if text.strip():
                return text, tables
            logger.warning(
                "Unstructured extraction returned empty text filename=%s", filename
            )
        except Exception as exc:
            if parser == PARSER_UNSTRUCTURED:
                raise
            logger.warning(
                "Unstructured extraction failed filename=%s error=%s — falling back to light extractor",
                filename,
                exc,
            )
    elif parser == PARSER_AUTO:
        logger.info(
            "UNSTRUCTURED_API_KEY not set — using light extractor for filename=%s", filename
        )

    return LightExtractor().extract(filename, content), []
