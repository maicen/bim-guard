"""Pre-thesis repository validation pass.

Runs the eight-point validation the thesis compilation depends on, plus a
credential scan, and prints a pass/fail summary. Every check is read-only:
nothing here writes to the repository, the database, or the network.

Usage::

    uv run python scripts/validate_repo.py            # full pass
    uv run python scripts/validate_repo.py --list     # show check ids
    uv run python scripts/validate_repo.py -k flags   # run matching checks

Exit codes: 0 = every check passed, warned, or was skipped; 1 = at least one
FAIL.

Checks:
    1. tests         Full pytest suite under tests/.
    2. imports       Every module under app/ imports; no circular imports.
    3. flags         FEATURE_PATH_B_MM / FEATURE_PATH_B_XM work independently.
    4. adapter       Path A dict -> Issue -> UI dict roundtrip contract.
    5. orchestrator  orchestrate_workflow() end to end, flags on and off.
    6. lint          ruff check app/ against the recorded baseline.
    7. wiring        Integration points are called and call-compatible.
    8. blockers      Known issues are still known issues, not regressions.
    9. secrets       No credentials in tracked template files.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# The defect registries live in tests/conftest.py so pytest and this driver
# cannot drift apart about what is broken. Importing them here rather than
# restating them means a module repaired in one place is repaired in both.
from tests.conftest import (  # noqa: E402 - needs REPO_ROOT on sys.path first
    IMPORT_REGRESSIONS,
    KNOWN_IMPORT_FAILURES,
)

# ruff error count for app/ at 4edba3a, the commit before this session's
# F-series (F2 producer overload, F4 adapter, F5 adapter tests, band casing,
# F6 wiring). A current count at or below this means no new lint debt.
RUFF_BASELINE = 346

# The suite size the work order expects. Anything lower means tests went missing.
EXPECTED_MIN_PASSED = 277

# Modules that have never imported in a plain checkout, with the reason. These
# are reported but not counted as blockers: an import failure outside this map
# is new, and that is the signal the check exists to give.
KNOWN_TEST_FAILURES = {
    "tests/test_anode_convention.py::test_verify_script_runs_and_reports_the_expected_convention":
        "Windows-only harness bug: subprocess.run(text=True) with no encoding hits cp1252 "
        "on the script's em-dash. The script itself exits 0 - see check 'blockers'.",
    "tests/test_compliance_orchestrator.py":
        "Pre-dates this session (B1 in the integration plan): the file imports "
        "ComplianceOrchestrator, which F6 replaced with orchestrate_workflow. Pinned by "
        "tests/test_orchestrator.py::test_known_broken_orchestrator_test_is_still_broken.",
}

PASS, FAIL, WARN, SKIP = "PASS", "FAIL", "WARN", "SKIP"

_STATUS_ORDER = {FAIL: 0, WARN: 1, SKIP: 2, PASS: 3}


@dataclass
class Result:
    """Outcome of one validation check."""

    check_id: str
    title: str
    status: str
    summary: str
    details: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    known: list[str] = field(default_factory=list)


def run(argv: list[str], timeout: int = 900) -> subprocess.CompletedProcess:
    """Run a subprocess from the repo root, decoding as UTF-8.

    Windows consoles default to cp1252, which raises UnicodeDecodeError on the
    em-dashes this codebase prints. Decoding is pinned and errors are replaced
    so a check never fails on its own plumbing.
    """
    return subprocess.run(
        argv,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def run_python(
    source: str,
    env_extra: dict[str, str] | None = None,
    timeout: int = 900,
) -> subprocess.CompletedProcess:
    """Run a Python snippet in a child interpreter and return its result.

    Args:
        source: Snippet to execute. It must print a single JSON verdict line.
        env_extra: Environment overrides layered on the current environment.
        timeout: Seconds before the child is killed.
    """
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
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


def last_json(stdout: str) -> dict:
    """Parse the last JSON object printed on stdout.

    Child snippets print their verdict last, so incidental prints from imported
    modules cannot corrupt the parse.

    Raises:
        ValueError: If no JSON object line is present.
    """
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise ValueError(f"no JSON verdict in output:\n{stdout[-2000:]}")


# ---------------------------------------------------------------------------
# 1. Full test suite
# ---------------------------------------------------------------------------


def check_tests() -> Result:
    """Run tests/ and require zero failures and zero collection errors."""
    proc = run([
        sys.executable, "-m", "pytest", "tests/", "-q", "--no-header",
        "--continue-on-collection-errors", "-p", "no:cacheprovider",
    ])
    lines = proc.stdout.strip().splitlines()
    summary_line = next(
        (ln for ln in reversed(lines) if re.search(r"\d+ (passed|failed|error)", ln)), ""
    )

    def count(word: str) -> int:
        match = re.search(rf"(\d+) {word}", summary_line)
        return int(match.group(1)) if match else 0

    passed, failed, errors = count("passed"), count("failed"), count("error")
    skipped, xfailed = count("skipped"), count("xfailed")

    details = [f"summary line: {summary_line or '(not found)'}"]
    blockers: list[str] = []
    known: list[str] = []
    new_breaks = 0

    for line in lines:
        if not line.startswith(("FAILED", "ERROR")):
            continue
        node = line.split(" ", 1)[-1].split(" - ")[0].strip()
        reason = KNOWN_TEST_FAILURES.get(node)
        if reason:
            details.append(f"known  {line}")
            known.append(f"test: {node} - {reason}")
        else:
            new_breaks += 1
            details.append(f"NEW    {line}")
            blockers.append(line.strip())

    if new_breaks == 0 and passed >= EXPECTED_MIN_PASSED:
        status = PASS if not known else WARN
        summary = (
            f"{passed} passed, {skipped} skipped, {xfailed} xfailed"
            + (f", {len(known)} known break(s)" if known else "")
        )
    elif new_breaks == 0:
        status = WARN
        summary = f"{passed} passed but expected at least {EXPECTED_MIN_PASSED}"
    else:
        status = FAIL
        summary = (
            f"{passed} passed, {failed} failed, {errors} collection error(s); "
            f"{new_breaks} not previously known"
        )

    return Result("tests", "Full test suite", status, summary, details, blockers, known)


# ---------------------------------------------------------------------------
# 2. Import chain
# ---------------------------------------------------------------------------

_IMPORT_PROBE = r"""
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

