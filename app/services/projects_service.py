"""Project service for IFC-backed project CRUD and file handling."""

import hashlib
from pathlib import Path

from app.constants import (
    ANALYSIS_TYPES,
    DOCUMENT_CATEGORIES,
    STANDARD_UPLOAD_EXTENSIONS,
    get_standard,
)
from app.logging_config import get_logger
from app.services.model_lineage import SupabaseModelLineageRepository
from app.services.object_storage import ObjectStorage
from app.services.persistence import PersistenceService
from app.utils import (
    md5_hex,
    now_iso_utc,
    rows_desc_by_id,
    safe_upload_name,
)

logger = get_logger(__name__)


def is_enhancement_authorized(token: str = "") -> bool:
    """Authorize explicit model mutation. Token is no longer required."""
    return True


class ProjectsService:
    """Encapsulates projects persistence and IFC file operations."""

    def __init__(self):
        """Initialize project storage and ensure required table columns exist."""
        self._storage = ObjectStorage()
        self._lineage = SupabaseModelLineageRepository()
        self._projects = PersistenceService.get_table(
            "projects",
            {
                "id": int,
                "name": str,
                "description": str,
                "status": str,
                "country": str,
                "analysis_type": str,
                "ifc_file_path": str,
                "ifc_md5_hash": str,
                "created_at": str,
                "updated_at": str,
            },
            required_columns={"ifc_file_path": str, "ifc_md5_hash": str},
        )
        # Both tables are created by migration_002 / migration_003. The Supabase
        # adapter's create() is a no-op (schema is managed outside runtime), so
        # declaring them here is safe even before those migrations have been run.
        self._standards = PersistenceService.get_table(
            "standards_by_project",
            {
                "id": int,
                "project_id": int,
                "standard_id": str,
                "source": str,
                "file_path": str,
                "created_at": str,
                "updated_at": str,
            },
        )
        self._client_documents = PersistenceService.get_table(
            "client_documents",
            {
                "id": int,
                "project_id": int,
                "filename": str,
                "file_path": str,
                "file_type": str,
                "category": str,
                "description": str,
                "tags": str,
                "upload_date": str,
                "updated_at": str,
            },
        )

    def list_projects(self):
        """Return all projects ordered by newest first."""
        return rows_desc_by_id(self._projects)

    def total_projects(self) -> int:
        """Return the number of stored projects."""
        return len(self.list_projects())

    def get_project(self, project_id: int):
        """Return a single project by primary key."""
        return self._projects.get(project_id)

    async def prepare_ifc_upload(self, ifc_file) -> tuple[str, str]:
        """Validate and persist an uploaded IFC file, returning path and MD5 hash."""
        if not ifc_file or not getattr(ifc_file, "filename", None):
            logger.warning("Skipped IFC upload because no file was supplied")
            return "", ""

        filename = safe_upload_name(ifc_file.filename)
        if not filename.lower().endswith(".ifc"):
            logger.warning("Rejected non-IFC project upload filename=%s", filename)
            return "", ""

        content = await ifc_file.read()
        if not content:
            logger.warning("Rejected empty IFC upload filename=%s", filename)
            return "", ""

        ifc_md5_hash = md5_hex(content)
        storage_ref = self._storage.save_upload(filename, content, "uploads/ifc")
        logger.info("IFC upload prepared filename=%s bytes=%d", filename, len(content))
        return storage_ref, ifc_md5_hash

    def create_project(
        self,
        name: str,
        description: str = "",
        status: str = "Draft",
        ifc_file_path: str = "",
        ifc_md5_hash: str = "",
        country: str = "",
        analysis_type: str = "",
    ):
        """Insert a new project record into the database.

        Args:
            name: Project name. Required; a blank name is rejected.
            description: Optional free-text description.
            status: Workflow status.
            ifc_file_path: Storage reference for the uploaded IFC model.
            ifc_md5_hash: MD5 of the uploaded IFC model.
            country: Jurisdiction governing which codes apply. Required.
            analysis_type: One of :data:`app.constants.ANALYSIS_TYPES`. Required.

        Returns:
            The inserted project row.

        Raises:
            ValueError: if name, country or analysis_type is missing, or if
                analysis_type is not a recognised value. Validating here rather
                than only in the route keeps the ``valid_analysis_type`` check
                constraint from being the first thing to notice a bad value.
        """
        name = name.strip()
        country = country.strip()
        analysis_type = analysis_type.strip()
        if not name:
            raise ValueError("Project name is required")
        if not country:
            raise ValueError("Country is required")
        if analysis_type not in ANALYSIS_TYPES:
            raise ValueError(
                f"analysis_type must be one of {ANALYSIS_TYPES!r}, got {analysis_type!r}"
            )

        now = now_iso_utc()
        project = self._projects.insert(
            {
                "name": name,
                "description": description.strip(),
                "status": status,
                "country": country,
                "analysis_type": analysis_type,
                "ifc_file_path": ifc_file_path,
                "ifc_md5_hash": ifc_md5_hash,
                "created_at": now,
                "updated_at": now,
            }
        )
        logger.info(
            "Project created project_id=%s status=%s country=%s analysis_type=%s has_ifc=%s",
            project.get("id"),
            status,
            country,
            analysis_type,
            bool(ifc_file_path),
        )
        return project

    def update_project(
        self,
        project_id: int,
        name: str,
        description: str = "",
        status: str = "Draft",
        country: str = "",
        analysis_type: str = "",
    ):
        """Update editable fields for an existing project."""
        updates = {
            "name": name.strip(),
            "description": description.strip(),
            "status": status,
            "updated_at": now_iso_utc(),
        }
        if country:
            updates["country"] = country.strip()
        if analysis_type:
            if analysis_type not in ANALYSIS_TYPES:
                raise ValueError(
                    f"analysis_type must be one of {ANALYSIS_TYPES!r}, got {analysis_type!r}"
                )
            updates["analysis_type"] = analysis_type.strip()

        self._projects.update(
            updates=updates,
            pk_values=project_id,
        )
        logger.info("Project updated project_id=%d status=%s", project_id, status)
        return self.get_project(project_id)

    def attach_ifc(self, project_id: int, storage_ref: str) -> None:
        """Point a project at an IFC object already in storage.

        Used by the Phase 6 upload route, where ``FileUploadService`` has
        already stored the bytes and recorded their SHA-256 in
        ``uploaded_files``. Only the reference is written here: ``projects``
        has no SHA-256 column, and putting one into ``ifc_md5_hash`` would make
        the schema describe the wrong algorithm.

        Args:
            project_id: Project to update.
            storage_ref: Reference returned by ``ObjectStorage.save_upload``.
        """
        self._projects.update(
            updates={"ifc_file_path": storage_ref, "updated_at": now_iso_utc()},
            pk_values=project_id,
        )
        logger.info("Project IFC attached project_id=%d ref=%s", project_id, storage_ref)

    def delete_project(self, project_id: int):
        """Delete a project row by primary key."""
        project = self.get_project(project_id)
        if project is not None:
            self._storage.delete(project.get("ifc_file_path") or "")
        self._projects.delete(project_id)
        logger.info("Project deleted project_id=%d existed=%s", project_id, project is not None)

    def resolve_ifc_file(self, project_id: int) -> Path | None:
        """Return an existing IFC file path for a project, if present."""
        project = self.get_project(project_id)
        if project is None:
            return None

        ifc_file_path = project.get("ifc_file_path") or ""
        if not ifc_file_path:
            logger.debug("Project has no IFC file project_id=%d", project_id)
            return None

        local_path = self._storage.materialize_local_path(ifc_file_path)
        logger.debug("Resolved project IFC project_id=%d available=%s", project_id, local_path is not None)
        return local_path

    def resolve_analysis_ifc(self, project_id: int) -> tuple[Path | None, dict | None]:
        """Return the persisted improved IFC for the current source, when available."""
        source_path = self.resolve_ifc_file(project_id)
        if source_path is None:
            return None, None

        source_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
        lineage = self._lineage.find_by_source_sha256(project_id, source_sha256)
        if lineage is None:
            logger.info(
                "Analysis using original IFC project_id=%d source_sha256=%s improved=False",
                project_id,
                source_sha256,
            )
            return source_path, None

        improved_path = self._storage.materialize_local_path(
            str(lineage.get("output_reference") or "")
        )
        if improved_path is None:
            logger.warning(
                "Persisted improved IFC unavailable; using original project_id=%d lineage_id=%s",
                project_id,
                lineage.get("id"),
            )
            return source_path, None

        logger.info(
            "Analysis using persisted improved IFC project_id=%d lineage_id=%s version=%s source_sha256=%s",
            project_id,
            lineage.get("id"),
            lineage.get("version"),
            source_sha256,
        )
        return improved_path, lineage
    # ── standards ────────────────────────────────────────────────────────────

    def get_standards_by_project(self, project_id: int) -> list[dict]:
        """Return the standards selected for a project.

        Each row is enriched with ``name``, ``domain`` and ``description`` for
        notebook standards; uploaded standards fall back to their filename, so
        callers can render both kinds from one list.
        """
        rows = list(self._standards.rows_where("project_id = ?", [project_id]))
        for row in rows:
            meta = get_standard(row.get("standard_id") or "")
            if meta is not None:
                row["name"] = meta["name"]
                row["domain"] = meta["domain"]
                row["description"] = meta["description"]
            else:
                row.setdefault("name", Path(row.get("file_path") or "").name or row.get("standard_id", ""))
                row.setdefault("domain", "Custom")
                row.setdefault("description", "")
        logger.debug("Loaded standards project_id=%d count=%d", project_id, len(rows))
        return rows

    def add_standard_to_project(
        self,
        project_id: int,
        standard_id: str,
        source: str = "notebook",
        file_path: str = "",
    ) -> dict | None:
        """Link one standard to a project, ignoring an existing identical link.

        The ``(project_id, standard_id, source)`` unique index makes a repeated
        submit a no-op rather than a duplicate row.
        """
        if source not in {"notebook", "uploaded"}:
            raise ValueError(f"source must be 'notebook' or 'uploaded', got {source!r}")

        existing = [
            row
            for row in self._standards.rows_where("project_id = ?", [project_id])
            if row.get("standard_id") == standard_id and row.get("source") == source
        ]
        if existing:
            logger.debug(
                "Standard already linked project_id=%d standard_id=%s", project_id, standard_id
            )
            return existing[0]

        now = now_iso_utc()
        row = self._standards.insert(
            {
                "project_id": project_id,
                "standard_id": standard_id,
                "source": source,
                "file_path": file_path,
                "created_at": now,
                "updated_at": now,
            }
        )
        logger.info(
            "Standard linked project_id=%d standard_id=%s source=%s", project_id, standard_id, source
        )
        return row

    def set_standards_for_project(self, project_id: int, standard_ids: list[str]) -> int:
        """Replace a project's notebook standards with ``standard_ids``.

        Uploaded standards are left untouched, since they own a stored file that
        this method has no mandate to delete.

        Returns:
            The number of notebook standards linked afterwards.
        """
        current = self._standards.rows_where("project_id = ?", [project_id])
        wanted = set(standard_ids)
        for row in list(current):
            if row.get("source") == "notebook" and row.get("standard_id") not in wanted:
                self._standards.delete(row["id"])

        for standard_id in standard_ids:
            self.add_standard_to_project(project_id, standard_id, source="notebook")

        logger.info("Standards set project_id=%d count=%d", project_id, len(wanted))
        return len(wanted)

    async def upload_custom_standard(self, project_id: int, upload) -> dict | None:
        """Store an uploaded standard document and link it to the project.

        Accepts ``.pdf`` and ``.docx`` only; anything else is rejected and
        ``None`` returned, matching how ``prepare_ifc_upload`` handles a bad file.
        """
        if not upload or not getattr(upload, "filename", None):
            return None

        filename = safe_upload_name(upload.filename)
        if not filename.lower().endswith(STANDARD_UPLOAD_EXTENSIONS):
            logger.warning("Rejected custom standard with unsupported type filename=%s", filename)
            return None

        content = await upload.read()
        if not content:
            logger.warning("Rejected empty custom standard filename=%s", filename)
            return None

        storage_ref = self._storage.save_upload(filename, content, f"standards/project-{project_id}")
        row = self.add_standard_to_project(
            project_id, standard_id=filename, source="uploaded", file_path=storage_ref
        )
        logger.info(
            "Custom standard uploaded project_id=%d filename=%s bytes=%d",
            project_id,
            filename,
            len(content),
        )
        return row

    def remove_standard_from_project(self, standard_row_id: int) -> None:
        """Unlink one standard, deleting its stored file when it was uploaded."""
        row = self._standards.get(standard_row_id)
        if row is None:
            return
        if row.get("source") == "uploaded" and row.get("file_path"):
            self._storage.delete(row["file_path"])
        self._standards.delete(standard_row_id)
        logger.info("Standard unlinked id=%d project_id=%s", standard_row_id, row.get("project_id"))

    # ── client documents ─────────────────────────────────────────────────────

    def get_client_documents_by_project(self, project_id: int) -> list[dict]:
        """Return the client documents uploaded against a project."""
        rows = list(self._client_documents.rows_where("project_id = ?", [project_id]))
        logger.debug("Loaded client documents project_id=%d count=%d", project_id, len(rows))
        return rows

    async def add_client_document(
        self,
        project_id: int,
        upload,
        category: str = "Other",
        description: str = "",
        tags: str = "",
    ) -> dict | None:
        """Store one client document and record its metadata.

        Args:
            project_id: Owning project.
            upload: Starlette ``UploadFile``.
            category: One of :data:`app.constants.DOCUMENT_CATEGORIES`.
            description: Optional free text.
            tags: Optional comma-separated tags.

        Returns:
            The inserted row, or ``None`` if no usable file was supplied.

        Raises:
            ValueError: if ``category`` is not a recognised value. The column
                carries a check constraint, so catching it here gives a better
                message than a Postgres violation.
        """
        if category not in DOCUMENT_CATEGORIES:
            raise ValueError(
                f"category must be one of {DOCUMENT_CATEGORIES!r}, got {category!r}"
            )
        if not upload or not getattr(upload, "filename", None):
            return None

        filename = safe_upload_name(upload.filename)
        content = await upload.read()
        if not content:
            logger.warning("Rejected empty client document filename=%s", filename)
            return None

        storage_ref = self._storage.save_upload(
            filename, content, f"client-documents/project-{project_id}"
        )
        now = now_iso_utc()
        row = self._client_documents.insert(
            {
                "project_id": project_id,
                "filename": filename,
                "file_path": storage_ref,
                "file_type": getattr(upload, "content_type", "") or Path(filename).suffix.lstrip("."),
                "category": category,
                "description": description.strip(),
                "tags": tags.strip(),
                "upload_date": now,
                "updated_at": now,
            }
        )
        logger.info(
            "Client document stored project_id=%d filename=%s category=%s bytes=%d",
            project_id,
            filename,
            category,
            len(content),
        )
        return row

    def delete_client_document(self, document_id: int) -> None:
        """Delete one client document row and its stored file."""
        row = self._client_documents.get(document_id)
        if row is None:
            return
        if row.get("file_path"):
            self._storage.delete(row["file_path"])
        self._client_documents.delete(document_id)
        logger.info("Client document deleted id=%d project_id=%s", document_id, row.get("project_id"))

    def get_analysis_inputs(self, project_id: int) -> list[dict]:
        """Return standards and client documents as one list for the analyze forms.

        Both analysis pages offer a single multi-select spanning the two sources,
        so merging them here keeps that shape in one place. Each entry carries
        ``kind`` (``standard`` or ``document``) so the caller can label it.
        """
        merged: list[dict] = []
        for row in self.get_standards_by_project(project_id):
            merged.append(
                {
                    "kind": "standard",
                    "id": f"standard-{row.get('id')}",
                    "label": row.get("name") or row.get("standard_id", ""),
                    "detail": row.get("domain") or "",
                    "file_path": row.get("file_path") or "",
                }
            )
        for row in self.get_client_documents_by_project(project_id):
            merged.append(
                {
                    "kind": "document",
                    "id": f"document-{row.get('id')}",
                    "label": row.get("filename", ""),
                    "detail": row.get("category") or "",
                    "file_path": row.get("file_path") or "",
                }
            )
        return merged
