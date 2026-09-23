"""FastAPI router for compliance analysis, IFC upload, and report exports."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)

from app.api.dependencies import (
    get_arch_analysis_service,
    get_ifc_pipeline_service,
    get_membership_service,
    get_models_service,
    get_profile_service,
    get_projects_service,
    get_report_service,
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
from app.modules.pipeline_io.analysis_result_exporter import export
from app.services.analysis_runner import RUNNABLE_SLUGS, run_analysis
from app.services.arch_analysis_service import ArchAnalysisService
from app.services.ifc_pipeline_service import IFCPipelineService
from app.services.membership_service import MembershipService
from app.services.models_service import ModelsService
from app.services.profile_service import ProfileService
from app.services.project_visibility import visible_project_rows
from app.services.projects_service import ProjectsService
from app.services.report_csv import render_report_csv
from app.services.report_excel import render_report_excel
from app.services.report_rendering import render_report_html, render_report_pdf
from app.services.report_service import ReportService
from app.services.workflow_status import status_snapshot

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
        shacl_issues=result.get("shacl_issues", []),
        shacl_error=result.get("shacl_error"),
    )


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


def _source_files_for(project_id: int) -> list[dict]:
    """Return the project's attached models for a BCF export's ``Header``.

    ``[{"filename": ..., "date": ...}, ...]`` naming each attached IFC and when
    it was uploaded, so a topic's ``Header/File`` names the model it was
    actually computed from instead of the placeholder ``BIMGUARD_AI_Model.ifc``.

    A project whose models cannot be resolved yields an empty list rather than
    raising: a Header that names no file is a smaller failure than an export
    that does not happen.
    """
    try:
        resolved, _missing = ModelsService(
            project_mirror=ProjectsService()
        ).resolve_all_paths(project_id)
    except Exception:
        logger.warning("Could not resolve model filenames for project %s", project_id)
        return []
    files: list[dict] = []
    for row, _path in resolved:
        name = str((row or {}).get("file_name") or "").strip()
        if not name:
            continue
        files.append({"filename": name, "date": str((row or {}).get("uploaded_at") or "")})
    return files


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

    ``mechanisms`` is a case-insensitive prefix match on ``rule_id``, so
    ``ARCH`` and ``ARCH-EGRESS-001`` both select an engine's verdicts together
    with its ``.DATA`` notes; the token ``data_quality`` selects the notes on
    their own. Several values union, so ``ARCH`` and ``data_quality`` together
    select both.

    An unrecognised mechanism selects nothing rather than falling back to
    everything: the caller is filtering a view, and quietly widening it back
    to the full run would misreport what was asked for.
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

    Applied to what ``run_analysis`` returned rather than inside it: the cache
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
    models_service: Annotated[ModelsService, Depends(get_models_service)],
    ifc_pipeline_service: Annotated[IFCPipelineService, Depends(get_ifc_pipeline_service)],
) -> IfcUploadAttachResponse:
    """Upload and attach an IFC model to a project."""
    project_access(project_id)
    if not ifc_file.filename or not ifc_file.filename.lower().endswith(".ifc"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid .ifc file is required.",
        )

    content = await ifc_file.read()
    response = ifc_pipeline_service.upload_service.upload(
        ifc_file.filename, content, project_id=project_id, kind="ifc"
    )
    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=response.error or "Upload failed.",
        )

    models_service.attach_model(
        project_id,
        file_path=response.ref.storage_ref,
        file_name=response.ref.filename,
        is_primary=True,
    )
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
    """Execute architectural compliance analysis for a project."""
    project_access(payload.project_id)
    slug = payload.slug.lower()
    if slug not in RUNNABLE_SLUGS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown analysis slug {slug!r}. Supported: {RUNNABLE_SLUGS}",
        )

    if background:
        background_tasks.add_task(
            run_analysis,
            slug,
            payload.project_id,
            use_cache=payload.use_cache,
            enable_shacl=payload.enable_shacl,
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
        enable_shacl=payload.enable_shacl,
    )
    if raw_result.get("compliance_error"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=raw_result["compliance_error"],
        )
    return _format_result(slug, payload.project_id, raw_result)


@router.post("/lbd/{project_id}", summary="Persist BOT graph and SHACL evaluation to triplestore")
def run_lbd_persistence(
    project_id: int,
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker)],
) -> dict[str, Any]:
    """Execute SHACL compliance and persist the BOT graph to the triplestore."""
    project_access(project_id)

    # We call run_analysis for 'architecture' with enable_shacl=True. The
    # orchestrator is wired with the triplestore service, and saves the graph
    # during the SHACL step -- but only when that step actually runs.
    # use_cache is forced off: `enable_shacl` is part of the cache key
    # (analysis_cache.CacheKey), so a prior cached run with SHACL enabled
    # (e.g. from the "SHACL (preview)" toggle) would otherwise short-circuit
    # orchestrate_workflow entirely and skip the persistence side effect,
    # while this endpoint still reported success.
    raw_result = run_analysis("architecture", project_id, use_cache=False, enable_shacl=True)

    if raw_result.get("compliance_error"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=raw_result["compliance_error"],
        )
        
    return {
        "success": True,
        "message": "BOT graph successfully persisted to triplestore.",
        "project_id": project_id,
        "shacl_issues": raw_result.get("shacl_issues", []),
    }


@router.get("/results/{project_id}/{slug}", response_model=AnalysisResultContract)
def get_analysis_results(
    project_id: int,
    slug: str,
    project: Annotated[dict, Depends(get_authorized_project_for_analyze)],
    use_cache: bool = Query(True, description="Whether to read from cache"),
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
            "Engine code prefixes the returned issues are limited to. The "
            "token `data_quality` selects the data-quality notes instead."
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
    enable_shacl: bool = Query(False, description="Enable SHACL validation side-channel"),
) -> AnalysisResultContract:
    """Get analysis results (retrieved from cache or computed on-demand).

    Sending no pagination parameter returns the whole run and no ``page``
    object, byte for byte what this endpoint returned before pagination
    existed. Sending any of ``limit``, a non-zero ``offset``, ``band``,
    ``mechanism``, ``q``, ``include_data_quality=false`` or ``sort`` narrows
    ``audit_issues`` and adds ``page``.

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
    raw_result = run_analysis(slug, project_id, use_cache=use_cache, enable_shacl=enable_shacl)
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
    """Get the current live workflow stages and metrics for a project.

    Merged across run keys, so the polled fallback reports a graph run exactly
    as the SSE stream does. Without the merge the two disagreed:
    the stream carried the events and this reported every engine as pending.

    ``status`` is the overall run state shared with the SSE ``status`` frames
    (:func:`app.services.workflow_status.overall_status`): ``complete`` or
    ``failed`` once every engine of the active run has finished, rather than
    falling back to ``idle`` the moment nothing is running.
    """
    snap = status_snapshot(project_id)
    return WorkflowStatusContract(
        project_id=project_id,
        status=snap["status"],
        run_key=snap.get("run_key", "default"),
        engines=snap.get("engines", {}),
        timestamp=snap.get("timestamp"),
    )



