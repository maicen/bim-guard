"""Landing route for the ``Architecture`` analysis type.

Reached as ``/analyze/architecture?project_id=<id>``, which is where the project
setup wizard redirects after creating a project whose analysis type is
``Architecture``. The check itself is run by the existing ARCH workflow — doors,
windows, stairs, ramps, egress, washrooms, fire and garage — and this page is
the handoff into it.
"""

from app.components.analysis_ui import AnalysisSpec, analysis_landing_page

SPEC = AnalysisSpec(
    slug="architecture",
    analysis_type="Architecture",
    title="Architecture Analysis",
    summary=(
        "Building code compliance across doors, windows, stairs, ramps, egress "
        "and washrooms."
    ),
    run_href="/analysis/ARCH",
    run_label="Run architecture analysis",
)


def setup_routes(rt):
    """Register the architecture analysis landing route."""

    # GET only: a bare @rt() also binds POST, which would shadow the
    # Phase 6 run endpoint registered on the same path.
    @rt("/analyze/architecture", methods=["GET"])
    def analyze_architecture(project_id: int = None):
        return analysis_landing_page(SPEC, project_id)
