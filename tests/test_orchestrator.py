"""End-to-end behaviour of orchestrate_workflow() under every flag combination.

``orchestrate_workflow()`` is the single entry point F6 introduced: Path A
always, MM-001 and XM-001 behind their own flags, everything projected onto the
per-element dicts the analyze card renders. This module drives it with a mock
element and asserts what comes back.

Almost every test here is a strict xfail today, for one root cause: the module
cannot be imported at all, because ``compliance_runner`` imports
``app.engines.bimguard_galvanic_engine``, which has never existed. See
IMPORT_REGRESSIONS in conftest. The tests are written against the behaviour the
orchestrator is supposed to have, so repairing the import turns them green
rather than requiring them to be rewritten.

The structural tests — the ones that read the module's source rather than
running it — pass today, and are what keeps this file from being an entirely
inert placeholder.

Run: uv run pytest tests/test_orchestrator.py -v
"""

from __future__ import annotations

import ast

import pytest

from tests.conftest import FLAG_COMBO_IDS, FLAG_COMBOS, REPO_ROOT

pytestmark = pytest.mark.slow

ORCHESTRATOR_PATH = (
    REPO_ROOT / "app" / "modules" / "module4_comparator" / "compliance_orchestrator.py"
)

# Drives one full orchestrate_workflow() call and reports how far it got.
_RUN_PROBE = r"""
import json, sys, types
sys.path.insert(0, ".")
try:
    from dotenv import load_dotenv; load_dotenv()
except Exception:
    pass

verdict = {"imported": False, "ran": False}
try:
    from app.modules.module4_comparator.compliance_orchestrator import orchestrate_workflow
    verdict["imported"] = True
except Exception as exc:
    verdict["error"] = "%s: %s" % (type(exc).__name__, exc)
    print(json.dumps(verdict))
    raise SystemExit(0)

element = types.SimpleNamespace(
    id="EL-001",
    GlobalId="0FQ6pMwzXBJucYaRTqfuw2",
    Name="SS316 Flanged Joint",
    material="stainless_316",
    environment_class=None,
    properties={},
    joined_to=[],
    extraction_warnings=[],
)

import io, contextlib
buffer = io.StringIO()
try:
    with contextlib.redirect_stdout(buffer):
        rows = orchestrate_workflow([element], run_id="BGR-VALIDATE")
    verdict["ran"] = True
    verdict["rows"] = len(rows)
    verdict["path_b_total"] = sum(r.get("path_b_count", 0) for r in rows)
    verdict["row_keys"] = sorted(rows[0].keys()) if rows else []
except Exception as exc:
    verdict["error"] = "%s: %s" % (type(exc).__name__, exc)

# Path B catches its own exceptions and prints them, so the swallowed text is
# evidence the caller never sees as a raise.
verdict["swallowed"] = [
    line for line in buffer.getvalue().splitlines() if "error:" in line.lower()
]
print(json.dumps(verdict))
"""


@pytest.fixture(scope="session")
def orchestrator_source() -> str:
    """Return the orchestrator module's text, for structural assertions."""
    return ORCHESTRATOR_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Structural contract - these run without importing the broken module
# ---------------------------------------------------------------------------


def test_orchestrator_module_exists():
    """The file F6 rewrote is where the rest of the suite expects it."""
    assert ORCHESTRATOR_PATH.is_file(), f"missing {ORCHESTRATOR_PATH}"


def test_orchestrate_workflow_is_the_declared_entry_point(orchestrator_source):
    """A module-level orchestrate_workflow(elements, run_id) must be defined.

    F6 replaced the previous ``ComplianceOrchestrator`` class with this
    function. tests/test_compliance_orchestrator.py still imports the class and
    errors on collection; this test pins whichever name is actually current so
    that mismatch is visible as a statement rather than as a stack trace.
    """
    tree = ast.parse(orchestrator_source)
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    assert "orchestrate_workflow" in functions, (
        f"module-level functions are {sorted(functions)}"
    )

    args = [a.arg for a in functions["orchestrate_workflow"].args.args]
    assert args[:2] == ["elements", "run_id"], (
        f"expected orchestrate_workflow(elements, run_id, ...), got {args}"
    )


def test_orchestrator_wires_both_paths(orchestrator_source):
    """Path A, the adapter and both Path B comparators are all referenced.

    Cheap, but it is the assertion that would have caught an integration commit
    that wired only half of what its message claimed.
    """
    for symbol in (
        "run_compliance_checks",
        "issues_from_path_a",
        "path_a_view",
        "IssueIdAllocator",
        "material_media",
        "cross_material",
    ):
        assert symbol in orchestrator_source, f"orchestrator never references {symbol}"


# ---------------------------------------------------------------------------
# Behavioural contract
# ---------------------------------------------------------------------------