@router.get("/export", summary="Export analysis report as BCF, CSV or JSON")
def export_analysis_report(
    project_id: Annotated[int, Query(...)],
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker_flexible)],
    slug: str = Query("architecture"),
    fmt: str = Query("bcf", description="Export format: bcf, csv or json."),
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

    result = run_analysis(slug, project_id, use_cache=True)
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
        "source_files": _source_files_for(project_id),
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


@router.get("/report/{project_id}", summary="Render a compliance report as PDF, HTML or Excel")
def get_analysis_report(
    project_id: int,
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker_flexible)],
    slug: str = Query("architecture"),
    format: str = Query(
        "pdf", description="Output format: pdf (download), html (in-app preview) or xlsx (working punch-list)."
    ),
    report_service: ReportService = Depends(get_report_service),
):
    """Render the project's latest compliance analysis as a formatted report.

    Built from ``rule_compliance``/``rule_compliance_summary`` (see
    ``ReportService``), not from ``audit_issues`` -- the only source in this
    run that records a rule having *passed*, which the report's executive
    summary and pass-rate figures depend on. Deterministic: no LLM, every
    number and sentence comes from the analysis run and a fixed template.

    The PDF caps its findings register (see
    ``ReportModel.findings_register_truncated``); ``xlsx`` is the uncapped,
    filterable counterpart with blank Status/Assigned To/Resolved
    Date/Notes columns for the user's own remediation tracking.
    """
    project_access(project_id)
    if slug not in RUNNABLE_SLUGS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown slug {slug!r}")

    try:
        model = report_service.build_report_model(project_id, slug)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    fmt = format.strip().lower()
    if fmt == "html":
        return Response(content=render_report_html(model, render_target="full"), media_type="text/html")
    if fmt == "xlsx":
        filename = f"bimguard-report-{slug}-project-{project_id}.xlsx"
        return Response(
            content=render_report_excel(model),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    if fmt != "pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported report format {format!r}; expected pdf, html or xlsx.",
        )

    try:
        pdf_bytes = render_report_pdf(model)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    filename = f"bimguard-report-{slug}-project-{project_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/arch", response_model=ArchAnalysisResponse, summary="Run architectural compliance analysis")
