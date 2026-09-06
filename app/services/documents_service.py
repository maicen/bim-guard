"""Document persistence service for uploaded source files and extracted text."""

from app.logging_config import get_logger
from app.services.object_storage import ObjectStorage
from app.services.persistence import PersistenceService
from app.utils import (
    cache_db_query,
    invalidate_cache,
    now_iso_utc,
    rows_desc_by_id,
)

logger = get_logger(__name__)


class DocumentService:
    """Encapsulates CRUD and lookup operations for uploaded documents."""

    def __init__(self, *, documents_repo=None, storage=None):
        """Initialize the documents table and storage adapter with dependency injection."""
        self._storage = storage if storage is not None else ObjectStorage()
        self._documents = (
            documents_repo
            if documents_repo is not None
            else PersistenceService.get_table(
                "documents",
                {
                    "id": int,
                    "md5_hash": str,
                    "filename": str,
                    "file_path": str,
                    "extracted_text": str,
                    "upload_date": str,
                    "doc_type": str,
                    "project_code": str,
                    "originator": str,
                    "volume_system": str,
                    "level": str,
                    "type": str,
                    "role": str,
                    "number": str,
                    "suitability_code": str,
                    "revision_code": str,
                    "cde_state": str,
                },
            )
        )

    @cache_db_query(key_prefix="bimguard:documents:list")
    def list_documents(self):
        """Return all documents ordered by newest first."""
        return rows_desc_by_id(self._documents)

    @cache_db_query(key_prefix="bimguard:documents:item")
    def get_document(self, document_id: int):
        """Return a single document row by primary key."""
        return self._documents.get(document_id)

    def find_by_md5(self, md5_hash: str):
        """Return a document row matching the provided file hash."""
        # ⚡ Bolt Optimization: Replaced O(N) full-table fetch in Python with an O(1) database-level limit=1 query.
        # This dramatically reduces memory allocation and network transfer time when checking for duplicate document uploads.
        rows = self._documents.rows_where("md5_hash = ?", [md5_hash], limit=1)
        return next(iter(rows), None)

    def create_document(
        self,
        md5_hash: str,
        filename: str,
        file_path: str,
        extracted_text: str,
        doc_type: str = "Specification",
        project_code: str = "",
        originator: str = "",
        volume_system: str = "",
        level: str = "",
        type: str = "",
        role: str = "",
        number: str = "",
        suitability_code: str = "S0",
        revision_code: str = "P01.01",
        cde_state: str = "WIP",
    ):
        """Create and persist a new uploaded document record."""
        clean_doc_type = (doc_type or "").strip() or "Specification"
        payload = {
            "md5_hash": md5_hash,
            "filename": filename,
            "file_path": file_path,
            "extracted_text": extracted_text,
            "upload_date": now_iso_utc(),
            "doc_type": clean_doc_type,
            "project_code": project_code,
            "originator": originator,
            "volume_system": volume_system,
            "level": level,
            "type": type,
            "role": role,
            "number": number,
            "suitability_code": suitability_code or "S0",
            "revision_code": revision_code or "P01.01",
            "cde_state": cde_state or "WIP",
        }
        document = self._documents.insert(payload)
        invalidate_cache("bimguard:documents:list")
        logger.info(
            "Document created document_id=%s filename=%s doc_type=%s suitability=%s extracted_chars=%d",
            document.get("id"),
            filename,
            clean_doc_type,
            suitability_code,
            len(extracted_text),
        )
        return document

    def store_document_file(self, filename: str, content: bytes) -> str:
        """Persist document bytes and return the durable storage reference."""
        storage_ref = self._storage.save_upload(filename, content, "uploads")
        logger.info("Document file stored filename=%s bytes=%d", filename, len(content))
        return storage_ref

    def materialize_local_path(self, file_path: str):
        """Resolve a stored file reference to a local path for streaming/serving."""
        return self._storage.materialize_local_path(file_path)

    def update_document(
        self,
        document_id: int,
        filename: str,
        extracted_text: str,
        doc_type: str | None = None,
        project_code: str | None = None,
        originator: str | None = None,
        suitability_code: str | None = None,
        revision_code: str | None = None,
        cde_state: str | None = None,
    ):
        """Update mutable document metadata and extracted text."""
        updates: dict = {"filename": filename, "extracted_text": extracted_text}
        if doc_type is not None:
            updates["doc_type"] = doc_type.strip() or "Specification"
        if project_code is not None:
            updates["project_code"] = project_code.strip()
        if originator is not None:
            updates["originator"] = originator.strip()
        if suitability_code is not None:
            updates["suitability_code"] = suitability_code.strip() or "S0"
        if revision_code is not None:
            updates["revision_code"] = revision_code.strip() or "P01.01"
        if cde_state is not None:
            updates["cde_state"] = cde_state.strip() or "WIP"

        self._documents.update(
            updates=updates,
            pk_values=document_id,
        )
        invalidate_cache(f"bimguard:documents:item:document_id={document_id}")
        invalidate_cache("bimguard:documents:list")
        logger.info("Document updated document_id=%d extracted_chars=%d", document_id, len(extracted_text))

    def delete_document(self, document_id: int):
        """Delete a document row by primary key."""
        self._documents.delete(document_id)
        invalidate_cache(f"bimguard:documents:item:document_id={document_id}")
        invalidate_cache("bimguard:documents:list")
        logger.info("Document deleted document_id=%d", document_id)

    def delete_document_with_file(self, document_id: int):
        """Delete a document and best-effort remove its stored file from disk."""
        document = self.get_document(document_id)
        if document is None:
            logger.warning("Skipped deletion for missing document_id=%d", document_id)
            return

        file_path = document.get("file_path")
        if file_path:
            try:
                self._storage.delete(file_path)
            except OSError:
                # Keep DB deletion resilient even when file cleanup fails.
                logger.warning("Document file cleanup failed document_id=%d", document_id, exc_info=True)
                pass

        self.delete_document(document_id)

    def ingest_uploaded_bytes(
        self,
        filename: str,
        content: bytes,
        *,
        doc_type: str = "Specification",
        project_code: str = "",
        originator: str = "",
        suitability_code: str = "S0",
        revision_code: str = "P01.01",
        parser: str = "auto",
        instance: dict | None = None,
    ) -> tuple[dict, bool]:
        """Extract, store, and persist an uploaded/imported document.

        Shared by the multipart upload endpoint and the Google Drive import
        endpoint — the only difference between those two entry points is how
        `content` bytes were obtained. Dedupes by md5: a byte-identical
        re-upload/re-import returns the existing row unchanged.

        Returns:
            row (dict): the document row (existing or newly created)
            created (bool): False when an existing row was reused
        """
        from app.modules.document_parsing.iso_validator import ISO19650Validator
        from app.utils import md5_hex

        file_md5 = md5_hex(content)
        existing = self.find_by_md5(file_md5)
        if existing:
            return existing, False

        clean_doc_type = (doc_type or "").strip() or "Specification"

        val = ISO19650Validator.validate_filename(filename)
        if val.is_valid:
            project_code = project_code or val.fields.get("project_code", "")
            originator = originator or val.fields.get("originator", "")
            suitability_code = (
                suitability_code
                if suitability_code != "S0"
                else val.fields.get("suitability_code", "S0")
            )
            revision_code = (
                revision_code
                if revision_code != "P01.01"
                else val.fields.get("revision_code", "P01.01")
            )

        try:
            extracted_text, pages = self.extract_document_text_paged(
                filename, content, parser=parser, instance=instance
            )
        except (ValueError, RuntimeError):
            raise
        except Exception as exc:
            logger.warning("Document extraction failed filename=%s parser=%s error=%s", filename, parser, exc)
            extracted_text, pages = f"[Text extraction error: {exc}]", []

        file_path = self.store_document_file(filename, content)
        created = self.create_document(
            md5_hash=file_md5,
            filename=filename,
            file_path=file_path,
            extracted_text=extracted_text,
            doc_type=clean_doc_type,
            project_code=project_code,
            originator=originator,
            suitability_code=suitability_code,
            revision_code=revision_code,
            cde_state="WIP",
        )

        if pages:
            from app.services.document_pages_service import DocumentPagesService

            DocumentPagesService().save_pages(created["id"], pages)

        return created, True

    @staticmethod
    def extract_document_text(
        filename: str, content: bytes, parser: str = "auto", instance: dict | None = None
    ) -> str:
        """Extract text from raw uploaded file bytes via the document parser module.

        parser: "auto" (the configured parsing engine, falling back to the
        light local extractor), "unstructured" (force the configured
        engine), or "light" (force the local extractor). `instance`
        optionally selects which configured parsing engine to use (a local
        container, or which hosted account) — see
        document_parsing/document_extractor.py.
        """
        text, _pages = DocumentService.extract_document_text_paged(
            filename, content, parser=parser, instance=instance
        )
        return text

    @staticmethod
    def extract_document_text_paged(
        filename: str, content: bytes, parser: str = "auto", instance: dict | None = None
    ) -> tuple[str, list[dict]]:
        """Extract text and page-tagged text, like `extract_document_text` plus pages.

        See document_parsing/document_extractor.py for the `pages` shape
        ([{"page_number": int, "text": str}, ...], empty for pageless
        formats or engines that don't report page numbers).
        """
        from app.modules.document_parsing.document_extractor import extract_document_text

        text, _tables, pages = extract_document_text(filename, content, parser=parser, instance=instance)
        return text, pages