def test_orchestrator_module_imports(run_probe):
    """The entry point must be reachable before anything else can be true."""
    verdict = run_probe(_RUN_PROBE)
    assert verdict["imported"], verdict.get("error")


@pytest.mark.parametrize(("mm", "xm"), FLAG_COMBOS, ids=FLAG_COMBO_IDS)
def test_orchestrate_workflow_runs_under_every_flag_combination(
    run_probe, flag_env, mm, xm
):
    """The pipeline completes with both packs off, either on, and both on."""
    verdict = run_probe(_RUN_PROBE, flag_env(mm, xm))
    assert verdict["imported"], verdict.get("error")
    assert verdict["ran"], verdict.get("error")


def test_orchestrate_workflow_returns_one_row_per_element(run_probe, flag_env):
    """The output keeps the per-element spine, compliant elements included.

    The row-per-element shape is what makes "nothing flagged" a statement about
    coverage rather than about silence. Building the table from findings alone
    would lose the denominator.
    """
    verdict = run_probe(_RUN_PROBE, flag_env("0", "0"))
    assert verdict["ran"], verdict.get("error")
    assert verdict["rows"] == 1, f"expected 1 row for 1 element, got {verdict['rows']}"


def test_orchestrate_workflow_projects_the_path_b_columns(run_probe, flag_env):
    """Every row carries the projection keys the analyze card reads."""
    verdict = run_probe(_RUN_PROBE, flag_env("0", "0"))
    assert verdict["ran"], verdict.get("error")
    missing = {
        "path_b_issues",
        "path_b_band",
        "path_b_count",
        "mm_band",
        "mm_score",
        "xm_band",
        "xm_score",
    } - set(verdict["row_keys"])
    assert not missing, f"projection keys missing from the row: {sorted(missing)}"


@pytest.mark.parametrize(
    ("mm", "xm"), [("1", "0"), ("0", "1"), ("1", "1")], ids=FLAG_COMBO_IDS[1:]
)
def test_an_enabled_flag_reaches_its_comparator(run_probe, flag_env, mm, xm):
    """An enabled pack must actually execute, or fail loudly if it cannot.

    Zero findings is a legitimate answer for a compliant model. Zero findings
    because the call raised TypeError and something printed it is not, and the
    two are indistinguishable from the caller — which is precisely why this is
    the most dangerous defect in the wiring.
    """
    verdict = run_probe(_RUN_PROBE, flag_env(mm, xm))
    assert verdict["ran"], verdict.get("error")
    assert not verdict["swallowed"], (
        "Path B swallowed an exception rather than raising it:\n"
        + "\n".join(f"  {line}" for line in verdict["swallowed"])
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "DEFECT: both Path B arms are wrapped in `except Exception` whose only "
        "handler is print(). A comparator failure is reported to stdout and the "
        "run continues as though the pack found nothing."
    ),
)
def test_path_b_failures_are_not_swallowed(orchestrator_source):
    """A comparator that cannot run must not look like one that found nothing.

    Read from the source rather than from a run, so this stays meaningful even
    while the module is unimportable.
    """
    tree = ast.parse(orchestrator_source)
    bare_print_handlers = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        catches_everything = (
            node.type is None
            or (isinstance(node.type, ast.Name) and node.type.id == "Exception")
        )
        only_prints = all(
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Name)
            and stmt.value.func.id == "print"
            for stmt in node.body
        )
        if catches_everything and only_prints:
            bare_print_handlers.append(node.lineno)

    assert not bare_print_handlers, (
        "except Exception handlers whose only action is print(), at line(s) "
        f"{bare_print_handlers}. Let the failure propagate, or record it on the "
        "returned rows as 'not assessed' - never as an empty result."
    )


def test_known_broken_orchestrator_test_is_still_broken():
    """tests/test_compliance_orchestrator.py expects an API F6 deleted.

    That file imports ``ComplianceOrchestrator``, which F6 replaced with
    ``orchestrate_workflow``. It has errored on collection since before this
    session (it was B1 in the integration plan) and errors still, for a new
    reason. Pinned here so nobody mistakes the collection error for a fresh
    break, and so the day someone repairs that file, this test says so.
    """
    legacy = REPO_ROOT / "tests" / "test_compliance_orchestrator.py"
    if not legacy.is_file():
        pytest.skip("the legacy orchestrator test has been removed")

    source = legacy.read_text(encoding="utf-8")
    assert "ComplianceOrchestrator" in source, (
        "tests/test_compliance_orchestrator.py no longer imports the deleted "
        "class - if it has been ported to orchestrate_workflow(), delete this "
        "test and let the real one speak for itself"
    )
    assert "orchestrate_workflow" not in source, (
        "tests/test_compliance_orchestrator.py has been ported to the current "
        "entry point; this guard is now stale and should be removed"
    )
