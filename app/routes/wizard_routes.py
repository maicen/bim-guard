"""Routes for the five-step project setup wizard.

    GET  /wizard          renders the wizard at step 1
    POST /wizard          navigation: next / prev / reset / submit
    POST /wizard/upload   stores a dropped IFC, returns its reference

WHERE THE DATABASE WORK LIVES

    Here, not in :mod:`app.components.project_setup_wizard`. That component
    renders, validates and emits a dict; it imports no persistence at all. The
    three things it cannot do for itself are done in this module and handed to
    it: the document rows for step 3, the storing of the model dropped at step
    2, and turning the emitted dict into a project row.

    The component takes the last of those as an ``on_submit`` callback, so the
    dependency points this way round -- the wizard does not know a database
    exists, and this module does not know how a step is drawn.

WHY THE UPLOAD HAPPENS AT STEP 2 RATHER THAN AT SUBMIT

    Every other answer travels between steps as a hidden input. A file cannot:
    an ``<input type=file>`` value is not settable from script, so a model
    chosen at step 2 would be gone by step 3. It is stored on drop instead --
    with no project id, which ``FileUploadService.upload`` allows, since no
    project exists until step 5 -- and only the returned reference rides on.

    That leaves an object in storage if the wizard is abandoned. Preferable to
    what this flow did before, which was to silently drop the file at submit so
    that a project was created with no model attached at all.
"""

from __future__ import annotations

from fasthtml.common import Div, Script, Title
from starlette.datastructures import UploadFile
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.components.layout import DashboardLayout
from app.components.project_setup_wizard import (
    handle_wizard_get,
    handle_wizard_post,
)
from app.constants import ANALYSIS_ROUTES, DEFAULT_ANALYSIS_TYPE
from app.logging_config import get_logger
from app.modules.phase_6.phase_6a_upload import FileUploadService
from app.services.documents_service import DocumentService
from app.services.projects_service import ProjectsService

logger = get_logger(__name__)

_documents_service = DocumentService()
_projects_service = ProjectsService()
_upload_service = FileUploadService()


def _documents() -> list[dict]:
    """Return the rows step 3 offers, or an empty list if they cannot be read.

    A documents table that is briefly unavailable should cost that one step its
    options, not the whole wizard.
    """
    try:
        return list(_documents_service.list_documents())
    except Exception:
        logger.exception("Wizard could not list documents")
        return []


def analysis_route_for(analysis_types: list[str]) -> str:
    """Return the slug to land on after creation.

    The first selected analysis wins, because the wizard can now select several
    and only one page can be navigated to. An unrecognised or empty selection
    falls back to the default type's slug rather than a 404.
    """
    for analysis_type in analysis_types:
        slug = ANALYSIS_ROUTES.get(analysis_type)
        if slug:
            return slug
    return ANALYSIS_ROUTES[DEFAULT_ANALYSIS_TYPE]


def create_project_from_wizard(emitted: dict) -> int:
    """Create the project the wizard collected and return its id.

    The ``on_submit`` half of the component's contract. Maps the wizard's own
    key names onto ``ProjectsService.create_project``'s, attaches the model
    staged at step 2, and links the chosen standards.

    Args:
        emitted: The dict from
            :func:`app.components.project_setup_wizard.emit_form_data`.
            Already validated -- this creates, it does not re-check.

    Returns:
        The new project's id.
    """
    project = _projects_service.create_project(
        name=emitted["project_name"],
        description=emitted["description"],
        status=emitted["settings"].get("status") or "Draft",
        country=emitted["location"],
        analysis_types=emitted["analysis_types"] or [DEFAULT_ANALYSIS_TYPE],
    )
    project_id = int(project["id"])

    # Step 2 stored the object with no project id, because none existed yet.
    # Pointing the row at it here is what makes the model reachable.
    reference = emitted.get("ifc_file_reference")
    if reference:
        _projects_service.attach_ifc(project_id, reference)

    standards = emitted.get("standards_codes") or []
    if standards:
        try:
            _projects_service.set_standards_for_project(project_id, standards)
        except Exception:
            # The project exists and is usable; losing the standards link is
            # worth a log rather than an error page over a created row.
            logger.exception("Wizard could not link standards project_id=%d", project_id)

    logger.info(
        "Wizard created project_id=%d name=%r analyses=%s ifc=%s standards=%d",
        project_id,
        emitted["project_name"],
        ",".join(emitted["analysis_types"]),
        "attached" if reference else "none",
        len(standards),
    )
    return project_id


def setup_routes(rt):
    """Register the wizard's page, navigation and upload endpoints."""

    @rt("/wizard", methods=["GET"])
    def wizard_get():
        """Render the wizard at step 1."""
        logger.info("Wizard opened")
        return Title("New project - BIM Guard"), DashboardLayout(
            handle_wizard_get(documents=_documents())
        )

    @rt("/wizard", methods=["POST"])
    async def wizard_post(req: Request):
        """Handle navigation, and create the project on submit.

        Returns the component alone rather than the whole page: the form posts
        with HTMX and swaps itself, so re-sending the chrome would nest a
        second sidebar inside the first.
        """
        form = await req.form()

        def on_submit(emitted: dict):
            """Create the project, then send the browser to its analysis page."""
            try:
                project_id = create_project_from_wizard(emitted)
            except Exception:
                logger.exception("Wizard project creation failed")
                # Re-render rather than 500: the answers are all still in the
                # POST, so the user keeps them and can retry.
                return Div(
                    Script(
                        "alert('The project could not be created. "
                        "Your answers are still here — try again.');"
                    ),
                    id="wizard",
                )
            slug = analysis_route_for(emitted["analysis_types"])
            return Div(
                Script(
                    f"window.location.href = '/analyze/{slug}?project_id={project_id}'"
                ),
                id="wizard",
            )

        return await handle_wizard_post(form, documents=_documents(), on_submit=on_submit)

    @rt("/wizard/upload", methods=["POST"])
    async def wizard_upload(req: Request):
        """Store a dropped IFC and answer with the reference to carry forward.

        JSON rather than a fragment: the drop zone is driven by the wizard's
        own script, which writes the reference into three hidden inputs.
        Handing it markup would decide that for it.
        """
        form = await req.form()
        upload = form.get("ifc_file")
        if not isinstance(upload, UploadFile) or not upload.filename:
            return JSONResponse({"ok": False, "error": "Choose an IFC file to upload."})

        content = await upload.read()
        response = _upload_service.upload(upload.filename, content, kind="ifc")
        if not response.success:
            logger.warning(
                "Wizard upload refused filename=%s reason=%s",
                upload.filename,
                response.error,
            )
            return JSONResponse({"ok": False, "error": response.error or "The upload failed."})

        logger.info(
            "Wizard staged a model filename=%s bytes=%d",
            response.ref.filename,
            response.ref.size_bytes,
        )
        return JSONResponse(
            {
                "ok": True,
                "storage_ref": response.ref.storage_ref,
                "filename": response.ref.filename,
                "size_bytes": response.ref.size_bytes,
            }
        )
