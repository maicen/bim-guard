"""The seams between modules: whether the new integration points are wired.

Unit tests cover each module in isolation and pass. What they cannot see is
whether anything calls the code they cover, or whether a caller's arguments fit
the callee's signature. Three of this session's defects live exactly there:

* the F2 producer overload has no caller anywhere under ``app/``;
* the F6 Path B call sites pass an ``id_allocator`` keyword the comparators do
  not accept, and a single element where a list is expected;
* ``IssueIdAllocator`` is constructed for the run and then ignored by the two
  comparators whose id collisions it exists to prevent.

Each is asserted here against the wiring the integration plan specifies, as a
strict xfail, so repairing the wiring turns the test green rather than needing
it rewritten.

The adapter roundtrip and the known-defect reproductions pass today. They are
the regression floor: whatever else moves, these must not.

Run: uv run pytest tests/test_integration.py -v
"""

from __future__ import annotations

import ast
import inspect
import re
import subprocess
import sys

import pytest

from app.modules.module4_comparator.issue_adapter import issues_from_path_a, path_a_view
from app.modules.module4_comparator.issue_schema import RiskBand, make_issue
from tests.conftest import REPO_ROOT

APP_DIR = REPO_ROOT / "app"
PRODUCER_PATH = APP_DIR / "modules" / "module2_ifc_read" / "piping_producer.py"
ORCHESTRATOR_PATH = APP_DIR / "modules" / "module4_comparator" / "compliance_orchestrator.py"


# ---------------------------------------------------------------------------
# F2: the producer overload
# ---------------------------------------------------------------------------


def test_producer_overload_has_a_production_caller():
    """Something outside piping_producer.py must use the open-model overload.

    This was an xfail: the overload existed and nothing under app/ called it,
    so the "avoid a second ifcopenshell.open on large models" win it was
    written for was never realised. ``phase_6b_parsing.parse_ifc_bytes`` now
    calls it, under ``with_piping``, to build the network MM-001 and XM-001
    read -- from the model it already has open, which is the whole point of the
    overload. The assertion is kept, now as a regression guard.
    """
    callers = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in APP_DIR.rglob("*.py")
        if path != PRODUCER_PATH
        and "__pycache__" not in path.parts
        and "produce_piping_elements_from_model" in path.read_text(
            encoding="utf-8", errors="replace"
        )
    ]
    assert callers, (
        "produce_piping_elements_from_model() is defined and documented as the "
        "preferred entry point, but nothing under app/ calls it"
    )


def test_producer_wrapper_delegates_to_the_overload():
    """The path-taking wrapper must not re-implement the extraction.

    This one passes: it is the half of F2 that did land, and it is what makes
    the dead-code finding above a wiring gap rather than a broken feature.
    """
    from app.modules.module2_ifc_read import piping_producer

    wrapper = inspect.getsource(piping_producer.produce_piping_elements)
    assert "produce_piping_elements_from_model(" in wrapper, (
        "produce_piping_elements() no longer delegates; the two entry points "
        "have diverged and can now disagree about the same model"
    )


# ---------------------------------------------------------------------------
# F6: Path B call compatibility
# ---------------------------------------------------------------------------

_PATH_B_ALIASES = {"compare_mm": "material_media", "compare_xm": "cross_material"}


def _path_b_call_sites() -> list[ast.Call]:
    """Return the orchestrator's calls to the imported comparator aliases."""
    tree = ast.parse(ORCHESTRATOR_PATH.read_text(encoding="utf-8"))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _PATH_B_ALIASES
    ]


def test_the_orchestrator_calls_both_comparators():
    """Both Path B packs are invoked somewhere in the module.

    Passes today. It is the premise the binding tests below depend on: a call
    that does not exist cannot be checked for signature compatibility.
    """
    aliases = {call.func.id for call in _path_b_call_sites()}
    assert aliases == set(_PATH_B_ALIASES), (
        f"expected calls to {sorted(_PATH_B_ALIASES)}, found {sorted(aliases)}"
    )


