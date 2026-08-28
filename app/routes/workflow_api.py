"""Real-time pipeline status endpoint.

    GET /api/workflow/{project_id}

Returns every engine's current stage and metrics as JSON, for a frontend that polls
while an analysis runs. A JSON API rather than an HTMX partial: the caller is a
progress display that decides for itself how to render a stage, and handing it
markup would fix that decision here.

WHAT THE STATUSES MEAN

    ``pending``
        No run has reported anything for this engine. Also what an engine that
        exists but is switched off reports -- MM-001 and XM-001 sit behind the
        Path B feature flags.
    ``running``
        A run is in progress; ``current_stage`` and ``metrics`` are live.
    ``complete`` / ``failed``
        The run finished. ``failed`` carries an ``error`` string.
    ``not_implemented``
        Declared, with no engine behind it in this build.

A project nobody has analysed is not an error: it answers 200 with every engine
at its declared status, because "nothing has started" is the truthful answer to
"how far has this got". Only a malformed project id is a 400.

STATUS IS PER PROCESS, AND ONLY EVER A REPORT

    Progress lives in the worker that ran the analysis (see
    :mod:`app.services.pipeline_tracker`). Under multiple uvicorn workers a poll
    can land elsewhere and see ``pending`` for a run that is genuinely in
    flight. That is a reporting gap and never a correctness one -- nothing reads
    this endpoint back into an analysis, and the findings themselves come from
    :func:`app.services.analysis_runner.run_analysis`.
"""

from __future__ import annotations

from starlette.responses import JSONResponse

from app.logging_config import get_logger
from app.services.pipeline_tracker import snapshot

logger = get_logger(__name__)


def workflow_status(project_id: int) -> JSONResponse:
    """Build the workflow payload for one project.

    Args:
        project_id: Project to report on.

    Returns:
        200 with the status payload, or 400 with an ``error`` key when the id
        is not a usable project id.
    """
    if project_id <= 0:
        return JSONResponse(
            {"error": "A positive project id is required."},
            status_code=400,
        )

    payload = snapshot(project_id)
    logger.debug(
        "Workflow status served project_id=%d statuses=%s",
        project_id,
        {code: engine.get("status") for code, engine in payload["engines"].items()},
    )
    # No-store rather than a short max-age: this describes a run in flight, and
    # a cached copy would report a stage the pipeline has already left.
    return JSONResponse(payload, headers={"Cache-Control": "no-store"})


def setup_routes(rt):
    """Register the workflow status endpoint."""

    @rt("/api/workflow/{project_id}", methods=["GET"])
    def api_workflow(project_id: int):
        """GET /api/workflow/{project_id} — live engine stages and metrics."""
        return workflow_status(project_id)
