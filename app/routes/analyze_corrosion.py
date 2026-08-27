"""Landing route for the ``Piping (Corrosive)`` analysis type.

Reached as ``/analyze/corrosion?project_id=<id>``, which is where the project
setup wizard redirects after creating a project whose analysis type is
``Piping (Corrosive)``. The check itself is run by the existing MEP workflow,
which drives the GC-001 / CC-001 / MC-001 corrosion engines; this page is the
handoff into it.
"""

from app.components.analysis_ui import AnalysisSpec, analysis_landing_page

SPEC = AnalysisSpec(
    slug="corrosion",
    analysis_type="Piping (Corrosive)",
    title="Corrosion Analysis",
    summary=(
        "Galvanic, crevice and microbiologically influenced corrosion checks "
        "across the project's piping."
    ),
    run_href="/analysis/MEP",
    run_label="Run corrosion analysis",
)


def setup_routes(rt):
    """Register the corrosion analysis landing route."""

    @rt("/analyze/corrosion")
    def analyze_corrosion(project_id: int = None):
        return analysis_landing_page(SPEC, project_id)
