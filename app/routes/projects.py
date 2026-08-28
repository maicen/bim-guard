"""Project management routes for creating and maintaining IFC projects."""

import hmac
import os

from fasthtml.common import (
    FileResponse,
    Response,
    Title,
    UploadFile,
)
from monsterui.all import Container

from app.components.layout import DashboardLayout
from app.components.projects_ui import project_enhancements_page, project_form, projects_page
from app.constants import DEFAULT_ANALYSIS_TYPE, DEFAULT_COUNTRY
from app.services.pipeline_services import execute_model_enhancement
from app.services.model_lineage import SupabaseModelLineageRepository
from app.services.object_storage import ObjectStorage
from app.services.projects_service import ProjectsService
from app.utils import redirect_see_other

_projects_service = ProjectsService()
_lineage_repository = SupabaseModelLineageRepository()
_object_storage = ObjectStorage()


def _is_enhancement_authorized(token: str) -> bool:
    """Authorize explicit model mutation with a deployment-managed secret."""
    expected = os.getenv("BIM_GUARD_ENHANCEMENT_TOKEN", "").strip()
    supplied = (token or "").strip()
    return bool(expected and supplied and hmac.compare_digest(supplied, expected))


def setup_routes(rt):
    """Register project CRUD and IFC download routes."""

    @rt("/projects")
    def projects_list():
        return Title("Projects - BIM Guard"), projects_page(_projects_service.list_projects())

    @rt("/projects/new")
    def projects_new():
        return Title("New Project - BIM Guard"), DashboardLayout(
            Container(project_form("Create Project", "/projects/create", include_ifc=True))
        )

    @rt("/projects/create", methods=["POST"])
    async def projects_create(
        name: str,
        description: str = "",
        status: str = "Draft",
        ifc_file: UploadFile = None,
        country: str = DEFAULT_COUNTRY,
        analysis_type: str = DEFAULT_ANALYSIS_TYPE,
    ):
        """Create a project from the simple form.

        country and analysis_type default to the same values migration_001 gave
        existing rows, so this legacy form keeps working while the five-step
        wizard is the route that collects them explicitly.
        """
        ifc_file_path, ifc_md5_hash = await _projects_service.prepare_ifc_upload(ifc_file)
        try:
            _projects_service.create_project(
                name=name,
                description=description,
                status=status,
                ifc_file_path=ifc_file_path,
                ifc_md5_hash=ifc_md5_hash,
                country=country,
                analysis_type=analysis_type,
            )
        except ValueError as exc:
            # Previously a blank name was accepted and created an unusable row.
            return Response(str(exc), status_code=400)
        return redirect_see_other("/projects")

    @rt("/projects/{project_id}/edit")
    def projects_edit(project_id: int):
        project = _projects_service.get_project(project_id)
        return Title("Edit Project - BIM Guard"), DashboardLayout(
            Container(project_form("Edit Project", f"/projects/{project_id}/update", project))
        )

    @rt("/projects/{project_id}/update", methods=["POST"])
    def projects_update(project_id: int, name: str, description: str = "", status: str = "Draft"):
        _projects_service.update_project(project_id, name, description, status)
        return redirect_see_other("/projects")

    @rt("/projects/{project_id}/delete", methods=["POST"])
    def projects_delete(project_id: int):
        _projects_service.delete_project(project_id)
        return redirect_see_other("/projects")

    @rt("/projects/{project_id}/ifc")
    def project_ifc_file(project_id: int):
        file_path = _projects_service.resolve_ifc_file(project_id)
        if file_path is None:
            return redirect_see_other("/projects")

        return FileResponse(
            file_path, media_type="application/octet-stream", filename=file_path.name
        )

    @rt("/projects/{project_id}/enhancements")
    def project_enhancements(project_id: int, message: str = "", level: str = "success"):
        project = _projects_service.get_project(project_id)
        if project is None:
            return redirect_see_other("/projects")
        return Title("Quality Improvements - BIM Guard"), project_enhancements_page(
            project,
            _lineage_repository.list_for_project(project_id),
            message=message or None,
            level=level,
        )

    @rt("/projects/{project_id}/enhance", methods=["POST"])
    def project_enhance(project_id: int, enhancement_token: str = ""):
        if not _is_enhancement_authorized(enhancement_token):
            return redirect_see_other(
                f"/projects/{project_id}/enhancements?message=Enhancement+authorization+failed&level=warning"
            )

        project = _projects_service.get_project(project_id)
        if project is None or not project.get("ifc_file_path"):
            return redirect_see_other(
                f"/projects/{project_id}/enhancements?message=Project+IFC+source+not+found&level=warning"
            )

        try:
            result = execute_model_enhancement(
                project_id=project_id,
                source_reference=project["ifc_file_path"],
            )
        except Exception:
            return redirect_see_other(
                f"/projects/{project_id}/enhancements?message=Enhancement+failed&level=warning"
            )
        if result.get("reused"):
            message = f"Reused persisted quality-improved version {result['version']}"
        else:
            message = f"Quality improvements persisted as version {result['version']}"
        return redirect_see_other(
            f"/projects/{project_id}/enhancements?message={message.replace(' ', '+')}"
        )

    @rt("/projects/{project_id}/enhancements/{lineage_id}/download")
    def project_enhancement_download(project_id: int, lineage_id: int):
        lineage = _lineage_repository.get(lineage_id)
        if lineage is None or int(lineage.get("project_id") or 0) != project_id:
            return redirect_see_other(f"/projects/{project_id}/enhancements")

        local_path = _object_storage.materialize_local_path(
            str(lineage.get("output_reference") or "")
        )
        if local_path is None:
            return redirect_see_other(
                f"/projects/{project_id}/enhancements?message=Generated+artifact+not+found&level=warning"
            )
        return FileResponse(
            local_path,
            media_type="application/octet-stream",
            filename=local_path.name,
        )
