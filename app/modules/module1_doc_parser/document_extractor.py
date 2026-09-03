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

An "instance" is an optional dict describing which Unstructured engine to use
— {name, kind ("local"|"hosted"), api_url, api_key, strategy} — as returned
by UnstructuredInstancesService (app/services/unstructured_instances_service.py).
Callers with access to that service (documents_service.py) resolve an
instance name (or the configured default) before calling in; callers that
don't pass one fall back to the legacy env-var-only hosted configuration
(UNSTRUCTURED_API_KEY / _API_URL / _STRATEGY), preserving old behavior.

Usage:
    from module1_doc_parser.document_extractor import extract_document_text
    text, tables = extract_document_text("code.pdf", file_bytes)                # auto
    text, tables = extract_document_text("code.pdf", file_bytes, parser="light")
    text, tables = extract_document_text(
        "code.pdf", file_bytes, parser="unstructured", instance=resolved_instance
    )
"""

from app.logging_config import get_logger

logger = get_logger(__name__)

PARSER_AUTO = "auto"
PARSER_UNSTRUCTURED = "unstructured"
PARSER_LIGHT = "light"
VALID_PARSERS = {PARSER_AUTO, PARSER_UNSTRUCTURED, PARSER_LIGHT}


def extract_document_text(
    filename: str, content: bytes, parser: str = PARSER_AUTO, instance: dict | None = None
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
                          "unstructured"    — force Unstructured; raises if no
                                              instance is configured or the call fails
                          "light"           — force the local, dependency-light
                                              extractor
        instance (dict | None): a resolved Unstructured instance — {name, kind,
                                 api_url, api_key, strategy} — selecting which
                                 configured engine (local container, or which
                                 hosted account) to use. When omitted, falls
                                 back to the legacy env-var-only hosted config.

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

    have_engine = bool(instance) or bool(UNSTRUCTURED_API_KEY)

    if parser == PARSER_UNSTRUCTURED and not have_engine:
        raise RuntimeError(
            "No Unstructured instance is configured; cannot force the 'unstructured' parser."
        )

    if have_engine:
        from app.modules.module1_doc_parser.unstructured_extractor import UnstructuredExtractor

        try:
            if instance:
                extractor = UnstructuredExtractor(
                    api_key=instance.get("api_key") or None,
                    api_url=instance.get("api_url") or None,
                    strategy=instance.get("strategy") or None,
                    kind=instance.get("kind") or "hosted",
                    name=instance.get("name"),
                )
            else:
                extractor = UnstructuredExtractor()
            text, tables = extractor.extract_bytes(content, filename)
            if text.strip():
                return text, tables
            logger.warning(
                "Unstructured extraction returned empty text filename=%s instance=%s",
                filename,
                instance.get("name") if instance else "env-default",
            )
        except Exception as exc:
            if parser == PARSER_UNSTRUCTURED:
                raise
            logger.warning(
                "Unstructured extraction failed filename=%s instance=%s error=%s — falling back to light extractor",
                filename,
                instance.get("name") if instance else "env-default",
                exc,
            )
    elif parser == PARSER_AUTO:
        logger.info(
            "No Unstructured instance configured — using light extractor for filename=%s", filename
        )

    return LightExtractor().extract(filename, content), []
