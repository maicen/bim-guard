"""FastAPI router for compliance analysis, IFC upload, and report exports."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)

from app.api.dependencies import (
    get_arch_analysis_service,
    get_membership_service,
    get_phase6_service,
    get_profile_service,
    get_projects_service,
)
from app.api.projects import (
    ProjectAccessChecker,
    _can_access_project,
    get_project_access_checker,
    get_project_access_checker_flexible,
    require_project_access,
)
from app.auth import CurrentUser, get_current_user, get_current_user_flexible
from app.logging_config import get_logger
from app.modules.contracts import (
    AnalysisQueuedResponse,
    AnalysisResultContract,
    AnalysisRunRequest,
    ArchAnalysisResponse,
    AuditIssueContract,
    IfcUploadAttachResponse,
    IssueStatsContract,
    ResultPageContract,
    RevitRuleResult,
    RevitSyncRequest,
    RevitSyncResponse,
    WorkflowStatusContract,
)
from app.modules.phase_6.phase_6e_export import export
from app.services.analysis_runner import RUNNABLE_SLUGS, run_analysis
from app.services.arch_analysis_service import ArchAnalysisService
from app.services.membership_service import MembershipService
from app.services.phase6_service import Phase6Service
from app.services.pipeline_tracker import snapshot
from app.services.profile_service import ProfileService
from app.services.projects_service import ProjectsService

logger = get_logger(__name__)

router = APIRouter()


def get_authorized_project_for_analyze(
    project_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ProjectsService, Depends(get_projects_service)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> dict:
    """Path-param project authorization for this router's own GET routes.

    Behaviourally identical to app.api.projects.get_authorized_project (same
    require_project_access call), but a distinct function object so tests can
    override it independently -- see tests/conftest.py's note on why this
    router's pagination/status routes need a permissive override that
    app.api.projects's own 404-for-a-nonexistent-project tests must not get.
    """
    return require_project_access(project_id, current_user, service, memberships, profiles)


def get_authorized_project_for_analyze_flexible(
    project_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user_flexible)],
    service: Annotated[ProjectsService, Depends(get_projects_service)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> dict:
    """Like :func:`get_authorized_project_for_analyze`, but also accepts a query token.

    For the ``download_latest_bcf`` link, which the frontend opens via a
    plain ``<a href>`` rather than an authenticated ``fetch``.
    """
    return require_project_access(project_id, current_user, service, memberships, profiles)


#: Corrosion engine codes a corrosion run may be narrowed to, matching the
#: ``MechanismSpec.code`` values in ``phase_6c_corrosion_ui``. Issues carry rule
#: ids like "GC-001.01" and "GC-001.DATA", so a prefix match selects an engine's
#: verdicts and its data-quality notes together.
#:
#: All five engines are here, and the list must stay in step with
#: ``phase_6c_corrosion_ui.MECHANISMS``. A code missing from this tuple is not
#: merely unselectable: it is dropped from ``wanted`` in
#: :func:`_filter_issues_by_engine`, so a caller naming it alongside a listed
#: engine ran it and then had its findings filtered away. MM-001 and XM-001
#: were absent while the network mechanisms that produce them were running,
#: which is exactly that silent loss.
SELECTABLE_ENGINES: tuple[str, ...] = (
    "GC-001",
    "CC-001",
    "MC-001",
    "MM-001",
    "XM-001",
)


def _issue_stats(issues: list) -> dict[str, int]:
    """Count ``issues`` by band, keeping data-quality notes out of the totals.

    Data-quality findings report what could not be assessed rather than a
    verdict, so they are counted on their own line and excluded from ``total``
    — the same split the analyse page draws.
    """
    stats = {"total": 0, "critical": 0, "high": 0, "medium": 0, "low": 0, "data_quality": 0}
    for issue in issues:
        if issue.mechanism == "data_quality":
            stats["data_quality"] += 1
            continue
        stats["total"] += 1
        band = getattr(issue.band, "value", str(issue.band)).lower()
        if band in stats:
            stats[band] += 1
    return stats


def _filter_issues_by_engine(result: dict, engines: list[str]) -> dict:
    """Narrow an ``AnalysisResult`` to the issues the given engines raised.

    This is the legacy ``rule_ids`` path only. The analyse page sends
    ``engines``, which ``resolve_mechanisms`` honours before the element loop,
    so an unselected engine is never entered rather than being run and then
    filtered. Narrowing here is what remains for a caller that predates that
    field.

    Applied to what ``run_analysis`` returns rather than inside it: narrowing
    before the cache write would store a partial run, and while
    :class:`~app.services.analysis_cache.CacheKey` now carries the engine
    tuple and would keep the two apart, the result a cache entry holds should
    be the whole run its key describes.

    An empty or unrecognised selection returns the result untouched, so a
    caller cannot accidentally narrow a run down to nothing.
    """
    wanted = [e for e in engines if e in SELECTABLE_ENGINES]
    if not wanted:
        return result

    kept = [
        i
        for i in result.get("audit_issues", [])
        if any(i.rule_id.startswith(code) for code in wanted)
    ]

    # issue_stats describes the whole run, so it is recomputed rather than
    # carried across: a narrowed list under unnarrowed totals reads as data
    # silently going missing.
    return {**result, "audit_issues": kept, "issue_stats": _issue_stats(kept)}


def _format_result(slug: str, project_id: int, result: dict) -> AnalysisResultContract:
    """Format raw analysis result dictionary into strict Pydantic model."""
    raw_issues = result.get("audit_issues", [])
    issues: list[AuditIssueContract] = []
    for i in raw_issues:
        band_val = getattr(i.band, "value", str(i.band)).lower()
        raw_citations = getattr(i, "citations", []) or []
        citations: list[dict[str, str]] = []
        for c in raw_citations:
            if isinstance(c, dict):
                citations.append({
                    "standard": c.get("standard", ""),
                    "clause": c.get("clause", ""),
                    "reason": c.get("reason", ""),
                })
            elif hasattr(c, "standard"):
                citations.append({
                    "standard": getattr(c, "standard", ""),
                    "clause": getattr(c, "clause", ""),
                    "reason": getattr(c, "reason", ""),
                })

        issues.append(
            AuditIssueContract(
                id=i.id,
                element_id=i.element_id,
                rule_id=i.rule_id,
                title=i.title,
                band=band_val,
                score=getattr(i, "score", 0.0) or 0.0,
                mechanism=i.mechanism,
                description=i.description or "",
                mitigation=i.mitigation or "",
                assignee_role=getattr(i, "assignee_role", "BIM coordinator") or "BIM coordinator",
                citations=citations,
                details=dict(i.metadata) if hasattr(i, "metadata") and i.metadata else {},
            )
        )

    raw_stats = result.get("issue_stats", {})
    stats = IssueStatsContract(
        total=raw_stats.get("total", len([i for i in issues if i.mechanism != "data_quality"])),
        critical=raw_stats.get("critical", 0),
        high=raw_stats.get("high", 0),
        medium=raw_stats.get("medium", 0),
        low=raw_stats.get("low", 0),
        data_quality=raw_stats.get("data_quality", sum(1 for i in issues if i.mechanism == "data_quality")),
    )

    element_count = result.get("ifc_element_count") or len(issues)

    return AnalysisResultContract(
        pipeline="audit",
        project_id=project_id,
        slug=slug,
        element_count=element_count,
        audit_issues=issues,
        issue_stats=stats,
        compliance_error=result.get("compliance_error"),
        compliance_is_demo=result.get("compliance_is_demo", False),
        cached=result.get("cached", False),
    )


def _selected_engines(payload: AnalysisRunRequest) -> list[str] | None:
    """Return the engine codes a run request selected, or ``None`` for all.

    ``engines`` is the field the analyse page sends. ``rule_ids`` predates it
    and names the same thing in rule-id form, so it is honoured as a fallback
    rather than silently ignored — an existing caller that narrowed a run
    through it keeps working.
    """
    if payload.engines is not None:
        return payload.engines
    return payload.rule_ids


# ---------------------------------------------------------------------------
# Result pagination
# ---------------------------------------------------------------------------

#: Band ranking used when ordering a page, mirroring ``SEVERITY_WEIGHTS`` in
#: ``AnalyzeView.svelte``. An unrecognised band ranks last rather than raising,
#: the same as the page's ``?? 0``.
_BAND_WEIGHT: dict[str, int] = {"critical": 4, "high": 3, "medium": 2, "low": 1}

#: Sort orders a paginated request may ask for.
#:
#: ``band_then_score`` is the default and is the analyse page's order: the page
#: sorts on the band column descending and nothing else, so criticals lead and
#: lows trail. Within a band the page relies on ``Array.prototype.sort`` being
#: stable, i.e. on whatever order the run emitted — which is not a sort key a
#: second request can reproduce, so score descending is the tiebreak here.
#: ``natural`` is the escape hatch for a caller that wants the run's own order
#: sliced verbatim, exactly as the unpaginated body would have listed it.
#:
#: ``band_asc`` and ``score_asc`` are the ascending counterparts, added so the
#: analyse page's column headers can offer a direction rather than a single
#: fixed order. In both, data-quality notes sort *last* rather than first: a
#: plain reversal would open the table with the elements the engines refused to
#: score, which reads as "here are your least severe findings" when it is not a
#: finding list at all. Least-severe-first means the mildest verdict first, and
#: the notes still trail it.
PageSort = Literal[
    "band_then_score",
    "score_desc",
    "natural",
    "band_asc",
    "score_asc",
]

#: Bands a page may be filtered to.
#:
#: ``data_quality`` is not a band the engines emit; it selects the notes that
#: report what could not be assessed. It is here because the analyse page's
#: severity dropdown offers it alongside the four real bands, and a filter the
#: page cannot express is a filter the page cannot use. ``include_data_quality``
#: remains the separate, global "show these at all" switch.
IssueBand = Literal["critical", "high", "medium", "low", "data_quality"]

#: The ``mechanism`` token that selects data-quality notes rather than an
#: engine prefix, mirroring the analyse page's mechanism dropdown.
DATA_QUALITY_TOKEN = "DATA_QUALITY"


def _band_of(issue: Any) -> str:
    """Return an issue's band as a lowercase string, enum or not."""
    return getattr(issue.band, "value", str(issue.band)).lower()


