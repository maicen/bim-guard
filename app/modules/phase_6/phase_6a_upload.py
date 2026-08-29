"""Session A — take an uploaded file into storage and record where it went.

Session A owns writes; Session B (``phase_6b_parsing``) is pure read. This
module is the boundary between them: it puts bytes into object storage and
hands back a :class:`StoredFileRef` carrying the storage reference and the
SHA-256 of exactly those bytes.

WHY SHA-256 AND NOT MD5

    ``ProjectsService.prepare_ifc_upload`` records an ``ifc_md5_hash``, but
    model lineage (``resolve_analysis_ifc``) and the Phase 6B parser both key on
    SHA-256. Introducing a third scheme would guarantee they never agree, so
    this service uses SHA-256 and nothing else. The digest here is byte-identical
    to ``phase_6b_parsing.sha256_of`` over the same content — a test asserts it,
    because that equality is what makes the cache key work across the two
    sessions.

FAILURE IS A VALUE, NOT AN EXCEPTION

    ``ObjectStorage.save_upload`` raises when the bucket is unreachable. Routes
    calling this service render a message; they do not catch storage errors. So
    every entry point returns :class:`UploadResponse` with ``success`` set, and
    the reason in ``error``. This mirrors the same rule Session B follows for
    unreadable models.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.logging_config import get_logger
from app.services.object_storage import ObjectStorage
from app.services.persistence import PersistenceService

logger = get_logger(__name__)

#: Storage subdirectories per kind of upload, so objects stay sorted by purpose.
SUBDIR_BY_KIND: dict[str, str] = {
    "ifc": "uploads/ifc",
    "document": "uploads/documents",
    "standard": "uploads/standards",
}

#: Accepted extensions per kind. An empty tuple means "accept anything".
EXTENSIONS_BY_KIND: dict[str, tuple[str, ...]] = {
    "ifc": (".ifc",),
    "document": (".pdf", ".docx"),
    "standard": (".pdf", ".docx"),
}

#: Upload ceiling. Storage will accept more, but a model this large will not
#: parse inside a request, so refusing early gives a better message than a
#: timeout would.
MAX_UPLOAD_BYTES: int = 512 * 1024 * 1024


@dataclass(frozen=True)
class StoredFileRef:
    """Where an uploaded file went, and what it hashed to.

    Attributes:
        storage_ref: Reference returned by :meth:`ObjectStorage.save_upload`,
            e.g. ``sb://bucket/uploads/ifc/<uuid>_model.ifc``. This is what
            Session B is handed.
        file_hash_sha256: Hex SHA-256 over the stored bytes. The lineage and
            re-parse cache key.
        filename: Original filename, stripped of any directory component.
        size_bytes: Length of the stored content.
        kind: One of :data:`SUBDIR_BY_KIND`.
    """

    storage_ref: str
    file_hash_sha256: str
    filename: str
    size_bytes: int
    kind: str


@dataclass(frozen=True)
class UploadResponse:
    """Outcome of an upload attempt.

    Attributes:
        success: Whether the bytes reached storage.
        ref: The stored reference on success, ``None`` on failure.
        error: Human-readable reason on failure, ``None`` on success.
        recorded: Whether the metadata row was written. ``False`` with
            ``success`` ``True`` means the file is safely stored but its row is
            not — the upload is not rolled back for a bookkeeping failure.
    """

    success: bool
    ref: StoredFileRef | None = None
    error: str | None = None
    recorded: bool = False


def sha256_of(content: bytes) -> str:
    """Return the hex SHA-256 digest of ``content``.

    Deliberately the same computation as ``phase_6b_parsing.sha256_of`` so the
    upload-side and parse-side cache keys agree.
    """
    return hashlib.sha256(content).hexdigest()


def _now_iso() -> str:
    """UTC timestamp in ISO 8601, second precision."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _validate(filename: str, content: bytes, kind: str) -> str | None:
    """Return a rejection reason, or ``None`` if the upload is acceptable."""
    if kind not in SUBDIR_BY_KIND:
        return f"Unknown upload kind {kind!r}."

    safe_name = Path(filename or "").name
    if not safe_name:
        return "The file has no name."

    if not content:
        return "The file is empty."

    if len(content) > MAX_UPLOAD_BYTES:
        limit_mb = MAX_UPLOAD_BYTES // (1024 * 1024)
        return f"The file is larger than the {limit_mb} MB upload limit."

    allowed = EXTENSIONS_BY_KIND.get(kind, ())
    if allowed and not safe_name.lower().endswith(allowed):
        return f"{safe_name} is not one of the accepted types: {', '.join(allowed)}."

    return None