def run_arch_analysis(
    project_id: Annotated[int, Form(...)],
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    rule_folder: Annotated[str, Form()] = "",
    arch_service: ArchAnalysisService = Depends(get_arch_analysis_service),
) -> ArchAnalysisResponse:
    """Run architectural compliance checks (egress, daylight, fire separations, clearances) against the active building-code ruleset."""
    project_access(project_id)
    try:
        return arch_service.run_analysis(
            project_id=project_id,
            rule_folder=rule_folder,
            created_by=current_user.id,
            created_by_email=current_user.email,
        )
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
    organization_id: Optional[int] = Query(None, description="Filter by organization ID"),
    x_org_id: Optional[str] = Header(None, alias="X-Organization-Id"),
) -> list[dict[str, Any]]:
    """List persisted BCF report artifacts ordered newest first.

    With no organization_id, a superadmin sees every artifact and everyone
    else sees only the ones whose project they can access across all their
    orgs. When organization_id is given (via query or X-Organization-Id
    header), results are further narrowed to that org's visible projects
    using the same rules as GET /api/projects, so the Reports page and the
    dashboard's "Issues Identified" count never disagree about which
    projects' reports are in view for a given org.
    """
    from app.services.report_artifacts import ReportArtifactService

    artifacts = ReportArtifactService().list_bcf()
    return _visible_report_artifacts(
        artifacts,
        current_user=current_user,
        projects_service=projects_service,
        memberships=memberships,
        profiles=profiles,
        organization_id=organization_id,
        x_org_id=x_org_id,
    )


def _visible_report_artifacts(
    artifacts: list[dict[str, Any]],
    *,
    current_user: CurrentUser,
    projects_service: ProjectsService,
    memberships: MembershipService,
    profiles: ProfileService,
    organization_id: Optional[int],
    x_org_id: Optional[str],
) -> list[dict[str, Any]]:
    """Narrow *artifacts* to the ones whose project the caller may see.

    Shared by every report-artifact list endpoint (BCF, PDF, CSV) -- see
    ``list_bcf_artifacts`` for the visibility rules this implements.
    """
    effective_org_id: Optional[int] = organization_id
    if effective_org_id is None and x_org_id and x_org_id.strip().isdigit():
        effective_org_id = int(x_org_id.strip())

    if effective_org_id is not None:
        visible_ids = {
            row.get("id")
            for row in visible_project_rows(
                projects_service.list_projects(),
                user_id=current_user.id,
                organization_id=effective_org_id,
                memberships=memberships,
                profiles=profiles,
            )
        }
        return [a for a in artifacts if a.get("project_id") in visible_ids]

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
# Generic Report Artifact Endpoints (PDF / CSV; BCF's routes above stay as-is)
# ---------------------------------------------------------------------------

#: Formats the "save and download" buttons can persist on demand. BCF isn't
#: here -- it's already persisted automatically by POST /arch whenever a run
#: produces findings, so a second, explicit save action for it would just
#: create a duplicate row.
_PERSISTABLE_ARTIFACT_TYPES = {"pdf", "csv", "xlsx"}
#: Every type report_artifacts can hold, for the read-only routes below.
_REPORT_ARTIFACT_TYPES = {"bcf", "pdf", "csv", "xlsx"}


@router.post("/report-artifacts/{artifact_type}", summary="Save a ruleset-scoped PDF, CSV or Excel report")
def persist_report_artifact(
    artifact_type: str,
    project_id: Annotated[int, Form(...)],
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    rule_folder: Annotated[str, Form()] = "",
    arch_service: ArchAnalysisService = Depends(get_arch_analysis_service),
    report_service: ReportService = Depends(get_report_service),
) -> dict[str, Any]:
    """Render and persist a ruleset-scoped PDF, CSV or Excel report.

    Backs the audit page's "PDF" / "CSV" / "Excel" save-and-download buttons.
    Scoped to whatever ``rule_folder`` was run (blank means "All Rules"), the
    same way BCF already is -- built from
    ``ArchAnalysisService.compute_rule_compliance``, which runs the
    orchestrator fresh for this ruleset without the side effect of also
    persisting a BCF artifact.
    """
    if artifact_type not in _PERSISTABLE_ARTIFACT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported artifact type {artifact_type!r}; expected pdf, csv or xlsx.",
        )
    project_access(project_id)

    from app.services.report_artifacts import ReportArtifactService

    try:
        rule_compliance, rule_compliance_summary = arch_service.compute_rule_compliance(project_id, rule_folder)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    model = report_service.build_report_model_from_run(project_id, rule_compliance, rule_compliance_summary)
    ruleset_name = arch_service.resolve_ruleset_name(rule_folder)
    issue_count = model.executive_summary.failed
    report_svc = ReportArtifactService()

    if artifact_type == "pdf":
        content = render_report_pdf(model)
        filename = f"bimguard-report-project-{project_id}.pdf"
        artifact = report_svc.persist_pdf(
            project_id,
            content,
            filename,
            issue_count=issue_count,
            rule_folder=rule_folder,
            ruleset_name=ruleset_name,
            created_by=current_user.id,
            created_by_email=current_user.email,
        )
    elif artifact_type == "xlsx":
        content = render_report_excel(model)
        filename = f"bimguard-report-project-{project_id}.xlsx"
        artifact = report_svc.persist_xlsx(
            project_id,
            content,
            filename,
            issue_count=issue_count,
            rule_folder=rule_folder,
            ruleset_name=ruleset_name,
            created_by=current_user.id,
            created_by_email=current_user.email,
        )
    else:
        content = render_report_csv(model)
        filename = f"bimguard-report-project-{project_id}.csv"
        artifact = report_svc.persist_csv(
            project_id,
            content,
            filename,
            issue_count=issue_count,
            rule_folder=rule_folder,
            ruleset_name=ruleset_name,
            created_by=current_user.id,
            created_by_email=current_user.email,
        )

    return artifact