def _is_data_quality(issue: Any) -> bool:
    """Report whether a finding describes unassessable data, not a verdict.

    Both spellings are checked because the engines emit ``"data_quality"`` and
    the architecture path emits ``"Data Quality"``; the analyse page tests for
    both for the same reason.
    """
    return issue.mechanism in ("data_quality", "Data Quality")


def _search_haystack(issue: Any) -> list[str]:
    """Return the text ``q`` matches against.

    The same fields the analyse page's search box already covers, so moving
    the search to the server does not quietly change what a query finds.
    """
    fields = [issue.title, issue.rule_id, issue.element_id, issue.mechanism]
    for citation in getattr(issue, "citations", None) or []:
        if isinstance(citation, dict):
            fields.append(citation.get("standard", ""))
            fields.append(citation.get("clause", ""))
    return fields


def _select_issues(
    issues: list,
    *,
    bands: list[str] | None,
    mechanisms: list[str] | None,
    include_data_quality: bool,
    query: str | None = None,
) -> list:
    """Narrow ``issues`` to what a page should list.

    Filters shape ``audit_issues`` alone. ``issue_stats`` is left describing
    the whole run, so a page of criticals still reports the run's real totals
    rather than the page's.

    ``bands`` excludes data-quality notes from the four real bands even when a
    note carries a matching one: asking for "the criticals" means the critical
    verdicts. The notes are selected by the ``data_quality`` band instead,
    which is exactly how the page's severity dropdown behaves.

    ``mechanisms`` is a case-insensitive prefix match on ``rule_id``, so ``GC``
    and ``GC-001`` both select an engine's verdicts together with its ``.DATA``
    notes; the token ``data_quality`` selects the notes on their own. Several
    values union, so ``GC`` and ``data_quality`` together select both.

    Unlike :func:`_filter_issues_by_engine`, an unrecognised mechanism selects
    nothing rather than falling back to everything. That function guards a run
    selection, where narrowing to nothing would throw away work already done;
    here the caller is filtering a view, and quietly widening it back to the
    full run would misreport what was asked for.
    """
    selected = issues

    if not include_data_quality:
        selected = [i for i in selected if not _is_data_quality(i)]

    if bands:
        wanted_bands = {b.lower() for b in bands}
        notes_wanted = "data_quality" in wanted_bands
        selected = [
            i
            for i in selected
            if (notes_wanted if _is_data_quality(i) else _band_of(i) in wanted_bands)
        ]

    if mechanisms:
        tokens = {m.upper() for m in mechanisms}
        notes_wanted = DATA_QUALITY_TOKEN in tokens
        prefixes = tuple(t for t in tokens if t != DATA_QUALITY_TOKEN)
        selected = [
            i
            for i in selected
            if (notes_wanted and _is_data_quality(i))
            or (prefixes and i.rule_id.upper().startswith(prefixes))
        ]

    if query:
        needle = query.strip().lower()
        if needle:
            selected = [
                i
                for i in selected
                if any(needle in (field or "").lower() for field in _search_haystack(i))
            ]

    return selected


