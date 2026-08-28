"""Piping (Corrosion) analysis form and async run endpoint.

    GET  /analysis/piping/{project_id}   renders the run form
    POST /analysis/piping/run            dispatches the run, redirects to the dashboard

The same async shape as the MEP endpoint in :mod:`app.routes.analyze`: the run
is handed to a daemon thread rather than awaited, so the redirect lands while
the engines are still working and ``/workflow/{project_id}`` has progress left
to show. Everything that can be rejected is checked *before* the thread starts,
because once the run is detached there is nowhere to return an error to.

This is a second entry point to the corrosion pipeline, not a second pipeline.
``/analyze/corrosion`` (the wizard's landing page) and this page both end at
:func:`app.services.analysis_runner.run_analysis`, so they cannot disagree
about what the model contains.
"""

from __future__ import annotations

import threading
from urllib.parse import quote

from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.responses import Response as StarletteResponse

from app.components.piping_analysis_ui import engine_options, piping_analysis_page
from app.logging_config import get_logger
from app.services.analysis_runner import run_analysis
from app.services.projects_service import ProjectsService

logger = get_logger(__name__)

_projects_service = ProjectsService()

#: Slug the dashboard's own run button posts under, so the "Back to analysis"
#: link on ``/workflow/{project_id}`` resolves to a page that exists.
ANALYSIS_SLUG = "corrosion"


def _selected_engines(form) -> list[str]:
    """Return the engine codes the form asked for, in queue order.

    Unknown codes are dropped rather than trusted: the value arrives from the
    client, and the only codes that mean anything are the ones the selector
    offers. Ordering comes from :func:`engine_options` so the log reads the same
    way regardless of how the browser serialised the checkboxes.

    Args:
        form: The parsed request form.

    Returns:
        The recognised codes. Empty when nothing was ticked, which the caller
        treats as "all default engines".
    """
    requested = {value for value in form.getlist("engines") if value}
    return [engine.code for engine in engine_options() if engine.code in requested]


def _run_piping_background(project_id: int, engines: list[str]) -> None:
    """Run the corrosion analysis off-request so the dashboard can watch it.

    Runs in a daemon thread. :mod:`app.services.pipeline_tracker` binds its
    ContextVar inside whichever thread calls it and keys the shared tracker
    store by ``project_id``, so the progress this populates is exactly what
    ``GET /api/workflow/{project_id}`` reads back -- no context needs carrying
    across the thread boundary.

    Nothing awaits this, so a failure has nowhere to be returned to. It is
    logged and the dashboard simply stops advancing; the caller has already been
    redirected by the time anything here can go wrong.

    ``use_cache=False`` because the point of pressing the button is to see the
    run happen: a cache hit returns without touching the tracker, leaving the
    dashboard at ``pending`` for a run that never started.

    Args:
        project_id: Project whose model to analyse.
        engines: Codes the form asked for. Logged with the run for traceability.
            ``run_analysis`` takes no engine subset, so this does not narrow
            what computes -- see the note in
            :mod:`app.components.piping_analysis_ui`.
    """
    try:
        result = run_analysis(ANALYSIS_SLUG, project_id, use_cache=False)
    except Exception:
        logger.exception("Background piping analysis crashed project_id=%d", project_id)
        return

    error = result.get("compliance_error")
    if error:
        logger.warning(
            "Background piping analysis failed project_id=%d error=%s", project_id, error
        )
        return

    logger.info(
        "Background piping analysis complete project_id=%d engines=%s issues=%d",
        project_id,
        ",".join(engines) or "default",
        len(result.get("audit_issues", [])),
    )


def setup_routes(rt):
    """Register the Piping (Corrosion) form and run endpoints."""

    # GET only: a bare @rt() also binds POST on the same path, which is not
    # where the run is posted and would answer 405-shaped surprises instead.
    @rt("/analysis/piping/{project_id}", methods=["GET"])
    def piping_analysis(project_id: int):
        """Render the run form for one project."""
        logger.info("Piping analysis form requested project_id=%d", project_id)
        return piping_analysis_page(project_id)

    @rt("/analysis/piping/run", methods=["POST"])
    async def piping_analysis_run(req: Request):
        """Start the run in the background and send the user to the dashboard.

        The form posts normally, so a 303 is the answer. An HTMX caller follows
        a 303 itself and would swap the dashboard's markup into the page rather
        than navigating, so it gets ``HX-Redirect`` instead -- the same split
        ``/analysis/results`` makes.
        """
        form = await req.form()

        project_id_raw = (form.get("project_id") or "").strip()
        if not project_id_raw:
            logger.warning("Rejected piping analysis request without a project ID")
            return _reject(req, "Please select a project.")
        try:
            project_id = int(project_id_raw)
        except ValueError:
            logger.warning(
                "Rejected piping analysis request with invalid project ID=%r", project_id_raw
            )
            return _reject(req, "Invalid project selection.")

        if _projects_service.get_project(project_id) is None:
            logger.warning("Rejected piping analysis request for missing project_id=%d", project_id)
            return _reject(req, "That project no longer exists.")

        engines = _selected_engines(form)
        logger.info(
            "Dispatching background piping analysis project_id=%d engines=%s "
            "rule_folder=%s documents=%d openings=%s spaces=%s type_defs=%s",
            project_id,
            ",".join(engines) or "default",
            (form.get("rule_folder") or "").strip() or "all",
            len(form.getlist("document_ids")),
            bool(form.get("include_openings")),
            bool(form.get("include_spaces")),
            bool(form.get("include_type_definitions")),
        )

        threading.Thread(
            target=_run_piping_background,
            args=(project_id, engines),
            name=f"bimguard-piping-{project_id}",
            daemon=True,
        ).start()

        # ?status=running tells the dashboard a run it did not start is already
        # in flight, so it polls instead of taking one read and going idle.
        target = f"/workflow/{project_id}?status=running"
        if req.headers.get("hx-request"):
            return StarletteResponse(status_code=204, headers={"HX-Redirect": target})
        return RedirectResponse(url=target, status_code=303)


def _reject(req: Request, message: str):
    """Send a rejected submission back to the form with the reason.

    A redirect rather than a rendered error: the POST has no page of its own,
    and re-rendering the form here would leave the browser on ``/run`` with a
    URL that 405s on refresh.
    """
    if req.headers.get("hx-request"):
        return StarletteResponse(status_code=400, content=message)
    return RedirectResponse(url=f"/projects?error={quote(message)}", status_code=303)
