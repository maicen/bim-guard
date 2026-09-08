"""Models service for IFC model CRUD, attachment, and lifecycle.

Split out of ``ProjectsService``: a project can hold many IFC models, and each
one has a lifecycle of its own (attach, become primary, get replaced, get
deleted) independent of the project's. ``ProjectsService`` still owns the
legacy ``projects.ifc_file_path``/``ifc_md5_hash`` mirror columns and the
project row itself; this service owns everything about ``project_ifc_files``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol

from app.logging_config import get_logger
from app.modules.ifc_reader.ifc_parser import IfcModelSummary, extract_ifc_summary_metadata
from app.services.model_lineage import SupabaseModelLineageRepository
from app.services.object_storage import ObjectStorage
from app.services.persistence import PersistenceService
from app.utils import cache_db_query, invalidate_cache, now_iso_utc

logger = get_logger(__name__)


class ProjectMirror(Protocol):
    """What :class:`ModelsService` needs from ``ProjectsService``.

    A structural type, not a concrete import: ``ModelsService`` never imports
    ``ProjectsService`` itself, so wiring ``ProjectsService -> ModelsService``
    for cascade-delete never creates an import cycle.
    """

    def get_project(self, project_id: int) -> dict | None: ...

    def attach_ifc(self, project_id: int, storage_ref: str) -> None: ...


class ModelsService:
    """Encapsulates ``project_ifc_files`` persistence and IFC model lifecycle."""

    #: Role recorded for a model that carries no discipline of its own: the one
    #: the migration's backfill uses, so a row this service writes and a row the
    #: backfill wrote describe the primary model the same way.
    PRIMARY_ROLE = "primary"

    def __init__(
        self,
        *,
        ifc_files_repo=None,
        storage=None,
        lineage=None,
        project_mirror: ProjectMirror | None = None,
    ):
        """Initialize model storage and repositories with explicit dependency injection."""
        self._storage = storage if storage is not None else ObjectStorage()
        self._lineage = lineage if lineage is not None else SupabaseModelLineageRepository()
        self._project_mirror = project_mirror
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

    def bind_project_mirror(self, project_mirror: ProjectMirror) -> None:
        """Attach the ``ProjectMirror`` after construction.

        Bootstrap builds ``ModelsService`` and ``ProjectsService`` in a single
        pass where each needs the other (``ProjectsService`` for the mirror
        read/write, ``ModelsService`` for cascade-delete), so one of the two
        is necessarily wired in after the other already exists.
        """
        self._project_mirror = project_mirror

    def _get_project(self, project_id: int) -> dict | None:
        if self._project_mirror is None:
            return None
        return self._project_mirror.get_project(project_id)

    def _mirror_attach(self, project_id: int, storage_ref: str) -> None:
        if self._project_mirror is not None:
            self._project_mirror.attach_ifc(project_id, storage_ref)

    def _read_rows(self, project_id: int) -> list[dict]:
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

    @cache_db_query(key_prefix="bimguard:models:list")
    def list_models(self, project_id: int) -> list[dict]:
        """Return every IFC model attached to a project, primary first.

        The primary model sorts first and the rest follow by insertion order, so
        a caller that wants "the model" can take the head of the list and one
        that wants "all the models" can iterate.

        On a database where the ``project_ifc_files`` migration has not run, or
        for a project created before it did, the project's own
        ``ifc_file_path`` is reported as a single primary entry. Callers
        therefore see one shape whichever side of the migration they are on.
        """
        rows = self._read_rows(project_id)
        if not rows:
            legacy = self._legacy_row(project_id)
            return [legacy] if legacy else []

        rows.sort(key=lambda row: (not row.get("is_primary"), row.get("id") or 0))
        logger.debug("Loaded IFC files project_id=%d count=%d", project_id, len(rows))
        return rows

    def get_primary(self, project_id: int) -> dict | None:
        """Return the model an analysis run starts from, or None.

        The unique partial index on ``(project_id) WHERE is_primary`` means at
        most one row can claim it. A project whose rows somehow all say
        otherwise still resolves to its first file rather than to nothing: a
        project that owns models has a model to analyse.
        """
        files = self.list_models(project_id)
        if not files:
            return None
        for row in files:
            if row.get("is_primary"):
                return row
        return files[0]

    def _legacy_row(self, project_id: int) -> dict | None:
        """Present ``projects.ifc_file_path`` in ``project_ifc_files`` shape.

        Returned rows carry no ``id``: they are a view of the projects row, not
        a record in the child table, and nothing should try to update them by
        primary key.
        """
        project = self._get_project(project_id)
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

    def _invalidate(self, project_id: int) -> None:
        """Drop the cached model list for a project after writing to it."""
        invalidate_cache(f"bimguard:models:list:project_id={project_id}")

    def _demote_primary(self, project_id: int) -> None:
        """Clear ``is_primary`` on every row of a project.

        Called before a row claims primary, never after: the unique partial
        index on ``(project_id) WHERE is_primary`` rejects a second claimant, so
        demoting first is what makes the promotion succeed rather than a
        tidy-up that happens to follow it.
        """
        for row in self._read_rows(project_id):
            if row.get("is_primary") and row.get("id") is not None:
                self._ifc_files.update(updates={"is_primary": False}, pk_values=row["id"])

    def _adopt_legacy(self, project_id: int) -> None:
        """Give a pre-migration model a row of its own before others join it.

        ``list_models`` reports ``projects.ifc_file_path`` only while the
        child table holds nothing for the project. The first row written
        therefore ends that fallback, and a model attached before this table
        existed would drop out of the list at exactly the moment a second
        model arrived. Writing it in first is what stops an upload from
        detaching the model already there.
        """
        if self._read_rows(project_id):
            return
        legacy = self._legacy_row(project_id)
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

    def _extract_summary(self, file_path: str) -> IfcModelSummary:
        """Best-effort read of schema/authoring-app/storey/element/discipline metadata.

        Never blocks or fails the attach: a model that cannot be opened yet
        (corrupt upload, unreachable repo URL) still gets a row -- it just
        carries a blank summary instead of the whole attach failing.
        """
        try:
            local_path = self._storage.materialize_local_path(file_path)
            if local_path is None:
                return IfcModelSummary()
            return extract_ifc_summary_metadata(str(local_path))
        except Exception as exc:  # noqa: BLE001 - display metadata, not a hard requirement
            logger.warning(
                "IFC summary metadata extraction failed ref=%s error=%s", file_path, exc
            )
            return IfcModelSummary()

    def attach_model(
        self,
        project_id: int,
        *,
        file_path: str,
        file_name: str = "",
        role: str = "context",
        is_primary: bool = False,
        project_code: str | None = None,
        originator: str | None = None,
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
            project_code: ISO 19650 project code for this model's container
                naming. Defaults to the owning project's own ``project_code``
                when not given, so every attached model carries one without
                the upload form asking for it again.
            originator: ISO 19650 originator code. Defaults to the owning
                project's own ``originator`` (itself defaulted from the
                organization's code at project-creation time) when not given.

        Returns:
            The inserted row.

        Raises:
            ValueError: if ``file_path`` is blank. A row with no reference
                names no model and would only fail later, at read time.
        """
        file_path = (file_path or "").strip()
        if not file_path:
            raise ValueError("file_path is required to attach an IFC model")

        self._adopt_legacy(project_id)
        if is_primary:
            self._demote_primary(project_id)

        if project_code is None or originator is None:
            parent = self._get_project(project_id) or {}
            if project_code is None:
                project_code = parent.get("project_code", "")
            if originator is None:
                originator = parent.get("originator", "")

        summary = self._extract_summary(file_path)

        row = {
            "project_id": project_id,
            "file_path": file_path,
            "file_name": (file_name or "").strip() or Path(file_path.replace("\\", "/")).name,
            "is_primary": bool(is_primary),
            "role": (role or "").strip() or "context",
            "uploaded_at": now_iso_utc(),
            "project_code": project_code or "",
            "originator": originator or "",
            "ifc_schema": summary.schema,
            "authoring_application": summary.authoring_application,
            "storey_count": summary.storey_count,
            "element_count": summary.element_count,
            "discipline_summary": summary.discipline_summary,
        }
        inserted = self._ifc_files.insert(row)
        self._invalidate(project_id)

        # The mirror, not a duplicate: every reader that predates this table --
        # the analysis runner, the IFC download, model lineage -- resolves a
        # project's model through projects.ifc_file_path, so the primary is only
        # really primary once that column names it too.
        if is_primary:
            self._mirror_attach(project_id, file_path)

        logger.info(
            "IFC file attached project_id=%d role=%s primary=%s ref=%s",
            project_id,
            row["role"],
            row["is_primary"],
            file_path,
        )
        return inserted if isinstance(inserted, dict) else row

    def set_primary(self, project_id: int, file_id: int) -> dict | None:
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
            (row for row in self._read_rows(project_id) if row.get("id") == file_id),
            None,
        )
        if target is None:
            logger.warning(
                "Primary IFC not set; no such file project_id=%d file_id=%s",
                project_id,
                file_id,
            )
            return None

        self._demote_primary(project_id)
        self._ifc_files.update(updates={"is_primary": True}, pk_values=file_id)
        self._invalidate(project_id)
        self._mirror_attach(project_id, target.get("file_path") or "")

        logger.info("Primary IFC set project_id=%d file_id=%s", project_id, file_id)
        return {**target, "is_primary": True}

    def refresh_metadata(self, project_id: int, file_id: int) -> dict | None:
        """Re-read schema/authoring-app/storey/element/discipline metadata and persist it.

        For a row attached before this feature existed (blank/zero summary),
        or one whose stored bytes were replaced by ``replace_model`` without a
        metadata refresh landing first. Does not touch the stored model bytes
        -- only the derived columns.

        Args:
            project_id: Project owning the row.
            file_id: ``project_ifc_files.id`` to refresh.

        Returns:
            The updated row, or ``None`` if the project holds no such row.
        """
        target = next(
            (row for row in self._read_rows(project_id) if row.get("id") == file_id),
            None,
        )
        if target is None:
            logger.warning(
                "IFC metadata not refreshed; no such file project_id=%d file_id=%s",
                project_id,
                file_id,
            )
            return None

        summary = self._extract_summary(target.get("file_path") or "")
        updates = {
            "ifc_schema": summary.schema,
            "authoring_application": summary.authoring_application,
            "storey_count": summary.storey_count,
            "element_count": summary.element_count,
            "discipline_summary": summary.discipline_summary,
        }
        self._ifc_files.update(updates=updates, pk_values=file_id)
        self._invalidate(project_id)

        logger.info("IFC metadata refreshed project_id=%d file_id=%s", project_id, file_id)
        return {**target, **updates}

    def update_model(
        self,
        project_id: int,
        file_id: int,
        *,
        file_name: str | None = None,
        role: str | None = None,
        project_code: str | None = None,
        originator: str | None = None,
        volume_system: str | None = None,
        level: str | None = None,
        type: str | None = None,
        number: str | None = None,
        suitability_code: str | None = None,
        revision_code: str | None = None,
    ) -> dict | None:
        """Update naming/ISO 19650 fields on an attached model.

        Every argument is optional and independently applied: a caller sends
        only the fields the user actually changed, and the rest of the row is
        left as it was. Does not touch the stored model bytes or the derived
        IFC summary columns -- use ``replace_model`` or ``refresh_metadata``
        for those.

        Args:
            project_id: Project owning the row.
            file_id: ``project_ifc_files.id`` to update.

        Returns:
            The updated row, or ``None`` if the project holds no such row.
        """
        target = next(
            (row for row in self._read_rows(project_id) if row.get("id") == file_id),
            None,
        )
        if target is None:
            logger.warning(
                "IFC file not updated; no such file project_id=%d file_id=%s",
                project_id,
                file_id,
            )
            return None

        updates: dict = {}
        if file_name is not None:
            updates["file_name"] = file_name.strip() or target.get("file_name") or ""
        if role is not None:
            updates["role"] = role.strip() or "context"
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
        if number is not None:
            updates["number"] = number.strip()
        if suitability_code is not None:
            updates["suitability_code"] = suitability_code.strip() or "S0"
        if revision_code is not None:
            updates["revision_code"] = revision_code.strip() or "P01.01"

        if not updates:
            return target

        self._ifc_files.update(updates=updates, pk_values=file_id)
        self._invalidate(project_id)

        logger.info("IFC file updated project_id=%d file_id=%s fields=%s", project_id, file_id, list(updates))
        return {**target, **updates}

    def replace_model(
        self,
        project_id: int,
        file_id: int,
        *,
        content: bytes,
        file_name: str,
    ) -> dict | None:
        """Replace the stored bytes of an attached model with a new upload.

        The old storage object is deleted only after the new one is written,
        so a failed upload never leaves the row pointing at nothing. The
        replacement is re-summarized immediately -- a stale schema/element
        count from the file it replaced would be a worse display than a
        moment of "Loading models..." during the swap. If the replaced file
        was primary, ``projects.ifc_file_path`` is repointed at the new
        object so every reader that predates this table still resolves it.

        Args:
            project_id: Project owning the row.
            file_id: ``project_ifc_files.id`` to replace.
            content: New IFC file bytes.
            file_name: Display name for the replacement.

        Returns:
            The updated row, or ``None`` if the project holds no such row.
        """
        target = next(
            (row for row in self._read_rows(project_id) if row.get("id") == file_id),
            None,
        )
        if target is None:
            logger.warning(
                "IFC file not replaced; no such file project_id=%d file_id=%s",
                project_id,
                file_id,
            )
            return None

        old_file_path = target.get("file_path") or ""
        new_file_path = self._storage.save_upload(file_name, content, "uploads/ifc")
        summary = self._extract_summary(new_file_path)

        updates = {
            "file_path": new_file_path,
            "file_name": (file_name or "").strip() or Path(new_file_path.replace("\\", "/")).name,
            "ifc_schema": summary.schema,
            "authoring_application": summary.authoring_application,
            "storey_count": summary.storey_count,
            "element_count": summary.element_count,
            "discipline_summary": summary.discipline_summary,
        }
        self._ifc_files.update(updates=updates, pk_values=file_id)
        self._invalidate(project_id)

        if target.get("is_primary"):
            self._mirror_attach(project_id, new_file_path)

        if old_file_path and old_file_path != new_file_path:
            try:
                self._storage.delete(old_file_path)
            except Exception:  # noqa: BLE001 - the row already points at the new file
                logger.warning(
                    "Old IFC object not deleted after replace project_id=%d file_id=%s ref=%s",
                    project_id,
                    file_id,
                    old_file_path,
                    exc_info=True,
                )

        logger.info("IFC file replaced project_id=%d file_id=%s ref=%s", project_id, file_id, new_file_path)
        return {**target, **updates}

    def delete_model(self, project_id: int, file_id: int) -> dict | None:
        """Detach and delete one of a project's models.

        Deleting the primary promotes the next remaining model (by
        ``list_models`` order) so the project always has a model to analyse
        as long as it has any left. Deleting a project's last model is
        allowed -- an existing project with no model is a state this service
        already supports (``list_models`` returns ``[]`` for one), so
        ``projects.ifc_file_path`` is cleared to match rather than left
        naming bytes that no longer exist.

        Args:
            project_id: Project owning the row.
            file_id: ``project_ifc_files.id`` to remove.

        Returns:
            The deleted row, or ``None`` if the project holds no such row --
            including ``file_id`` belonging to another project.
        """
        rows = self._read_rows(project_id)
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
        self._invalidate(project_id)

        if target.get("is_primary"):
            remaining = [row for row in rows if row.get("id") != file_id]
            if remaining:
                promoted = remaining[0]
                self._ifc_files.update(updates={"is_primary": True}, pk_values=promoted["id"])
                self._invalidate(project_id)
                self._mirror_attach(project_id, promoted.get("file_path") or "")
            else:
                self._mirror_attach(project_id, "")

        logger.info(
            "IFC file deleted project_id=%d file_id=%s was_primary=%s",
            project_id,
            file_id,
            target.get("is_primary"),
        )
        return target

    def delete_all_for_project(self, project_id: int) -> None:
        """Delete storage for every model a project owns, ahead of deleting the project.

        Only the primary model's bytes used to be cleaned up when a project
        was deleted (via ``projects.ifc_file_path``); every other attached
        model's storage object was orphaned once the row cascade-deleted with
        the project. This deletes storage for all of them; the rows
        themselves are removed by the ``project_ifc_files.project_id``
        cascade once the project row is deleted.
        """
        for row in self._read_rows(project_id):
            file_path = row.get("file_path") or ""
            if file_path:
                try:
                    self._storage.delete(file_path)
                except Exception:  # noqa: BLE001 - best-effort cleanup, project deletion proceeds
                    logger.warning(
                        "Model storage not deleted project_id=%d ref=%s",
                        project_id,
                        file_path,
                        exc_info=True,
                    )
        self._invalidate(project_id)

    def resolve_primary_path(self, project_id: int) -> Path | None:
        """Materialise the one model an analysis of a single model reads.

        Resolves through ``get_primary`` rather than through
        ``projects.ifc_file_path`` directly. The two agree -- every writer here
        mirrors the primary onto that column -- but reading the child table
        makes "the corrosion engines assess the primary model" a fact about the
        code rather than an invariant a reader has to know about.
        """
        primary = self.get_primary(project_id)
        if primary is None:
            return None
        return self._storage.materialize_local_path(primary.get("file_path") or "")

    def resolve_all_paths(
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
            list in ``list_models`` order.
        """
        resolved: list[tuple[dict, Path]] = []
        missing: list[dict] = []
        for row in self.list_models(project_id):
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

    def resolve_analysis(self, project_id: int) -> tuple[Path | None, dict | None]:
        """Return the persisted improved IFC for the current source, when available."""
        source_path = self.resolve_primary_path(project_id)
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