def _sort_issues(issues: list, sort: PageSort) -> list:
    """Order ``issues`` deterministically for slicing.

    Every order but ``natural`` breaks ties on ``id``, so two requests for
    adjacent pages of the same run cannot overlap or skip a finding just
    because two issues compared equal.
    """
    if sort == "natural":
        return issues
    if sort == "score_desc":
        return sorted(issues, key=lambda i: (-(i.score or 0.0), i.id))
    if sort == "band_asc":
        # ``_is_data_quality`` leads the key so the notes land after every
        # verdict: they carry the Low band, so sorting on band alone would
        # bring them to the front of an ascending page.
        return sorted(
            issues,
            key=lambda i: (
                _is_data_quality(i),
                _BAND_WEIGHT.get(_band_of(i), 0),
                i.score or 0.0,
                i.id,
            ),
        )
    if sort == "score_asc":
        return sorted(issues, key=lambda i: (_is_data_quality(i), i.score or 0.0, i.id))
    return sorted(
        issues,
        key=lambda i: (-_BAND_WEIGHT.get(_band_of(i), 0), -(i.score or 0.0), i.id),
    )


def _paginate_result(
    result: dict,
    *,
    limit: int | None,
    offset: int,
    bands: list[str] | None,
    mechanisms: list[str] | None,
    include_data_quality: bool,
    sort: PageSort,
    query: str | None = None,
) -> tuple[dict, ResultPageContract]:
    """Return ``result`` with ``audit_issues`` narrowed to one page.

    Applied to what ``run_analysis`` returned, in the same place
    :func:`_filter_issues_by_engine` narrows and for the same reason: the cache
    entry must hold the whole run its key describes, so nothing here reaches
    the cache.

    ``issue_stats`` is filled in from the whole run before the slice, and
    ``ifc_element_count`` is pinned, so :func:`_format_result` computes neither
    from the handful of issues it is about to be handed.
    """
    all_issues = result.get("audit_issues", [])
    matching = _select_issues(
        all_issues,
        bands=bands,
        mechanisms=mechanisms,
        include_data_quality=include_data_quality,
        query=query,
    )
    ordered = _sort_issues(matching, sort)

    # An offset past the end is an empty page, not an error: a client holding a
    # page number while the run shrank asked a reasonable question and gets a
    # truthful "nothing here", with total_matching to re-aim by.
    window = ordered[offset:] if limit is None else ordered[offset : offset + limit]

    page = ResultPageContract(
        limit=limit,
        offset=offset,
        returned=len(window),
        total_matching=len(ordered),
        has_more=offset + len(window) < len(ordered),
    )

    narrowed = {
        **result,
        "audit_issues": window,
        "issue_stats": result.get("issue_stats") or _issue_stats(all_issues),
        "ifc_element_count": result.get("ifc_element_count") or len(all_issues),
    }
    return narrowed, page


