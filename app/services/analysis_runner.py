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
from app.modules.comparator.issue_schema import Issue, RiskBand
from app.modules.phase_6.phase_6b_parsing import sha256_of
from app.services.analysis_cache import ANALYSIS_CACHE, CacheKey
from app.services.models_service import ModelsService
from app.services.projects_service import ProjectsService

logger = get_logger(__name__)

_projects_service = ProjectsService()
_models_service = ModelsService(project_mirror=_projects_service)

#: Analysis slugs this runner can produce, matching the values of
#: ``app.constants.ANALYSIS_ROUTES`` that have an engine behind them.
RUNNABLE_SLUGS: tuple[str, ...] = ("architecture",)


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
    """Return a project's primary IFC content, or a reason it is unavailable.

    Reads through ``resolve_primary_ifc_file``, which materialises the object
    from storage into the local cache when needed. A read path; nothing here
    writes.

    Returns:
        ``(content, None)`` on success, ``(None, reason)`` on failure.
    """
    project = _projects_service.get_project(project_id)
    if project is None:
        return None, "That project no longer exists."

    path = _models_service.resolve_primary_path(project_id)
    if path is None:
        if not _models_service.list_models(project_id):
            return None, "No IFC model is attached to this project yet."
        return None, "The IFC model could not be retrieved from storage."
    try:
        return path.read_bytes(), None
    except OSError as exc:
        logger.warning("IFC unreadable project_id=%d error=%s", project_id, exc)
        return None, f"The IFC model could not be read: {exc}"


#: Band names an ``AuditIssue`` dict may carry, mapped onto the enum the
#: exporter sorts and prioritises by. Anything unrecognised becomes LOW rather
#: than raising: a band typo should cost one finding its severity, not a
#: coordinator the whole report.
_BAND_BY_NAME: dict[str, RiskBand] = {band.value: band for band in RiskBand}

#: Fields an ``Issue`` defines a default for that an ``AuditIssue`` dict has no
#: column for. Copied only when actually present, so the dataclass defaults keep
#: deciding what "unset" means rather than this module restating them.
_OPTIONAL_ISSUE_FIELDS: tuple[str, ...] = (
    "assignee_role",
    "status",
    "created_at",
    "updated_at",
)


def as_issue(raw: Issue | dict) -> Issue:
    """Adapt one audit finding to the :class:`Issue` the exporter consumes.

    The architecture pipeline emits findings as ``asdict(AuditIssue)`` dicts --
    a flat shape with a string ``band`` and a ``details`` mapping -- while
    :class:`Issue` is a dataclass with a :class:`RiskBand` and ``metadata``.
    ``phase_6e_export`` reads attributes, so a dict reaches it as
    ``AttributeError`` rather than as a report. Converting here keeps that
    difference in one place and leaves the exporter free of a per-pipeline
    branch.

    An ``Issue`` passes through untouched, so this is safe to map over any
    pipeline's output without first knowing which pipeline produced it.
    """
    if isinstance(raw, Issue):
        return raw

    optional = {f: raw[f] for f in _OPTIONAL_ISSUE_FIELDS if raw.get(f)}
    return Issue(
        id=str(raw.get("id", "")),
        element_id=str(raw.get("element_id", "")),
        rule_id=str(raw.get("rule_id", "")),
        title=str(raw.get("title", "")),
        description=raw.get("description") or None,
        band=_BAND_BY_NAME.get(str(raw.get("band", "")).lower(), RiskBand.LOW),
        score=float(raw.get("score") or 0.0),
        mechanism=str(raw.get("mechanism", "")),
        mitigation=str(raw.get("mitigation", "")),
        # ``details`` is AuditIssue's name for what Issue calls ``metadata``.
        metadata=dict(raw.get("details") or raw.get("metadata") or {}),
        citations=list(raw.get("citations") or []),
        **optional,
    )


