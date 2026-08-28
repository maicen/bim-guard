"""Live workflow dashboard: every engine in a run, with its real progress.

Renders the shell; :file:`static/js/workflow-poller.js` fills it from
``GET /api/workflow/{project_id}``, served by
:mod:`app.routes.workflow_api` and fed by :mod:`app.services.pipeline_tracker`.

THIS COMPONENT INVENTS NOTHING

    Stage numbers, percentages and metrics all come from the tracker, which the
    analysis emits into as it runs. Where the payload omits a field — an engine
    nothing has tracked reports only its status — the panel shows that engine as
    not started rather than filling the gap with zeros that look like measured
    values. That distinction is the same one ``data_quality`` keeps everywhere
    else in this codebase: absent is not the same as assessed-and-nothing.

    In particular, an engine declared ``not_implemented`` is rendered as such
    and never given a progress bar.
"""

from __future__ import annotations

from fasthtml.common import Button, Div, Link, Script, Span

from app.services.pipeline_tracker import ENGINE_SPECS, TOTAL_STAGES

#: Tracker status -> the CSS modifier its badge uses. Keys are exactly the
#: values :class:`app.services.pipeline_tracker.Status` emits, so no translation
#: happens between the JSON and the DOM and an unknown status is visible rather
#: than silently styled as something else.
STATUS_CLASS: dict[str, str] = {
    "pending": "wf-pending",
    "running": "wf-running",
    "complete": "wf-complete",
    "failed": "wf-failed",
    "not_implemented": "wf-not-implemented",
}

#: What each status is called in the UI.
STATUS_LABEL: dict[str, str] = {
    "pending": "PENDING",
    "running": "RUNNING",
    "complete": "COMPLETE",
    "failed": "FAILED",
    "not_implemented": "NOT IMPLEMENTED",
}

#: What to show as an engine's detail line before any run has touched it.
STATUS_DETAIL: dict[str, str] = {
    "pending": "Queued",
    "not_implemented": "No engine behind this code in this build",
}


def _engine_row(code: str, label: str, status: str) -> Div:
    """One engine's row, in its declared pre-run state.

    Rendered server-side so the panel is readable before the first poll returns,
    and if JavaScript never runs at all — the layout does not depend on the
    poller, only its live values do.
    """
    return Div(
        Div(
            Div(
                Span(code, cls="wf-code"),
                Span(label, cls="wf-label"),
                cls="wf-name",
            ),
            Div(
                Div(cls="wf-bar-fill", style="width:0%", data_role="bar"),
                cls="wf-bar",
            ),
            Span("0%", cls="wf-percent", data_role="percent"),
            cls="wf-row-top",
        ),
        Div(
            Span(
                STATUS_LABEL.get(status, status.upper()),
                cls=f"wf-badge {STATUS_CLASS.get(status, 'wf-pending')}",
                data_role="badge",
            ),
            Span(
                STATUS_DETAIL.get(status, ""),
                cls="wf-detail",
                data_role="detail",
            ),
            cls="wf-row-meta",
        ),
        cls="wf-engine",
        data_engine=code,
    )


def workflow_dashboard(
    project_id: int,
    slug: str = "corrosion",
    *,
    autostart: bool = False,
) -> Div:
    """Render the live dashboard for one project.

    Args:
        project_id: Project whose run to display.
        slug: Analysis to start when the run button is pressed. The tracker
            reports per project rather than per slug, so this only selects which
            endpoint the button posts to.
        autostart: Begin a run as soon as the panel loads. Off by default —
            opening a page should not launch seconds of work unasked.

    Returns:
        The panel. Inert until the poller attaches to it.
    """
    return Div(
        Div(
            Span(f"{slug.upper()} ANALYSIS WORKFLOW", cls="wf-title"),
            Span("", cls="wf-stage", data_role="stage"),
            cls="wf-header",
        ),
        Div(
            *[_engine_row(s.code, s.label, s.declared_status.value) for s in ENGINE_SPECS],
            cls="wf-engines",
        ),
        Div(
            Button("Run analysis", type="button", cls="wf-run", data_role="run"),
            Span("", cls="wf-summary", data_role="summary"),
            cls="wf-footer",
        ),
        # Configuration travels as data attributes rather than inline script, so
        # the markup stays inspectable and the poller reads from one place.
        #
        # The run endpoint is the existing POST /analyze/{slug}, which is what
        # populates the tracker. There is no separate "start" API: the dashboard
        # watches the same run the analyse page triggers, rather than owning a
        # second way to launch one.
        id=f"workflow-{slug}",
        cls="wf-dashboard",
        data_project_id=str(project_id),
        data_slug=slug,
        data_total_stages=str(TOTAL_STAGES),
        data_status_endpoint=f"/api/workflow/{project_id}",
        data_run_endpoint=f"/analyze/{slug}",
        data_autostart="1" if autostart else "0",
    )


def workflow_dashboard_assets() -> tuple:
    """Return the stylesheet and script tags the dashboard needs.

    Kept separate from the panel so a page can place them once in its head, and
    so rendering two dashboards does not load either twice.
    """
    return (
        Link(rel="stylesheet", href="/static/css/workflow-dashboard.css"),
        Script(src="/static/js/workflow-poller.js", defer=True),
    )