@router.post("/upload", response_model=IfcUploadAttachResponse, summary="Attach an IFC model to a project")
async def analyze_upload_ifc(
    project_id: Annotated[int, Form(...)],
    ifc_file: Annotated[UploadFile, File(...)],
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker)],
    projects_service: Annotated[ProjectsService, Depends(get_projects_service)],
    phase6_service: Annotated[Phase6Service, Depends(get_phase6_service)],
) -> IfcUploadAttachResponse:
    """Upload and attach an IFC model to a project."""
    project_access(project_id)
    if not ifc_file.filename or not ifc_file.filename.lower().endswith(".ifc"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid .ifc file is required.",
        )

    content = await ifc_file.read()
    response = phase6_service.upload_service.upload(
        ifc_file.filename, content, project_id=project_id, kind="ifc"
    )
    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=response.error or "Upload failed.",
        )

    projects_service.attach_ifc(project_id, response.ref.storage_ref)
    return IfcUploadAttachResponse(
        success=True,
        filename=response.ref.filename,
        size_bytes=response.ref.size_bytes,
        sha256=response.ref.file_hash_sha256,
    )


@router.post(
    "/run",
    response_model=AnalysisResultContract | AnalysisQueuedResponse,
    summary="Trigger compliance analysis",
)
def run_analysis_endpoint(
    payload: AnalysisRunRequest,
    background_tasks: BackgroundTasks,
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker)],
    background: bool = Query(False, description="Run in background task if true"),
) -> AnalysisResultContract | AnalysisQueuedResponse:
    """Execute analysis (corrosion or seismic) for a project."""
    project_access(payload.project_id)
    slug = payload.slug.lower()
    if slug not in RUNNABLE_SLUGS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown analysis slug {slug!r}. Supported: {RUNNABLE_SLUGS}",
        )

    engines = _selected_engines(payload)

    if background:
        background_tasks.add_task(
            run_analysis,
            slug,
            payload.project_id,
            use_cache=payload.use_cache,
            engines=engines,
            include_low=payload.include_low,
        )
        return AnalysisQueuedResponse(
            status="queued",
            project_id=payload.project_id,
            slug=slug,
            message="Analysis started in background.",
        )

    raw_result = run_analysis(
        slug,
        payload.project_id,
        use_cache=payload.use_cache,
        engines=engines,
        include_low=payload.include_low,
    )
    if raw_result.get("compliance_error"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=raw_result["compliance_error"],
        )
    # Only corrosion has an engine subset. Applying a corrosion engine list to
    # another slug would match no rule ids and silently return an empty run
    # rather than the findings the caller asked for.
    if payload.rule_ids and slug == "corrosion":
        raw_result = _filter_issues_by_engine(raw_result, payload.rule_ids)
    return _format_result(slug, payload.project_id, raw_result)


