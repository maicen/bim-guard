"""Multi-model IFC viewer routes.

Two routes, one pair:

``GET /analyze/viewer``
    Lists every IFC recorded against a project in ``uploaded_files`` and
    renders them into a single federated viewer.

``GET /uploads/{file_id}/ifc``
    Serves the raw bytes of one of those files, which is what the browser
    fetches for each model.

WHY A SEPARATE DOWNLOAD ROUTE

    ``/projects/{id}/ifc`` serves the *one* model in ``projects.ifc_file_path``
    and has no way to name any other. Federating N files needs a per-file
    address, and ``uploaded_files.id`` is the only stable one available.

ON AUTHORIZATION

    This application has no session, login, or user table -- nothing in
    ``app/`` reads ``request.session`` and no middleware installs one. So the
    check here is scoping, not authentication: the caller must state which
    project it believes the file belongs to, and a file is refused when it
    belongs to a different project. That stops ``/uploads/{id}/ifc`` from
    becoming an unqualified enumeration handle over every upload in the
    bucket, which is what it would be with no check at all. It is NOT a
    substitute for authentication, and both routes stay as public as the rest
    of the FastHTML surface until one exists.
"""

from __future__ import annotations

from fasthtml.common import FileResponse, Response, Title
from monsterui.all import Container

from app.components.layout import DashboardLayout
from app.components.ui import NotFoundBlock
from app.components.viewer_ui import ViewerModel, multi_model_viewer
from app.logging_config import get_logger
from app.modules.phase_6.phase_6a_upload import FileUploadService
from app.services.object_storage import ObjectStorage
from app.services.projects_service import ProjectsService

logger = get_logger(__name__)

_projects_service = ProjectsService()
_upload_service = FileUploadService()
_object_storage = ObjectStorage()

#: Only IFC uploads are viewable; the same table also holds documents and
#: standards, which have no geometry to render.
VIEWABLE_KIND = "ifc"


def _download_url(file_id: int, project_id: int) -> str:
    """Return the per-file download address the browser fetches."""
    return f"/uploads/{file_id}/ifc?project_id={project_id}"


def _to_viewer_models(rows: list[dict], project_id: int) -> list[ViewerModel]:
    """Convert ``uploaded_files`` rows into viewer models.

    Rows with no ``id`` or no ``storage_ref`` are dropped: neither can produce
    a working download URL, and a broken entry in the list is worse than an
    absent one.
    """
    models = []
    for row in rows:
        file_id = row.get("id")
        if file_id is None or not row.get("storage_ref"):
            logger.warning("Skipping unusable upload row project_id=%s row=%s", project_id, row)
            continue
        file_id = int(file_id)
        models.append(
            ViewerModel(
                file_id=file_id,
                filename=str(row.get("filename") or f"model-{file_id}.ifc"),
                url=_download_url(file_id, project_id),
                size_bytes=int(row.get("size_bytes") or 0),
                created_at=str(row.get("created_at") or ""),
            )
        )
    return models


def setup_routes(rt):
    """Register the multi-model viewer page and its per-file download route."""

    @rt("/analyze/viewer")
    def analyze_viewer(project_id: int | None = None):
        """Render every IFC uploaded to ``project_id`` in one viewer."""
        if project_id is None:
            return Title("Model Viewer - BIM Guard"), DashboardLayout(
                Container(NotFoundBlock("Project", "/projects", "Back to Projects"))
            )

        project = _projects_service.get_project(project_id)
        if project is None:
            return Title("Not Found - BIM Guard"), DashboardLayout(
                Container(NotFoundBlock("Project", "/projects", "Back to Projects"))
            )

        rows = _upload_service.list_for_project(project_id, kind=VIEWABLE_KIND)
        models = _to_viewer_models(rows, project_id)
        logger.info(
            "Multi-model viewer project_id=%d rows=%d models=%d",
            project_id,
            len(rows),
            len(models),
        )
        return Title("Model Viewer - BIM Guard"), DashboardLayout(
            Container(
                multi_model_viewer(models, project_name=str(project.get("name") or "")),
                cls="space-y-4",
            )
        )

    @rt("/uploads/{file_id}/ifc")
    def upload_ifc_file(file_id: int, project_id: int | None = None):
        """Serve the raw IFC bytes of one recorded upload.

        Args:
            file_id: ``uploaded_files.id``.
            project_id: Project the caller believes owns the file. Required --
                see the module docstring on why this is scoping rather than
                authentication.

        Returns:
            A ``FileResponse`` carrying the IFC, or 400/403/404 explaining
            which check refused it.
        """
        if project_id is None:
            return Response("A project_id is required.", status_code=400)

        row = _upload_service.get_recorded(file_id)
        if row is None:
            logger.info("Upload not found file_id=%d", file_id)
            return Response("File not found.", status_code=404)

        row_project_id = row.get("project_id")
        if row_project_id is None or int(row_project_id) != project_id:
            # Deliberately 403 and not 404: the row exists, and the caller
            # named the wrong project for it.
            logger.warning(
                "Upload project mismatch file_id=%d asked=%d owns=%s",
                file_id,
                project_id,
                row_project_id,
            )
            return Response("This file belongs to a different project.", status_code=403)

        if row.get("kind") != VIEWABLE_KIND:
            return Response("This file is not an IFC model.", status_code=404)

        local_path = _object_storage.materialize_local_path(str(row.get("storage_ref") or ""))
        if local_path is None:
            logger.warning("Upload object unavailable file_id=%d ref=%s", file_id, row.get("storage_ref"))
            return Response("The model could not be retrieved from storage.", status_code=404)

        return FileResponse(
            local_path,
            media_type="application/octet-stream",
            filename=str(row.get("filename") or local_path.name),
        )
