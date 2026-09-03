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

ENGINE SELECTION

    A corrosion run assesses only the engines the caller selected, and the
    selection is part of the cache key. Two things follow: an unselected engine
    costs nothing, because it is never entered rather than filtered out
    afterwards, and a narrowed run cannot be served back to a request that
    asked for more.
"""

from __future__ import annotations

from app.logging_config import get_logger
from app.modules.comparator.issue_schema import Issue, RiskBand
from app.modules.phase_6.phase_6b_parsing import parse_ifc_bytes, sha256_of
from app.modules.phase_6.phase_6c_corrosion_ui import (
    DATA_QUALITY,
    resolve_engine_codes,
    run_corrosion_analysis,
)
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
RUNNABLE_SLUGS: tuple[str, ...] = ("corrosion", "seismic", "architecture")


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

    The primary model and only the primary model. A project may hold several --
    the discipline models of one building -- but corrosion assessment is a
    question about a pipe run and its materials, and a second model's copy of
    the same run would double every finding rather than add one. The analysis
    that does want the whole building is seismic; it uses
    :func:`model_bytes_all`.

    Reads through ``resolve_primary_ifc_file``, which materialises the object
    from storage into the local cache when needed. A read path; nothing here
    writes.

    Returns:
        ``(content, None)`` on success, ``(None, reason)`` on failure.
    """
    project = _projects_service.get_project(project_id)
    if project is None:
        return None, "That project no longer exists."

    path = _projects_service.resolve_primary_ifc_file(project_id)
    if path is None:
        if not _projects_service.get_ifc_files_by_project(project_id):
            return None, "No IFC model is attached to this project yet."
        return None, "The IFC model could not be retrieved from storage."
    try:
        return path.read_bytes(), None
    except OSError as exc:
        logger.warning("IFC unreadable project_id=%d error=%s", project_id, exc)
        return None, f"The IFC model could not be read: {exc}"


def _federated_sha256(models: list[tuple[str, bytes]]) -> str:
    """Digest a set of models as one, so any change to any of them is a miss.

    Digests the per-model digests rather than the concatenated bytes: it is the
    same one-pass cost, and it keeps the result independent of how the models
    happen to be chunked in memory.
    """
    return sha256_of("".join(sha256_of(content) for _, content in models).encode("ascii"))


def model_bytes_all(
    project_id: int,
) -> tuple[list[tuple[str, bytes]], str | None]:
    """Return every IFC model attached to a project, primary first.

    WHY A MISSING FILE FAILS THE WHOLE RUN

        The caller federates these into one geometry set and looks for clashes
        between them. Dropping a model that could not be fetched would not cost
        detail, it would remove the clashes that model takes part in -- and the
        run would report clearance where it had simply stopped looking. A
        partial set is therefore refused by name rather than analysed quietly.

    Returns:
        ``([(file_name, content), ...], None)`` on success, ``([], reason)`` on
        failure.
    """
    if _projects_service.get_project(project_id) is None:
        return [], "That project no longer exists."

    resolved, missing = _projects_service.resolve_ifc_file_paths(project_id)
    if missing:
        names = ", ".join(row.get("file_name") or row.get("file_path", "?") for row in missing)
        return [], f"These models could not be retrieved from storage: {names}."
    if not resolved:
        return [], "No IFC model is attached to this project yet."

    models: list[tuple[str, bytes]] = []
    for row, path in resolved:
        name = row.get("file_name") or path.name
        try:
            models.append((name, path.read_bytes()))
        except OSError as exc:
            logger.warning(
                "IFC unreadable project_id=%d file=%s error=%s", project_id, name, exc
            )
            return [], f"{name} could not be read: {exc}"
    return models, None