@router.post("/corrosion", summary="Run corrosion analysis")
def run_corrosion(
    project_id: Annotated[int, Form(...)],
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker)],
    engines: Annotated[list[str] | None, Form()] = None,
    include_low: Annotated[bool, Form()] = True,
    use_cache: Annotated[bool, Form()] = True,
) -> AnalysisResultContract:
    """Run the selected corrosion engines.

    All five are selectable: GC-001, CC-001 and MC-001 score each element,
    while MM-001 and XM-001 assess the network once. Omitting ``engines`` runs
    every one of them; naming a subset runs only those, and the rest are never
    entered.

    ``use_cache`` defaults to ``True``, matching ``/analyze/run``. This endpoint
    used to pass ``False`` unconditionally, so pressing Run twice on an
    unchanged model re-ran every engine and the response always said
    ``cached=false`` — a 141-second answer to a question already answered, and
    a report that could differ from the one the page was showing. Send
    ``use_cache=false`` to force a recompute; that still refreshes the entry
    rather than bypassing the store.
    """
    project_access(project_id)
    raw_result = run_analysis(
        "corrosion", project_id, use_cache=use_cache, engines=engines, include_low=include_low
    )
    if raw_result.get("compliance_error"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=raw_result["compliance_error"],
        )
    return _format_result("corrosion", project_id, raw_result)


@router.post("/seismic", summary="Run seismic clearance analysis")
def run_seismic(
    project_id: Annotated[int, Form(...)],
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker)],
    use_cache: Annotated[bool, Form()] = True,
) -> AnalysisResultContract:
    """Run Blue Halo seismic clearance volume validation.

    ``use_cache`` defaults to ``True`` for the reason given on
    :func:`run_corrosion`: a federated clash run over three models is minutes of
    work, and repeating it for an unchanged set of models answers a question
    already answered. The cache key covers every attached model's digest, so
    attaching or replacing one misses and recomputes on its own.
    """
    project_access(project_id)
    raw_result = run_analysis("seismic", project_id, use_cache=use_cache)
    if raw_result.get("compliance_error"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=raw_result["compliance_error"],
        )
    return _format_result("seismic", project_id, raw_result)


