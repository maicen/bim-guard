"""HTTP surface for the Phase 6 pipeline.

The Phase 6 sessions are libraries; this module is the orchestration layer that
makes them reachable. It owns the four POST/GET endpoints the analyse pages
drive, and nothing else — the stages themselves stay in
``app/modules/phase_6/``.

    POST /analyze/upload      attach an IFC model to a project (Session A)
    POST /analyze/corrosion   parse + run GC/CC/MC (Sessions B, C)
    POST /analyze/seismic     run Blue Halo clearance detection (Session D)
    GET  /analyze/export      download BCF / CSV / JSON (Session E)

HTMX CONTRACT

    Every POST here is called via ``hx_post`` from an analyse page and returns
    a **fragment** — never ``Title`` or ``DashboardLayout``. The export route is
    a plain GET because it returns a file download, which HTMX cannot swap.

WHY EXPORT RE-RUNS THE ANALYSIS

    Export needs an ``AnalysisResult``, and there is nowhere to keep one between
    requests. ``analyze.py`` solves this with module-level globals
    (``_last_simple_compliance``), which are per-process and leak across users.
    Re-running is slower but stateless and correct: the file you download is
    computed from the model as it is now, not from whatever the last request
    happened to leave in memory.
"""

from __future__ import annotations

from fasthtml.common import Div, P, Request, Response, UploadFile

from app.components.ui import (
    Alert,
    AlertT,
    Card,
    CardContent,
    CardHeader,
    CardTitle,
    LinkButton,
)
from app.logging_config import get_logger
from app.modules.phase_6.phase_6a_upload import FileUploadService
from app.modules.phase_6.phase_6b_parsing import parse_ifc_bytes
from app.modules.phase_6.phase_6c_corrosion_ui import run_corrosion_analysis
from app.modules.phase_6.phase_6d_seismic import run_seismic_analysis
from app.modules.phase_6.phase_6e_export import DATA_QUALITY, FORMATS, export, sort_issues
from app.services.analysis_runner import run_analysis
from app.services.projects_service import ProjectsService

logger = get_logger(__name__)

_projects_service = ProjectsService()
_upload_service = FileUploadService()

#: Analysis slug -> the runner that produces its AnalysisResult. Keyed by the
#: same slugs as app.constants.ANALYSIS_ROUTES so a new analysis type wires
#: itself in one place.
_RUNNERS = ("corrosion", "seismic")


def _error(message: str) -> Div:
    """Render a failure as a fragment the page can swap in."""
    return Div(Alert(message, cls=AlertT.error), cls="space-y-4")


def _run(slug: str, project_id: int) -> dict:
    """Return the ``AnalysisResult`` for one project.

    Delegates to :func:`app.services.analysis_runner.run_analysis`, which the
    download endpoints also call — so a report downloaded from this page is the
    same computation the page rendered, and both are cached on the model digest.

    It is also the instrumented path: ``run_analysis`` reports each stage to
    :mod:`app.services.pipeline_tracker`, which is what
    ``GET /api/workflow/{project_id}`` serves to the live dashboard. Running the
    check from anywhere else would leave that dashboard showing "pending"
    through a run that was actually in flight.
    """
    return run_analysis(slug, project_id)


# ---------------------------------------------------------------------------
# Result rendering
# ---------------------------------------------------------------------------

_BAND_CLS = {
    "critical": "bg-red-600 text-white",
    "high": "bg-orange-500 text-white",
    "medium": "bg-yellow-400 text-black",
    "low": "bg-green-600 text-white",
}


def _band_pill(band_value: str):
    """Render a band badge from a lowercase ``RiskBand`` value.

    Keys on the lowercase value directly rather than Title-casing into
    ``analyze.py``'s ``_band_badge``, which greys out anything it does not
    recognise. See data contracts §4.2.
    """
    cls = _BAND_CLS.get(band_value, "bg-muted text-muted-foreground")
    return Div(
        band_value.title(),
        cls=f"inline-block px-2 py-0.5 rounded text-xs font-semibold {cls}",
    )


def _stats_row(stats: dict) -> Div:
    """Summarise the counts, keeping data quality visibly separate."""
    cells = [
        ("Findings", stats.get("total", 0)),
        ("Critical", stats.get("critical", 0)),
        ("High", stats.get("high", 0)),
        ("Medium", stats.get("medium", 0)),
        ("Low", stats.get("low", 0)),
        ("Data quality", stats.get("data_quality", 0)),
    ]
    return Div(
        *[
            Div(
                P(str(value), cls="text-2xl font-semibold"),
                P(label, cls="text-xs uppercase tracking-wide text-muted-foreground"),
                cls="space-y-0.5",
            )
            for label, value in cells
        ],
        cls="flex flex-wrap gap-8",
    )


def _issue_row(issue) -> Div:
    """One finding or data-quality entry."""
    is_dq = issue.mechanism == DATA_QUALITY
    return Div(
        Div(
            _band_pill(issue.band.value),
            P(issue.title, cls="text-sm font-medium"),
            P(
                "Data quality" if is_dq else issue.mechanism,
                cls="text-xs text-muted-foreground",
            ),
            cls="space-y-1",
        ),
        P(issue.mitigation or "", cls="text-xs text-muted-foreground mt-1"),
        cls="border-b border-border py-3 last:border-b-0",
    )


