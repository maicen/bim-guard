"""File download endpoints for completed analyses.

    GET /download/csv/{project_id}
    GET /download/json/{project_id}
    GET /download/bcf/{project_id}

Each returns a real file with a ``Content-Disposition`` attachment header, so a
browser saves it rather than rendering it. Plain GETs, not HTMX posts: HTMX
cannot swap a binary download into a page, and a bare link is what a download
button should be.

The analysis slug is a query parameter (``?slug=seismic``) rather than another
path segment. It defaults to ``corrosion``, so the common case is a short,
guessable URL, and the format — the thing a user is actually choosing between —
stays the most prominent part of the path.

RESULTS COME FROM THE SHARED RUNNER

    :func:`app.services.analysis_runner.run_analysis` is the same function the
    analyse pages call, so a downloaded report and the page it was downloaded
    from cannot disagree. It caches on the model's SHA-256, so fetching CSV then
    JSON then BCF runs the analysis once; a model that changes produces a
    different digest and therefore a fresh run.
"""

from __future__ import annotations

from fasthtml.common import Response

from app.logging_config import get_logger
from app.modules.phase_6.phase_6e_export import FORMATS, export
from app.services.analysis_runner import RUNNABLE_SLUGS, run_analysis

logger = get_logger(__name__)


def _filename(slug: str, project_id: int, extension: str) -> str:
    """Build the name the browser saves the file under.

    Carries the project id and the analysis so a folder of downloads from
    several projects stays legible.
    """
    return f"bimguard-{slug}-project-{project_id}.{extension}"


def _download(fmt: str, project_id: int, slug: str) -> Response:
    """Render one analysis in one format as an attachment response.

    Args:
        fmt: One of :data:`app.modules.phase_6.phase_6e_export.FORMATS`.
        project_id: Project to analyse.
        slug: Which analysis; see :data:`RUNNABLE_SLUGS`.

    Returns:
        A 200 with the file, or a status carrying a plain-text reason:
        400 for an unusable request, 409 when the analysis could not run.
    """
    if project_id <= 0:
        return Response("No project was supplied.", status_code=400)

    if slug not in RUNNABLE_SLUGS:
        return Response(
            f"Unknown analysis {slug!r}; expected one of {', '.join(RUNNABLE_SLUGS)}.",
            status_code=400,
        )

    if fmt not in FORMATS:
        return Response(
            f"Unsupported format {fmt!r}; expected one of {', '.join(sorted(FORMATS))}.",
            status_code=400,
        )

    result = run_analysis(slug, project_id)

    # 409 rather than 404 or 500: the project exists and the request is
    # well-formed, but the analysis cannot be produced in the current state —
    # usually no model attached. The message is shown to the user.
    if result.get("compliance_error"):
        logger.info(
            "Download refused project_id=%d slug=%s fmt=%s reason=%s",
            project_id,
            slug,
            fmt,
            result["compliance_error"],
        )
        return Response(result["compliance_error"], status_code=409)

    content, media_type, extension = export(result, fmt)
    filename = _filename(slug, project_id, extension)

    logger.info(
        "Download served project_id=%d slug=%s fmt=%s bytes=%d issues=%d",
        project_id,
        slug,
        fmt,
        len(content),
        len(result.get("audit_issues", [])),
    )
    return Response(
        content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(content)),
            # Downloads are computed per request from the current model; a
            # cached copy in the browser could outlive the model it describes.
            "Cache-Control": "no-store",
        },
    )


def setup_routes(rt):
    """Register the download endpoints."""

    @rt("/download/csv/{project_id}", methods=["GET"])
    def download_csv(project_id: int, slug: str = "corrosion"):
        """Download the analysis as CSV — one row per finding."""
        return _download("csv", project_id, slug)

    @rt("/download/json/{project_id}", methods=["GET"])
    def download_json(project_id: int, slug: str = "corrosion"):
        """Download the full result as JSON, findings and data quality apart."""
        return _download("json", project_id, slug)

    @rt("/download/bcf/{project_id}", methods=["GET"])
    def download_bcf(project_id: int, slug: str = "corrosion"):
        """Download a BCF 2.1 archive — one topic per finding."""
        return _download("bcf", project_id, slug)
