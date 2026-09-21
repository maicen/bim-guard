"""Cross-module wiring checks that a unit test cannot see.

A unit test covers a module in isolation and passes; it cannot see whether
anything calls the code it covers. These few checks stay generic to the
codebase's own shape rather than to any one analysis domain.

Run: uv run pytest tests/test_integration.py -v
"""

from __future__ import annotations

import re

import pytest

from tests.conftest import REPO_ROOT

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
