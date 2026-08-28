"""Landing route for the ``Halo`` (seismic) analysis type.

Reached as ``/analyze/seismic?project_id=<id>``, which is where the project
setup wizard redirects after creating a project whose analysis type is
``Halo``. Session D wired Blue Halo's clearance detection behind this page, so
the check now runs: envelopes are generated from the model's own geometry and
intrusions are reported as Issues in the shared shape.
"""

from app.components.analysis_ui import AnalysisSpec, analysis_landing_page

SPEC = AnalysisSpec(
    slug="seismic",
    analysis_type="Halo",
    title="Seismic Analysis",
    summary="Seismic restraint and bracing compliance for the project's systems.",
    run_endpoint="/analyze/seismic",
    run_label="Run seismic analysis",
)


def setup_routes(rt):
    """Register the seismic analysis landing route."""

    # GET only: a bare @rt() also binds POST, which would shadow the
    # Phase 6 run endpoint registered on the same path.
    @rt("/analyze/seismic", methods=["GET"])
    def analyze_seismic(project_id: int = None):
        return analysis_landing_page(SPEC, project_id)