@router.get("/results/{project_id}/{slug}", response_model=AnalysisResultContract)
def get_analysis_results(
    project_id: int,
    slug: str,
    project: Annotated[dict, Depends(get_authorized_project_for_analyze)],
    use_cache: bool = Query(True, description="Whether to read from cache"),
    engines: list[str] | None = Query(
        None, description="Engine codes to run; omit to run every engine"
    ),
    include_low: bool = Query(
        True,
        description=(
            "Emit Low-band verdicts. True by default: a Low verdict is an "
            "assessed finding, and suppressing it made whole engines look "
            "empty — every GC-001 finding on Clinic Plumbing bands Low. Set "
            "false for the Medium-and-above view. This selects what the run "
            "produces, unlike band/mechanism, which narrow what a page returns."
        ),
    ),
    limit: int | None = Query(
        None,
        ge=1,
        le=2000,
        description="Issues per page. Omit to return every matching issue.",
    ),
    offset: int = Query(0, ge=0, description="Issues to skip before the page"),
    band: list[IssueBand] | None = Query(
        None,
        description=(
            "Bands the returned issues are limited to; repeat for several. "
            "`data_quality` selects the notes rather than a verdict band. "
            "Filters audit_issues only — issue_stats still describes the whole run."
        ),
    ),
    mechanism: list[str] | None = Query(
        None,
        description=(
            "Engine code prefixes the returned issues are limited to, e.g. GC or "
            "GC-001. Same prefix semantics as `engines`, but applied to what is "
            "returned rather than to what runs. The token `data_quality` selects "
            "the data-quality notes instead."
        ),
    ),
    q: str | None = Query(
        None,
        max_length=200,
        description=(
            "Free-text filter over title, rule id, element id, mechanism and "
            "citation standard/clause — the fields the analyse page's search box "
            "already covers. Case-insensitive substring match."
        ),
    ),
    include_data_quality: bool = Query(
        True, description="Set false to leave data-quality notes out of the page"
    ),
    sort: PageSort | None = Query(
        None,
        description=(
            "Order the page is cut from, defaulting to band_then_score: the "
            "analyse page's order (criticals first), tiebroken on score then "
            "id. score_desc ignores bands; natural keeps the run's own order."
        ),
    ),
) -> AnalysisResultContract:
    """Get analysis results (retrieved from cache or computed on-demand).

    Sending no pagination parameter returns the whole run and no ``page``
    object, byte for byte what this endpoint returned before pagination
    existed. Sending any of ``limit``, a non-zero ``offset``, ``band``,
    ``mechanism``, ``q``, ``include_data_quality=false`` or ``sort`` narrows
    ``audit_issues`` and adds ``page``.

    ``include_low`` is the exception among the parameters above: it selects
    what the run computes, not what this page returns, so it changes the cache
    key and never adds a ``page`` object on its own.

    Narrowing happens after ``run_analysis`` has returned, so the cache keeps
    the whole run and two callers paging the same result share one computation.
    ``issue_stats`` always counts the whole run: a page of 200 criticals under
    a run of 22,827 findings still reports 22,827, because stats that shrank
    with the window would read as findings having disappeared.
    """
    if slug not in RUNNABLE_SLUGS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown analysis slug {slug!r}.",
        )
    raw_result = run_analysis(
        slug, project_id, use_cache=use_cache, engines=engines, include_low=include_low
    )
    if raw_result.get("compliance_error"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=raw_result["compliance_error"],
        )

    # Defaults are indistinguishable from an unsent parameter, and that is the
    # point: a request that asks for nothing in particular must not sprout a
    # `page` object that an existing consumer never expected to parse.
    paginating = (
        limit is not None
        or offset > 0
        or bool(band)
        or bool(mechanism)
        or not include_data_quality
        or sort is not None
        or bool(q and q.strip())
    )
    if not paginating:
        return _format_result(slug, project_id, raw_result)

    narrowed, page = _paginate_result(
        raw_result,
        limit=limit,
        offset=offset,
        bands=list(band) if band else None,
        mechanisms=mechanism,
        include_data_quality=include_data_quality,
        sort=sort or "band_then_score",
        query=q,
    )
    contract = _format_result(slug, project_id, narrowed)
    contract.page = page
    return contract


@router.get("/status/{project_id}", response_model=WorkflowStatusContract)
def get_workflow_status(
    project_id: int, project: Annotated[dict, Depends(get_authorized_project_for_analyze)]
) -> WorkflowStatusContract:
    """Get the current live workflow stages and metrics for a project."""
    snap = snapshot(project_id)
    raw_engines = snap.get("engines", {})
    return WorkflowStatusContract(
        project_id=project_id,
        status="running" if any(isinstance(e, dict) and e.get("status") == "running" for e in raw_engines.values()) else "idle",
        engines=raw_engines,
        timestamp=snap.get("timestamp"),
    )



