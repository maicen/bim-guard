"""Service entry point for the Digital Inspector agent.

Thin wrapper around `app.digital_inspector.runner.run_inspection`, kept as
its own service (rather than calling the runner directly from the API
router) so it follows the same DI/service-layer convention as the rest of
`app/api/dependencies.py` (e.g. `get_analysis_service`).
"""

from __future__ import annotations

from app.modules.contracts import InspectorResponse


class DigitalInspectorService:
    """Runs Digital Inspector queries against a project."""

    async def run_inspection(self, project_id: int, query: str) -> InspectorResponse:
        """Run one natural-language query through the Digital Inspector graph."""
        from app.digital_inspector.runner import run_inspection

        return await run_inspection(project_id, query)
