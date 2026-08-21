"""FEATURE_PATH_B_MM and FEATURE_PATH_B_XM must switch independently.

The two Path B comparators are not equivalent. MM-001 is APPROVED v1.0 and runs
entirely from disk; XM-001 is still DRAFT and its loader reaches the database
for the GC-001 galvanic series. The integration plan's section 5 rules that
they must never sit on one switch, so every test here exercises all four
on/off combinations rather than just "on" and "off".

Each combination runs in its own child interpreter. The flags are read at
module import time, so a test that mutated ``os.environ`` in-process would be
reading whatever the first test to import the module happened to see.

Run: uv run pytest tests/test_feature_flags.py -v
"""

from __future__ import annotations

import pytest

from tests.conftest import FLAG_COMBO_IDS, FLAG_COMBOS

# Reads the flags the way the pipeline's shared config does: DB setting first,
# then environment, then the literal default.
_CONFIG_PROBE = r"""
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

# Reads the flags the way orchestrate_workflow() actually does, and reports
# which source the module's text shows it consulting.
_ORCHESTRATOR_PROBE = r"""
import json, os, sys
sys.path.insert(0, ".")
src = open(
    "app/modules/module4_comparator/compliance_orchestrator.py", encoding="utf-8"
).read()
print(json.dumps({
    "mm": os.environ.get("FEATURE_PATH_B_MM", "0") == "1",
    "xm": os.environ.get("FEATURE_PATH_B_XM", "0") == "1",
    "reads_env": 'os.environ.get("FEATURE_PATH_B_MM"' in src,
    "reads_config": "app.modules.config" in src,
}))
"""

# Imports the shared config with no database reachable and no .env loaded.
_OFFLINE_CONFIG_PROBE = r"""
import json, sys
sys.path.insert(0, ".")
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


@pytest.mark.parametrize(("mm", "xm"), FLAG_COMBOS, ids=FLAG_COMBO_IDS)
def test_config_flags_follow_the_environment(run_probe, flag_env, mm, xm):
    """app.modules.config resolves each flag from its own environment variable."""
    result = run_probe(_CONFIG_PROBE, flag_env(mm, xm))
    assert result["ok"], f"app.modules.config failed to import: {result.get('error')}"
    assert (result["mm"], result["xm"]) == (mm == "1", xm == "1")


@pytest.mark.parametrize(("mm", "xm"), FLAG_COMBOS, ids=FLAG_COMBO_IDS)
def test_orchestrator_flags_follow_the_environment(run_probe, flag_env, mm, xm):
    """orchestrate_workflow() resolves each flag from its own variable."""
    result = run_probe(_ORCHESTRATOR_PROBE, flag_env(mm, xm))
    assert (result["mm"], result["xm"]) == (mm == "1", xm == "1")


def test_flags_are_genuinely_independent(run_probe, flag_env):
    """Turning one flag on must leave the other alone.

    The parametrised tests above would still pass if both names resolved to a
    single underlying switch and the assertions happened to line up, so this
    states the property directly: MM on and XM off is a reachable state, and so
    is its mirror.
    """
    mm_only = run_probe(_CONFIG_PROBE, flag_env("1", "0"))
    xm_only = run_probe(_CONFIG_PROBE, flag_env("0", "1"))

    assert (mm_only["mm"], mm_only["xm"]) == (True, False), (
        "enabling MM-001 also enabled XM-001; the DRAFT pack must not ride "
        "on the APPROVED pack's switch"
    )
    assert (xm_only["mm"], xm_only["xm"]) == (False, True), (
        "enabling XM-001 also enabled MM-001"
    )


def test_both_flags_default_to_off(run_probe):
    """With nothing set, both Path B packs stay dark.

    XM-001 is DRAFT. A default-on flag would put an unapproved rule pack in
    front of a reviewer without anyone choosing to.
    """
    result = run_probe(_CONFIG_PROBE, {"FEATURE_PATH_B_MM": "", "FEATURE_PATH_B_XM": ""})
    assert result["ok"], f"app.modules.config failed to import: {result.get('error')}"
    assert (result["mm"], result["xm"]) == (False, False)


@pytest.mark.parametrize("value", ["0", "true", "TRUE", "yes", "on", "2", " 1"])
def test_only_the_literal_one_enables_a_flag(run_probe, value):
    """Anything other than the string "1" reads as off.

    config.py documents this rule explicitly. Pinning it matters because the
    plausible-looking values are the dangerous ones: someone setting
    ``FEATURE_PATH_B_XM=true`` should get a dark DRAFT pack, not a live one.
    """
    result = run_probe(
        _CONFIG_PROBE, {"FEATURE_PATH_B_MM": value, "FEATURE_PATH_B_XM": value}
    )
    assert result["ok"], f"app.modules.config failed to import: {result.get('error')}"
    assert (result["mm"], result["xm"]) == (False, False), (
        f"{value!r} enabled a Path B flag; only the exact string '1' should"
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "DEFECT: compliance_orchestrator.py reads os.environ directly and never "
        "imports app.modules.config, so a flag set through SettingsService (the "
        "database) is invisible to orchestrate_workflow(). One switch, two truths."
    ),
)
def test_orchestrator_reads_the_shared_config_flags(run_probe):
    """The orchestrator should consult the same flags the rest of the pipeline does."""
    result = run_probe(_ORCHESTRATOR_PROBE)
    assert result["reads_config"], (
        "compliance_orchestrator.py does not reference app.modules.config; it "
        f"reads the environment directly (reads_env={result['reads_env']})"
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "DEFECT: app.modules.config instantiates SettingsService() at module "
        "import time, which calls PersistenceService.get_db() and raises "
        "ValueError('SUPABASE_URL is required'). The flags cannot be read "
        "offline, which is why the orchestrator bypasses this module entirely."
    ),
)
def test_config_imports_without_a_database(run_probe):
    """Reading a feature flag must not require a database round trip.

    MM-001's whole design claim is that it runs from disk. If the flag that
    gates it cannot be read without Supabase, that claim does not hold for the
    switch even where it holds for the comparator.
    """
    result = run_probe(
        _OFFLINE_CONFIG_PROBE,
        {
            "SUPABASE_URL": "",
            "SUPABASE_SERVICE_ROLE_KEY": "",
            "SUPABASE_KEY": "",
            "FEATURE_PATH_B_MM": "1",
            "FEATURE_PATH_B_XM": "0",
        },
    )
    assert result["ok"], f"app.modules.config needs a database to import: {result.get('error')}"
    assert (result["mm"], result["xm"]) == (True, False)
