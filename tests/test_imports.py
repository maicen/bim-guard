"""Every module under app/ must import, and none may import circularly.

An import sweep is the cheapest regression detector this repository has. Two of
its modules broke this session in a way no unit test caught, because a module
that cannot be imported has no tests that run against it — the failure hides as
a collection error rather than as a red assertion.

The sweep runs once in a child interpreter (see conftest) and every test here
reads that one result, so the 119 modules are imported once per session rather
than once per test.

Run: uv run pytest tests/test_imports.py -v
"""

from __future__ import annotations

import pytest

from tests.conftest import IMPORT_REGRESSIONS, KNOWN_IMPORT_FAILURES

_SWEEP = r"""
import importlib, json, sys
from pathlib import Path
sys.path.insert(0, ".")
try:
    from dotenv import load_dotenv; load_dotenv()
except Exception:
    pass

modules = []
for path in sorted(Path("app").rglob("*.py")):
    parts = path.with_suffix("").parts
    if "__pycache__" in parts or "tests" in parts:
        continue
    if parts[-1] == "__init__":
        parts = parts[:-1]
    if parts:
        modules.append(".".join(parts))

failures, circular = {}, {}
for name in modules:
    try:
        importlib.import_module(name)
    except Exception as exc:
        text = "%s: %s" % (type(exc).__name__, exc)
        failures[name] = text
        low = text.lower()
        if "partially initialized" in low or "circular import" in low:
            circular[name] = text

print(json.dumps({"total": len(modules), "failures": failures, "circular": circular}))
"""

_SINGLE = r"""
import importlib, json, sys
sys.path.insert(0, ".")
try:
    from dotenv import load_dotenv; load_dotenv()
except Exception:
    pass
try:
    importlib.import_module(%r)
    print(json.dumps({"ok": True}))
except Exception as exc:
    print(json.dumps({"ok": False, "error": "%%s: %%s" %% (type(exc).__name__, exc)}))
"""


@pytest.fixture(scope="session")
def sweep(run_probe) -> dict:
    """Import every non-test module under app/ once, and cache the outcome."""
    return run_probe(_SWEEP)


def test_the_sweep_actually_found_modules(sweep):
    """A sweep that silently collected nothing would pass every other test."""
    assert sweep["total"] > 100, (
        f"expected the app package to hold well over 100 modules, swept {sweep['total']}. "
        "The collector's filter is probably excluding too much."
    )


def test_no_module_imports_circularly(sweep):
    """A circular import is always a defect, never an accepted state.

    There is no allowlist for this one: unlike a missing optional dependency, a
    cycle is entirely within the project's control.
    """
    assert sweep["circular"] == {}, (
        "circular imports detected:\n"
        + "\n".join(f"  {mod}: {err}" for mod, err in sweep["circular"].items())
    )


def test_no_unexpected_import_failures(sweep):
    """Every failing import must be a registered known failure or regression.

    This is the test that catches the next 68d4cdb. A module that starts
    failing without an entry in either registry fails here by name.
    """
    expected = set(KNOWN_IMPORT_FAILURES) | set(IMPORT_REGRESSIONS)
    unexpected = {
        mod: err for mod, err in sweep["failures"].items() if mod not in expected
    }
    assert unexpected == {}, (
        "modules failing to import with no registry entry:\n"
        + "\n".join(f"  {mod}: {err}" for mod, err in unexpected.items())
        + "\n\nIf this is a new defect, fix it. If it is genuinely permanent, "
        "add it to KNOWN_IMPORT_FAILURES in tests/conftest.py with a reason."
    )


@pytest.mark.parametrize("module", sorted(KNOWN_IMPORT_FAILURES))
def test_known_import_failures_still_fail(sweep, module):
    """A known failure that starts working means the registry is stale.

    Without this, KNOWN_IMPORT_FAILURES would only ever grow, and would slowly
    stop describing the repository.
    """
    assert module in sweep["failures"], (
        f"{module} now imports cleanly. Remove it from KNOWN_IMPORT_FAILURES "
        "in tests/conftest.py so the registry keeps meaning something."
    )


# One case per regression, each carrying the registry's own reason string so
# there is a single source of truth for what is broken and why.
_REGRESSION_CASES = [
    pytest.param(module, marks=pytest.mark.xfail(strict=True, reason=reason))
    for module, reason in sorted(IMPORT_REGRESSIONS.items())
]


@pytest.mark.parametrize("module", _REGRESSION_CASES)
def test_regressed_module_imports(run_probe, module):
    """Each regressed module must import again. Strict xfail is the ratchet.

    These xfail today. When the underlying defect is fixed the test XPASSes,
    and ``strict=True`` turns that into a failure — forcing the entry out of
    IMPORT_REGRESSIONS rather than letting a repaired module sit in a registry
    of broken ones forever.
    """
    result = run_probe(_SINGLE % module)
    assert result["ok"], f"{module} does not import: {result.get('error')}"