failures, circular = [], []
for name in modules:
    try:
        importlib.import_module(name)
    except Exception as exc:
        text = "%s: %s" % (type(exc).__name__, exc)
        entry = {"module": name, "error": text}
        low = text.lower()
        if "partially initialized" in low or "circular import" in low:
            circular.append(entry)
        failures.append(entry)

print(json.dumps({"total": len(modules), "failures": failures, "circular": circular}))
"""


def check_imports() -> Result:
    """Import every non-test module under app/ and report failures."""
    proc = run_python(_IMPORT_PROBE)
    try:
        data = last_json(proc.stdout)
    except ValueError:
        return Result(
            "imports", "Import chain", FAIL, "probe crashed",
            [proc.stderr[-2000:]], ["import probe did not complete"],
        )

    failures, circular = data["failures"], data["circular"]
    details = [f"{data['total']} modules probed"]
    blockers, known = [], []

    regressed, unregistered = [], []
    for failure in failures:
        module, error = failure["module"], failure["error"]
        if module in KNOWN_IMPORT_FAILURES:
            details.append(f"known       {module}: {error}")
            known.append(f"import: {module} - {KNOWN_IMPORT_FAILURES[module]}")
        elif module in IMPORT_REGRESSIONS:
            regressed.append(module)
            details.append(f"REGRESSION  {module}: {error}")
            blockers.append(f"{module} does not import. {IMPORT_REGRESSIONS[module]}")
        else:
            unregistered.append(module)
            details.append(f"UNREGISTERED {module}: {error}")
            blockers.append(
                f"{module} does not import and is in neither registry: {error}"
            )

    if circular:
        cycles = [c["module"] for c in circular]
        return Result(
            "imports", "Import chain", FAIL,
            f"{len(circular)} circular import(s): {', '.join(cycles)}",
            details, blockers, known,
        )
    if unregistered or regressed:
        parts = []
        if unregistered:
            parts.append(f"{len(unregistered)} unregistered")
        if regressed:
            parts.append(f"{len(regressed)} regression(s)")
        parts.append(f"{len(known)} known, no circular deps")
        return Result(
            "imports", "Import chain", FAIL, ", ".join(parts), details, blockers, known,
        )
    return Result(
        "imports", "Import chain", PASS,
        f"{data['total'] - len(failures)}/{data['total']} import; "
        f"{len(failures)} known-broken; no circular deps",
        details, known=known,
    )


# ---------------------------------------------------------------------------
# 3. Feature flags
# ---------------------------------------------------------------------------

_CONFIG_FLAG_PROBE = r"""
import json, sys
sys.path.insert(0, ".")
try:
    from dotenv import load_dotenv; load_dotenv()
except Exception:
    pass
try:
    import app.modules.config as cfg
    print(json.dumps({
        "ok": True,
        "mm": bool(cfg.FEATURE_PATH_B_MM),
        "xm": bool(cfg.FEATURE_PATH_B_XM),
    }))
