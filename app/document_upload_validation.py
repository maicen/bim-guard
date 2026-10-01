import hashlib
import uuid
from pathlib import Path

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


def md5_hex(content: bytes) -> str:
    return hashlib.md5(content).hexdigest()

def md5_file(filepath: Path) -> str:
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()



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
        return True
    except UnicodeDecodeError:
        # If byte 4096 cut a multi-byte sequence, slice to the last valid UTF-8 boundary
        for trim in range(1, 4):
            if len(sample) > trim:
                try:
                    sample[:-trim].decode("utf-8")
                    return True
                except UnicodeDecodeError:
                    continue
        return False


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
    return _validate_document_bytes(suffix, content_type, len(file_content), file_content[:4096])


def validate_document_file(
    filename: str,
    content_type: str | None,
    filepath: Path,
) -> str | None:
    if not filepath.exists() or filepath.stat().st_size == 0:
        return "Uploaded file is empty."
    
    size = filepath.stat().st_size
    suffix = Path(filename).suffix.lower()
    
    with open(filepath, "rb") as f:
        head = f.read(4096)
        
    return _validate_document_bytes(suffix, content_type, size, head)


def _validate_document_bytes(
    suffix: str,
    content_type: str | None,
    size_bytes: int,
    head: bytes,
) -> str | None:
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

    if not head:
        return "Uploaded file is empty."

    if size_bytes > MAX_DOCUMENT_UPLOAD_BYTES:
        return (
            f"Uploaded file is too large ({size_bytes / (1024 * 1024):.1f} MB). "
            f"Maximum allowed size is {MAX_DOCUMENT_UPLOAD_BYTES // (1024 * 1024)} MB."
        )

    if suffix == ".pdf" and not head.startswith(b"%PDF-"):
        return "Uploaded file content does not match a valid PDF signature."

    if suffix in {".docx", ".xlsx", ".pptx", ".dclx"} and not head.startswith(b"PK"):
        return f"Uploaded file content does not match a valid {suffix} (zip) signature."

    if suffix in {".md", ".markdown", ".txt", ".csv", ".adoc", ".asciidoc", ".html", ".htm"} and not is_likely_text_content(
        head
    ):
        return f"Uploaded {suffix} file appears to be binary content."

    image_signatures = _IMAGE_SIGNATURES.get(suffix)
    if image_signatures and not head.startswith(image_signatures):
        return f"Uploaded file content does not match a valid {suffix} image signature."

    if suffix in {".doclang", ".dclg"}:
        if not is_likely_text_content(head):
            return f"Uploaded {suffix} file must be UTF-8 encoded XML text."
        if not head.lstrip().startswith(b"<"):
            return f"Uploaded {suffix} file does not look like DocLang XML (expected it to start with '<')."

    return None
