"""Produce an ``AnalysisResult`` for a project, computing it only when needed.

Lives in ``app/services/`` rather than in a route module because two route
modules need it: the analyse pages run a check and render it, and the download
endpoints render the same result as a file. Sharing one function is what stops
a downloaded report and the page it came from disagreeing.

CACHING

    Results are cached on the model's SHA-256 (see
    :mod:`app.services.analysis_cache`), so downloading CSV, then JSON, then BCF
    runs the analysis once rather than three times. A model that changes
    produces a different digest and therefore a miss, which is what makes a
    stale download structurally impossible rather than merely unlikely.

    A miss is never an error — it just recomputes. Nothing here depends on the
    cache for correctness.
"""

from __future__ import annotations

from app.logging_config import get_logger
from app.modules.phase_6.phase_6b_parsing import parse_ifc_bytes, sha256_of
from app.modules.phase_6.phase_6c_corrosion_ui import run_corrosion_analysis
from app.modules.phase_6.phase_6d_seismic import run_seismic_analysis
from app.services.analysis_cache import ANALYSIS_CACHE, CacheKey
from app.services.projects_service import ProjectsService

logger = get_logger(__name__)

_projects_service = ProjectsService()

#: Analysis slugs this runner can produce, matching the values of
#: ``app.constants.ANALYSIS_ROUTES`` that have an engine behind them.
RUNNABLE_SLUGS: tuple[str, ...] = ("corrosion", "seismic")


def failure_result(error: str) -> dict:
    """An ``AnalysisResult`` carrying only a reason it could not be produced.

    Errors cross this boundary as values, not exceptions — the same rule the
    Phase 6 stages follow, so a route renders a message rather than a traceback.
    """
    return {
        "audit_issues": [],
        "issue_stats": {},
        "cost_impact": None,
        "compliance_error": error,
        "compliance_is_demo": False,
    }


def model_bytes(project_id: int) -> tuple[bytes | None, str | None]:
    """Return a project's IFC content, or a reason it is unavailable.

    Reads through ``resolve_ifc_file``, which materialises the object from
    storage into the local cache when needed. A read path; nothing here writes.

    Returns:
        ``(content, None)`` on success, ``(None, reason)`` on failure.
    """
    project = _projects_service.get_project(project_id)
    if project is None:
        return None, "That project no longer exists."
    if not project.get("ifc_file_path"):
        return None, "No IFC model is attached to this project yet."

    path = _projects_service.resolve_ifc_file(project_id)
    if path is None:
        return None, "The IFC model could not be retrieved from storage."
    try:
        return path.read_bytes(), None
    except OSError as exc:
        logger.warning("IFC unreadable project_id=%d error=%s", project_id, exc)
        return None, f"The IFC model could not be read: {exc}"


def run_analysis(slug: str, project_id: int, *, use_cache: bool = True) -> dict:
    """Return the ``AnalysisResult`` for ``slug`` on ``project_id``.

    Args:
        slug: One of :data:`RUNNABLE_SLUGS`.
        project_id: Project whose model to analyse.
        use_cache: Set ``False`` to force a recompute. The result is still
            stored, so a forced run refreshes the entry rather than bypassing it.

    Returns:
        An ``AnalysisResult``. An unknown slug, a missing project or an
        unreadable model all come back as a result carrying
        ``compliance_error`` — never as an exception.
    """
    if slug not in RUNNABLE_SLUGS:
        return failure_result(
            f"Unknown analysis {slug!r}; expected one of {', '.join(RUNNABLE_SLUGS)}."
        )

    content, error = model_bytes(project_id)
    if error:
        return failure_result(error)

    key = CacheKey(project_id=project_id, slug=slug, source_sha256=sha256_of(content))

    if use_cache:
        cached = ANALYSIS_CACHE.get(key)
        if cached is not None:
            return cached

    if slug == "seismic":
        result = run_seismic_analysis(content)
    else:
        parsed = parse_ifc_bytes(content, source_ref=f"project-{project_id}")
        result = run_corrosion_analysis(parsed, include_low=False)

    # Failures are not cached: an unreachable storage object or an unreadable
    # model is usually transient, and caching it would make one bad moment
    # persist for the whole TTL.
    if not result.get("compliance_error"):
        ANALYSIS_CACHE.put(key, result)

    logger.info(
        "Analysis computed project_id=%d slug=%s issues=%d cached=%s",
        project_id,
        slug,
        len(result.get("audit_issues", [])),
        not result.get("compliance_error"),
    )
    return result