def _results_fragment(slug: str, project_id: int, result: dict) -> Div:
    """Render an ``AnalysisResult`` as the fragment the page swaps in."""
    if result.get("compliance_error"):
        return _error(result["compliance_error"])

    issues = sort_issues(result.get("audit_issues", []))
    stats = result.get("issue_stats", {})
    findings = [i for i in issues if i.mechanism != DATA_QUALITY]

    body = [
        _stats_row(stats),
        Div(
            *(
                [_issue_row(i) for i in issues]
                if issues
                else [
                    P(
                        "No findings. Every element the engines could assess is "
                        "within tolerance.",
                        cls="text-sm text-muted-foreground",
                    )
                ]
            ),
            cls="mt-6",
        ),
    ]

    if not findings and any(i.mechanism == DATA_QUALITY for i in issues):
        body.insert(
            1,
            Alert(
                "Every entry below is a data-quality report, not a compliance "
                "verdict. These elements could not be assessed.",
                cls=AlertT.warning,
            ),
        )

    downloads = Div(
        *[
            LinkButton(
                fmt.upper(),
                href=f"/analyze/export?project_id={project_id}&slug={slug}&fmt={fmt}",
                variant="secondary" if fmt != "bcf" else "primary",
            )
            for fmt in ("bcf", "csv", "json")
        ],
        cls="flex gap-2 mt-6",
    )

    return Div(
        Card(
            CardHeader(CardTitle(f"{slug.title()} Results")),
            CardContent(*body, downloads),
        ),
        cls="space-y-4",
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def setup_routes(rt):
    """Register the Phase 6 pipeline endpoints."""

    @rt("/analyze/upload", methods=["POST"])
    async def analyze_upload(req: Request):
        """Attach an IFC model to a project (Session A)."""
        form = await req.form()
        raw_id = (form.get("project_id") or "").strip()
        if not raw_id.isdigit():
            return _error("No project was supplied.")
        project_id = int(raw_id)

        upload: UploadFile | None = form.get("ifc_file")
        if upload is None or not getattr(upload, "filename", ""):
            return _error("Choose an IFC file to upload.")

        content = await upload.read()
        response = _upload_service.upload(
            upload.filename, content, project_id=project_id, kind="ifc"
        )
        if not response.success:
            return _error(response.error or "The upload failed.")

        # Session A stored the object; the project row still has to point at it
        # for the analysis routes to find it. The SHA-256 stays in
        # uploaded_files — projects has no column for it.
        _projects_service.attach_ifc(project_id, response.ref.storage_ref)

        note = (
            ""
            if response.recorded
            else " Its metadata row could not be written, so re-upload detection "
            "will not see it."
        )
        return Div(
            Alert(
                f"{response.ref.filename} attached "
                f"({response.ref.size_bytes:,} bytes).{note}",
                cls=AlertT.success if response.recorded else AlertT.warning,
            ),
            P(
                f"SHA-256 {response.ref.file_hash_sha256[:16]}…",
                cls="text-xs text-muted-foreground mt-2",
            ),
            cls="space-y-2",
        )

    @rt("/analyze/corrosion", methods=["POST"])
    def analyze_corrosion_run(project_id: int = 0):
        """Parse the model and run GC-001 / CC-001 / MC-001 (Sessions B, C)."""
        if not project_id:
            return _error("No project was supplied.")
        logger.info("Corrosion run requested project_id=%d", project_id)
        return _results_fragment("corrosion", project_id, _run("corrosion", project_id))

    @rt("/analyze/seismic", methods=["POST"])
    def analyze_seismic_run(project_id: int = 0):
        """Run Blue Halo clearance detection (Session D)."""
        if not project_id:
            return _error("No project was supplied.")
        logger.info("Seismic run requested project_id=%d", project_id)
        return _results_fragment("seismic", project_id, _run("seismic", project_id))

    @rt("/analyze/export")
    def analyze_export(project_id: int = 0, slug: str = "corrosion", fmt: str = "bcf"):
        """Download an analysis as BCF, CSV or JSON (Session E).

        A plain GET rather than an HTMX POST: this returns a file, which HTMX
        cannot swap into the page.
        """
        if not project_id:
            return Response("No project was supplied.", status_code=400)
        if slug not in _RUNNERS:
            return Response(f"Unknown analysis {slug!r}.", status_code=400)

        result = _run(slug, project_id)
        if result.get("compliance_error"):
            return Response(result["compliance_error"], status_code=409)

        try:
            content, media_type, extension = export(result, fmt)
        except ValueError as exc:
            return Response(str(exc), status_code=400)

        filename = f"bimguard-{slug}-project-{project_id}.{extension}"
        logger.info(
            "Export served project_id=%d slug=%s fmt=%s bytes=%d",
            project_id,
            slug,
            fmt,
            len(content),
        )
        return Response(
            content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
