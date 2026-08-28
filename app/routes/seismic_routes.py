"""Seismic (Blue Halo) analysis form and async run endpoint.

    GET  /analysis/seismic/{project_id}   renders the run form
    POST /analysis/seismic/run            dispatches the run, redirects to the dashboard

The same async shape as :mod:`app.routes.piping_routes`: the run is handed to a
daemon thread rather than awaited, so the redirect lands while Blue Halo is
still working. Everything that can be rejected is checked *before* the thread
starts, because once the run is detached there is nowhere to return an error to.

WHAT THE WORKFLOW DASHBOARD SHOWS AFTER A SEISMIC RUN

    Not this run. :func:`app.services.analysis_runner.run_analysis` deliberately
    leaves the seismic path untracked -- ``tracking()`` resets a project's
    tracker, so binding one here would wipe the progress of a corrosion run for
    the same project -- and ``workflow_dashboard`` renders
    ``pipeline_tracker.ENGINE_SPECS``, which is the five corrosion engines
    whatever slug it is given.

    So the dashboard this redirects to reports corrosion engines under a SEISMIC
    heading, and a seismic run never advances them. The redirect target is what
    the page was specified to use and is left as-is; making it truthful means
    instrumenting seismic in the tracker and teaching the dashboard which engines
    belong to a slug, which is a change to shared code rather than to this page.
    Until then the findings are read from the seismic analysis page itself.
"""

from __future__ import annotations

import threading
from urllib.parse import quote

from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.responses import Response as StarletteResponse

from app.components.seismic_analysis_ui import seismic_analysis_page
from app.logging_config import get_logger
from app.services.analysis_runner import run_analysis
from app.services.projects_service import ProjectsService

logger = get_logger(__name__)

_projects_service = ProjectsService()

#: Slug this page runs, and the one the dashboard's "Back to analysis" link
#: resolves against.
ANALYSIS_SLUG = "seismic"


def _clearance_mm(form) -> float | None:
    """Return the requested clearance in millimetres, or ``None`` when unusable.

    Parsed rather than trusted: the value arrives from the client, and a blank
    or malformed box means "use the config's own clearance" -- which is what
    happens anyway, since the engine reads the config. A negative clearance is
    rejected the same way, as no envelope can be smaller than nothing.

    Args:
        form: The parsed request form.

    Returns:
        The parsed millimetre value, or ``None`` when absent or invalid.
    """
    raw = (form.get("clearance_mm") or "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value >= 0 else None


def _run_seismic_background(project_id: int, clearance_mm: float | None, codes: str) -> None:
    """Run the seismic analysis off-request so the caller is not held open.

    Runs in a daemon thread. Nothing awaits this, so a failure has nowhere to be
    returned to: it is logged, and the caller has already been redirected by the
    time anything here can go wrong.

    ``use_cache=False`` because the point of pressing the button is to run the
    check again rather than to be handed the previous answer.

    Args:
        project_id: Project whose model to analyse.
        clearance_mm: Clearance the form asked for, or ``None`` to leave the
            config's own value alone. Logged with the run for traceability;
            ``run_analysis`` exposes no override, so this does not resize the
            envelope -- see the note in
            :mod:`app.components.seismic_analysis_ui`.
        codes: Standards reference recorded with the run.
    """
    try:
        result = run_analysis(ANALYSIS_SLUG, project_id, use_cache=False)
    except Exception:
        logger.exception("Background seismic analysis crashed project_id=%d", project_id)
        return

    error = result.get("compliance_error")
    if error:
        logger.warning(
            "Background seismic analysis failed project_id=%d error=%s", project_id, error
        )
        return

    logger.info(
        "Background seismic analysis complete project_id=%d clearance_mm=%s codes=%s issues=%d",
        project_id,
        "config" if clearance_mm is None else f"{clearance_mm:g}",
        codes or "config",
        len(result.get("audit_issues", [])),
    )


def setup_routes(rt):
    """Register the Seismic (Blue Halo) form and run endpoints."""

    # GET only: a bare @rt() also binds POST on the same path, which is not
    # where the run is posted.
    @rt("/analysis/seismic/{project_id}", methods=["GET"])
    def seismic_analysis(project_id: int):
        """Render the run form for one project."""
        logger.info("Seismic analysis form requested project_id=%d", project_id)
        return seismic_analysis_page(project_id)

    @rt("/analysis/seismic/run", methods=["POST"])
    async def seismic_analysis_run(req: Request):
        """Start the run in the background and send the user to the dashboard.

        The form posts normally, so a 303 is the answer. An HTMX caller follows
        a 303 itself and would swap a whole page into the form, so it gets
        ``HX-Redirect`` instead -- the same split the piping endpoint makes.
        """
        form = await req.form()

        project_id_raw = (form.get("project_id") or "").strip()
        if not project_id_raw:
            logger.warning("Rejected seismic analysis request without a project ID")
            return _reject(req, "Please select a project.")
        try:
            project_id = int(project_id_raw)
        except ValueError:
            logger.warning(
                "Rejected seismic analysis request with invalid project ID=%r", project_id_raw
            )
            return _reject(req, "Invalid project selection.")

        if _projects_service.get_project(project_id) is None:
            logger.warning(
                "Rejected seismic analysis request for missing project_id=%d", project_id
            )
            return _reject(req, "That project no longer exists.")

        clearance = _clearance_mm(form)
        codes = (form.get("seismic_codes") or "").strip()
        logger.info(
            "Dispatching background seismic analysis project_id=%d clearance_mm=%s codes=%s "
            "openings=%s spaces=%s type_defs=%s",
            project_id,
            "config" if clearance is None else f"{clearance:g}",
            codes or "config",
            bool(form.get("include_openings")),
            bool(form.get("include_spaces")),
            bool(form.get("include_type_definitions")),
        )

        threading.Thread(
            target=_run_seismic_background,
            args=(project_id, clearance, codes),
            name=f"bimguard-seismic-{project_id}",
            daemon=True,
        ).start()

        # ?status=running tells the dashboard a run it did not start is already
        # in flight, so it polls instead of taking one read and going idle.
        target = f"/workflow/{project_id}?status=running"
        if req.headers.get("hx-request"):
            return StarletteResponse(status_code=204, headers={"HX-Redirect": target})
        return RedirectResponse(url=target, status_code=303)


def _reject(req: Request, message: str):
    """Send a rejected submission back to a page that exists, with the reason.

    A redirect rather than a rendered error: the POST has no page of its own,
    and re-rendering the form here would leave the browser on ``/run`` with a
    URL that 405s on refresh.
    """
    if req.headers.get("hx-request"):
        return StarletteResponse(status_code=400, content=message)
    return RedirectResponse(url=f"/projects?error={quote(message)}", status_code=303)