@pytest.mark.parametrize("alias", sorted(_PATH_B_ALIASES), ids=sorted(_PATH_B_ALIASES))
def test_path_b_call_sites_bind_to_the_comparator_signature(alias):
    """The orchestrator's arguments must fit the function it is calling.

    ``Signature.bind`` is the check the interpreter itself would run, done
    statically so it reports the mismatch without needing the surrounding
    module to import.
    """
    from app.modules.module4_comparator import cross_material, material_media

    module = {"material_media": material_media, "cross_material": cross_material}[
        _PATH_B_ALIASES[alias]
    ]
    signature = inspect.signature(module.compare)

    calls = [call for call in _path_b_call_sites() if call.func.id == alias]
    assert calls, f"no call to {alias}() found"

    for call in calls:
        keywords = [kw.arg for kw in call.keywords if kw.arg]
        try:
            signature.bind(*[None] * len(call.args), **dict.fromkeys(keywords))
        except TypeError as exc:
            pytest.fail(
                f"compliance_orchestrator.py:{call.lineno} calls {alias}("
                f"{len(call.args)} positional, {keywords}) but "
                f"{_PATH_B_ALIASES[alias]}.compare{signature} - {exc}"
            )


@pytest.mark.parametrize("module_name", ["material_media", "cross_material"])
def test_path_b_accepts_the_run_wide_id_allocator(module_name):
    """Both comparators must take ids from the run, not from a local counter."""
    from app.modules.module4_comparator import cross_material, material_media

    module = {"material_media": material_media, "cross_material": cross_material}[
        module_name
    ]
    parameters = inspect.signature(module.compare).parameters
    assert "id_allocator" in parameters, (
        f"{module_name}.compare() takes {sorted(parameters)} and mints its own "
        "'BGR-%04d' ids internally"
    )


def test_the_allocator_keeps_prefixes_independent():
    """Two prefixes count separately and never collide.

    Passes today: the allocator itself is correct. That is what makes the
    xfails above a wiring defect rather than a design one.
    """
    from app.modules.module4_comparator.issue_adapter import IssueIdAllocator

    alloc = IssueIdAllocator("BGR-2026")
    minted = [alloc.next("MM"), alloc.next("XM"), alloc.next("MM"), alloc.next("XM")]
    assert minted == ["MM-0001", "XM-0001", "MM-0002", "XM-0002"]
    assert len(set(minted)) == 4


# ---------------------------------------------------------------------------
# F4: the adapter roundtrip, end to end
# ---------------------------------------------------------------------------


def test_path_a_dict_to_issue_to_ui_dict_roundtrip(path_a_results, allocator):
    """One Path A element survives the full trip onto a renderable row.

    tests/test_issue_adapter.py pins the adapter's internals. This is the
    integration statement: the shape the runner emits goes in, and the shape
    the analyze card reads comes out, with nothing lost in between.
    """
    original = [dict(row) for row in path_a_results]

    issues = issues_from_path_a(path_a_results, id_allocator=allocator)

    # Two mechanisms above LOW on element A. Element B carries only a galvanic
    # band, so crevice and MIC were never assessed for it — reported as
    # data_quality rather than passed over, which would state that an
    # unassessed mechanism is compliant (data contracts §4.2 failure mode 5).
    assert [issue.rule_id for issue in issues] == [
        "GC-001.01",
        "CC-001.01",
        "CC-001.DATA",
        "MC-001.DATA",
    ]
    findings = [i for i in issues if i.mechanism != "data_quality"]
    assert [issue.band for issue in findings] == [RiskBand.MEDIUM, RiskBand.CRITICAL]
    assert len({issue.id for issue in issues}) == len(issues)

    rows = path_a_view(issues, path_a_results)

    assert path_a_results == original, "path_a_view mutated the dicts it was given"
    assert [row["guid"] for row in rows] == ["GUID-A", "GUID-B"]

    flagged, compliant = rows
    assert flagged["path_b_count"] == 2
    assert flagged["path_b_band"] == "critical", "worst band must win by rank, not alphabetically"
    assert flagged["name"] == "SS316 Flanged Joint", "an original key was dropped"
    assert compliant["path_b_count"] == 0, "the compliant element must keep its row"


