"""Document persistence service for uploaded source files and their canonical DocLang XML."""

from app.logging_config import get_logger
from app.modules.document_parsing.doclang_text import doclang_to_text
from app.services.object_storage import ObjectStorage
from app.services.persistence import PersistenceService
from app.utils import (
    cache_db_query,
    invalidate_cache,
    now_iso_utc,
    rows_desc_by_id,
)

logger = get_logger(__name__)

DOCLANG_OFFLOAD_THRESHOLD_BYTES = 256 * 1024  # 256 KB threshold for offloading XML to Supabase Storage


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
                    "doclang_xml": str,
                    "doclang_storage_path": str,
                    "doclang_archive_path": str,
                    "char_count": int,
                    "text_preview": str,
                },
            )
        )

    DOCUMENT_SUMMARY_COLUMNS = [
        "id",
        "md5_hash",
        "filename",
        "file_path",
        "upload_date",
        "doc_type",
        "project_code",
        "originator",
        "volume_system",
        "level",
        "type",
        "role",
        "number",
        "suitability_code",
        "revision_code",
        "cde_state",
        "doclang_storage_path",
        "doclang_archive_path",
        "char_count",
        "text_preview",
    ]

    TEXT_PREVIEW_LENGTH = 200

    @cache_db_query(key_prefix="bimguard:documents:list")
    def list_documents(self):
        """Return all documents ordered by newest first, omitting bulky XML from table scans."""
        if hasattr(self._documents, "select_projected"):
            try:
                rows = self._documents.select_projected(self.DOCUMENT_SUMMARY_COLUMNS)
                return sorted(rows, key=lambda row: row.get("id", 0), reverse=True)
            except Exception:
                pass
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
        doclang_xml: str = "",
        doclang_storage_path: str | None = None,
        doclang_archive_path: str | None = None,
    ):
        """Create and persist a new uploaded document record."""
        clean_doc_type = (doc_type or "").strip() or "Specification"
        extracted_assets: list[dict] = []
        if "data:image/" in (doclang_xml or ""):
            from app.modules.document_parsing.doclang_asset_manager import DocLangAssetManager

            doclang_xml, extracted_assets = DocLangAssetManager.extract_and_offload_assets(
                doclang_xml=doclang_xml,
                doc_key=str(md5_hash[:12]),
                storage=self._storage,
            )

        doclang_bytes = (doclang_xml or "").encode("utf-8")
        inline_xml = doclang_xml or ""
        resolved_storage_path = doclang_storage_path
        resolved_archive_path = doclang_archive_path

        if resolved_storage_path is None and len(doclang_bytes) > DOCLANG_OFFLOAD_THRESHOLD_BYTES:
            filename_key = f"doclang_{md5_hash[:12]}.xml"
            try:
                resolved_storage_path = self._storage.save_upload(filename_key, doclang_bytes, "doclang")
                inline_xml = ""
                logger.info(
                    "Offloaded large DocLang XML to storage ref=%s bytes=%d",
                    resolved_storage_path,
                    len(doclang_bytes),
                )
            except Exception:
                logger.warning("Failed offloading DocLang XML to storage; retaining inline in database")
                inline_xml = doclang_xml or ""

        if resolved_archive_path is None and (doclang_xml or "").strip():
            filename_key = f"archive_{md5_hash[:12]}.dclx"
            try:
                temp_doc = {
                    "filename": filename,
                    "project_code": project_code,
                    "originator": originator,
                    "cde_state": cde_state or "WIP",
                    "suitability_code": suitability_code or "S0",
                    "revision_code": revision_code or "P01.01",
                }
                archive_bytes = self.build_doclang_archive(temp_doc, doclang_xml, assets=extracted_assets)
                resolved_archive_path = self._storage.save_upload(filename_key, archive_bytes, "doclang")
                logger.info(
                    "Pre-persisted DocLang .dclx archive to storage ref=%s bytes=%d",
                    resolved_archive_path,
                    len(archive_bytes),
                )
            except Exception:
                logger.warning("Failed pre-persisting DocLang archive to storage; will generate on demand", exc_info=True)

        derived_text = doclang_to_text(doclang_xml or "")
        payload = {
            "md5_hash": md5_hash,
            "filename": filename,
            "file_path": file_path,
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
            "doclang_xml": inline_xml,
            "doclang_storage_path": resolved_storage_path,
            "doclang_archive_path": resolved_archive_path,
            "char_count": len(derived_text),
            "text_preview": derived_text[: self.TEXT_PREVIEW_LENGTH],
        }
        document = self._documents.insert(payload)
        invalidate_cache("bimguard:documents:list")
        logger.info(
            "Document created document_id=%s filename=%s doc_type=%s suitability=%s doclang_chars=%d",
            document.get("id"),
            filename,
            clean_doc_type,
            suitability_code,
            len(derived_text),
        )
        return document

    def store_document_file(self, filename: str, content: bytes) -> str:
        """Persist document bytes and return the durable storage reference."""
        storage_ref = self._storage.save_upload(filename, content, "uploads")
        logger.info("Document file stored filename=%s bytes=%d", filename, len(content))
        return storage_ref

    def store_doclang_file(self, document_id: int, xml_content: str) -> str:
        """Persist canonical DocLang XML into Supabase Storage and return the storage reference."""
        data = xml_content.encode("utf-8")
        filename = f"doclang_{document_id}.xml"
        storage_ref = self._storage.save_upload(filename, data, "doclang")
        logger.info("DocLang XML stored document_id=%d bytes=%d ref=%s", document_id, len(data), storage_ref)
        return storage_ref

    @staticmethod
    def build_doclang_archive(
        doc: dict,
        xml_content: str,
        assets: list[dict] | None = None,
    ) -> bytes:
        """Package DocLang XML and metadata into a standardized .dclx zip bundle."""
        import io
        import json
        import zipfile

        filename = doc.get("filename") or f"document_{doc.get('id', 'doc')}"
        manifest = {
            "format": "doclang-archive",
            "version": "1.0",
            "document_name": filename,
            "entrypoint": "document.xml",
            "created_by": "BIM-Guard DocLang Engine",
            "metadata": {
                "project_code": doc.get("project_code", ""),
                "originator": doc.get("originator", ""),
                "cde_state": doc.get("cde_state", ""),
                "suitability_code": doc.get("suitability_code", ""),
                "revision_code": doc.get("revision_code", ""),
            },
        }

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("document.xml", xml_content.encode("utf-8"))
            zf.writestr("manifest.json", json.dumps(manifest, indent=2).encode("utf-8"))
            if assets:
                for asset in assets:
                    asset_fname = asset.get("filename")
                    asset_content = asset.get("asset_bytes")
                    if asset_fname and asset_content:
                        zf.writestr(f"assets/{asset_fname}", asset_content)
        return buf.getvalue()

    def store_doclang_archive(self, document_id: int, archive_bytes: bytes) -> str:
        """Persist a pre-generated .dclx archive into Supabase Storage."""
        filename = f"archive_{document_id}.dclx"
        storage_ref = self._storage.save_upload(filename, archive_bytes, "doclang")
        logger.info(
            "DocLang archive stored document_id=%d bytes=%d ref=%s",
            document_id,
            len(archive_bytes),
            storage_ref,
        )
        return storage_ref

    def get_doclang_archive_signed_url(self, doc: dict, expires_in: int = 3600) -> str | None:
        """Return a pre-signed direct download URL for the document's .dclx archive."""
        storage_ref = doc.get("doclang_archive_path")
        if storage_ref and hasattr(self._storage, "create_signed_url"):
            return self._storage.create_signed_url(storage_ref, expires_in=expires_in)
        return None

    def get_doclang_archive_bytes(self, doc: dict) -> bytes | None:
        """Return .dclx archive bytes, reading from persistent storage cache or generating dynamically."""
        storage_ref = doc.get("doclang_archive_path")
        if storage_ref:
            path = self.materialize_local_path(storage_ref)
            if path and path.is_file():
                try:
                    return path.read_bytes()
                except Exception:
                    logger.warning("Failed reading cached .dclx archive from %s", path, exc_info=True)

        xml = self.get_doclang_content(doc)
        if not xml.strip():
            return None

        # Build archive dynamically
        archive_bytes = self.build_doclang_archive(doc, xml)

        # Opportunistically persist to storage cache for future requests
        doc_id = doc.get("id")
        if doc_id and not storage_ref:
            try:
                new_ref = self.store_doclang_archive(doc_id, archive_bytes)
                self._documents.update(updates={"doclang_archive_path": new_ref}, pk_values=doc_id)
                invalidate_cache(f"bimguard:documents:item:document_id={doc_id}")
                invalidate_cache("bimguard:documents:list")
            except Exception:
                logger.warning("Failed persisting generated .dclx archive for document %s", doc_id, exc_info=True)

        return archive_bytes

    def get_doclang_content(self, doc: dict) -> str:
        """Return canonical DocLang XML from inline column or materialized from storage."""
        xml = doc.get("doclang_xml") or ""
        if xml.strip():
            return xml
        storage_ref = doc.get("doclang_storage_path")
        if storage_ref:
            path = self.materialize_local_path(storage_ref)
            if path and path.is_file():
                try:
                    return path.read_text(encoding="utf-8")
                except Exception:
                    logger.exception("Failed reading materialized DocLang XML from %s", path)
        return ""

    def materialize_local_path(self, file_path: str):
        """Resolve a stored file reference to a local path for streaming/serving."""
        return self._storage.materialize_local_path(file_path)

    def get_document_text(self, doc: dict) -> str:
        """Return the document's full plain text, derived on demand from its DocLang XML."""
        return doclang_to_text(self.get_doclang_content(doc))

    def update_document(
        self,
        document_id: int,
        filename: str,
        doc_type: str | None = None,
        project_code: str | None = None,
        originator: str | None = None,
        suitability_code: str | None = None,
        revision_code: str | None = None,
        cde_state: str | None = None,
        doclang_xml: str | None = None,
        doclang_storage_path: str | None = None,
        doclang_archive_path: str | None = None,
    ):
        """Update mutable document metadata and, when provided, its DocLang XML."""
        updates: dict = {"filename": filename}
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
        if doclang_xml is not None:
            extracted_assets = []
            if "data:image/" in doclang_xml:
                from app.modules.document_parsing.doclang_asset_manager import DocLangAssetManager

                doclang_xml, extracted_assets = DocLangAssetManager.extract_and_offload_assets(
                    doclang_xml=doclang_xml,
                    doc_key=str(document_id),
                    storage=self._storage,
                )

            doclang_bytes = doclang_xml.encode("utf-8")
            if len(doclang_bytes) > DOCLANG_OFFLOAD_THRESHOLD_BYTES and doclang_storage_path is None:
                try:
                    storage_ref = self.store_doclang_file(document_id, doclang_xml)
                    updates["doclang_storage_path"] = storage_ref
                    updates["doclang_xml"] = ""
                    logger.info("Offloaded updated DocLang XML to storage ref=%s bytes=%d", storage_ref, len(doclang_bytes))
                except Exception:
                    logger.warning("Failed offloading DocLang XML to storage on update; retaining inline")
                    updates["doclang_xml"] = doclang_xml
            else:
                updates["doclang_xml"] = doclang_xml

            derived_text = doclang_to_text(doclang_xml)
            updates["char_count"] = len(derived_text)
            updates["text_preview"] = derived_text[: self.TEXT_PREVIEW_LENGTH]

            if doclang_archive_path is None and doclang_xml.strip():
                try:
                    updated_doc_dict = {
                        "id": document_id,
                        "filename": filename,
                        "project_code": updates.get("project_code", ""),
                        "originator": updates.get("originator", ""),
                        "cde_state": updates.get("cde_state", ""),
                        "suitability_code": updates.get("suitability_code", ""),
                        "revision_code": updates.get("revision_code", ""),
                    }
                    archive_bytes = self.build_doclang_archive(updated_doc_dict, doclang_xml, assets=extracted_assets)
                    archive_ref = self.store_doclang_archive(document_id, archive_bytes)
                    updates["doclang_archive_path"] = archive_ref
                except Exception:
                    logger.warning("Failed updating DocLang archive on document %d", document_id, exc_info=True)

        if doclang_storage_path is not None:
            updates["doclang_storage_path"] = doclang_storage_path
        if doclang_archive_path is not None:
            updates["doclang_archive_path"] = doclang_archive_path

        self._documents.update(
            updates=updates,
            pk_values=document_id,
        )
        invalidate_cache(f"bimguard:documents:item:document_id={document_id}")
        invalidate_cache("bimguard:documents:list")
        logger.info("Document updated document_id=%d", document_id)

    def delete_document(self, document_id: int):
        """Delete a document row by primary key."""
        self._documents.delete(document_id)
        invalidate_cache(f"bimguard:documents:item:document_id={document_id}")
        invalidate_cache("bimguard:documents:list")
        logger.info("Document deleted document_id=%d", document_id)

    def delete_document_with_file(self, document_id: int):
        """Delete a document and best-effort remove its stored files from storage/disk."""
        document = self.get_document(document_id)
        if document is None:
            logger.warning("Skipped deletion for missing document_id=%d", document_id)
            return

        for path_key in ("file_path", "doclang_storage_path", "doclang_archive_path"):
            stored_ref = document.get(path_key)
            if stored_ref:
                try:
                    self._storage.delete(stored_ref)
                except Exception:
                    logger.warning(
                        "Document file cleanup failed key=%s ref=%s doc_id=%d",
                        path_key,
                        stored_ref,
                        document_id,
                        exc_info=True,
                    )

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
        generate_doclang: bool = True,
    ) -> tuple[dict, bool]:
        """Extract, store, and persist an uploaded/imported document.

        Shared by the multipart upload endpoint and the Google Drive import
        endpoint — the only difference between those two entry points is how
        `content` bytes were obtained. Dedupes by md5: a byte-identical
        re-upload/re-import returns the existing row unchanged.

        When `generate_doclang` is False, the file is stored but DocLang
        generation is skipped — the resulting row has `has_doclang=False`
        until `generate_doclang_for_existing` is called on it later (e.g. via
        the documents datatable's "Generate DocLang" action).

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

        pages: list = []
        doclang_xml = ""
        if generate_doclang:
            try:
                _text, pages, doclang_xml, _bboxes = self.extract_document_text_paged(
                    filename, content, parser=parser, instance=instance, return_doclang=True
                )
            except (ValueError, RuntimeError):
                raise
            except Exception as exc:
                logger.warning("Document extraction failed filename=%s parser=%s error=%s", filename, parser, exc)
                pages, doclang_xml = [], ""

        file_path = self.store_document_file(filename, content)
        created = self.create_document(
            md5_hash=file_md5,
            filename=filename,
            file_path=file_path,
            doc_type=clean_doc_type,
            project_code=project_code,
            originator=originator,
            suitability_code=suitability_code,
            revision_code=revision_code,
            cde_state="WIP",
            doclang_xml=doclang_xml,
        )

        if pages:
            from app.services.document_pages_service import DocumentPagesService

            DocumentPagesService().save_pages(created["id"], pages)

        return created, True

    def generate_doclang_for_existing(
        self, document_id: int, parser: str = "auto", instance: dict | None = None
    ) -> dict:
        """Run extraction against an already-stored file and persist its DocLang XML.

        Backs the documents datatable's "Generate DocLang" action for a
        document that was uploaded with generation deferred (`generate_doclang=False`)
        or whose earlier generation attempt failed.
        """
        doc = self.get_document(document_id)
        if doc is None:
            raise ValueError(f"Document {document_id} not found.")

        file_path = doc.get("file_path")
        if not file_path:
            raise ValueError(f"Document {document_id} has no stored file to parse.")

        local_path = self.materialize_local_path(file_path)
        if local_path is None or not local_path.is_file():
            raise ValueError(f"Stored file for document {document_id} could not be resolved.")

        filename = doc.get("filename") or local_path.name
        content = local_path.read_bytes()

        _text, pages, doclang_xml, _bboxes = self.extract_document_text_paged(
            filename, content, parser=parser, instance=instance, return_doclang=True
        )
        if not doclang_xml.strip():
            raise RuntimeError(f"DocLang generation produced no content for document {document_id}.")

        self.update_document(
            document_id,
            filename=filename,
            doc_type=doc.get("doc_type"),
            project_code=doc.get("project_code"),
            originator=doc.get("originator"),
            suitability_code=doc.get("suitability_code"),
            revision_code=doc.get("revision_code"),
            cde_state=doc.get("cde_state"),
            doclang_xml=doclang_xml,
        )

        if pages:
            from app.services.document_pages_service import DocumentPagesService

            DocumentPagesService().save_pages(document_id, pages)

        return self.get_document(document_id)

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
        filename: str,
        content: bytes,
        parser: str = "auto",
        instance: dict | None = None,
        return_doclang: bool = False,
    ) -> tuple:
        """Extract text and page-tagged text, like `extract_document_text` plus pages.

        When `return_doclang=True`, returns `(text, pages, doclang_xml, bboxes)`.
        Otherwise returns `(text, pages)`.
        """
        from app.modules.document_parsing.document_extractor import extract_document_text

        res = extract_document_text(
            filename, content, parser=parser, instance=instance, return_doclang=return_doclang
        )
        if return_doclang:
            text, _tables, pages, doclang_xml, bboxes = res
            return text, pages, doclang_xml, bboxes
        text, _tables, pages = res[:3]
        return text, pages
