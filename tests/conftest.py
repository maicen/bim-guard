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

# ---------------------------------------------------------------------------
# Auth override
# ---------------------------------------------------------------------------
# app.api.projects and app.api.rules require Depends(get_current_user).
# Every test file builds its own TestClient(app) against the same singleton
# `app`, so overriding the dependency once here — rather than in each test
# file — authenticates all of them as one fixed fake user. FastAPI applies a
# dependency override transitively, so this also covers get_authorized_project
# and anywhere else get_current_user appears in a dependency chain.
from app.auth import CurrentUser, get_current_user, get_current_user_flexible  # noqa: E402
from app.main import app  # noqa: E402

TEST_USER = CurrentUser(
    id="99999999-9999-9999-9999-999999999999",
    email="test@example.com",
    claims={"sub": "99999999-9999-9999-9999-999999999999", "email": "test@example.com"},
)


def _override_get_current_user() -> CurrentUser:
    return TEST_USER


app.dependency_overrides[get_current_user] = _override_get_current_user
# get_current_user_flexible is a separate callable (not get_current_user
# wrapped), for routes the frontend downloads via <a href>/window.location
# rather than fetch (report exports, BCF artifacts, SSE) and so accept the
# token via ?token= too. It needs its own override for the same reason.
app.dependency_overrides[get_current_user_flexible] = _override_get_current_user

# app.api.projects.get_authorized_project (and its ?token= sibling
# get_authorized_project_flexible) do a REAL DB lookup and are deliberately
# left un-overridden: app.api.projects's and app.api.naming_config's own
# tests assert a genuine 404 for a project TEST_USER doesn't own or that
# doesn't exist, and that must keep working.
#
# app.api.analyze defines its OWN distinct functions for this
# (get_authorized_project_for_analyze / _flexible), and events.py has its own
# get_authorized_project_for_sse, precisely so those can be overridden here
# independently of app.api.projects's. Many pre-existing tests of those two
# routers (pagination, export defaults, pipeline-tracker, SSE) key a
# synthetic run off a project_id that was never a real row to begin with
# (e.g. PROJECT_ID = 4242) -- they predate either router having an ownership
# check at all, and were never testing authorization, only the route's own
# logic downstream of it. Overriding these two to a stand-in dict rather than
# a real, owned project keeps that pre-existing "run as one all-powerful fake
# user" test philosophy intact for them, without weakening the real check
# app.api.projects's and app.api.naming_config's own tests depend on.
from app.api.projects import (  # noqa: E402
    ProjectAccessChecker,
    get_project_access_checker,
    get_project_access_checker_flexible,
)


def _override_get_authorized_project(project_id: int) -> dict:
    return {"id": project_id, "name": f"Test Project {project_id}", "organization_id": None}


try:
    from app.api.analyze import (  # noqa: E402
        get_authorized_project_for_analyze,
        get_authorized_project_for_analyze_flexible,
    )

    app.dependency_overrides[get_authorized_project_for_analyze] = _override_get_authorized_project
    app.dependency_overrides[get_authorized_project_for_analyze_flexible] = _override_get_authorized_project
except ImportError:
    pass

try:
    from app.api.events import get_authorized_project_for_sse  # noqa: E402

    app.dependency_overrides[get_authorized_project_for_sse] = _override_get_authorized_project
except ImportError:
    pass


# analyze.py's own project_id (a Form/Body/Query field, not a path segment)
# can't reuse get_authorized_project as a Depends sub-dependency, so it goes
# through ProjectAccessChecker instead -- see get_project_access_checker's
# docstring. Overriding its factory to hand back a checker that never raises
# keeps the same "run as an all-powerful fake user" philosophy for these
# routes too.
class _PermissiveProjectAccessChecker(ProjectAccessChecker):
    def __init__(self) -> None:  # noqa: D107 - trivial, no real deps needed
        pass

    def __call__(self, project_id: int) -> dict:
        return _override_get_authorized_project(project_id)


def _override_get_project_access_checker() -> ProjectAccessChecker:
    return _PermissiveProjectAccessChecker()


app.dependency_overrides[get_project_access_checker] = _override_get_project_access_checker
app.dependency_overrides[get_project_access_checker_flexible] = _override_get_project_access_checker

# Same idea for app.api.rules's ruleset-grant checks (create/update/delete
# rule, folder CRUD, bulk ops, imports): ruleset_id there is likewise a path
# segment, Form field, or list, not uniformly a path parameter, so it goes
# through RulesetAccessChecker rather than a bare Depends(project_id).
try:
    from app.api.rules import RulesetAccessChecker, get_ruleset_access_checker  # noqa: E402

    class _PermissiveRulesetAccessChecker(RulesetAccessChecker):
        def __init__(self) -> None:  # noqa: D107 - trivial, no real deps needed
            pass

        def __call__(self, ruleset_id) -> None:  # noqa: ANN001 - matches base signature
            return None

    def _override_get_ruleset_access_checker() -> RulesetAccessChecker:
        return _PermissiveRulesetAccessChecker()

    app.dependency_overrides[get_ruleset_access_checker] = _override_get_ruleset_access_checker
except ImportError:
    pass

# Membership auto-provisioning lands a first-time signer as a plain 'member',
# which the group-based RBAC layer (MembershipService.member_can_access_project)
# now restricts to nothing without a group grant. Tests need TEST_USER to act
# like an org owner — full access to whatever it creates — so promote it here,
# once, rather than in every test file that touches a project.
from app.bootstrap import get_container  # noqa: E402

_test_user_memberships = get_container().membership_service.ensure_default_membership(TEST_USER.id)
if _test_user_memberships:
    get_container().membership_service.update_role(
        _test_user_memberships[0]["organization_id"], TEST_USER.id, "owner"
    )


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

KNOWN_IMPORT_FAILURES: dict[str, str] = {}

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
    from app.modules.comparator.issue_adapter import IssueIdAllocator

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