def test_an_issue_with_no_matching_element_becomes_its_own_row(path_a_results, allocator):
    """An XM couple whose anode is absent from Path A must not vanish.

    Dropping it would under-report silently, which for a compliance tool is
    worse than a visible error.
    """
    issues = issues_from_path_a(path_a_results, id_allocator=allocator)
    orphan = make_issue(
        id="XM-0001",
        element_id="GUID-ABSENT",
        rule_id="XM-001.zinc.copper",
        title="dissimilar couple",
        mechanism="XM-001 high",
        band=RiskBand.HIGH,
        score=0.7,
        mitigation="Isolate the couple",
    )

    rows = path_a_view([*issues, orphan], path_a_results)
    appended = [row for row in rows if row.get("path_b_only")]

    assert len(appended) == 1
    assert appended[0]["guid"] == "GUID-ABSENT"
    assert appended[0]["xm_band"] == "high"


# ---------------------------------------------------------------------------
# Known defects: still known, and still exactly as recorded
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


def test_map_ordering_defect_reproduces_as_documented(run_probe):
    """docs/defects/defect_report_map_ordering.md still describes reality.

    This asserts the *broken* behaviour on purpose. The defect is open and
    unscheduled; what must not happen is for it to change shape without the
    report being updated, because the thesis cites these exact two examples.
    """
    result = run_probe(_MAP_ORDERING_PROBE)

    assert result["pipework_in_room"] == "IfcSpace", (
        "first-match-wins over CODE_TO_IFC_MAP no longer sends 'pipework in the "
        "pool plant room' to IfcSpace - the defect report is now stale"
    )
    assert result["duct_in_riser_room"] == "IfcStairFlight", (
        "'duct in the riser room' no longer resolves to IfcStairFlight - the "
        "defect report is now stale"
    )
    assert result["pipe_pset"] is None
    assert result["duct_pset"] is None


def test_anode_convention_still_holds():
    """The galvanic series convention settled at 4edba3a has not drifted.

    Run as a subprocess with the encoding pinned. The existing
    tests/test_anode_convention.py makes the same call without an encoding and
    fails on Windows for that reason alone, which is a harness bug rather than
    an engine regression - the distinction this test exists to keep clear.
    """
    proc = subprocess.run(
        [sys.executable, "scripts/verify_anode_convention.py", "--from-seeder"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )

    if proc.returncode == 2:
        pytest.skip("seeded GC-001 payload not recoverable in this checkout")

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "CONVENTION: more_positive_is_anodic" in proc.stdout


# ---------------------------------------------------------------------------
# Deployment hygiene
# ---------------------------------------------------------------------------

_SECRET_PATTERNS = [
    (re.compile(r"sb_secret_[A-Za-z0-9_\-]{8,}"), "Supabase service-role key"),
    (re.compile(r"eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}"), "JWT"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "OpenAI-style API key"),
    (re.compile(r"AIza[A-Za-z0-9_\-]{30,}"), "Google API key"),
    (re.compile(r"https://[a-z0-9]{15,}\.supabase\.co"), "Supabase project URL"),
]

# Files whose entire purpose is to be committed, and which must therefore hold
# placeholders only.
_TEMPLATE_FILES = [
    "example.env",
    "README.md",
    "docker-compose.yml",
    "render.yaml",
    "Dockerfile",
]


@pytest.mark.parametrize("relative_path", _TEMPLATE_FILES)
def test_template_files_hold_no_credentials(relative_path):
    """A secret in a template file is one `git add` away from being permanent.

    Deliberately not xfailed. If this goes red, the finding is in the working
    tree right now and the fix is to remove the value and rotate the
    credential - not to record it as a known issue.
    """
    path = REPO_ROOT / relative_path
    if not path.is_file():
        pytest.skip(f"{relative_path} is not present in this checkout")

    text = path.read_text(encoding="utf-8", errors="replace")
    findings = []
    for pattern, label in _SECRET_PATTERNS:
        for match in pattern.finditer(text):
            line_number = text[: match.start()].count("\n") + 1
            token = match.group(0)
            redacted = token[:12] + "..." if len(token) > 12 else "..."
            findings.append(f"{relative_path}:{line_number} {label} ({redacted})")

    assert not findings, (
        "credential-shaped values in a file meant for the repository:\n"
        + "\n".join(f"  {item}" for item in findings)
        + "\n\nRemove the value and rotate the credential."
    )