@router.get("/export", summary="Export analysis report as BCF, CSV, or JSON")
def export_analysis_report(
    project_id: Annotated[int, Query(...)],
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker_flexible)],
    slug: str = Query("corrosion"),
    fmt: str = Query("bcf", description="Export format: bcf, csv, or json"),
    engines: list[str] | None = Query(
        None, description="Engine codes the export covers; omit for every engine"
    ),
    include_low: bool | None = Query(
        None,
        description=(
            "Emit Low-band verdicts. Defaults per format: true for CSV and "
            "JSON, which are the asset register and carry every assessed "
            "element; false for BCF, because the rulesets say a Low verdict is "
            "'asset register only — no BCF issue'. Pass it explicitly to "
            "override either default."
        ),
    ),
    band: list[IssueBand] | None = Query(
        None,
        description=(
            "Bands the export is limited to; repeat for several. "
            "`data_quality` selects the notes rather than a verdict band. "
            "Omit to export the format's default bands."
        ),
    ),
    include_data_quality: bool | None = Query(
        None,
        description=(
            "Keep data-quality notes. Defaults per format: true for CSV and "
            "JSON, false for BCF — a note saying an element could not be "
            "assessed is not a coordination issue to assign in Revit or "
            "Solibri, and 29,183 of them buried the verdicts in the audit."
        ),
    ),
):
    """Export compliance analysis findings into requested format.

    ``engines`` must match the selection the page ran, or the export reports a
    different set of findings from the results it was downloaded from.

    ONE RUN, FILTERED THREE WAYS

        The analysis is always requested with ``include_low=True`` and served
        from the cache when it is there, and ``include_low`` is then applied as
        a filter over that superset. The alternative — passing the caller's
        ``include_low`` into the run — forks the cache key, so downloading the
        Medium-and-above BCF for a page showing every band recomputed the whole
        analysis instead of reading what the page had just produced. Suppressing
        Low is a strict subtraction inside the engines (``data_quality`` notes
        are exempt from it either way), so filtering the superset yields the
        same issues the narrower run would have, from one cached result.
    """
    project_access(project_id)
    if slug not in RUNNABLE_SLUGS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown slug {slug!r}")

    # BCF is a coordination format: what lands in it becomes somebody's task.
    # CSV and JSON are the asset register, where an unassessed element is a row
    # worth having. Hence the split, rather than one default for all three.
    wants_bcf = fmt.strip().lower() == "bcf"
    keep_low = (not wants_bcf) if include_low is None else include_low
    keep_data_quality = (not wants_bcf) if include_data_quality is None else include_data_quality

    result = run_analysis(
        slug, project_id, use_cache=True, engines=engines, include_low=True
    )
    if result.get("compliance_error"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result["compliance_error"])

    # Apply band, Low and data_quality filtering to the export
    all_issues = result.get("audit_issues", [])
    if not keep_low:
        all_issues = [
            issue
            for issue in all_issues
            if _is_data_quality(issue) or _band_of(issue) != "low"
        ]
    filtered_issues = _select_issues(
        all_issues,
        bands=band,
        mechanisms=None,
        include_data_quality=keep_data_quality,
        query=None,
    )
    result = {
        **result,
        "audit_issues": filtered_issues,
    }

    try:
        content, media_type, extension = export(result, fmt)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    filename = f"bimguard-{slug}-project-{project_id}.{extension}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/arch", response_model=ArchAnalysisResponse, summary="Run architectural compliance analysis")
def run_arch_analysis(
    project_id: Annotated[int, Form(...)],
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker)],
    rule_folder: Annotated[str, Form()] = "",
    arch_service: ArchAnalysisService = Depends(get_arch_analysis_service),
) -> ArchAnalysisResponse:
    """Run architectural compliance checks (egress, daylight, fire separations, clearances) against the active building-code ruleset."""
    project_access(project_id)
    try:
        return arch_service.run_analysis(project_id=project_id, rule_folder=rule_folder)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.get("/arch/{project_id}", response_model=ArchAnalysisResponse, summary="Get architectural compliance results")
def get_arch_analysis(
    project_id: int,
    project: Annotated[dict, Depends(get_authorized_project_for_analyze)],
    arch_service: ArchAnalysisService = Depends(get_arch_analysis_service),
) -> ArchAnalysisResponse:
    """Retrieve architectural compliance findings for a project."""
    try:
        return arch_service.run_analysis(project_id=project_id, rule_folder="")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


# ---------------------------------------------------------------------------
# BCF Report Artifact Endpoints
# ---------------------------------------------------------------------------


@router.get("/bcf/artifacts/{artifact_id}", summary="Download BCF artifact by ID")
def download_bcf_artifact(
    artifact_id: int,
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker_flexible)],
):
    """Download a stored BCF 2.1 report archive by artifact primary key."""
    from fastapi.responses import FileResponse

    from app.services.report_artifacts import ReportArtifactService

    report_svc = ReportArtifactService()
    artifact = report_svc.get_bcf(artifact_id)
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BCF artifact {artifact_id} not found.",
        )
    # 404 (not 403) if the artifact's project isn't the caller's: an artifact
    # id is a small guessable integer, and confirming an inaccessible one
    # exists is exactly the information get_authorized_project also withholds.
    project_access(artifact["project_id"])

    bcf_path = report_svc.materialize(artifact)
    if bcf_path is None or not bcf_path.exists():
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not retrieve the BCF file from storage.",
        )

    filename = artifact.get("filename") or f"compliance_artifact_{artifact_id}.bcf"
    return FileResponse(
        str(bcf_path),
        media_type=artifact.get("content_type") or "application/octet-stream",
        filename=filename,
    )


