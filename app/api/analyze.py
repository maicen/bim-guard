"""FastAPI router for compliance analysis, IFC upload, and report exports."""

from __future__ import annotations

from typing import Annotated, Any

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

from app.api.dependencies import get_phase6_service, get_projects_service
from app.logging_config import get_logger
from app.modules.contracts import (
    AnalysisResultContract,
    AnalysisRunRequest,
    AuditIssueContract,
    IssueStatsContract,
    WorkflowStatusContract,
)
from app.modules.phase_6.phase_6e_export import export
from app.services.analysis_runner import RUNNABLE_SLUGS, run_analysis
from app.services.phase6_service import Phase6Service
from app.services.pipeline_tracker import snapshot
from app.services.projects_service import ProjectsService

logger = get_logger(__name__)

router = APIRouter()


def _format_result(slug: str, project_id: int, result: dict) -> AnalysisResultContract:
    """Format raw analysis result dictionary into strict Pydantic model."""
    raw_issues = result.get("audit_issues", [])
    issues: list[AuditIssueContract] = []
    for i in raw_issues:
        band_val = getattr(i.band, "value", str(i.band)).lower()
        issues.append(
            AuditIssueContract(
                id=i.id,
                element_id=i.element_id,
                rule_id=i.rule_id,
                title=i.title,
                band=band_val,
                score=i.score,
                mechanism=i.mechanism,
                description=i.description or "",
                mitigation=i.mitigation or "",
                details=dict(i.metadata) if hasattr(i, "metadata") else {},
            )
        )

    raw_stats = result.get("issue_stats", {})
    stats = IssueStatsContract(
        total=raw_stats.get("total", len(issues)),
        critical=raw_stats.get("critical", 0),
        high=raw_stats.get("high", 0),
        medium=raw_stats.get("medium", 0),
        low=raw_stats.get("low", 0),
    )

    return AnalysisResultContract(
        pipeline="audit",
        project_id=project_id,
        slug=slug,
        element_count=len(issues),
        audit_issues=issues,
        issue_stats=stats,
        compliance_error=result.get("compliance_error"),
        cached=result.get("cached", False),
    )


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

    if background:
        background_tasks.add_task(run_analysis, slug, payload.project_id)
        return {
            "status": "queued",
            "project_id": payload.project_id,
            "slug": slug,
            "message": "Analysis started in background.",
        }

    raw_result = run_analysis(slug, payload.project_id)
    if raw_result.get("compliance_error"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=raw_result["compliance_error"],
        )
    return _format_result(slug, payload.project_id, raw_result)


@router.post("/corrosion", summary="Run corrosion analysis")
def run_corrosion(
    project_id: Annotated[int, Form(...)],
) -> AnalysisResultContract:
    """Run GC-001, CC-001, MC-001 corrosion engines."""
    raw_result = run_analysis("corrosion", project_id)
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
    raw_result = run_analysis("seismic", project_id)
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
) -> AnalysisResultContract:
    """Get analysis results (retrieved from cache or computed on-demand)."""
    if slug not in RUNNABLE_SLUGS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown analysis slug {slug!r}.",
        )
    raw_result = run_analysis(slug, project_id)
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
):
    """Export compliance analysis findings into requested format."""
    if slug not in RUNNABLE_SLUGS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown slug {slug!r}")

    result = run_analysis(slug, project_id)
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


@router.post("/arch", summary="Run architectural compliance analysis")
def run_arch_analysis(
    project_id: Annotated[int, Form(...)],
    rule_folder: Annotated[str, Form()] = "",
) -> dict:
    """Run Ontario Building Code Part 9 architectural checks (egress, daylight, fire separations, clearances)."""
    from app.services.pipeline_services import PipelineOrchestratorService

    result = PipelineOrchestratorService.orchestrate_workflow(
        project_id=project_id,
        analysis_theme="Architecture",
        rule_folder=rule_folder,
    )
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"],
        )

    categories = result.get("categories", {})
    issues = result.get("issues", [])
    project = result.get("project", {})

    return {
        "project_id": project_id,
        "project_name": project.get("name", f"Project {project_id}"),
        "categories": categories,
        "total_issues": len(issues),
        "issues": issues,
        "summary": result.get("summary", {}),
    }


@router.get("/arch/{project_id}", summary="Get architectural compliance results")
def get_arch_analysis(project_id: int) -> dict:
    """Retrieve architectural compliance findings for a project."""
    return run_arch_analysis(project_id=project_id)


