"""Shared fixtures and defect registry for the BIMGUARD validation suite.

This conftest is deliberately additive: it defines fixtures and constants and
installs no hooks, so the pre-existing tests under ``tests/`` behave exactly as
they did before it existed.

Two registries live here, and the difference between them is the point:

``KNOWN_IMPORT_FAILURES``
    Modules that have never imported in a plain checkout, each with the reason.
    These are environmental or long-dead; they are not regressions and nobody
    is expected to fix them for the thesis.

``IMPORT_REGRESSIONS``
    Modules that imported at ``4edba3a`` and stopped importing afterwards.
    Every entry here is a bug introduced by this session's work. This dict must
    shrink to empty. ``tests/test_imports.py`` holds a strict-xfail test per
    entry, so the moment a module is repaired the test XPASSes and fails the
    run until the entry is deleted — the registry cannot rot into an allowlist.

Probes that sweep the whole ``app`` package run in a child interpreter rather
than in-process. Importing 119 modules into the pytest session would leave
module-level database clients and settings singletons behind for whatever test
ran next; a subprocess throws that state away with the process.

Run: uv run pytest tests/test_imports.py tests/test_feature_flags.py \
     tests/test_orchestrator.py tests/test_integration.py -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def reset_in_memory_cache():
    """Reset the global database query cache before and after every test."""
    try:
        from app.services.cache import clear_cache

        clear_cache()
        yield
        clear_cache()
    except ImportError:
        yield

# The commit this suite treats as the last known-good state: the point before
# the F-series (producer overload, issue adapter, band casing, MM/XM wiring).
BASELINE_COMMIT = "4edba3a"

KNOWN_IMPORT_FAILURES: dict[str, str] = {
    "app.modules.module1_doc_parser.tfidf_analyzer": (
        "needs scikit-learn from the optional ml-pipeline group "
        "(uv sync --group ml-pipeline)"
    ),
}

IMPORT_REGRESSIONS: dict[str, str] = {}

# The two Path B feature flags, exercised over every on/off combination so a
# test can prove they are independent rather than assuming it.
FLAG_COMBOS = [("0", "0"), ("1", "0"), ("0", "1"), ("1", "1")]

FLAG_COMBO_IDS = [f"MM={mm},XM={xm}" for mm, xm in FLAG_COMBOS]


# ---------------------------------------------------------------------------
# Subprocess probe plumbing
# ---------------------------------------------------------------------------


def _run_probe(
    source: str,
    env_extra: dict[str, str] | None = None,
    timeout: int = 600,
) -> dict:
    """Execute a probe snippet in a child interpreter and parse its verdict.

    The snippet must print exactly one JSON object as its final line. Anything
    printed before it — import chatter, a swallowed traceback — is ignored, so
    a noisy dependency cannot corrupt the result.

    Args:
        source: Python source to execute.
        env_extra: Environment overrides layered onto the current environment.
        timeout: Seconds before the child is killed.

    Returns:
        The decoded verdict object.

    Raises:
        AssertionError: If the child printed no JSON object.
    """
    env = dict(os.environ)
    # Windows consoles default to cp1252 and this codebase prints em-dashes.
    env["PYTHONIOENCODING"] = "utf-8"
    if env_extra:
        env.update(env_extra)

    proc = subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        env=env,
    )

    for line in reversed(proc.stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)

    raise AssertionError(
        "probe printed no JSON verdict\n"
        f"--- stdout ---\n{proc.stdout[-2000:]}\n"
        f"--- stderr ---\n{proc.stderr[-2000:]}"
    )


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Absolute path to the repository root."""
    return REPO_ROOT


@pytest.fixture(scope="session")
def run_probe():
    """Return the child-interpreter probe runner.

    Session-scoped because it is stateless; each call still gets a fresh
    process, so tests cannot leak state into one another through it.
    """
    return _run_probe


@pytest.fixture
def flag_env():
    """Build the environment overrides for one Path B flag combination."""

    def _build(mm: str, xm: str) -> dict[str, str]:
        return {"FEATURE_PATH_B_MM": mm, "FEATURE_PATH_B_XM": xm}

    return _build


# ---------------------------------------------------------------------------
# Domain fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def path_a_results() -> list[dict]:
    """Two Path A rows: one multi-mechanism failure, one compliant element.

    Built by hand rather than by running the engines, so the band under test is
    the band asserted. The key set mirrors ``run_compliance_checks()``; the
    compliant row exists so tests can prove the projection keeps a denominator
    rather than only listing findings.
    """
    return [
        {
            "guid": "GUID-A",
            "name": "SS316 Flanged Joint",
            "galvanic_band": "MEDIUM",
            "galvanic_score": 0.42,
            "voltage_gap_V": 0.35,
            "crevice_band": "CRITICAL",
            "crevice_score": 0.89,
            "crevice_geometry": "Crevice",
            "mic_band": "LOW",
            "mic_score": 0.05,
            "dominant_mechanism": "crevice",
            "mitigation": "Isolate",
            "action": "BLOCK",
        },
        {
            "guid": "GUID-B",
            "name": "Compliant Copper Run",
            "galvanic_band": "LOW",
            "galvanic_score": 0.05,
            "dominant_mechanism": "galvanic",
            "mitigation": "",
            "action": "PASS",
        },
    ]


@pytest.fixture
def allocator():
    """Return a fresh run-wide Issue id allocator."""
    from app.modules.module4_comparator.issue_adapter import IssueIdAllocator

    return IssueIdAllocator("BGR-TEST")


@pytest.fixture
def mock_element() -> types.SimpleNamespace:
    """Return a minimal stand-in for one IFC piping element.

    Deliberately a plain namespace rather than an ifcopenshell entity: these
    tests measure how far the pipeline gets and where it stops, not whether
    ifcopenshell parses a file. It carries both the IFC-shaped attributes the
    Path A runner reads and the PipingElement-shaped ones Path B reads, so
    whichever arm executes, the failure is about wiring and not about a
    missing attribute.
    """
    return types.SimpleNamespace(
        id="EL-001",
        GlobalId="0FQ6pMwzXBJucYaRTqfuw2",
        Name="SS316 Flanged Joint",
        material="stainless_316",
        environment_class=None,
        properties={},
        joined_to=[],
        extraction_warnings=[],
    )