@router.get(
    "/report-artifacts/{artifact_type}/{artifact_id}", summary="Download a BCF/PDF/CSV/Excel report artifact by ID"
)
def download_report_artifact(
    artifact_type: str,
    artifact_id: int,
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker_flexible)],
):
    """Download a persisted BCF, PDF or CSV report archive by artifact primary key."""
    if artifact_type not in _REPORT_ARTIFACT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown artifact type {artifact_type!r}."
        )

    from fastapi.responses import FileResponse

    from app.services.report_artifacts import ReportArtifactService

    report_svc = ReportArtifactService()
    artifact = report_svc.get(artifact_id, artifact_type)
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{artifact_type.upper()} artifact {artifact_id} not found.",
        )
    # 404 (not 403) if the artifact's project isn't the caller's -- same
    # reasoning as download_bcf_artifact above.
    project_access(artifact["project_id"])

    file_path = report_svc.materialize(artifact)
    if file_path is None or not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not retrieve the report file from storage.",
        )

    filename = artifact.get("filename") or f"compliance_artifact_{artifact_id}.{artifact_type}"
    return FileResponse(
        str(file_path),
        media_type=artifact.get("content_type") or "application/octet-stream",
        filename=filename,
    )


@router.get(
    "/report-artifacts/{artifact_type}",
    response_model=list[dict[str, Any]],
    summary="List persisted report artifacts by type",
)
def list_report_artifacts(
    artifact_type: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    projects_service: Annotated[ProjectsService, Depends(get_projects_service)],
    memberships: Annotated[MembershipService, Depends(get_membership_service)],
    profiles: Annotated[ProfileService, Depends(get_profile_service)],
    organization_id: Optional[int] = Query(None, description="Filter by organization ID"),
    x_org_id: Optional[str] = Header(None, alias="X-Organization-Id"),
) -> list[dict[str, Any]]:
    """List persisted report artifacts of one type, newest first.

    Same visibility rules as ``GET /bcf/list`` -- see that docstring.
    """
    if artifact_type not in _REPORT_ARTIFACT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown artifact type {artifact_type!r}."
        )

    from app.services.report_artifacts import ReportArtifactService

    artifacts = ReportArtifactService().list_by_type(artifact_type)
    return _visible_report_artifacts(
        artifacts,
        current_user=current_user,
        projects_service=projects_service,
        memberships=memberships,
        profiles=profiles,
        organization_id=organization_id,
        x_org_id=x_org_id,
    )


@router.delete(
    "/report-artifacts/{artifact_type}/{artifact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a report artifact by ID",
)
def delete_report_artifact(
    artifact_type: str,
    artifact_id: int,
    project_access: Annotated[ProjectAccessChecker, Depends(get_project_access_checker)],
) -> None:
    """Delete a persisted BCF, PDF or CSV report artifact."""
    if artifact_type not in _REPORT_ARTIFACT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown artifact type {artifact_type!r}."
        )

    from app.services.report_artifacts import ReportArtifactService

    report_svc = ReportArtifactService()
    artifact = report_svc.get(artifact_id, artifact_type)
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{artifact_type.upper()} artifact {artifact_id} not found.",
        )
    project_access(artifact["project_id"])

    deleted = report_svc.delete(artifact_id, artifact_type)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{artifact_type.upper()} artifact {artifact_id} not found.",
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



