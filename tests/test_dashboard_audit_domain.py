"""The project Dashboard's Compliance Audit card opens the project's own domain tab.

Architecture is now the only analysis domain, so every stored or legacy
``analysis_type`` value resolves to the same "arch" view through
``viewForAnalysisDomain`` (``frontend/src/lib/analysisDomain.ts``).

The mapping is executed for real under Node's type stripping (Node >= 22.6);
the frontend has no test runner of its own. Those tests skip where no
suitable Node is installed. The source checks pin the card and the router to
that mapping.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"
ANALYSIS_DOMAIN_TS = FRONTEND_SRC / "lib" / "analysisDomain.ts"
DASHBOARD = FRONTEND_SRC / "routes" / "ProjectDashboardView.svelte"
APP = FRONTEND_SRC / "App.svelte"


def _node() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    probe = subprocess.run(
        [node, "--experimental-strip-types", "--no-warnings", "-e", "0"],
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        pytest.skip("this node cannot strip TypeScript types (needs >= 22.6)")
    return node


def _views_for(analysis_types: list[str | None]) -> list[str]:
    """Run viewForAnalysisDomain over each value in one Node process."""
    script = (
        f"const m = await import({json.dumps(ANALYSIS_DOMAIN_TS.as_uri())});"
        f"console.log(JSON.stringify({json.dumps(analysis_types)}.map(m.viewForAnalysisDomain)));"
    )
    result = subprocess.run(
        [_node(), "--experimental-strip-types", "--no-warnings", "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


CASES = [
    # Current and legacy spellings of the architectural domain.
    ("Arch", "arch"),
    ("Architectural", "arch"),
    ("Architecture", "arch"),
    ("arch", "arch"),
    # No domain, or a retired one (Piping, seismic): Architectural, never an error.
    (None, "arch"),
    ("", "arch"),
    ("   ", "arch"),
    ("Structural", "arch"),
    ("Piping", "arch"),
    ("seismic", "arch"),
]


def test_each_domain_opens_the_architectural_audit_tab():
    """Every domain value, current or retired, opens the Architectural tab."""
    domains = [domain for domain, _ in CASES]
    expected = [view for _, view in CASES]
    assert _views_for(domains) == expected


def test_dashboard_audit_card_routes_through_the_project_domain():
    """The card no longer hardcodes the arch view; it resolves the domain on click."""
    source = DASHBOARD.read_text(encoding="utf-8")
    card = re.search(r"\{\s*(?://[^\n]*\n\s*)*view: ([^,]+),\s*label: \"Compliance Audit\"", source)
    assert card, "Compliance Audit quick action not found"
    assert card.group(1).strip() == "AUDIT_ACTION", "the card must not name a fixed audit view"
    assert "onNavigate(viewForAnalysisDomain(await projectAnalysisDomain()))" in source
    assert "onclick={() => openQuickAction(action.view)}" in source


def test_dashboard_only_trusts_selected_project_when_it_is_this_dashboards():
    """A stale selectedProject for another project must not choose the tab."""
    source = DASHBOARD.read_text(encoding="utf-8")
    assert "selectedProject.id === initialProjectId" in source
    assert "projectsApi.get(initialProjectId)" in source


def test_app_selects_the_audit_tab_from_the_route():
    """Arch is the only tab, and a stale link snaps back to the project's own domain."""
    source = APP.read_text(encoding="utf-8")
    assert re.search(
        r'let auditDomain: AnalysisDomainTab = "arch";',
        source,
    ), "App.svelte no longer fixes the audit tab to the sole Architectural domain"
    assert "auditDomain !== projectAuditDomain" in source, (
        "App.svelte no longer reconciles a stale route against the project's domain"
    )
    assert "onNavigate={(view) => push(buildTargetUrl(view, targetProjectId!))}" in source
