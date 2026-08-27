"""Landing route for the ``Halo`` (seismic) analysis type.

Reached as ``/analyze/seismic?project_id=<id>``, which is where the project
setup wizard redirects after creating a project whose analysis type is
``Halo``. Unlike corrosion and architecture there is no engine behind this one
yet, so the page shows what was set up and says plainly that the check cannot
be run — rather than offering a button that would fail.
"""

from app.components.analysis_ui import AnalysisSpec, analysis_landing_page

SPEC = AnalysisSpec(
    slug="seismic",
    analysis_type="Halo",
    title="Seismic Analysis",
    summary="Seismic restraint and bracing compliance for the project's systems.",
    pending_note=(
        "The seismic analysis engine is not implemented yet. The project, its "
        "standards and its model are saved and will be picked up once the "
        "engine lands."
    ),
)


def setup_routes(rt):
    """Register the seismic analysis landing route."""

    @rt("/analyze/seismic")
    def analyze_seismic(project_id: int = None):
        return analysis_landing_page(SPEC, project_id)
