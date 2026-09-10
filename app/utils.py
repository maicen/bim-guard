import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from starlette.responses import RedirectResponse

# Kept in sync with the input formats Docling converts to DocLang (see
# https://docling-project.github.io/docling/usage/supported_formats/):
# PDF, Word, Excel, PowerPoint, HTML, AsciiDoc, Markdown, CSV, and common
# raster image formats. Plus pre-converted DocLang files — standard XML (.dclg, .doclang)
# and DocLang Archive (.dclx) exports that are ingested as-is, with no Docling conversion
# step, and need no original PDF/DOCX source document alongside them.
ALLOWED_DOCUMENT_SUFFIXES = {
    ".pdf",
    ".docx",
    ".xlsx",
    ".pptx",
    ".md",
    ".markdown",
    ".adoc",
    ".asciidoc",
    ".html",
    ".htm",
    ".csv",
    ".txt",
    ".png",
    ".jpg",
    ".jpeg",
    ".tiff",
    ".tif",
    ".bmp",
    ".webp",
    ".doclang",
    ".dclg",
    ".dclx",
}
MAX_DOCUMENT_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB cap on a single uploaded/imported document

_OOXML_MIME = "application/octet-stream"
ALLOWED_DOCUMENT_MIME_BY_SUFFIX = {
    ".pdf": {"application/pdf"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        _OOXML_MIME,
    },
    ".xlsx": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        _OOXML_MIME,
    },
    ".pptx": {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        _OOXML_MIME,
    },
    ".md": {"text/markdown", "text/x-markdown", "text/plain"},
    ".markdown": {"text/markdown", "text/x-markdown", "text/plain"},
    ".adoc": {"text/plain", "text/x-asciidoc", _OOXML_MIME},
    ".asciidoc": {"text/plain", "text/x-asciidoc", _OOXML_MIME},
    ".html": {"text/html"},
    ".htm": {"text/html"},
    ".csv": {"text/csv", "application/vnd.ms-excel", "text/plain"},
    ".txt": {"text/plain"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".tiff": {"image/tiff"},
    ".tif": {"image/tiff"},
    ".bmp": {"image/bmp", "image/x-ms-bmp"},
    ".webp": {"image/webp"},
    ".doclang": {"text/xml", "application/xml", "text/plain", _OOXML_MIME, ""},
    ".dclg": {"text/xml", "application/xml", "text/plain", _OOXML_MIME, ""},
    ".dclx": {"application/zip", "application/x-zip-compressed", _OOXML_MIME},
}


def now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def md5_hex(content: bytes) -> str:
    return hashlib.md5(content).hexdigest()


def safe_upload_name(filename: str | None) -> str:
    return Path(filename or "").name


def store_upload_bytes(filename: str, content: bytes, destination_dir: Path) -> Path:
    stored_name = f"{uuid.uuid4().hex}_{filename}"
    stored_path = destination_dir / stored_name
    stored_path.write_bytes(content)
    return stored_path


def is_likely_text_content(content: bytes) -> bool:
    sample = content[:4096]
    if b"\x00" in sample:
        return False
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


_IMAGE_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".bmp": (b"BM",),
    ".tif": (b"II*\x00", b"MM\x00*"),
    ".tiff": (b"II*\x00", b"MM\x00*"),
    ".webp": (b"RIFF",),
}


def validate_document_upload(
    filename: str,
    content_type: str | None,
    file_content: bytes,
) -> str | None:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_DOCUMENT_SUFFIXES:
        return (
            "Unsupported file type. Supported formats: PDF, Word (.docx), Excel (.xlsx), "
            "PowerPoint (.pptx), HTML, AsciiDoc, Markdown, CSV, TXT, common image formats "
            "(PNG/JPEG/TIFF/BMP/WEBP), and pre-converted DocLang files (.dclg, .dclx, .doclang)."
        )

    normalized_content_type = (content_type or "").split(";", 1)[0].strip().lower()
    allowed_mime_types = ALLOWED_DOCUMENT_MIME_BY_SUFFIX.get(suffix, set())
    if normalized_content_type not in allowed_mime_types:
        return f"Invalid MIME type '{normalized_content_type or 'unknown'}' for {suffix} file."

    if not file_content:
        return "Uploaded file is empty."

    if len(file_content) > MAX_DOCUMENT_UPLOAD_BYTES:
        return (
            f"Uploaded file is too large ({len(file_content) / (1024 * 1024):.1f} MB). "
            f"Maximum allowed size is {MAX_DOCUMENT_UPLOAD_BYTES // (1024 * 1024)} MB."
        )

    if suffix == ".pdf" and not file_content.startswith(b"%PDF-"):
        return "Uploaded file content does not match a valid PDF signature."

    if suffix in {".docx", ".xlsx", ".pptx", ".dclx"} and not file_content.startswith(b"PK"):
        return f"Uploaded file content does not match a valid {suffix} (zip) signature."

    if suffix in {".md", ".markdown", ".txt", ".csv", ".adoc", ".asciidoc", ".html", ".htm"} and not is_likely_text_content(
        file_content
    ):
        return f"Uploaded {suffix} file appears to be binary content."

    image_signatures = _IMAGE_SIGNATURES.get(suffix)
    if image_signatures and not file_content.startswith(image_signatures):
        return f"Uploaded file content does not match a valid {suffix} image signature."

    if suffix in {".doclang", ".dclg"}:
        if not is_likely_text_content(file_content):
            return f"Uploaded {suffix} file must be UTF-8 encoded XML text."
        if not file_content.lstrip().startswith(b"<"):
            return f"Uploaded {suffix} file does not look like DocLang XML (expected it to start with '<')."

    return None


def redirect_see_other(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


def rows_desc_by_id(table) -> list[dict]:
    return sorted(list(table.rows), key=lambda row: row["id"], reverse=True)


from app.services.cache import (  # noqa: E402
    cache_db_query,
    cache_stats,
    clear_cache,
    get_cache,
    invalidate_cache,
    local_cache,
)

__all__ = [
    "ALLOWED_DOCUMENT_MIME_BY_SUFFIX",
    "ALLOWED_DOCUMENT_SUFFIXES",
    "MAX_DOCUMENT_UPLOAD_BYTES",
    "cache_db_query",
    "cache_stats",
    "clear_cache",
    "get_cache",
    "invalidate_cache",
    "is_likely_text_content",
    "local_cache",
    "md5_hex",
    "now_iso_utc",
    "redirect_see_other",
    "rows_desc_by_id",
    "safe_upload_name",
    "store_upload_bytes",
    "validate_document_upload",
]


