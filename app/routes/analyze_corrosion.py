"""Landing route for the ``Piping (Corrosive)`` analysis type.

Reached as ``/analyze/corrosion?project_id=<id>``, which is where the project
setup wizard redirects after creating a project whose analysis type is
``Piping (Corrosive)``. The check runs in place via the Phase 6 pipeline: the model is parsed by
Session B and assessed by Session C's GC-001 / CC-001 / MC-001 wiring, and the
results are swapped into this page.
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
    run_endpoint="/analyze/corrosion",
    run_label="Run corrosion analysis",
)


def setup_routes(rt):
    """Register the corrosion analysis landing route."""

    # GET only: a bare @rt() also binds POST, which would shadow the
    # Phase 6 run endpoint registered on the same path.
    @rt("/analyze/corrosion", methods=["GET"])
    def analyze_corrosion(project_id: int = None):
        return analysis_landing_page(SPEC, project_id)
