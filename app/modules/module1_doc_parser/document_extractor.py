"""
module1_doc_parser/document_extractor.py
-------------------------------------------
Unified document-text extraction entry point used by both the web upload
flow (documents_service.py) and the CLI/enhanced pipelines (orchestrator.py,
enhanced_orchestrator.py).

Structured extraction is pluggable: any number of engine "kinds" (Unstructured
local/hosted, Docling hosted/local, and whatever gets added later) can be
selected via an "instance" dict's `kind`, dispatched through
ParsingEngineRegistry (app/modules/module1_doc_parser/engines) rather than a
hardcoded per-kind chain here — this module only knows the *shape* of an
engine (ParsingEngine: extract_bytes(content, filename) -> (text, tables)),
never a concrete extractor class. See engines/base.py for the abstraction and
engines/unstructured_driver.py / engines/docling_driver.py for the currently
registered kinds. LightExtractor (fallback) is the one hardcoded engine —
plain per-format readers (pypdf, python-docx, openpyxl, csv), no upload, no
API key, no tables, effectively instant, and always available regardless of
what's configured.

An "instance" is an optional dict describing which structured-extraction
engine to use — {name, kind, api_url, api_key, strategy} — as returned by
ParsingEngineInstancesService (app/services/parsing_engine_instances_service.py).
Callers with access to that service (documents_service.py) resolve an
instance name (or the configured default) before calling in; callers that
don't pass one fall back to the legacy env-var-only hosted Unstructured
configuration (UNSTRUCTURED_API_KEY / _API_URL / _STRATEGY), preserving old
behavior.

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


def _build_extractor(instance: dict | None):
    """Build the ParsingEngine matching an instance's kind (or the legacy hosted default).

    Dispatch goes through ParsingEngineRegistry — adding a new engine kind
    never means adding a branch here.
    """
    from app.modules.module1_doc_parser.engines import ParsingEngineRegistry

    kind = (instance or {}).get("kind") or "hosted"
    driver = ParsingEngineRegistry.get(kind)
    return driver.build(
        api_key=(instance or {}).get("api_key") or "",
        api_url=(instance or {}).get("api_url") or "",
        strategy=(instance or {}).get("strategy") or "",
        name=(instance or {}).get("name") or driver.kind,
    )


def extract_document_text(
    filename: str, content: bytes, parser: str = PARSER_AUTO, instance: dict | None = None
) -> tuple:
    """
    Extract text (and tables, when available) from an uploaded document.

    Args:
        filename (str):   original filename, used to pick the format reader
        content  (bytes):  raw file bytes
        parser   (str):   "auto" (default)  — the configured engine if one is
                                              available, else LightExtractor;
                                              also falls back automatically on
                                              a failed or empty extraction
                          "unstructured"    — force the configured engine; raises
                                              if none is configured or the call fails
                          "light"           — force the local, dependency-light
                                              extractor
        instance (dict | None): a resolved engine instance — {name, kind,
                                 api_url, api_key, strategy} — selecting which
                                 configured engine (local Unstructured container,
                                 a hosted Unstructured account, or a hosted
                                 Docling instance) to use. When omitted, falls
                                 back to the legacy env-var-only hosted
                                 Unstructured config.

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
            "No parsing engine instance is configured; cannot force the 'unstructured' parser."
        )

    if have_engine:
        try:
            extractor = _build_extractor(instance)
            text, tables = extractor.extract_bytes(content, filename)
            if text.strip():
                return text, tables
            logger.warning(
                "Structured extraction returned empty text filename=%s instance=%s",
                filename,
                instance.get("name") if instance else "env-default",
            )
        except Exception as exc:
            if parser == PARSER_UNSTRUCTURED:
                raise
            logger.warning(
                "Structured extraction failed filename=%s instance=%s error=%s — falling back to light extractor",
                filename,
                instance.get("name") if instance else "env-default",
                exc,
            )
    elif parser == PARSER_AUTO:
        logger.info(
            "No parsing engine instance configured — using light extractor for filename=%s", filename
        )

    return LightExtractor().extract(filename, content), []
