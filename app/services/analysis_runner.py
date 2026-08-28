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
from app.modules.phase_6.phase_6c_corrosion_ui import DATA_QUALITY, run_corrosion_analysis
from app.modules.phase_6.phase_6d_seismic import run_seismic_analysis
from app.services.analysis_cache import ANALYSIS_CACHE, CacheKey
from app.services.pipeline_tracker import (
    CC_ENGINE,
    GC_ENGINE,
    Stage,
    complete,
    emit,
    tracking,
)
from app.services.pipeline_tracker import fail as track_failure
from app.services.projects_service import ProjectsService

logger = get_logger(__name__)

_projects_service = ProjectsService()

#: The engines a corrosion run drives and therefore reports stages for. MC-001
#: also runs (see ``phase_6c_corrosion_ui.MECHANISMS``) but is declared
#: ``not_implemented`` in the workflow contract, so it is not driven here — see
#: the note on :data:`app.services.pipeline_tracker.ENGINE_SPECS`.
TRACKED_ENGINES: tuple[str, ...] = (GC_ENGINE, CC_ENGINE)

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


def _run_corrosion_tracked(content: bytes, project_id: int) -> dict:
    """Parse and assess a model, reporting each stage to the pipeline tracker.

    This is the driver half of the six-stage split documented in
    :mod:`app.services.pipeline_tracker`: it owns Validation, IFC Parsing and
    Report Assembly, and the engines report Engine Execution from inside their
    per-element assessment.

    WHY STAGES 4 AND 5 ARE STAMPED AFTER THE LOOP

        ``run_corrosion_analysis`` interleaves the work: for each element it
        assesses every mechanism, normalises the band, applies the ``include_low``
        filter and builds the Issue. Scoring and report assembly are therefore
        not separable phases on this path. Rather than fake two long stages, the
        loop reports as Engine Execution throughout and stages 4 and 5 are
        stamped once at the end, carrying the totals that genuinely become final
        there. Their recorded durations are small on purpose -- they measure the
        aggregation, not the assessment.

    Args:
        content: Raw IFC bytes.
        project_id: Project being analysed; the tracker key.

    Returns:
        The ``AnalysisResult`` from :func:`run_corrosion_analysis`, unchanged.
        Tracking never alters the result, so a tracker failure could not change
        what a report says.
    """
    with tracking(project_id):
        for code in TRACKED_ENGINES:
            emit(code, Stage.VALIDATION, model_bytes=len(content))
        for code in TRACKED_ENGINES:
            emit(code, Stage.IFC_PARSING)

        parsed = parse_ifc_bytes(content, source_ref=f"project-{project_id}")
        quality = parsed.get("quality", {})

        if not quality.get("valid", False):
            reason = quality.get("error") or "The IFC model could not be read."
            for code in TRACKED_ENGINES:
                track_failure(code, reason)
            # Still routed through run_corrosion_analysis so the error result is
            # shaped in exactly one place.
            return run_corrosion_analysis(parsed, include_low=False)

        elements_total = len(parsed.get("elements", []))
        for code in TRACKED_ENGINES:
            emit(code, Stage.ENGINE_EXECUTION, elements_total=elements_total)

        result = run_corrosion_analysis(parsed, include_low=False)

        issues = result.get("audit_issues", [])
        for code in TRACKED_ENGINES:
            mine = [i for i in issues if i.rule_id.startswith(code)]
            emit(
                code,
                Stage.RISK_SCORING,
                elements_total=elements_total,
                findings=sum(1 for i in mine if i.mechanism != DATA_QUALITY),
            )
            emit(
                code,
                Stage.REPORT_ASSEMBLY,
                issues=len(mine),
                data_quality=sum(1 for i in mine if i.mechanism == DATA_QUALITY),
            )
            # Complete rather than advancing to Export: export happens later, in
            # a separate download request with no tracker bound, so claiming
            # stage 6 here would report an export that has not been asked for.
            complete(code)

        return result


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

    # A cache hit returns above without reaching here, and deliberately without
    # touching the tracker: no engine ran, so reporting stages for one would
    # describe work that did not happen.
    if slug == "seismic":
        # Not tracked: the seismic analysis is not one of the engines the
        # workflow endpoint reports, and binding a tracker here would reset a
        # corrosion run's progress for the same project.
        result = run_seismic_analysis(content)
    else:
        result = _run_corrosion_tracked(content, project_id)

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
