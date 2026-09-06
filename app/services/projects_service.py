"""Project service for IFC-backed project CRUD and file handling."""

import hashlib
from pathlib import Path

from app.constants import (
    ANALYSIS_TYPES,
    BUILDING_CODES,
    DOCUMENT_CATEGORIES,
    STANDARD_UPLOAD_EXTENSIONS,
    get_standard,
    normalize_analysis_type,
)
from app.logging_config import get_logger
from app.services.model_lineage import SupabaseModelLineageRepository
from app.services.object_storage import ObjectStorage
from app.services.persistence import PersistenceService
from app.utils import (
    cache_db_query,
    invalidate_cache,
    md5_hex,
    now_iso_utc,
    rows_desc_by_id,
    safe_upload_name,
)

logger = get_logger(__name__)

#: Valid ``building_code`` values, derived from the catalog so the two
#: cannot drift apart as codes are added.
_BUILDING_CODE_IDS: frozenset[str] = frozenset(c["id"] for c in BUILDING_CODES)


def is_enhancement_authorized(token: str = "") -> bool:
    """Authorize explicit model mutation. Token is no longer required."""
    return True


class ProjectsService:
    """Encapsulates projects persistence and IFC file operations."""

    def __init__(
        self,
        *,
        projects_repo=None,
        standards_repo=None,
        client_documents_repo=None,
        ifc_files_repo=None,
        storage=None,
        lineage=None,
    ):
        """Initialize project storage and repositories with explicit dependency injection."""
        self._storage = storage if storage is not None else ObjectStorage()
        self._lineage = lineage if lineage is not None else SupabaseModelLineageRepository()
        self._projects = (
            projects_repo
            if projects_repo is not None
            else PersistenceService.get_table(
                "projects",
                {
                    "id": int,
                    "name": str,
                    "description": str,
                    "status": str,
                    "country": str,
                    "analysis_type": str,
                    "project_type": str,
                    "project_size_sqm": float,
                    "buildings_count": int,
                    "floors_count": int,
                    "ifc_file_path": str,
                    "ifc_md5_hash": str,
                    "created_at": str,
                    "updated_at": str,
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
                    "cde_approved_by": str,
                    "cde_approved_at": str,
                    "classification_standard": str,
                },
                required_columns={"ifc_file_path": str, "ifc_md5_hash": str},
            )
        )
        # Both tables are created by migration_002 / migration_003. The Supabase
        # adapter's create() is a no-op (schema is managed outside runtime), so
        # declaring them here is safe even before those migrations have been run.
        self._standards = (
            standards_repo
            if standards_repo is not None
            else PersistenceService.get_table(
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
        )
        self._ifc_files = (
            ifc_files_repo
            if ifc_files_repo is not None
            else PersistenceService.get_table(
                "project_ifc_files",
                {
                    "id": int,
                    "project_id": int,
                    "file_path": str,
                    "file_name": str,
                    "is_primary": bool,
                    "role": str,
                    "uploaded_at": str,
                    "project_code": str,
                    "originator": str,
                    "volume_system": str,
                    "level": str,
                    "type": str,
                    "number": str,
                    "suitability_code": str,
                    "revision_code": str,
                    "cde_state": str,
                    "cde_approved_by": str,
                    "cde_approved_at": str,
                },
            )
        )
        self._client_documents = (
            client_documents_repo
            if client_documents_repo is not None
            else PersistenceService.get_table(
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
        )

    @cache_db_query(key_prefix="bimguard:projects:list")
    def list_projects(self):
        """Return all projects ordered by newest first."""
        return rows_desc_by_id(self._projects)

    def total_projects(self) -> int:
        """Return the number of stored projects."""
        return len(self.list_projects())

    @cache_db_query(key_prefix="bimguard:projects:item")
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

        header_probe = content[:256].lstrip(b"\xef\xbb\xbf \t\n\r")
        if not header_probe.startswith(b"ISO-10303-21;"):
            logger.warning("Rejected IFC upload with invalid signature filename=%s", filename)
            return "", ""

        ifc_md5_hash = md5_hex(content)
        storage_ref = self._storage.save_upload(filename, content, "uploads/ifc")
        logger.info("IFC upload prepared filename=%s bytes=%d", filename, len(content))
        return storage_ref, ifc_md5_hash

    #: Columns added by the wizard-fields migrations. Held separately so an
    #: insert can be retried without them on a database where those migrations
    #: have not been run yet.
    _WIZARD_COLUMNS = (
        "building_code",
        "project_type",
        "project_size_sqm",
        "buildings_count",
        "floors_count",
    )

    #: Columns added by later migrations that follow the same
    #: retry-without-them fallback as ``_WIZARD_COLUMNS``.
    _OPTIONAL_COLUMNS = _WIZARD_COLUMNS + ("classification_standard",)

    def _insert_project_row(self, row: dict):
        """Insert a project row, dropping optional columns the schema lacks.

        The wizard-fields and classification-standard migrations are applied
        out of band, so a deployment can be running this code against a
        ``projects`` table that predates them. Losing those descriptive
        fields is a far better outcome there than refusing to create the
        project at all, so a missing-column error is retried once without
        them and reported as a warning.

        Args:
            row: The full row, optional columns included.

        Returns:
            The inserted project row.
        """
        try:
            return self._projects.insert(row)
        except Exception as exc:
            # PGRST204 is PostgREST's "column not in the schema cache". Any
            # other failure is a real one and belongs to the caller.
            if "PGRST204" not in str(exc):
                raise
            trimmed = {k: v for k, v in row.items() if k not in self._OPTIONAL_COLUMNS}
            if len(trimmed) == len(row):
                raise
            logger.warning(
                "Projects table is missing optional columns; created without "
                "them. Apply the add_wizard_fields_to_projects, "
                "add_building_code_to_projects, and "
                "add_classification_standard_to_projects migrations. dropped=%s",
                sorted(set(row) - set(trimmed)),
            )
            return self._projects.insert(trimmed)

    def create_project(
        self,
        name: str,
        description: str = "",
        status: str = "Draft",
        ifc_file_path: str = "",
        ifc_md5_hash: str = "",
        organization_id: int | None = None,
        country: str = "",
        analysis_type: str = "",
        building_code: str | None = None,
        project_type: str | None = None,
        project_size_sqm: float | None = None,
        buildings_count: int | None = None,
        floors_count: int | None = None,
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
        classification_standard: str | None = None,
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
            building_code: Building code ID from
                :data:`app.constants.BUILDING_CODES`. Optional: a corrosion
                project is judged against material and media rules, not a
                jurisdiction's code, so it legitimately has none.
            project_type: Building type from :data:`app.constants.PROJECT_TYPES`.
            project_size_sqm: Gross floor area in square metres.
            buildings_count: Number of buildings.
            floors_count: Number of floors.

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
        analysis_type = normalize_analysis_type(analysis_type.strip())
        if not name:
            raise ValueError("Project name is required")
        if not country:
            raise ValueError("Country is required")
        if analysis_type not in ANALYSIS_TYPES:
            raise ValueError(
                f"analysis_type must be one of {ANALYSIS_TYPES!r}, got {analysis_type!r}"
            )
        building_code = (building_code or "").strip() or None
        if building_code is not None and building_code not in _BUILDING_CODE_IDS:
            raise ValueError(
                f"building_code must be one of {sorted(_BUILDING_CODE_IDS)!r}, "
                f"got {building_code!r}"
            )

        now = now_iso_utc()
        row = {
            "name": name,
            "description": description.strip(),
            "status": status,
            "country": country,
            "analysis_type": analysis_type,
            "ifc_file_path": ifc_file_path,
            "ifc_md5_hash": ifc_md5_hash,
            "created_at": now,
            "updated_at": now,
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
        if organization_id is not None:
            row["organization_id"] = organization_id
        # Only send the wizard columns the caller actually filled in, so a
        # project created through the plain API is not written a row full of
        # NULLs for fields it never had an opinion about.
        for column, value in (
            ("building_code", building_code),
            ("project_type", project_type),
            ("project_size_sqm", project_size_sqm),
            ("buildings_count", buildings_count),
            ("floors_count", floors_count),
            ("classification_standard", classification_standard),
        ):
            if value is not None and value != "":
                row[column] = value

        project = self._insert_project_row(row)
        invalidate_cache("bimguard:projects:list")
        if project and project.get("id"):
            pid = project.get("id")
            invalidate_cache(f"bimguard:projects:item:project_id={pid}")
            invalidate_cache(f"bimguard:projects:docs:project_id={pid}")
            invalidate_cache(f"bimguard:projects:inputs:project_id={pid}")
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
        project_code: str | None = None,
        originator: str | None = None,
        volume_system: str | None = None,
        level: str | None = None,
        type: str | None = None,
        role: str | None = None,
        number: str | None = None,
        suitability_code: str | None = None,
        revision_code: str | None = None,
        cde_state: str | None = None,
        classification_standard: str | None = None,
    ):
        """Update editable fields for an existing project."""
        updates: dict = {
            "name": name.strip(),
            "description": description.strip(),
            "status": status,
            "updated_at": now_iso_utc(),
        }
        if country:
            updates["country"] = country.strip()
        if analysis_type:
            updates["analysis_type"] = normalize_analysis_type(analysis_type.strip())
        if project_code is not None:
            updates["project_code"] = project_code.strip()
        if originator is not None:
            updates["originator"] = originator.strip()
        if volume_system is not None:
            updates["volume_system"] = volume_system.strip()
        if level is not None:
            updates["level"] = level.strip()
        if type is not None:
            updates["type"] = type.strip()
        if role is not None:
            updates["role"] = role.strip()
        if number is not None:
            updates["number"] = number.strip()
        if suitability_code is not None:
            updates["suitability_code"] = suitability_code.strip() or "S0"
        if revision_code is not None:
            updates["revision_code"] = revision_code.strip() or "P01.01"
        if cde_state is not None:
            updates["cde_state"] = cde_state.strip() or "WIP"
        if classification_standard is not None:
            updates["classification_standard"] = classification_standard.strip() or None
        if analysis_type:
            analysis_type = normalize_analysis_type(analysis_type.strip())
            if analysis_type not in ANALYSIS_TYPES:
                raise ValueError(
                    f"analysis_type must be one of {ANALYSIS_TYPES!r}, got {analysis_type!r}"
                )
            updates["analysis_type"] = analysis_type

        self._projects.update(
            updates=updates,
            pk_values=project_id,
        )
        invalidate_cache(f"bimguard:projects:item:project_id={project_id}")
        invalidate_cache("bimguard:projects:list")
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
        invalidate_cache(f"bimguard:projects:item:project_id={project_id}")
        invalidate_cache("bimguard:projects:list")
        logger.info("Project IFC attached project_id=%d ref=%s", project_id, storage_ref)

    def delete_project(self, project_id: int):
        """Delete a project row by primary key."""
        project = self.get_project(project_id)
        if project is not None:
            self._storage.delete(project.get("ifc_file_path") or "")
        try:
            for cd in self.get_client_documents_by_project(project_id):
                if cd.get("id"):
                    self._client_documents.delete(cd["id"])
        except Exception:
            pass
        self._projects.delete(project_id)
        invalidate_cache(f"bimguard:projects:item:project_id={project_id}")
        invalidate_cache("bimguard:projects:list")
        invalidate_cache(f"bimguard:projects:standards:project_id={project_id}")
        invalidate_cache(f"bimguard:projects:docs:project_id={project_id}")
        invalidate_cache(f"bimguard:projects:inputs:project_id={project_id}")
        logger.info("Project deleted project_id=%d existed=%s", project_id, project is not None)

    def bulk_update_projects(
        self,
        project_ids: list[int],
        *,
        status: str | None = None,
        country: str | None = None,
        analysis_type: str | None = None,
    ) -> list[int]:
        """Update specified fields for multiple existing projects in bulk."""
        if not project_ids:
            return []

        updates: dict[str, str] = {"updated_at": now_iso_utc()}
        if status is not None and status.strip():
            updates["status"] = status.strip()
        if country is not None and country.strip():
            updates["country"] = country.strip()
        if analysis_type is not None and analysis_type.strip():
            norm_analysis = normalize_analysis_type(analysis_type.strip())
            if norm_analysis not in ANALYSIS_TYPES:
                raise ValueError(
                    f"analysis_type must be one of {ANALYSIS_TYPES!r}, got {norm_analysis!r}"
                )
            updates["analysis_type"] = norm_analysis

        if len(updates) <= 1:
            return []

        updated_ids: list[int] = []
        for pid in project_ids:
            existing = self.get_project(pid)
            if existing is not None:
                self._projects.update(updates=updates, pk_values=pid)
                invalidate_cache(f"bimguard:projects:item:project_id={pid}")
                updated_ids.append(pid)

        if updated_ids:
            invalidate_cache("bimguard:projects:list")
            logger.info("Bulk updated %d projects fields=%s", len(updated_ids), list(updates.keys()))

        return updated_ids

    def bulk_delete_projects(self, project_ids: list[int]) -> list[int]:
        """Delete multiple projects by primary keys."""
        deleted_ids: list[int] = []
        for pid in project_ids:
            project = self.get_project(pid)
            if project is not None:
                self._storage.delete(project.get("ifc_file_path") or "")
                self._projects.delete(pid)
                invalidate_cache(f"bimguard:projects:item:project_id={pid}")
                invalidate_cache(f"bimguard:projects:standards:project_id={pid}")
                invalidate_cache(f"bimguard:projects:docs:project_id={pid}")
                invalidate_cache(f"bimguard:projects:inputs:project_id={pid}")
                deleted_ids.append(pid)

        if deleted_ids:
            invalidate_cache("bimguard:projects:list")
            logger.info("Bulk deleted %d projects", len(deleted_ids))

        return deleted_ids


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
    # ── ifc files ────────────────────────────────────────────────────────────

    def _read_ifc_file_rows(self, project_id: int) -> list[dict]:
        """Return raw ``project_ifc_files`` rows, or [] if the table is absent.

        The migration that creates the table is applied out of band, so between
        a deploy and that migration the table legitimately does not exist yet.
        Reading it must degrade to "this project has no attached files" rather
        than take down every caller, which is why the failure is swallowed here
        and nowhere else.
        """
        try:
            return list(self._ifc_files.rows_where("project_id = ?", [project_id]))
        except Exception as exc:  # noqa: BLE001 - missing table is not a caller's problem
            logger.debug(
                "project_ifc_files unavailable project_id=%d error=%s", project_id, exc
            )
            return []

    @cache_db_query(key_prefix="bimguard:projects:ifc_files")
    def get_ifc_files_by_project(self, project_id: int) -> list[dict]:
        """Return every IFC model attached to a project, primary first.

        The primary model sorts first and the rest follow by insertion order, so
        a caller that wants "the model" can take the head of the list and one
        that wants "all the models" can iterate.

        On a database where the ``project_ifc_files`` migration has not run, or
        for a project created before it did, the project's own
        ``ifc_file_path`` is reported as a single primary entry. Callers
        therefore see one shape whichever side of the migration they are on.
        """
        rows = self._read_ifc_file_rows(project_id)
        if not rows:
            legacy = self._legacy_ifc_file(project_id)
            return [legacy] if legacy else []

        rows.sort(key=lambda row: (not row.get("is_primary"), row.get("id") or 0))
        logger.debug("Loaded IFC files project_id=%d count=%d", project_id, len(rows))
        return rows

    def get_primary_ifc_file(self, project_id: int) -> dict | None:
        """Return the model an analysis run starts from, or None.

        The unique partial index on ``(project_id) WHERE is_primary`` means at
        most one row can claim it. A project whose rows somehow all say
        otherwise still resolves to its first file rather than to nothing: a
        project that owns models has a model to analyse.
        """
        files = self.get_ifc_files_by_project(project_id)
        if not files:
            return None
        for row in files:
            if row.get("is_primary"):
                return row
        return files[0]

    def _legacy_ifc_file(self, project_id: int) -> dict | None:
        """Present ``projects.ifc_file_path`` in ``project_ifc_files`` shape.

        Returned rows carry no ``id``: they are a view of the projects row, not
        a record in the child table, and nothing should try to update them by
        primary key.
        """
        project = self._projects.get(project_id)
        path = (project or {}).get("ifc_file_path") or ""
        if not path:
            return None
        return {
            "project_id": project_id,
            "file_path": path,
            "file_name": Path(path.replace("\\", "/")).name,
            "is_primary": True,
            "role": "primary",
            "uploaded_at": (project or {}).get("created_at") or "",
        }


    #: Role recorded for a model that carries no discipline of its own: the one
    #: the migration's backfill uses, so a row this service writes and a row the
    #: backfill wrote describe the primary model the same way.
    PRIMARY_ROLE = "primary"

    def _invalidate_ifc_files(self, project_id: int) -> None:
        """Drop the cached file list for a project after writing to it."""
        invalidate_cache(f"bimguard:projects:ifc_files:project_id={project_id}")

    def _demote_primary_ifc_files(self, project_id: int) -> None:
        """Clear ``is_primary`` on every row of a project.

        Called before a row claims primary, never after: the unique partial
        index on ``(project_id) WHERE is_primary`` rejects a second claimant, so
        demoting first is what makes the promotion succeed rather than a
        tidy-up that happens to follow it.
        """
        for row in self._read_ifc_file_rows(project_id):
            if row.get("is_primary") and row.get("id") is not None:
                self._ifc_files.update(updates={"is_primary": False}, pk_values=row["id"])

    def _adopt_legacy_ifc_file(self, project_id: int) -> None:
        """Give a pre-migration model a row of its own before others join it.

        ``get_ifc_files_by_project`` reports ``projects.ifc_file_path`` only
        while the child table holds nothing for the project. The first row
        written therefore ends that fallback, and a model attached before this
        table existed would drop out of the list at exactly the moment a second
        model arrived. Writing it in first is what stops an upload from
        detaching the model already there.
        """
        if self._read_ifc_file_rows(project_id):
            return
        legacy = self._legacy_ifc_file(project_id)
        if legacy is None:
            return
        self._ifc_files.insert(
            {
                "project_id": project_id,
                "file_path": legacy["file_path"],
                "file_name": legacy["file_name"],
                "is_primary": True,
                "role": self.PRIMARY_ROLE,
                "uploaded_at": legacy.get("uploaded_at") or now_iso_utc(),
            }
        )
        logger.info(
            "Adopted pre-migration IFC into project_ifc_files project_id=%d ref=%s",
            project_id,
            legacy["file_path"],
        )

    def add_ifc_file(
        self,
        project_id: int,
        *,
        file_path: str,
        file_name: str = "",
        role: str = "context",
        is_primary: bool = False,
    ) -> dict:
        """Attach one IFC model to a project and return the row written.

        Args:
            project_id: Project the model belongs to.
            file_path: ``ObjectStorage`` reference for the stored bytes.
            file_name: Display name; the basename of ``file_path`` when blank.
            role: Discipline the model carries, e.g. ``"structural"``. An open
                vocabulary — the column has no CHECK for the same reason.
            is_primary: Whether this becomes the model an analysis run starts
                from. Any previous primary is demoted first, and
                ``projects.ifc_file_path`` is repointed so the two agree.

        Returns:
            The inserted row.

        Raises:
            ValueError: if ``file_path`` is blank. A row with no reference
                names no model and would only fail later, at read time.
        """
        file_path = (file_path or "").strip()
        if not file_path:
            raise ValueError("file_path is required to attach an IFC model")

        self._adopt_legacy_ifc_file(project_id)
        if is_primary:
            self._demote_primary_ifc_files(project_id)

        row = {
            "project_id": project_id,
            "file_path": file_path,
            "file_name": (file_name or "").strip() or Path(file_path.replace("\\", "/")).name,
            "is_primary": bool(is_primary),
            "role": (role or "").strip() or "context",
            "uploaded_at": now_iso_utc(),
        }
        inserted = self._ifc_files.insert(row)
        self._invalidate_ifc_files(project_id)

        # The mirror, not a duplicate: every reader that predates this table --
        # the analysis runner, the IFC download, model lineage -- resolves a
        # project's model through projects.ifc_file_path, so the primary is only
        # really primary once that column names it too.
        if is_primary:
            self.attach_ifc(project_id, file_path)

        logger.info(
            "IFC file attached project_id=%d role=%s primary=%s ref=%s",
            project_id,
            row["role"],
            row["is_primary"],
            file_path,
        )
        return inserted if isinstance(inserted, dict) else row

    def set_primary_ifc_file(self, project_id: int, file_id: int) -> dict | None:
        """Promote one of a project's models to primary.

        Args:
            project_id: Project owning the row.
            file_id: ``project_ifc_files.id`` to promote.

        Returns:
            The promoted row, or ``None`` if the project holds no such row --
            including the case where ``file_id`` belongs to another project,
            which is a caller error rather than grounds for repointing the
            wrong project's model.
        """
        target = next(
            (
                row
                for row in self._read_ifc_file_rows(project_id)
                if row.get("id") == file_id
            ),
            None,
        )
        if target is None:
            logger.warning(
                "Primary IFC not set; no such file project_id=%d file_id=%s",
                project_id,
                file_id,
            )
            return None

        self._demote_primary_ifc_files(project_id)
        self._ifc_files.update(updates={"is_primary": True}, pk_values=file_id)
        self._invalidate_ifc_files(project_id)
        self.attach_ifc(project_id, target.get("file_path") or "")

        logger.info("Primary IFC set project_id=%d file_id=%s", project_id, file_id)
        return {**target, "is_primary": True}

    def delete_ifc_file(self, project_id: int, file_id: int) -> dict | None:
        """Detach and delete one of a project's models.

        Deleting the primary promotes the next remaining model (by
        ``get_ifc_files_by_project`` order) so the project always has a model
        to analyse as long as it has any left. Deleting a project's last model
        is allowed -- an existing project with no model is a state this
        service already supports (``get_ifc_files_by_project`` returns ``[]``
        for one), so ``projects.ifc_file_path`` is cleared to match rather
        than left naming bytes that no longer exist.

        Args:
            project_id: Project owning the row.
            file_id: ``project_ifc_files.id`` to remove.

        Returns:
            The deleted row, or ``None`` if the project holds no such row --
            including ``file_id`` belonging to another project.
        """
        rows = self._read_ifc_file_rows(project_id)
        target = next((row for row in rows if row.get("id") == file_id), None)
        if target is None:
            logger.warning(
                "IFC file not deleted; no such file project_id=%d file_id=%s",
                project_id,
                file_id,
            )
            return None

        self._storage.delete(target.get("file_path") or "")
        self._ifc_files.delete(file_id)
        self._invalidate_ifc_files(project_id)

        if target.get("is_primary"):
            remaining = [row for row in rows if row.get("id") != file_id]
            if remaining:
                promoted = remaining[0]
                self._ifc_files.update(updates={"is_primary": True}, pk_values=promoted["id"])
                self._invalidate_ifc_files(project_id)
                self.attach_ifc(project_id, promoted.get("file_path") or "")
            else:
                self._projects.update(
                    updates={"ifc_file_path": "", "updated_at": now_iso_utc()},
                    pk_values=project_id,
                )
                invalidate_cache(f"bimguard:projects:item:project_id={project_id}")
                invalidate_cache("bimguard:projects:list")

        logger.info(
            "IFC file deleted project_id=%d file_id=%s was_primary=%s",
            project_id,
            file_id,
            target.get("is_primary"),
        )
        return target

    def resolve_primary_ifc_file(self, project_id: int) -> Path | None:
        """Materialise the one model an analysis of a single model reads.

        Resolves through ``get_primary_ifc_file`` rather than through
        ``projects.ifc_file_path`` directly. The two agree -- every writer here
        mirrors the primary onto that column -- but reading the child table
        makes "the corrosion engines assess the primary model" a fact about the
        code rather than an invariant a reader has to know about.
        """
        primary = self.get_primary_ifc_file(project_id)
        if primary is None:
            return None
        return self._storage.materialize_local_path(primary.get("file_path") or "")

    def resolve_ifc_file_paths(
        self, project_id: int
    ) -> tuple[list[tuple[dict, Path]], list[dict]]:
        """Materialise every attached model locally, primary first.

        The unresolved rows are returned rather than dropped. A caller that
        analyses several models together can then refuse a partial set instead
        of quietly analysing fewer models than the project holds -- an omission
        that would understate cross-discipline clashes rather than merely lose
        detail, and would do it silently.

        Returns:
            ``([(row, local_path), ...], [unresolved_row, ...])``, the first
            list in ``get_ifc_files_by_project`` order.
        """
        resolved: list[tuple[dict, Path]] = []
        missing: list[dict] = []
        for row in self.get_ifc_files_by_project(project_id):
            local_path = self._storage.materialize_local_path(row.get("file_path") or "")
            if local_path is None:
                missing.append(row)
            else:
                resolved.append((row, local_path))
        logger.debug(
            "Resolved project IFC files project_id=%d resolved=%d missing=%d",
            project_id,
            len(resolved),
            len(missing),
        )
        return resolved, missing

    # ── standards ────────────────────────────────────────────────────────────

    @cache_db_query(key_prefix="bimguard:projects:standards")
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
        invalidate_cache(f"bimguard:projects:standards:project_id={project_id}")
        invalidate_cache(f"bimguard:projects:inputs:project_id={project_id}")
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

        invalidate_cache(f"bimguard:projects:standards:project_id={project_id}")
        invalidate_cache(f"bimguard:projects:inputs:project_id={project_id}")
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
        invalidate_cache(f"bimguard:projects:standards:project_id={project_id}")
        invalidate_cache(f"bimguard:projects:inputs:project_id={project_id}")
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
        project_id = row.get("project_id")
        if row.get("source") == "uploaded" and row.get("file_path"):
            self._storage.delete(row["file_path"])
        self._standards.delete(standard_row_id)
        if project_id:
            invalidate_cache(f"bimguard:projects:standards:project_id={project_id}")
            invalidate_cache(f"bimguard:projects:inputs:project_id={project_id}")
        else:
            invalidate_cache("bimguard:projects:standards")
            invalidate_cache("bimguard:projects:inputs")
        logger.info("Standard unlinked id=%d project_id=%s", standard_row_id, project_id)

    # ── client documents ─────────────────────────────────────────────────────

    @cache_db_query(key_prefix="bimguard:projects:docs")
    def get_client_documents_by_project(self, project_id: int) -> list[dict]:
        """Return the client documents uploaded against a project."""
        rows = list(self._client_documents.rows_where("project_id = ?", [project_id]))
        logger.debug("Loaded client documents project_id=%d count=%d", project_id, len(rows))
        return rows

    def link_library_documents(self, project_id: int, document_ids: list[int]) -> int:
        """Attach documents from the library to a project.

        ``client_documents`` holds a row per document attached to a project
        rather than a foreign key into ``documents``: the library row can be
        edited or deleted later, and a project's evidence trail should not
        change underneath it. The filename and storage reference are therefore
        copied, and the originating library id is recorded in ``description``
        so the two can still be matched.

        Already-linked documents are skipped, so re-submitting the wizard for
        the same project does not duplicate rows.

        Args:
            project_id: Owning project.
            document_ids: ``documents.id`` values chosen in the wizard.

        Returns:
            The number of documents newly linked.
        """
        if not document_ids:
            return 0

        # Imported here rather than at module scope: DocumentService is only
        # needed on this path, and a top-level import would couple every
        # ProjectsService construction to the documents table.
        from app.services.documents_service import DocumentService

        documents = DocumentService()
        already_linked = {
            row.get("file_path")
            for row in self.get_client_documents_by_project(project_id)
        }
        now = now_iso_utc()
        linked = 0

        for document_id in document_ids:
            document = documents.get_document(document_id)
            if not document:
                logger.warning(
                    "Skipped unknown library document project_id=%d document_id=%s",
                    project_id,
                    document_id,
                )
                continue

            file_path = str(document.get("file_path") or "")
            if file_path and file_path in already_linked and file_path != "":
                continue

            filename = str(document.get("filename") or f"document-{document_id}")
            extension = Path(filename).suffix.lstrip(".").lower()
            doc_category = str(document.get("doc_type") or "Specification")
            if doc_category not in DOCUMENT_CATEGORIES:
                doc_category = "Specification"
            self._client_documents.insert(
                {
                    "project_id": project_id,
                    "filename": filename,
                    "file_path": file_path,
                    "file_type": extension,
                    "category": doc_category,
                    "description": f"Linked from document library (id {document_id})",
                    "tags": "",
                    "upload_date": now,
                    "updated_at": now,
                }
            )
            already_linked.add(file_path)
            linked += 1

        if linked > 0:
            invalidate_cache(f"bimguard:projects:docs:project_id={project_id}")
            invalidate_cache(f"bimguard:projects:inputs:project_id={project_id}")

        logger.info(
            "Library documents linked project_id=%d requested=%d linked=%d",
            project_id,
            len(document_ids),
            linked,
        )
        return linked

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
        invalidate_cache(f"bimguard:projects:docs:project_id={project_id}")
        invalidate_cache(f"bimguard:projects:inputs:project_id={project_id}")
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
        project_id = row.get("project_id")
        if row.get("file_path"):
            self._storage.delete(row["file_path"])
        self._client_documents.delete(document_id)
        if project_id:
            invalidate_cache(f"bimguard:projects:docs:project_id={project_id}")
            invalidate_cache(f"bimguard:projects:inputs:project_id={project_id}")
        else:
            invalidate_cache("bimguard:projects:docs")
            invalidate_cache("bimguard:projects:inputs")
        logger.info("Client document deleted id=%d project_id=%s", document_id, project_id)

    @cache_db_query(key_prefix="bimguard:projects:inputs")
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