def _run_architecture(project_id: int, enable_shacl: bool = False) -> dict:
    """Run the Part 9 architectural checks, shaped as an ``AnalysisResult``.

    Runs the orchestrator's Architecture theme, which already returns the
    ``AnalysisResult`` keys but fills ``audit_issues`` with dicts. Mapping them
    through :func:`as_issue` is what lets the exporter serve this slug the same
    way it would any other.

    Only the ``AnalysisResult`` keys are kept. The orchestrator also returns the
    project record, parsed documents and per-rule tables, which the exporter
    never reads and which would otherwise be held in the analysis cache for the
    whole TTL.

    Not tracked: the orchestrator reports progress through its own
    ``log_progress`` and drives no engine the workflow endpoint knows about, so
    there is nothing here for the endpoint to report. Architecture would need
    an engine registered in ``pipeline_tracker.ENGINE_SPECS`` before tracking
    it could report anything, so it stays untracked until it has one.
    """
    # Errors cross this boundary as values, not exceptions -- the rule this
    # module opens with. The orchestrator breaks it in one place: its rule packs
    # are loaded at import time and a missing one raises, so an environment
    # without the BUILDING-CODE-PART9 asset answered a request for this analysis
    # with a 500 and a stack trace rather than saying what was missing.
    try:
        from app.services.pipeline_services import PipelineOrchestratorService

        raw = PipelineOrchestratorService.orchestrate_workflow(
            project_id=project_id,
            doc_ids=[],  # No documents needed for structural/architecture clash
            analysis_theme="Architecture",
            rule_folder="",
            include_openings=True,
            include_spaces=True,
            include_type_definitions=False,
            enable_shacl=enable_shacl,
        )
    except Exception as exc:
        logger.exception("Architectural analysis failed project_id=%d", project_id)
        return failure_result(f"The architectural analysis could not be run: {exc}")

    # The orchestrator reports a hard stop under "error" and a soft one under
    # "compliance_error"; only the first means no result was produced.
    if raw.get("error"):
        return failure_result(str(raw["error"]))

    return {
        "audit_issues": [as_issue(i) for i in raw.get("audit_issues", [])],
        "issue_stats": raw.get("issue_stats", {}),
        "cost_impact": raw.get("cost_impact"),
        "compliance_error": raw.get("compliance_error"),
        "compliance_is_demo": raw.get("compliance_is_demo", False),
        "shacl_issues": raw.get("shacl_issues", []),
        "shacl_error": raw.get("shacl_error"),
    }


def run_analysis(
    slug: str,
    project_id: int,
    *,
    use_cache: bool = True,
    enable_shacl: bool = False,
) -> dict:
    """Return the ``AnalysisResult`` for ``slug`` on ``project_id``.

    Args:
        slug: One of :data:`RUNNABLE_SLUGS`.
        project_id: Project whose model to analyse.
        use_cache: Set ``False`` to force a recompute. The result is still
            stored, so a forced run refreshes the entry rather than bypassing it.

    Returns:
        An ``AnalysisResult``. Its ``cached`` field says how this particular
        call was served: ``True`` when the result came from the store, ``False``
        when the engines ran. An unknown slug, a missing project or an
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

    key = CacheKey(
        project_id=project_id,
        slug=slug,
        source_sha256=sha256_of(content),
        engines=(),
        include_low=True,
        enable_shacl=enable_shacl,
    )

    if use_cache:
        hit = ANALYSIS_CACHE.get(key)
        if hit is not None:
            # A shallow copy, not the stored dict: flagging the entry in place
            # would make the next read of it report cached=True for a result
            # that was never served from the cache before, and would leave the
            # store holding a field that describes one delivery rather than the
            # result. The copy is per-request; the entry stays flag-free.
            return {**hit, "cached": True}

    result = _run_architecture(project_id, enable_shacl=enable_shacl)

    # Failures are not cached: an unreachable storage object or an unreadable
    # model is usually transient, and caching it would make one bad moment
    # persist for the whole TTL.
    if not result.get("compliance_error"):
        ANALYSIS_CACHE.put(key, result)

    logger.info(
        "Analysis computed project_id=%d slug=%s issues=%d ok=%s",
        project_id,
        slug,
        len(result.get("audit_issues", [])),
        not result.get("compliance_error"),
    )
    # Copied for the same reason as the hit above, and after the put: what goes
    # into the store carries no flag, so whether a result was served from the
    # cache stays a property of the delivery rather than of the entry.
    return {**result, "cached": False}
