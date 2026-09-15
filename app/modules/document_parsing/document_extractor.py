"""
document_parsing/document_extractor.py
-------------------------------------------
Unified document-text extraction entry point used by both the web upload
flow (documents_service.py) and the CLI/enhanced pipelines (orchestrator.py,
enhanced_orchestrator.py).

Structured extraction is pluggable: any number of engine "kinds" (today just
Docling hosted/local, and whatever gets added later) can be selected via an
"instance" dict's `kind`, dispatched through ParsingEngineRegistry
(app/modules/document_parsing/engines) rather than a hardcoded per-kind chain
here — this module only knows the *shape* of an engine
(ParsingEngine: extract_bytes(content, filename) -> (text, tables)), never a
concrete extractor class. See engines/base.py for the abstraction and
engines/docling_driver.py for the currently registered kinds.

There is no dependency-light fallback engine: when no parsing engine
instance is configured, or the configured one fails or returns empty text,
this raises `NoParsingEngineConfiguredError` rather than silently degrading
— callers (documents_service.py) let that propagate so the failure is
visible at upload time instead of surfacing later as an empty document.

An "instance" is an optional dict describing which structured-extraction
engine to use — {name, kind, api_url, api_key, strategy} — as returned by
ParsingEngineInstancesService (app/services/parsing_engine_instances_service.py).
Callers resolve an instance name (or the configured default) before calling
in; extraction cannot proceed without one.

Usage:
    from document_parsing.document_extractor import extract_document_text
    text, tables, pages = extract_document_text(
        "code.pdf", file_bytes, instance=resolved_instance
    )
"""

from app.logging_config import get_logger

logger = get_logger(__name__)

PARSER_AUTO = "auto"
VALID_PARSERS = {PARSER_AUTO}


class NoParsingEngineConfiguredError(RuntimeError):
    """Raised when document text extraction cannot proceed.

    `had_instance=False` means no parsing engine instance was resolved at
    all (nothing configured for the caller's org or the platform default);
    `had_instance=True` means an instance was resolved but its extraction
    failed or returned empty text (see `cause`).
    """

    def __init__(
        self,
        filename: str,
        *,
        had_instance: bool,
        instance_name: str | None = None,
        cause: Exception | None = None,
    ):
        self.filename = filename
        self.had_instance = had_instance
        self.instance_name = instance_name
        self.cause = cause
        if had_instance:
            message = (
                f"Parsing engine '{instance_name}' failed to extract text from "
                f"'{filename}'" + (f": {cause}" if cause else " (empty result).")
            )
        else:
            message = (
                f"No parsing engine instance is configured; cannot extract text from '{filename}'."
            )
        super().__init__(message)


def _build_extractor(instance: dict | None):
    """Build the ParsingEngine matching an instance's kind.

    Dispatch goes through ParsingEngineRegistry — adding a new engine kind
    never means adding a branch here.
    """
    from app.modules.document_parsing.engines import ParsingEngineRegistry

    kind = (instance or {}).get("kind") or "docling"
    driver = ParsingEngineRegistry.get(kind)
    return driver.build(
        api_key=(instance or {}).get("api_key") or "",
        api_url=(instance or {}).get("api_url") or "",
        strategy=(instance or {}).get("strategy") or "",
        name=(instance or {}).get("name") or driver.kind,
    )


def extract_document_text(
    filename: str,
    content: bytes,
    parser: str = PARSER_AUTO,
    instance: dict | None = None,
    return_doclang: bool = False,
) -> tuple:
    """
    Extract text (and tables, when available) from an uploaded document.

    Args:
        filename (str):   original filename, used to pick the format reader
        content  (bytes):  raw file bytes
        parser   (str):   validated against VALID_PARSERS (currently just
                          "auto") for forward-compatibility; has no effect
                          today since Docling is the only registered engine
        instance (dict | None): a resolved engine instance — {name, kind,
                                 api_url, api_key, strategy} — selecting which
                                 configured engine (local self-hosted Docling
                                 container or a hosted Docling instance) to
                                 use. Required: raises `NoParsingEngineConfiguredError`
                                 when omitted.
        return_doclang (bool):  when True, returns (text, tables, pages, doclang_xml, bboxes)

    Returns:
        text   (str)
        tables (list[dict])
        pages  (list[dict]): [{"page_number": int, "text": str}, ...]
        (plus doclang_xml, bboxes when return_doclang=True)

    Raises:
        NoParsingEngineConfiguredError: no instance was resolved, or the
            resolved instance's extraction failed / returned empty text.
    """
    if parser not in VALID_PARSERS:
        raise ValueError(f"Unknown parser '{parser}'. Expected one of {sorted(VALID_PARSERS)}.")

    if not instance:
        raise NoParsingEngineConfiguredError(filename, had_instance=False)

    instance_name = instance.get("name") or "unnamed"
    try:
        extractor = _build_extractor(instance)
        doclang_xml = ""
        bboxes = []
        if return_doclang and hasattr(extractor, "extract_bytes"):
            try:
                res = extractor.extract_bytes(content, filename, return_doclang=True)
                if len(res) == 5:
                    text, tables, pages, doclang_xml, bboxes = res
                else:
                    text, tables, pages = res[:3]
            except TypeError:
                text, tables, pages = extractor.extract_bytes(content, filename)
        else:
            text, tables, pages = extractor.extract_bytes(content, filename)
    except Exception as exc:
        raise NoParsingEngineConfiguredError(
            filename, had_instance=True, instance_name=instance_name, cause=exc
        ) from exc

    if not text.strip():
        raise NoParsingEngineConfiguredError(filename, had_instance=True, instance_name=instance_name)

    if return_doclang:
        return text, tables, pages, doclang_xml, bboxes
    return text, tables, pages