class FileUploadService:
    """Put uploaded bytes into object storage and record the result.

    Args:
        storage: Storage backend. Injected so tests can exercise the service
            without writing to a real bucket.
        table: Metadata table adapter. Injected for the same reason.
    """

    def __init__(self, storage: ObjectStorage | None = None, table=None) -> None:
        self._storage = storage or ObjectStorage()
        self._table = table if table is not None else self._default_table()

    @staticmethod
    def _default_table():
        """Declare the ``uploaded_files`` table.

        Safe to call before the migration has run: the Supabase adapter's
        ``create()`` is a no-op because schema is managed outside runtime — the
        same reason ``ProjectsService`` can declare ``standards_by_project``
        ahead of its migration.
        """
        return PersistenceService.get_table(
            "uploaded_files",
            {
                "id": int,
                "project_id": int,
                "kind": str,
                "filename": str,
                "storage_ref": str,
                "file_hash_sha256": str,
                "size_bytes": int,
                "created_at": str,
            },
        )

    def upload(
        self,
        filename: str,
        content: bytes,
        *,
        project_id: int | None = None,
        kind: str = "ifc",
    ) -> UploadResponse:
        """Store ``content`` and return where it went.

        Args:
            filename: Original filename. Any directory component is stripped.
            content: Raw bytes to store.
            project_id: Project the file belongs to. Recorded when present.
            kind: One of :data:`SUBDIR_BY_KIND`; selects the storage
                subdirectory and the accepted extensions.

        Returns:
            An :class:`UploadResponse`. Never raises — a rejected or failed
            upload comes back with ``success`` ``False`` and a reason.
        """
        rejection = _validate(filename, content, kind)
        if rejection:
            logger.warning(
                "Upload rejected filename=%s kind=%s reason=%s", filename, kind, rejection
            )
            return UploadResponse(success=False, error=rejection)

        safe_name = Path(filename.replace("\\", "/")).name
        file_hash = sha256_of(content)

        try:
            storage_ref = self._storage.save_upload(safe_name, content, SUBDIR_BY_KIND[kind])
        except Exception as exc:
            logger.exception("Upload failed filename=%s kind=%s", safe_name, kind)
            return UploadResponse(success=False, error=f"The file could not be stored: {exc}")

        ref = StoredFileRef(
            storage_ref=storage_ref,
            file_hash_sha256=file_hash,
            filename=safe_name,
            size_bytes=len(content),
            kind=kind,
        )
        recorded = self._record(ref, project_id)

        logger.info(
            "Upload stored filename=%s kind=%s bytes=%d sha256=%s ref=%s recorded=%s",
            safe_name,
            kind,
            len(content),
            file_hash,
            storage_ref,
            recorded,
        )
        return UploadResponse(success=True, ref=ref, recorded=recorded)

    def _record(self, ref: StoredFileRef, project_id: int | None) -> bool:
        """Write the metadata row.

        Returns ``False`` rather than raising when the row cannot be written:
        the bytes are already in storage, and losing the upload over a
        bookkeeping failure would be the worse outcome. The caller sees
        ``recorded=False`` and the reason is logged.
        """
        row = {
            "project_id": project_id,
            "kind": ref.kind,
            "filename": ref.filename,
            "storage_ref": ref.storage_ref,
            "file_hash_sha256": ref.file_hash_sha256,
            "size_bytes": ref.size_bytes,
            "created_at": _now_iso(),
        }
        try:
            self._table.insert(row)
            return True
        except Exception:
            logger.warning(
                "Upload stored but metadata row not written ref=%s", ref.storage_ref, exc_info=True
            )
            return False

    def find_by_hash(self, file_hash_sha256: str) -> list[dict]:
        """Return recorded uploads whose content hashed to ``file_hash_sha256``.

        The point of storing the digest: an identical re-upload can reuse the
        existing object and its parse rather than repeating both.
        """
        try:
            return list(
                self._table.rows_where("file_hash_sha256 = ?", [file_hash_sha256])
            )
        except Exception:
            logger.warning("Upload lookup by hash failed", exc_info=True)
            return []

    def list_for_project(self, project_id: int, kind: str | None = None) -> list[dict]:
        """Return recorded uploads for ``project_id``, newest first.

        ``kind`` is filtered in Python rather than in the predicate because
        ``parse_where`` accepts a single comparison only -- there is no way to
        express ``project_id = ? AND kind = ?`` through ``rows_where``.

        Args:
            project_id: Project whose uploads to list.
            kind: When given, keep only rows of that kind (e.g. ``"ifc"``).

        Returns:
            Matching rows, newest ``created_at`` first. Empty on any lookup
            failure -- a viewer with no models is a better outcome than a 500.
        """
        try:
            rows = list(self._table.rows_where("project_id = ?", [project_id]))
        except Exception:
            logger.warning(
                "Upload lookup by project failed project_id=%s", project_id, exc_info=True
            )
            return []

        if kind is not None:
            rows = [row for row in rows if row.get("kind") == kind]
        return sorted(rows, key=lambda row: str(row.get("created_at") or ""), reverse=True)

    def get_recorded(self, file_id: int) -> dict | None:
        """Return one recorded upload by primary key, or ``None``.

        Args:
            file_id: ``uploaded_files.id`` of the row to fetch.

        Returns:
            The row, or ``None`` when it does not exist or cannot be read.
        """
        try:
            return self._table.get(file_id)
        except Exception:
            logger.warning("Upload lookup by id failed file_id=%s", file_id, exc_info=True)
            return None
