"""Shared fixtures and defect registry for the BIMGUARD validation suite.

This conftest is deliberately additive: it defines fixtures and constants and
installs only a session-end cleanup hook, so the pre-existing tests under ``tests/`` behave exactly as
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


# TEST_USER is not a row in auth.users, so the real membership insert that
# ensure_default_membership performs on first sign-in always fails the
# memberships_user_id_fkey constraint against a live Supabase. Skip the write
# for this one fake user; every other user still takes the real path.
from app.services.membership_service import MembershipService  # noqa: E402

_real_ensure_default_membership = MembershipService.ensure_default_membership


# The fake user is nonetheless treated as an owner of the default organization
# (id 1, the home of every grandfathered project): the org-scoped project and
# listing tests need a user who can create in, and see, that organization.
_TEST_USER_MEMBERSHIPS = [
    {"organization_id": 1, "user_id": TEST_USER.id, "role": "owner"},
]


def _ensure_default_membership_skip_test_user(self, user_id: str):
    if user_id == TEST_USER.id:
        return [dict(row) for row in _TEST_USER_MEMBERSHIPS]
    return _real_ensure_default_membership(self, user_id)


MembershipService.ensure_default_membership = _ensure_default_membership_skip_test_user

_real_role_for_user = MembershipService.role_for_user


def _role_for_user_test_user(self, organization_id: int, user_id: str):
    if user_id == TEST_USER.id:
        return next(
            (m["role"] for m in _TEST_USER_MEMBERSHIPS if m["organization_id"] == organization_id),
            None,
        )
    return _real_role_for_user(self, organization_id, user_id)


MembershipService.role_for_user = _role_for_user_test_user

_real_membership_row = MembershipService._membership_row


def _membership_row_test_user(self, organization_id: int, user_id: str):
    if user_id == TEST_USER.id:
        return next(
            (dict(m) for m in _TEST_USER_MEMBERSHIPS if m["organization_id"] == organization_id),
            None,
        )
    return _real_membership_row(self, organization_id, user_id)


MembershipService._membership_row = _membership_row_test_user


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

# Same idea for app.api.documents's document-grant checks (get, update, delete,
# file download, asset streaming, extraction, doclang export).
try:
    from app.api.documents import (  # noqa: E402
        DocumentAccessChecker,
        get_document_access_checker,
        get_document_access_checker_flexible,
    )

    class _PermissiveDocumentAccessChecker(DocumentAccessChecker):
        def __init__(self) -> None:  # noqa: D107
            pass

        def __call__(self, document_id, *, for_mutation: bool = False) -> None:  # noqa: ANN001
            return None

    def _override_get_document_access_checker() -> DocumentAccessChecker:
        return _PermissiveDocumentAccessChecker()

    app.dependency_overrides[get_document_access_checker] = _override_get_document_access_checker
    app.dependency_overrides[get_document_access_checker_flexible] = _override_get_document_access_checker
except ImportError:
    pass

# TEST_USER acts as an org owner (full access to whatever it creates) via the
# synthetic membership stubbed in above -- there is no real membership row to
# promote, since the fake user is not in auth.users.


def purge_test_user_audit_rows() -> int:
    """Delete the ``audit_log`` rows written by the fake test user; return how many.

    Every project or document a test creates and deletes is audited under
    ``TEST_USER``, and the table is append-only, so the suite left hundreds of
    ``project.deleted`` rows behind. Only that one fake actor's rows are removed.
    """
    from app.bootstrap import get_container

    repo = get_container().audit_log_repo
    ids = [row["id"] for row in repo.rows_where("actor_id = ?", [TEST_USER.id])]
    if ids:
        repo.delete_many(ids)
    return len(ids)


def pytest_sessionfinish(session, exitstatus):
    """Purge the test user's audit rows once, on the main process only.

    Under pytest-xdist each worker also runs this hook; skipping workers keeps
    one worker finishing early from deleting rows another is still asserting on.
    """
    if hasattr(session.config, "workerinput"):
        return
    try:
        purge_test_user_audit_rows()
    except Exception:  # cleanup must never fail the run
        pass


@pytest.fixture(autouse=True)
def purge_created_storage_objects(monkeypatch, request):
    """Delete every storage object a test saves, whether or not the test passes.

    ObjectStorage.save_upload writes to the live Supabase bucket, and the
    tests that exercise document/doclang/upload flows through a real
    ObjectStorage left their files behind (the rows were cleaned up, the
    objects were not). Saves are recorded per test and deleted at teardown, so
    parallel xdist workers never touch each other's objects.
    """
    from app.services.object_storage import ObjectStorage

    created: list[str] = []
    real_save = ObjectStorage.save_upload

    def save_upload(self, *args, **kwargs):
        reference = real_save(self, *args, **kwargs)
        created.append(reference)
        return reference

    monkeypatch.setattr(ObjectStorage, "save_upload", save_upload)
    yield
    if not created:
        return
    storage = ObjectStorage()
    for reference in created:
        try:
            storage.delete(reference)
        except Exception:  # cleanup must never fail the test
            pass


@pytest.fixture(autouse=True)
def offline_embeddings(monkeypatch):
    """Keep tests off the real embedding provider.

    With provider keys in ``.env`` the suite made live ``text-embedding-3-small``
    calls (slow, billable, nondeterministic) and logged each one to the live
    ``llm_calls`` table. ``EmbeddingService`` already falls back to deterministic
    pseudo-vectors when the provider call raises, so raising here exercises that
    path. A test that needs a specific provider response can monkeypatch
    ``_call_embedding_provider`` itself; its patch is applied after this one.
    """
    from app.services.embedding_service import EmbeddingService

    async def _offline(self, texts):
        raise RuntimeError("embedding provider disabled in tests")

    monkeypatch.setattr(EmbeddingService, "_call_embedding_provider", _offline)


@pytest.fixture
def purge_created_bcf_topics(monkeypatch):
    """Delete every BCF topic the test creates, whether or not the test passes.

    BCF topics are written to the live database and the BCF API tests use fixed
    project ids ("0", "999"), so uncleaned runs piled up hundreds of rows and
    pushed new topics off the first page of list results. Creation is recorded
    per test (not diffed against a snapshot) so parallel xdist workers sharing
    those project ids never delete each other's in-flight topics.
    """
    from app.services.bcf_sync_service import BCFSyncService

    created: list[tuple[str, str]] = []
    real_create = BCFSyncService.create_topic
    real_import = BCFSyncService.import_topic

    def create_topic(self, project_id, *args, **kwargs):
        topic = real_create(self, project_id, *args, **kwargs)
        created.append((str(project_id), topic.guid))
        return topic

    def import_topic(self, project_id, *args, **kwargs):
        topic = real_import(self, project_id, *args, **kwargs)
        created.append((str(project_id), topic.guid))
        return topic

    monkeypatch.setattr(BCFSyncService, "create_topic", create_topic)
    monkeypatch.setattr(BCFSyncService, "import_topic", import_topic)
    yield
    service = BCFSyncService()
    for project_id, guid in created:
        service.delete_topic(project_id, guid)


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




