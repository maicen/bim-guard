"""Tests for the architectural analysis path in the runner.

The property under test is the one :mod:`app.services.analysis_runner` opens
with: errors cross this boundary as values, not exceptions, so a route renders
a message rather than a traceback.

The architecture path is the one that could break it. Its rule packs are loaded
at module import time and a missing pack raises, so an environment without the
BUILDING-CODE-PART9 static asset answered a request for this analysis with a
500 and a stack trace -- which is what an E2E run against a database-less
deployment actually produced.

Run: uv run pytest tests/test_analysis_runner_architecture.py -v
"""

from __future__ import annotations

import pytest

import app.services.analysis_runner as runner


@pytest.fixture
def orchestrator_raises(monkeypatch):
    """Make the orchestrator import raise the way a missing rule pack does."""
    import app.services.pipeline_services as pipeline_services

    def boom(**_kwargs):
        raise ValueError("Missing static asset ruleset:BUILDING-CODE-PART9")

    monkeypatch.setattr(
        pipeline_services.PipelineOrchestratorService, "orchestrate_workflow", boom
    )


class TestArchitectureFailuresAreValues:
    def test_a_raising_orchestrator_does_not_propagate(self, orchestrator_raises):
        """The exception must not reach the route, which would answer 500."""
        result = runner._run_architecture(1)
        assert isinstance(result, dict)

    def test_the_result_carries_the_reason(self, orchestrator_raises):
        """A caller needs to know what was missing, not just that it failed."""
        result = runner._run_architecture(1)
        assert "BUILDING-CODE-PART9" in result["compliance_error"]

    def test_the_result_has_no_findings(self, orchestrator_raises):
        """An analysis that did not run has not cleared the model."""
        result = runner._run_architecture(1)
        assert result["audit_issues"] == []

    def test_the_shape_is_still_an_analysis_result(self, orchestrator_raises):
        """The exporter reads these keys whatever happened upstream."""
        assert set(runner._run_architecture(1)) == {
            "audit_issues",
            "issue_stats",
            "cost_impact",
            "compliance_error",
            "compliance_is_demo",
        }

    def test_run_analysis_reports_it_as_a_failed_result(self, orchestrator_raises, monkeypatch):
        """Through the public entry point, too -- and it is not cached."""
        monkeypatch.setattr(runner, "model_bytes", lambda project_id: (b"IFC", None))
        result = runner.run_analysis("architecture", 1, use_cache=False)
        assert result["compliance_error"]
        assert result["audit_issues"] == []