@router.get("/bcf/latest/{project_id}", summary="Download latest BCF for a project")
def download_latest_bcf(project_id: int, project: Annotated[dict, Depends(get_authorized_project_for_analyze_flexible)]):
    """Retrieve the latest BCF 2.1 archive generated for a project."""
    from fastapi.responses import FileResponse

    from app.services.report_artifacts import ReportArtifactService

    report_svc = ReportArtifactService()
    artifact = report_svc.latest_bcf(project_id)
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No BCF artifacts found for project {project_id}.",
        )

    bcf_path = report_svc.materialize(artifact)
    if bcf_path is None or not bcf_path.exists():
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not retrieve the BCF file from storage.",
        )

    filename = artifact.get("filename") or f"compliance_project_{project_id}.bcf"
    return FileResponse(
        str(bcf_path),
        media_type=artifact.get("content_type") or "application/octet-stream",
        filename=filename,
    )


@router.get("/bcf/list", response_model=list[dict[str, Any]], summary="List all persisted BCF artifacts")
def list_bcf_artifacts(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    projects_service: Annotated[ProjectsService, Depends(get_projects_service)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
) -> list[dict[str, Any]]:
    """List persisted BCF report artifacts ordered newest first.

    A superadmin sees every artifact; everyone else only the ones whose
    project they can access, matching how ``/projects`` itself is scoped.
    """
    from app.services.report_artifacts import ReportArtifactService

    artifacts = ReportArtifactService().list_bcf()
    if profiles.is_superadmin(current_user.id):
        return artifacts

    accessible_projects: dict[int, bool] = {}

    def _is_accessible(pid: int | None) -> bool:
        if pid is None:
            return False
        if pid not in accessible_projects:
            project = projects_service.get_project(pid)
            accessible_projects[pid] = bool(
                project and _can_access_project(project, current_user.id, memberships)
            )
        return accessible_projects[pid]

    return [a for a in artifacts if _is_accessible(a.get("project_id"))]


@router.delete("/bcf/artifacts/{artifact_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete BCF artifact by ID")
def delete_bcf_artifact(
    artifact_id: int,
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker)],
) -> None:
    """Delete a persisted BCF report artifact."""
    from app.services.report_artifacts import ReportArtifactService

    report_svc = ReportArtifactService()
    artifact = report_svc.get_bcf(artifact_id)
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BCF artifact {artifact_id} not found.",
        )
    project_access(artifact["project_id"])

    deleted = report_svc.delete_bcf(artifact_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BCF artifact {artifact_id} not found.",
        )



# ---------------------------------------------------------------------------
# Revit Direct Sync Endpoint
# ---------------------------------------------------------------------------


@router.post("/revit-sync", response_model=RevitSyncResponse, summary="Direct Revit pyRevit synchronization")
def sync_revit_elements(
    payload: RevitSyncRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> RevitSyncResponse:
    """Accept element data pushed directly from Revit/pyRevit, run compliance checks, and return verdicts.

    Not project-scoped: the payload is ad-hoc element data validated against
    the active ruleset, not read from or written to a stored project, so
    there is nothing beyond "is this a signed-in caller" to check.
    """
    from app.services.pipeline_services import PipelineOrchestratorService
    from app.services.revit_sync_service import RevitSyncService

    sync_service = RevitSyncService()
    elements = [el.model_dump() for el in payload.elements]
    theme = payload.theme or "Architecture"

    extraction = sync_service.build_extraction_results(elements, theme)
    compliance = PipelineOrchestratorService.validate_metadata(extraction)
    summary = PipelineOrchestratorService.render_visual_report(compliance)

    results: list[RevitRuleResult] = []
    for r in compliance:
        results.append(
            RevitRuleResult(
                rule_ref=r.get("rule_ref"),
                rule_desc=r.get("rule_desc"),
                target=r.get("target"),
                property_name=r.get("property_name"),
                status=r.get("status"),
                pass_count=r.get("pass_count", 0),
                fail_count=r.get("fail_count", 0),
                missing_count=r.get("missing_count", 0),
                failures=r.get("failures", []) or [],
            )
        )

    return RevitSyncResponse(
        element_count=len(elements),
        theme=theme,
        summary=summary if isinstance(summary, dict) else {},
        results=results,
    )



