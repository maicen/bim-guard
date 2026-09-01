"""FastAPI router for compliance analysis, IFC upload, and report exports."""

from __future__ import annotations

from typing import Annotated

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
    get_phase6_service,
    get_projects_service,
)
from app.logging_config import get_logger
from app.modules.contracts import (
    AnalysisResultContract,
    AnalysisRunRequest,
    ArchAnalysisResponse,
    AuditIssueContract,
    IssueStatsContract,
    RevitRuleResult,
    RevitSyncRequest,
    RevitSyncResponse,
    WorkflowStatusContract,
)
from app.modules.phase_6.phase_6e_export import export
from app.services.analysis_runner import RUNNABLE_SLUGS, run_analysis
from app.services.arch_analysis_service import ArchAnalysisService
from app.services.phase6_service import Phase6Service
from app.services.pipeline_tracker import snapshot
from app.services.projects_service import ProjectsService

logger = get_logger(__name__)

router = APIRouter()


#: Corrosion engine codes a corrosion run may be narrowed to, matching the
#: ``MechanismSpec.code`` values in ``phase_6c_corrosion_ui``. Issues carry rule
#: ids like "GC-001.01" and "GC-001.DATA", so a prefix match selects an engine's
#: verdicts and its data-quality notes together.
SELECTABLE_ENGINES: tuple[str, ...] = ("GC-001", "CC-001", "MC-001")


def _filter_issues_by_engine(result: dict, engines: list[str]) -> dict:
    """Narrow an ``AnalysisResult`` to the issues the given engines raised.

    Applied to what ``run_analysis`` returns rather than inside it, deliberately:
    the analysis cache is keyed on (project, slug, model digest) with no engine
    dimension, so narrowing before the cache write would store a partial run
    under the key that the next caller asking for everything would hit.

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
    stats = {"total": 0, "critical": 0, "high": 0, "medium": 0, "low": 0, "data_quality": 0}
    for issue in kept:
        if issue.mechanism == "data_quality":
            stats["data_quality"] += 1
            continue
        stats["total"] += 1
        band = getattr(issue.band, "value", str(issue.band)).lower()
        if band in stats:
            stats[band] += 1

    return {**result, "audit_issues": kept, "issue_stats": stats}


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


@router.post("/upload", summary="Attach an IFC model to a project")
async def analyze_upload_ifc(
    project_id: Annotated[int, Form(...)],
    ifc_file: Annotated[UploadFile, File(...)],
    projects_service: Annotated[ProjectsService, Depends(get_projects_service)],
    phase6_service: Annotated[Phase6Service, Depends(get_phase6_service)],
) -> dict:
    """Upload and attach an IFC model to a project."""
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
    return {
        "success": True,
        "filename": response.ref.filename,
        "size_bytes": response.ref.size_bytes,
        "sha256": response.ref.file_hash_sha256,
    }


@router.post("/run", summary="Trigger compliance analysis")
def run_analysis_endpoint(
    payload: AnalysisRunRequest,
    background_tasks: BackgroundTasks,
    background: bool = Query(False, description="Run in background task if true"),
) -> AnalysisResultContract | dict:
    """Execute analysis (corrosion or seismic) for a project."""
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
        )
        return {
            "status": "queued",
            "project_id": payload.project_id,
            "slug": slug,
            "message": "Analysis started in background.",
        }

    raw_result = run_analysis(
        slug, payload.project_id, use_cache=payload.use_cache, engines=engines
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
    engines: Annotated[list[str] | None, Form()] = None,
) -> AnalysisResultContract:
    """Run the selected corrosion engines (GC-001, CC-001, MC-001).

    Omitting ``engines`` runs all three; naming a subset runs only those, and
    the rest are never entered.
    """
    raw_result = run_analysis("corrosion", project_id, use_cache=False, engines=engines)
    if raw_result.get("compliance_error"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=raw_result["compliance_error"],
        )
    return _format_result("corrosion", project_id, raw_result)


@router.post("/seismic", summary="Run seismic clearance analysis")
def run_seismic(
    project_id: Annotated[int, Form(...)],
) -> AnalysisResultContract:
    """Run Blue Halo seismic clearance volume validation."""
    raw_result = run_analysis("seismic", project_id, use_cache=False)
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
    use_cache: bool = Query(True, description="Whether to read from cache"),
    engines: list[str] | None = Query(
        None, description="Engine codes to run; omit to run every engine"
    ),
) -> AnalysisResultContract:
    """Get analysis results (retrieved from cache or computed on-demand)."""
    if slug not in RUNNABLE_SLUGS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown analysis slug {slug!r}.",
        )
    raw_result = run_analysis(slug, project_id, use_cache=use_cache, engines=engines)
    if raw_result.get("compliance_error"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=raw_result["compliance_error"],
        )
    return _format_result(slug, project_id, raw_result)


@router.get("/status/{project_id}", response_model=WorkflowStatusContract)
def get_workflow_status(project_id: int) -> WorkflowStatusContract:
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
    project_id: int = Query(...),
    slug: str = Query("corrosion"),
    fmt: str = Query("bcf", description="Export format: bcf, csv, or json"),
    engines: list[str] | None = Query(
        None, description="Engine codes the export covers; omit for every engine"
    ),
):
    """Export compliance analysis findings into requested format.

    ``engines`` must match the selection the page ran, or the export reports a
    different set of findings from the results it was downloaded from.
    """
    if slug not in RUNNABLE_SLUGS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown slug {slug!r}")

    result = run_analysis(slug, project_id, engines=engines)
    if result.get("compliance_error"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result["compliance_error"])

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
    rule_folder: Annotated[str, Form()] = "",
    arch_service: ArchAnalysisService = Depends(get_arch_analysis_service),
) -> ArchAnalysisResponse:
    """Run Ontario Building Code Part 9 architectural checks (egress, daylight, fire separations, clearances)."""
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
    arch_service: ArchAnalysisService = Depends(get_arch_analysis_service),
) -> ArchAnalysisResponse:
    """Retrieve architectural compliance findings for a project."""
    return run_arch_analysis(project_id=project_id, arch_service=arch_service)


# ---------------------------------------------------------------------------
# BCF Report Artifact Endpoints
# ---------------------------------------------------------------------------


@router.get("/bcf/artifacts/{artifact_id}", summary="Download BCF artifact by ID")
def download_bcf_artifact(artifact_id: int):
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
def download_latest_bcf(project_id: int):
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


@router.get("/bcf/list", summary="List all persisted BCF artifacts")
def list_bcf_artifacts() -> list[dict]:
    """List all persisted BCF report artifacts ordered newest first."""
    from app.services.report_artifacts import ReportArtifactService

    return ReportArtifactService().list_bcf()


@router.delete("/bcf/artifacts/{artifact_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete BCF artifact by ID")
def delete_bcf_artifact(artifact_id: int) -> None:
    """Delete a persisted BCF report artifact."""
    from app.services.report_artifacts import ReportArtifactService

    deleted = ReportArtifactService().delete_bcf(artifact_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BCF artifact {artifact_id} not found.",
        )



# ---------------------------------------------------------------------------
# Revit Direct Sync Endpoint
# ---------------------------------------------------------------------------


@router.post("/revit-sync", response_model=RevitSyncResponse, summary="Direct Revit pyRevit synchronization")
def sync_revit_elements(payload: RevitSyncRequest) -> RevitSyncResponse:
    """Accept element data pushed directly from Revit/pyRevit, run compliance checks, and return verdicts."""
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