except Exception as exc:
    print(json.dumps({"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}))
"""

_ORCH_FLAG_PROBE = r"""
import json, os, sys
sys.path.insert(0, ".")
src = open("app/modules/comparator/compliance_orchestrator.py", encoding="utf-8").read()
print(json.dumps({
    "mm": os.environ.get("FEATURE_PATH_B_MM", "0") == "1",
    "xm": os.environ.get("FEATURE_PATH_B_XM", "0") == "1",
    "reads_env": 'os.environ.get("FEATURE_PATH_B_MM"' in src,
    "reads_config": "app.modules.config" in src,
}))
"""

_FLAG_COMBOS = [("0", "0"), ("1", "0"), ("0", "1"), ("1", "1")]


def check_flags() -> Result:
    """Verify the two Path B flags are independently switchable."""
    details: list[str] = []
    blockers: list[str] = []
    status = PASS

    # 3a. config.py flags, which read SettingsService and then the environment.
    for mm, xm in _FLAG_COMBOS:
        proc = run_python(
            _CONFIG_FLAG_PROBE,
            {"FEATURE_PATH_B_MM": mm, "FEATURE_PATH_B_XM": xm},
        )
        try:
            data = last_json(proc.stdout)
        except ValueError:
            details.append(f"config MM={mm} XM={xm}: probe produced no verdict")
            status = FAIL
            blockers.append("app.modules.config flag probe did not complete")
            continue
        if not data.get("ok"):
            details.append(f"config MM={mm} XM={xm}: import failed - {data['error']}")
            status = FAIL
            blockers.append(
                "app.modules.config cannot be imported without a database: "
                f"{data['error']}. SettingsService() is instantiated at module import "
                "time, so FEATURE_PATH_B_* in config.py is unreachable offline."
            )
            continue
        want = (mm == "1", xm == "1")
        got = (data["mm"], data["xm"])
        details.append(
            f"config MM={mm} XM={xm} -> {got} [{'ok' if got == want else 'MISMATCH'}]"
        )
        if got != want:
            status = FAIL
            blockers.append(
                f"app.modules.config flags do not follow the environment for MM={mm} XM={xm}"
            )

    # 3b. The orchestrator's own flag reads, which bypass config.py entirely.
    for mm, xm in _FLAG_COMBOS:
        proc = run_python(
            _ORCH_FLAG_PROBE,
            {"FEATURE_PATH_B_MM": mm, "FEATURE_PATH_B_XM": xm},
        )
        data = last_json(proc.stdout)
        want = (mm == "1", xm == "1")
        got = (data["mm"], data["xm"])
        details.append(
            f"orchestrator MM={mm} XM={xm} -> {got} [{'ok' if got == want else 'MISMATCH'}]"
        )
        if got != want:
            status = FAIL
            blockers.append(
                f"orchestrator flags do not follow the environment for MM={mm} XM={xm}"
            )

    # 3c. Two independent flag sources is itself the defect worth naming.
    data = last_json(run_python(_ORCH_FLAG_PROBE).stdout)
    if data["reads_env"] and not data["reads_config"]:
        if status == PASS:
            status = WARN
        details.append(
            "compliance_orchestrator.py reads os.environ directly and never imports "
            "app.modules.config, so the two flag sources can disagree"
        )
        blockers.append(
            "Flag source split: FEATURE_PATH_B_* set through SettingsService (the "
            "database) is invisible to orchestrate_workflow(), which only reads "
            "os.environ. One switch, two truths."
        )

    summary = "independent and correct" if status == PASS else "see details"
    return Result("flags", "Feature flags", status, summary, details, blockers)


# ---------------------------------------------------------------------------
# 4. Adapter contract
# ---------------------------------------------------------------------------

_ADAPTER_PROBE = r'''
import copy, json, sys
sys.path.insert(0, ".")
from app.modules.comparator.issue_adapter import (
    IssueIdAllocator, issues_from_path_a, path_a_view,
)
from app.modules.comparator.issue_schema import RiskBand, make_issue

checks = {}


def note(name, ok, msg=""):
    checks[name] = {"ok": bool(ok), "msg": msg}


base = [
    {
        "guid": "GUID-A", "name": "SS316 Flanged Joint",
        "galvanic_band": "MEDIUM", "galvanic_score": 0.42, "voltage_gap_V": 0.35,
        "crevice_band": "CRITICAL", "crevice_score": 0.89, "crevice_geometry": "Crevice",
        "mic_band": "LOW", "mic_score": 0.05,
        "dominant_mechanism": "crevice", "mitigation": "Isolate", "action": "BLOCK",
    },
    {
        "guid": "GUID-B", "name": "Compliant Copper Run",
        "galvanic_band": "LOW", "galvanic_score": 0.05,
        "dominant_mechanism": "galvanic", "mitigation": "", "action": "PASS",
    },
]
frozen = copy.deepcopy(base)

issues = issues_from_path_a(base, id_allocator=IssueIdAllocator("BGR-TEST"))

# A1: one Issue per element per non-LOW mechanism, not one per element.
note("A1_one_issue_per_mechanism", len(issues) == 2,
     "expected 2 (GC MEDIUM + CC CRITICAL), got %d" % len(issues))

# A2: LOW is excluded by default and included on request.
low = issues_from_path_a(base, id_allocator=IssueIdAllocator("BGR-TEST"), include_low=True)
note("A2_include_low", len(low) == 4, "expected 4 with include_low, got %d" % len(low))

# A3: ids are unique and carry the mechanism prefix.
ids = [i.id for i in issues]
note("A3_ids_unique_and_prefixed",
     len(set(ids)) == len(ids) and all(i.split("-")[0] in {"GC", "CC", "MC"} for i in ids),
     "ids=%s" % ids)

# A4: emission order is galvanic, crevice, MIC.
note("A4_mechanism_order", [i.rule_id for i in issues] == ["GC-001.01", "CC-001.01"],
     "rule_ids=%s" % [i.rule_id for i in issues])

# A5: band strings normalise onto the enum.
note("A5_band_normalised", [i.band.value for i in issues] == ["medium", "critical"],
     "bands=%s" % [i.band.value for i in issues])

# A6: an unknown band raises rather than silently mislabelling.
try:
    issues_from_path_a(
        [{"guid": "X", "name": "X", "galvanic_band": "SEVERE", "galvanic_score": 1.0}],
        id_allocator=IssueIdAllocator("BGR-TEST"),
    )
    note("A6_unknown_band_raises", False, "no ValueError raised")
except ValueError:
    note("A6_unknown_band_raises", True)

# A7: the projection keeps the element spine and never mutates its input.
view = path_a_view(issues, base)
note("A7_input_not_mutated", base == frozen, "path_a_view mutated base_results")
note("A7_spine_preserved",
     len(view) == 2 and [r["guid"] for r in view] == ["GUID-A", "GUID-B"],
     "guids=%s" % [r.get("guid") for r in view])
note("A7_original_keys_kept", all(k in view[0] for k in base[0]),
     "an original per-element key was dropped")
note("A7_projection_keys_added",
     all(k in view[0] for k in
         ("path_b_issues", "path_b_band", "path_b_count", "mm_band", "xm_band")),
     "a path_b_* projection key is missing")

# A8: worst band wins by severity rank, not string order.
note("A8_worst_band_wins", view[0]["path_b_band"] == "critical",
     "path_b_band=%s" % view[0]["path_b_band"])

# A9: a compliant element still gets a row, so the denominator survives.
note("A9_compliant_row_kept", view[1]["path_b_count"] == 0,
     "compliant row count=%s" % view[1]["path_b_count"])

# A10: an Issue with no matching row is appended and flagged, not dropped.
orphan = make_issue(id="XM-0001", element_id="GUID-Z", rule_id="XM-001.zinc.copper",
                    title="orphan", mechanism="XM-001 high", band=RiskBand.HIGH,
                    score=0.7, mitigation="Isolate the couple")
view2 = path_a_view(issues + [orphan], base)
orphans = [r for r in view2 if r.get("path_b_only")]
note("A10_orphan_appended",
     len(orphans) == 1 and orphans[0]["guid"] == "GUID-Z" and orphans[0]["xm_band"] == "high",
     "orphan rows=%d" % len(orphans))

print(json.dumps({"checks": checks}))
'''


def check_adapter() -> Result:
    """Exercise the Path A dict -> Issue -> UI dict roundtrip."""
    proc = run_python(_ADAPTER_PROBE)
    try:
        data = last_json(proc.stdout)
    except ValueError:
        return Result(
            "adapter", "Adapter contract", FAIL, "probe crashed",
            [proc.stderr[-2000:]], ["adapter smoke test did not run"],
        )

    details, blockers = [], []
    failed = 0
    for name, outcome in data["checks"].items():
        ok = outcome["ok"]
        failed += not ok
        suffix = "" if ok else f" - {outcome['msg']}"
        details.append(f"{'ok  ' if ok else 'FAIL'} {name}{suffix}")
        if not ok:
            blockers.append(f"adapter contract {name}: {outcome['msg']}")

    total = len(data["checks"])
    if failed:
        return Result(
            "adapter", "Adapter contract", FAIL,
            f"{total - failed}/{total} assertions held", details, blockers,
        )
    return Result(
        "adapter", "Adapter contract", PASS,
        f"all {total} roundtrip assertions held", details,
    )


# ---------------------------------------------------------------------------
# 5. Orchestrator end to end
# ---------------------------------------------------------------------------

_ORCH_PROBE = r"""
import json, sys, types
sys.path.insert(0, ".")
try:
    from dotenv import load_dotenv; load_dotenv()
except Exception:
    pass

verdict = {"imported": False}
try:
    from app.modules.comparator.compliance_orchestrator import orchestrate_workflow
    verdict["imported"] = True
except Exception as exc:
    verdict["error"] = "%s: %s" % (type(exc).__name__, exc)
    print(json.dumps(verdict))
    raise SystemExit(0)

# A minimal stand-in for one IFC piping element. Deliberately a plain object:
# the point is to see how far the pipeline gets, not to test ifcopenshell.
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

try:
    rows = orchestrate_workflow([element], run_id="BGR-VALIDATE")
    verdict["ran"] = True
    verdict["rows"] = len(rows)
    verdict["path_b_total"] = sum(r.get("path_b_count", 0) for r in rows)
except Exception as exc:
    verdict["ran"] = False
    verdict["error"] = "%s: %s" % (type(exc).__name__, exc)

print(json.dumps(verdict))
"""


def check_orchestrator() -> Result:
    """Run orchestrate_workflow() against a mock element under all flag combos."""
    details, blockers = [], []
    status = PASS
    import_error = None

    for mm, xm in _FLAG_COMBOS:
        proc = run_python(_ORCH_PROBE, {"FEATURE_PATH_B_MM": mm, "FEATURE_PATH_B_XM": xm})
        try:
            data = last_json(proc.stdout)
        except ValueError:
            details.append(f"MM={mm} XM={xm}: probe produced no verdict")
            status = FAIL
            continue

        if not data["imported"]:
            import_error = data.get("error", "unknown")
            details.append(f"MM={mm} XM={xm}: module does not import - {import_error}")
            status = FAIL
            continue

        if not data.get("ran"):
            details.append(f"MM={mm} XM={xm}: raised - {data.get('error')}")
            status = FAIL
            blockers.append(f"orchestrate_workflow() raised with MM={mm} XM={xm}: {data.get('error')}")
            continue

        # Path B prints its exceptions and continues, so a silent zero under a
        # flag that is on is a finding, not a pass.
        note = ""
        if (mm == "1" or xm == "1") and data["path_b_total"] == 0:
            note = "  <- flag on but zero Path B findings (swallowed exception?)"
            if status == PASS:
                status = WARN
        details.append(
            f"MM={mm} XM={xm}: {data['rows']} row(s), "
            f"{data['path_b_total']} Path B finding(s){note}"
        )
        swallowed = [ln for ln in proc.stdout.splitlines() if "error:" in ln.lower()]
        details.extend(f"    swallowed: {ln}" for ln in swallowed[:3])
        if swallowed:
            blockers.append(f"Path B swallowed an exception with MM={mm} XM={xm}: {swallowed[0]}")

    if import_error:
        blockers.insert(0, f"orchestrate_workflow() is unreachable: {import_error}")
        return Result(
            "orchestrator", "Orchestrator end to end", FAIL,
            "module does not import", details, blockers,
        )

    summary = "ran under all four flag combinations" if status == PASS else "see details"
    return Result("orchestrator", "Orchestrator end to end", status, summary, details, blockers)


# ---------------------------------------------------------------------------
# 6. Lint
# ---------------------------------------------------------------------------


def check_lint() -> Result:
    """Compare ruff's error count for app/ against the recorded baseline."""
    proc = run(["uvx", "ruff", "check", "app/", "--output-format", "concise"], timeout=600)
    if proc.returncode not in (0, 1):
        return Result(
            "lint", "Lint / style", SKIP,
            "ruff unavailable (uvx could not run it)", [proc.stderr[-500:]],
        )

    lines = [ln for ln in proc.stdout.splitlines() if re.match(r"^\S+\.py:\d+:\d+:", ln)]
    count = len(lines)

    by_rule: dict[str, int] = {}
    for line in lines:
        match = re.search(r":\d+:\d+: ([A-Z]+\d+)", line)
        if match:
            by_rule[match.group(1)] = by_rule.get(match.group(1), 0) + 1

    top = ", ".join(f"{r} x{n}" for r, n in sorted(by_rule.items(), key=lambda kv: -kv[1])[:6])
    details = [
        f"baseline at 4edba3a: {RUFF_BASELINE}",
        f"current: {count}",
        f"top rules: {top}",
    ]

    if count <= RUFF_BASELINE:
        return Result(
            "lint", "Lint / style", PASS,
            f"{count} findings, {RUFF_BASELINE - count} below baseline", details,
        )
    return Result(
        "lint", "Lint / style", WARN,
        f"{count} findings, {count - RUFF_BASELINE} above baseline", details,
        [f"ruff count for app/ rose from {RUFF_BASELINE} to {count}"],
    )


# ---------------------------------------------------------------------------
# 7. Integration points
# ---------------------------------------------------------------------------

_WIRING_PROBE = r"""
import ast, inspect, json, sys
from pathlib import Path
sys.path.insert(0, ".")

out = {}

# 7a. Is the F2 producer overload called by anything outside its own module?
producer = Path("app/modules/ifc_reader/piping_producer.py")
callers = []
for path in list(Path("app").rglob("*.py")) + list(Path("tests").rglob("*.py")):
    if path == producer or "__pycache__" in path.parts:
        continue
    if "produce_piping_elements_from_model" in path.read_text(encoding="utf-8", errors="replace"):
        callers.append(str(path).replace("\\", "/"))
out["f2_callers"] = callers
out["f2_app_callers"] = [c for c in callers if c.startswith("app/")]

orch_path = Path("app/modules/comparator/compliance_orchestrator.py")
orch_src = orch_path.read_text(encoding="utf-8", errors="replace")
out["orchestrator_uses_producer"] = "produce_piping_elements" in orch_src

# 7b. Do the orchestrator's Path B calls bind to compare()'s real signature?
targets = {"compare_mm": "material_media", "compare_xm": "cross_material"}
sigs = {}
try:
    from app.modules.comparator import cross_material, material_media
    sigs["material_media"] = inspect.signature(material_media.compare)
    sigs["cross_material"] = inspect.signature(cross_material.compare)
    out["signatures"] = {k: str(v) for k, v in sigs.items()}
except Exception as exc:
    out["signature_error"] = "%s: %s" % (type(exc).__name__, exc)

calls = []
for node in ast.walk(ast.parse(orch_src)):
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        continue
    alias = node.func.id
    if alias not in targets:
        continue
    kwargs = [kw.arg for kw in node.keywords if kw.arg]
    entry = {"alias": alias, "module": targets[alias], "positional": len(node.args),
             "kwargs": kwargs, "line": node.lineno}
    sig = sigs.get(targets[alias])
    if sig is not None:
        try:
            sig.bind(*[None] * len(node.args), **{k: None for k in kwargs})
            entry["binds"] = True
        except TypeError as exc:
            entry["binds"] = False
            entry["bind_error"] = str(exc)
    calls.append(entry)
out["path_b_calls"] = calls

# 7c. Does Path B honour the run-wide id allocator, or mint its own ids?
mm_src = Path("app/modules/comparator/material_media.py").read_text(
    encoding="utf-8", errors="replace")
xm_src = Path("app/modules/comparator/cross_material.py").read_text(
    encoding="utf-8", errors="replace")
out["path_b_mints_own_ids"] = ('id=f"BGR-' in mm_src) and ('id=f"BGR-' in xm_src)
out["path_b_accepts_allocator"] = "id_allocator" in mm_src or "id_allocator" in xm_src

print(json.dumps(out))
"""


def check_wiring() -> Result:
    """Confirm the new integration points are reached and call-compatible."""
    proc = run_python(_WIRING_PROBE)
    try:
        data = last_json(proc.stdout)
    except ValueError:
        return Result(
            "wiring", "Integration points", FAIL, "probe crashed",
            [proc.stderr[-2000:]], ["wiring probe did not complete"],
        )

    details, blockers = [], []
    status = PASS

    # F2: the producer overload.
    if data["f2_app_callers"]:
        details.append(
            "F2 produce_piping_elements_from_model called from: "
            + ", ".join(data["f2_app_callers"])
        )
    else:
        details.append(
            "F2 produce_piping_elements_from_model has no caller under app/ "
            f"(test-only references: {data['f2_callers'] or 'none'})"
        )
        status = FAIL
        blockers.append(
            "F2 is dead code in production: produce_piping_elements_from_model() is "
            "never called by the orchestrator or any other module under app/. Only the "
            "produce_piping_elements() wrapper inside piping_producer.py delegates to it, "
            "so the 'avoid a second ifcopenshell.open' win it was written for is unrealised."
        )

    if not data["orchestrator_uses_producer"]:
        details.append(
            "compliance_orchestrator.py never calls the piping producer at all - "
            "orchestrate_workflow() takes pre-built elements from its caller"
        )

    # Path B call compatibility.
    if "signature_error" in data:
        details.append(f"could not load comparator signatures: {data['signature_error']}")
        status = FAIL
        blockers.append(f"comparator modules do not import: {data['signature_error']}")
    else:
        for module, sig in data["signatures"].items():
            details.append(f"{module}.compare{sig}")

    for call in data["path_b_calls"]:
        if call.get("binds") is True:
            details.append(f"line {call['line']}: {call['alias']}(...) binds ok")
        elif call.get("binds") is False:
            details.append(
                f"line {call['line']}: {call['alias']}(...) DOES NOT BIND - {call['bind_error']}"
            )
            status = FAIL
            blockers.append(
                f"compliance_orchestrator.py:{call['line']} calls {call['alias']}() with "
                f"kwargs {call['kwargs']} - {call['bind_error']}. The call sits inside a bare "
                "`except Exception: print(...)`, so the feature flag turns on and silently "
                "produces no findings."
            )

    if data.get("path_b_mints_own_ids") and not data.get("path_b_accepts_allocator"):
        details.append(
            "material_media/cross_material still mint 'BGR-%04d' ids from a local counter"
        )
        if status == PASS:
            status = WARN
        blockers.append(
            "IssueIdAllocator is constructed and handed to issues_from_path_a(), but Path B "
            "ignores it: MM-001 and XM-001 each restart at BGR-0001, so a run with both flags "
            "on emits duplicate Issue ids - the exact collision IssueIdAllocator exists to "
            "prevent, and one BCF topic per id depends on."
        )

    summary = "all integration points wired" if status == PASS else "see details"
    return Result("wiring", "Integration points", status, summary, details, blockers)


# ---------------------------------------------------------------------------
# 8. Known blockers
# ---------------------------------------------------------------------------

_MAP_ORDERING_PROBE = r"""
import json, sys
sys.path.insert(0, ".")
try:
    from dotenv import load_dotenv; load_dotenv()
except Exception:
    pass
from app.modules.config import CODE_TO_IFC_MAP, IFC_PROPERTY_SET_MAP


def enrich(text):
    lowered = text.lower()
    for keyword, ifc in CODE_TO_IFC_MAP.items():
        if keyword in lowered:
            return ifc
    return None


print(json.dumps({
    "pipework_in_room": enrich("pipework in the pool plant room"),
    "duct_in_riser_room": enrich("duct in the riser room"),
    "pipe_pset": IFC_PROPERTY_SET_MAP.get("IfcPipeSegment"),
    "duct_pset": IFC_PROPERTY_SET_MAP.get("IfcDuctSegment"),
}))
"""


def check_blockers() -> Result:
    """Confirm the recorded known issues are unchanged, not regressed."""
    details, blockers, known = [], [], []
    status = PASS

    # 8a. Map ordering - docs/defects/defect_report_map_ordering.md.
    proc = run_python(_MAP_ORDERING_PROBE)
    try:
        data = last_json(proc.stdout)
    except ValueError:
        details.append("map-ordering probe failed to run (config needs a database)")
        status = WARN
    else:
        details.append(
            f"_enrich_target('pipework in the pool plant room') -> {data['pipework_in_room']}"
        )
        details.append(
            f"_enrich_target('duct in the riser room') -> {data['duct_in_riser_room']}"
        )
        details.append(f"IFC_PROPERTY_SET_MAP['IfcPipeSegment'] -> {data['pipe_pset']}")
        details.append(f"IFC_PROPERTY_SET_MAP['IfcDuctSegment'] -> {data['duct_pset']}")
        reproduces = (
            data["pipework_in_room"] == "IfcSpace"
            and data["duct_in_riser_room"] == "IfcStairFlight"
            and data["pipe_pset"] is None
            and data["duct_pset"] is None
        )
        if reproduces:
            known.append(
                "map ordering: reproduces exactly as the defect report records it - "
                "still a known issue, not a regression"
            )
        else:
            details.append("map-ordering reproduction no longer matches the defect report")
            status = WARN
            blockers.append(
                "map-ordering defect behaviour changed; defect_report_map_ordering.md is stale"
            )

    # 8b. Anode convention - settled at 4edba3a.
    proc = run([
        sys.executable, "-m", "pytest", "tests/test_anode_convention.py", "-q",
        "--no-header", "-p", "no:cacheprovider",
    ], timeout=600)
    tail = next(
        (ln for ln in reversed(proc.stdout.strip().splitlines())
         if re.search(r"\d+ (passed|failed)", ln)),
        "",
    )
    details.append(f"tests/test_anode_convention.py: {tail}")

    # The verification script is the substantive check. Run it directly so a
    # test-harness decoding bug cannot be mistaken for an engine regression.
    script = run([sys.executable, "scripts/verify_anode_convention.py", "--from-seeder"], timeout=300)
    convention_ok = (
        script.returncode == 0 and "CONVENTION: more_positive_is_anodic" in script.stdout
    )
    details.append(
        f"scripts/verify_anode_convention.py: exit {script.returncode}, "
        f"convention {'confirmed' if convention_ok else 'NOT confirmed'}"
    )

    if "failed" in tail and convention_ok:
        if status == PASS:
            status = WARN
        details.append(
            "the pytest failure is a harness bug, not an engine regression: the test calls "
            "subprocess.run(text=True) with no encoding, so Windows cp1252 chokes on the "
            "script's em-dash"
        )
        blockers.append(
            "tests/test_anode_convention.py::test_verify_script_runs_and_reports_the_"
            "expected_convention fails on Windows with UnicodeDecodeError. Fix: pass "
            "encoding='utf-8' to its subprocess.run call. The engine verdict is correct."
        )
        known.append("anode convention: engine verdict still correct - no regression")
    elif convention_ok:
        known.append("anode convention: settled and still correct - no regression")
    else:
        status = FAIL
        blockers.append(
            "anode convention verification no longer reports more_positive_is_anodic - "
            "this would be a genuine regression against 4edba3a"
        )

    summary = "known issues unchanged" if status == PASS else "see details"
    return Result("blockers", "Known blockers", status, summary, details, blockers, known)


# ---------------------------------------------------------------------------
# 9. Credential scan
# ---------------------------------------------------------------------------

_SECRET_PATTERNS = [
    (re.compile(r"sb_secret_[A-Za-z0-9_\-]{8,}"), "Supabase service-role key"),
    (re.compile(r"eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}"), "JWT"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "OpenAI-style API key"),
    (re.compile(r"AIza[A-Za-z0-9_\-]{30,}"), "Google API key"),
    (re.compile(r"https://[a-z0-9]{15,}\.supabase\.co"), "Supabase project URL"),
]

# Files that are tracked by git and meant to hold placeholders only.
_TEMPLATE_FILES = ["example.env", "README.md", "docker-compose.yml", "render.yaml", "Dockerfile"]


def check_secrets() -> Result:
    """Scan tracked template files for real credentials.

    A credential in example.env is one `git add` away from being permanent, so
    this runs before the thesis branch is packaged.
    """
    details, blockers = [], []
    status = PASS

    for rel in _TEMPLATE_FILES:
        path = REPO_ROOT / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern, label in _SECRET_PATTERNS:
            for match in pattern.finditer(text):
                line_no = text[: match.start()].count("\n") + 1
                token = match.group(0)
                redacted = token[:14] + "..." if len(token) > 14 else "..."
                details.append(f"{rel}:{line_no} {label} ({redacted})")
                status = FAIL
                blockers.append(
                    f"{rel}:{line_no} contains a real {label}. Remove it and rotate the "
                    "credential - it is in a file whose whole purpose is to be committed."
                )

    if status == PASS:
        details.append(
            f"scanned {len(_TEMPLATE_FILES)} template files, no credentials found"
        )
        return Result("secrets", "Credential scan", PASS, "template files are clean", details)
    return Result(
        "secrets", "Credential scan", FAIL,
        f"{len(blockers)} credential(s) in template files", details, blockers,
    )


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

CHECKS = [
    ("tests", check_tests),
    ("imports", check_imports),
    ("flags", check_flags),
    ("adapter", check_adapter),
    ("orchestrator", check_orchestrator),
    ("lint", check_lint),
    ("wiring", check_wiring),
    ("blockers", check_blockers),
    ("secrets", check_secrets),
]


def main() -> int:
    """Run the selected checks and print the summary. Returns the exit code."""
    parser = argparse.ArgumentParser(
        description="Pre-thesis repository validation pass.",
    )
    parser.add_argument("--list", action="store_true", help="list check ids and exit")
    parser.add_argument("-k", metavar="SUBSTR", help="only run checks whose id contains SUBSTR")
    args = parser.parse_args()

    if args.list:
        for check_id, _ in CHECKS:
            print(check_id)
        return 0

    selected = [(i, fn) for i, fn in CHECKS if not args.k or args.k in i]
    if not selected:
        print(f"no checks match {args.k!r}")
        return 1

    print("=" * 78)
    print("BIM-Guard pre-thesis validation")
    print(f"repo: {REPO_ROOT}")
    print("=" * 78)

    results: list[Result] = []
    for check_id, fn in selected:
        print(f"\n--- {check_id}", flush=True)
        try:
            result = fn()
        except Exception as exc:  # a broken check must not hide the others
            result = Result(
                check_id, check_id, FAIL,
                f"check crashed: {type(exc).__name__}: {exc}",
                blockers=[f"validation check {check_id!r} crashed: {exc}"],
            )
        results.append(result)
        print(f"    {result.status}: {result.summary}")
        for line in result.details:
            print(f"      {line}")

    print("\n" + "=" * 78)
    print("SUMMARY")
    print("=" * 78)
    width = max(len(r.title) for r in results)
    for result in sorted(results, key=lambda r: _STATUS_ORDER[r.status]):
        print(f"  {result.status:<5} {result.title:<{width}}  {result.summary}")

    blockers = [b for r in results for b in r.blockers]
    known = [k for r in results for k in r.known]

    if blockers:
        print(f"\nBLOCKERS ({len(blockers)})")
        for index, blocker in enumerate(blockers, 1):
            print(f"  {index}. {blocker}")

    if known:
        print(f"\nKNOWN ISSUES CONFIRMED ({len(known)})")
        for item in known:
            print(f"  - {item}")

    counts = {s: sum(r.status == s for r in results) for s in (PASS, WARN, SKIP, FAIL)}
    print(
        f"\n{counts[PASS]} passed, {counts[WARN]} warned, "
        f"{counts[SKIP]} skipped, {counts[FAIL]} failed"
    )
    verdict = "NOT READY for thesis compilation" if counts[FAIL] else "ready for thesis compilation"
    print(f"VERDICT: {verdict}")

    return 1 if counts[FAIL] else 0


if __name__ == "__main__":
    sys.exit(main())
