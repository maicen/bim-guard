"""Document persistence service for uploaded source files and extracted text."""

from app.logging_config import get_logger
from app.services.object_storage import ObjectStorage
from app.services.persistence import PersistenceService
from app.utils import find_row_by_field, now_iso_utc, rows_desc_by_id

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
                },
            )
        )

    def list_documents(self):
        """Return all documents ordered by newest first."""
        return rows_desc_by_id(self._documents)

    def get_document(self, document_id: int):
        """Return a single document row by primary key."""
        return self._documents.get(document_id)

    def find_by_md5(self, md5_hash: str):
        """Return a document row matching the provided file hash."""
        return find_row_by_field(self._documents, "md5_hash", md5_hash)

    def create_document(self, md5_hash: str, filename: str, file_path: str, extracted_text: str):
        """Create and persist a new uploaded document record."""
        document = self._documents.insert(
            {
                "md5_hash": md5_hash,
                "filename": filename,
                "file_path": file_path,
                "extracted_text": extracted_text,
                "upload_date": now_iso_utc(),
            }
        )
        logger.info(
            "Document created document_id=%s filename=%s extracted_chars=%d",
            document.get("id"),
            filename,
            len(extracted_text),
        )
        return document

    def store_document_file(self, filename: str, content: bytes) -> str:
        """Persist document bytes and return the durable storage reference."""
        storage_ref = self._storage.save_upload(filename, content, "uploads")
        logger.info("Document file stored filename=%s bytes=%d", filename, len(content))
        return storage_ref

    def update_document(self, document_id: int, filename: str, extracted_text: str):
        """Update mutable document metadata and extracted text."""
        self._documents.update(
            updates={"filename": filename, "extracted_text": extracted_text},
            pk_values=document_id,
        )
        logger.info("Document updated document_id=%d extracted_chars=%d", document_id, len(extracted_text))

    def delete_document(self, document_id: int):
        """Delete a document row by primary key."""
        self._documents.delete(document_id)
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
    def parse_pdf_content(content: bytes) -> str:
        """Parse raw PDF content bytes via doc parser module."""
        from app.modules.module1_doc_parser import Module1_DocReader

        reader = Module1_DocReader()
        return reader.parse_pdf(content)
