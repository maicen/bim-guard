"""Document persistence service for uploaded source files and extracted text."""

from app.logging_config import get_logger
from app.services.object_storage import ObjectStorage
from app.services.persistence import PersistenceService
from app.utils import (
    cache_db_query,
    find_row_by_field,
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
        return find_row_by_field(self._documents, "md5_hash", md5_hash)

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
        module1_doc_parser/document_extractor.py.
        """
        from app.modules.module1_doc_parser.document_extractor import extract_document_text

        text, _tables = extract_document_text(filename, content, parser=parser, instance=instance)
        return text
