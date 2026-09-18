"""The New Project wizard's Details-step lock-chain and client pick-list.

The rules live in ``frontend/src/lib/projectDetails.ts`` (plain TypeScript,
no Svelte) and ``ProjectDetailsStep.svelte`` wraps them in ``$derived``. The
frontend has no test runner of its own, so these tests execute the module
under Node's built-in type stripping (Node >= 22.6) and assert on what it
returns -- the real code, not a Python re-implementation of it. They skip
where no suitable Node is installed.

A few source-level checks at the end hold the two wizards to the shared
component, so neither can drift back to its own copy of Step 1.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"
MODULE = FRONTEND_SRC / "lib" / "projectDetails.ts"

CHAIN = ["clientName", "name", "shortName", "projectCode", "country", "projectType"]
FILLED = {
    "clientName": "Northwind Health Trust",
    "name": "Clinic extension",
    "shortName": "Clinic Ext",
    "projectCode": "CLX1",
    "country": "Canada",
    "projectType": "MEDICAL",
}


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


def _call(function: str, *args: object) -> object:
    """Run ``function(*args)`` from projectDetails.ts under Node, return its JSON result."""
    script = (
        f"const m = await import({json.dumps(MODULE.as_uri())});"
        f"console.log(JSON.stringify(m.{function}(...{json.dumps(list(args))})));"
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


def _locks(**values: str) -> dict[str, str | None]:
    return _call("detailLocks", {key: values.get(key, "") for key in CHAIN})


def _unlocked(locks: dict[str, str | None]) -> list[str]:
    return [key for key in CHAIN if locks[key] is None]


# ── lock-chain order ─────────────────────────────────────────────────────────


def test_empty_form_unlocks_only_client_name():
    """Client Name is first in the chain and the only field open on a blank form."""
    assert _unlocked(_locks()) == ["clientName"]


@pytest.mark.parametrize("filled_count", range(len(CHAIN) + 1))
def test_each_field_unlocks_once_every_field_before_it_is_filled(filled_count: int):
    """Filling the chain in order opens exactly one more field per step."""
    values = {key: FILLED[key] for key in CHAIN[:filled_count]}
    expected = CHAIN[: min(filled_count + 1, len(CHAIN))]
    assert _unlocked(_locks(**values)) == expected


def test_later_fields_stay_locked_when_an_earlier_one_is_skipped():
    """Filling past a gap unlocks nothing beyond the gap."""
    values = dict(FILLED)
    values["shortName"] = ""
    locks = _locks(**values)
    assert _unlocked(locks) == ["clientName", "name", "shortName"]
    # Every field after the gap names the gap, the one to fill next.
    for key in ("projectCode", "country", "projectType"):
        assert locks[key] == "Enter the short name first."


def test_clearing_client_name_relocks_the_whole_chain():
    """Emptying the first field re-locks everything after it."""
    values = dict(FILLED, clientName="")
    locks = _locks(**values)
    assert _unlocked(locks) == ["clientName"]
    assert all(locks[key] == "Enter the client name first." for key in CHAIN[1:])


def test_whitespace_does_not_count_as_filled():
    """A field holding only spaces is still empty for the chain."""
    assert _unlocked(_locks(clientName="   ")) == ["clientName"]


def test_hint_names_the_earliest_missing_field_with_its_verb():
    """Text fields say Enter, choice fields say Select."""
    locks = _locks(**dict(FILLED, name=""))
    assert locks["shortName"] == "Enter the project name first."
    locks = _locks(**dict(FILLED, country=""))
    assert locks["projectType"] == "Select the jurisdiction first."


def test_optional_fields_are_not_in_the_chain():
    """Description, size, buildings and floors never lock."""
    required = [field["key"] for field in _call_json_constant("REQUIRED_DETAIL_FIELDS")]
    assert required == CHAIN
    for optional in ("description", "projectSizeSqm", "buildingsCount", "floorsCount"):
        assert optional not in required


def _call_json_constant(name: str) -> object:
    script = (
        f"const m = await import({json.dumps(MODULE.as_uri())});"
        f"console.log(JSON.stringify(m.{name}));"
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


# ── client name: free text or a pick from prior clients ─────────────────────

KNOWN = ["Acme Developments", "Northwind Health Trust", "Northwind Retail"]


def test_free_text_client_not_in_the_list_unlocks_the_chain():
    """A brand-new client, matching nothing known, is a valid value."""
    assert _call("matchingClientNames", KNOWN, "Fabrikam Estates") == []
    assert _unlocked(_locks(clientName="Fabrikam Estates")) == ["clientName", "name"]


def test_picking_a_suggestion_fills_the_field_and_unlocks_the_chain():
    """Typing narrows the list; the picked name is then the field's value."""
    suggestions = _call("matchingClientNames", KNOWN, "north")
    assert suggestions == ["Northwind Health Trust", "Northwind Retail"]
    picked = suggestions[0]
    assert _unlocked(_locks(clientName=picked)) == ["clientName", "name"]


def test_empty_query_offers_every_known_client():
    """Opening the list on an empty field shows all prior clients."""
    assert _call("matchingClientNames", KNOWN, "  ") == KNOWN


def test_exact_match_is_not_offered_back():
    """Once the field holds a known client, the list does not repeat it."""
    assert _call("matchingClientNames", KNOWN, "acme developments") == []


# ── both wizards use the shared step ─────────────────────────────────────────

WIZARDS = [
    FRONTEND_SRC / "routes" / "NewProjectView.svelte",
    FRONTEND_SRC / "lib" / "components" / "ProjectWizardModal.svelte",
]


@pytest.mark.parametrize("wizard", WIZARDS, ids=lambda p: p.stem)
def test_wizard_renders_the_shared_details_step_and_sends_client_name(wizard: Path):
    """No wizard keeps its own Step 1, a lifecycle status, or drops client_name."""
    source = wizard.read_text(encoding="utf-8")
    assert "<ProjectDetailsStep" in source
    assert "bind:clientName" in source
    assert "client_name: clientName.trim()" in source
    assert "Lifecycle Status" not in source
    assert 'id="wizard-name"' not in source, "Step 1 markup duplicated back into the wizard"


def test_details_step_writes_client_name_from_typing_and_from_a_pick():
    """The combobox updates clientName on both input paths, and wires the locks."""
    source = (FRONTEND_SRC / "lib" / "components" / "ProjectDetailsStep.svelte").read_text(
        encoding="utf-8"
    )
    assert "clientName = e.currentTarget.value" in source  # free text
    assert "if (picked) clientName = picked" in source  # dropdown selection
    for key in CHAIN[1:]:
        assert f"locks.{key}" in source, f"{key} is not wired to its lock"