def _run_corrosion_tracked(
    content: bytes, project_id: int, engines: list[str] | None = None
) -> dict:
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
        engines: Ruleset codes to run, or ``None`` for all of them. Only the
            selected engines are tracked: reporting stages for an engine that
            was never entered would describe work that did not happen.

    Returns:
        The ``AnalysisResult`` from :func:`run_corrosion_analysis`, unchanged.
        Tracking never alters the result, so a tracker failure could not change
        what a report says.
    """
    # Only the selected engines are tracked. An engine that will not run has no
    # stages to report, and showing it as pending forever would misdescribe the
    # run rather than merely look untidy.
    selected = resolve_engine_codes(engines)
    tracked = tuple(code for code in TRACKED_ENGINES if code in selected)

    with tracking(project_id):
        for code in tracked:
            emit(code, Stage.VALIDATION, model_bytes=len(content))
        for code in tracked:
            emit(code, Stage.IFC_PARSING)

        # with_piping: MM-001 and XM-001 read the PipingElement view, which
        # carries the operating temperature and the connectivity ServiceElement
        # does not. Built from the model this parse already has open rather than
        # by reopening the file, which dominates runtime on large models.
        parsed = parse_ifc_bytes(
            content, source_ref=f"project-{project_id}", with_piping=True
        )
        quality = parsed.get("quality", {})

        if not quality.get("valid", False):
            reason = quality.get("error") or "The IFC model could not be read."
            for code in tracked:
                track_failure(code, reason)
            # Still routed through run_corrosion_analysis so the error result is
            # shaped in exactly one place.
            return run_corrosion_analysis(parsed, include_low=False, engines=engines)

        elements_total = len(parsed.get("elements", []))
        for code in tracked:
            emit(code, Stage.ENGINE_EXECUTION, elements_total=elements_total)

        result = run_corrosion_analysis(parsed, include_low=False, engines=engines)

        issues = result.get("audit_issues", [])
        for code in tracked:
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

    The architecture and MEP pipelines emit findings as ``asdict(AuditIssue)``
    dicts -- a flat shape with a string ``band`` and a ``details`` mapping --
    while Sessions C and D emit :class:`Issue` dataclasses with a
    :class:`RiskBand` and ``metadata``. ``phase_6e_export`` reads attributes, so
    a dict reaches it as ``AttributeError`` rather than as a report. Converting
    here keeps that difference in one place and leaves the exporter free of the
    per-pipeline branch its module docstring says it does not need.

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


def _run_architecture(project_id: int) -> dict:
    """Run the Part 9 architectural checks, shaped as an ``AnalysisResult``.

    Architecture does not reach its findings through Phase 6 the way corrosion
    and seismic do: it runs the orchestrator's Architecture theme, which already
    returns the ``AnalysisResult`` keys but fills ``audit_issues`` with dicts.
    Mapping them through :func:`as_issue` is what lets one exporter serve all
    three slugs.

    Only the ``AnalysisResult`` keys are kept. The orchestrator also returns the
    project record, parsed documents and per-rule tables, which the exporter
    never reads and which would otherwise be held in the analysis cache for the
    whole TTL.

    Not tracked: the orchestrator reports progress through its own
    ``log_progress`` and drives no engine the workflow endpoint knows about, so
    binding a tracker here would reset a corrosion run's stages for the same
    project -- the reason the seismic path stays untracked too.
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
            analysis_theme="Architecture",
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
    }


def run_analysis(
    slug: str,
    project_id: int,
    *,
    use_cache: bool = True,
    engines: list[str] | None = None,
) -> dict:
    """Return the ``AnalysisResult`` for ``slug`` on ``project_id``.

    Args:
        slug: One of :data:`RUNNABLE_SLUGS`.
        project_id: Project whose model to analyse.
        use_cache: Set ``False`` to force a recompute. The result is still
            stored, so a forced run refreshes the entry rather than bypassing it.
        engines: Corrosion ruleset codes to run, e.g. ``["GC-001", "CC"]``.
            ``None`` runs every engine. Ignored for ``"seismic"``, which is a
            single kernel with nothing to select between.

    Returns:
        An ``AnalysisResult``. An unknown slug, a missing project or an
        unreadable model all come back as a result carrying
        ``compliance_error`` — never as an exception.
    """
    if slug not in RUNNABLE_SLUGS:
        return failure_result(
            f"Unknown analysis {slug!r}; expected one of {', '.join(RUNNABLE_SLUGS)}."
        )

    # Seismic reads every model the project holds; the others read the primary.
    # The two are loaded through different helpers rather than one with a flag,
    # so which analysis federates is visible here rather than several calls away.
    models: list[tuple[str, bytes]] = []
    if slug == "seismic":
        models, error = model_bytes_all(project_id)
        content = models[0][1] if models else b""
    else:
        content, error = model_bytes(project_id)
    if error:
        return failure_result(error)

    # Canonicalised, not stored as the caller spelled it: ["gc"] and ["GC-001"]
    # run the same engine and must therefore share one entry.
    engine_codes = resolve_engine_codes(engines) if slug == "corrosion" else ()
    key = CacheKey(
        project_id=project_id,
        slug=slug,
        # A federated run is stale if any of its models changed, so the digest
        # covers all of them. Attaching a second model to a project therefore
        # misses the entry its primary alone produced, which is the point:
        # the answer genuinely differs once there is more geometry to clash with.
        source_sha256=_federated_sha256(models) if models else sha256_of(content),
        engines=engine_codes,
    )

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
        result = run_seismic_analysis(content, extra_models=models[1:])
    elif slug == "architecture":
        result = _run_architecture(project_id)
    else:
        result = _run_corrosion_tracked(content, project_id, engines)

    # Failures are not cached: an unreachable storage object or an unreadable
    # model is usually transient, and caching it would make one bad moment
    # persist for the whole TTL.
    if not result.get("compliance_error"):
        ANALYSIS_CACHE.put(key, result)

    logger.info(
        "Analysis computed project_id=%d slug=%s engines=%s issues=%d cached=%s",
        project_id,
        slug,
        ",".join(engine_codes) or "-",
        len(result.get("audit_issues", [])),
        not result.get("compliance_error"),
    )
    return result
