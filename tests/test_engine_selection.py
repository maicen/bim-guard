"""Engine selection: what the analyse page offers must be what the API honours.

The analyse page shows five checkboxes (GC-001, CC-001, MC-001, MM-001,
XM-001), all ticked by default, and sends their Issue-id prefixes as
``engines``. Two separate mechanisms have to agree with that list:

  * ``resolve_mechanisms`` decides what RUNS, before the element loop.
  * ``SELECTABLE_ENGINES`` / ``_filter_issues_by_engine`` decide what SURVIVES
    on the legacy ``rule_ids`` path.

They are independent, and a code present in the first but missing from the
second is worse than one missing from both: the engine runs and its findings
are then filtered away, so the run pays for work the caller never sees. That
is what these tests pin.
"""

from types import SimpleNamespace

import pytest

from app.api.analyze import SELECTABLE_ENGINES, _filter_issues_by_engine
from app.modules.phase_6.phase_6c_corrosion_ui import MECHANISMS, resolve_engine_codes

#: The prefixes AnalyzeView.svelte's PIPING_ENGINES sends, all five ticked.
UI_PREFIXES = ["GC", "CC", "MC", "MM", "XM"]

ALL_CODES = ("GC-001", "CC-001", "MC-001", "MM-001", "XM-001")


def _issue(rule_id, mechanism="galvanic", band="high"):
    return SimpleNamespace(rule_id=rule_id, mechanism=mechanism, band=band)


def _result(*rule_ids):
    return {
        "audit_issues": [_issue(r) for r in rule_ids],
        "issue_stats": {"total": len(rule_ids)},
    }


def _kept(result):
    return [i.rule_id for i in result["audit_issues"]]


# ---------------------------------------------------------------------------
# The two lists must describe the same five engines
# ---------------------------------------------------------------------------


def test_every_mechanism_is_selectable():
    """A mechanism that runs but cannot be named is one whose findings vanish."""
    assert tuple(spec.code for spec in MECHANISMS) == ALL_CODES
    assert SELECTABLE_ENGINES == ALL_CODES


def test_the_pages_default_selection_runs_all_five():
    """All five boxes ticked must reach all five engines, not silently three."""
    assert resolve_engine_codes(UI_PREFIXES) == ALL_CODES


def test_no_selection_still_runs_all_five():
    """None means "no selection was made", which runs everything."""
    assert resolve_engine_codes(None) == ALL_CODES


# ---------------------------------------------------------------------------
# Legacy rule_ids narrowing
# ---------------------------------------------------------------------------


def test_a_mixed_selection_keeps_every_engine_named():
    """The regression: MM-001 named alongside GC-001 used to be filtered away.

    MM-001 was absent from SELECTABLE_ENGINES, so it dropped out of ``wanted``
    while GC-001 survived — a narrowing the caller never asked for, applied to
    findings the run had already computed.
    """
    narrowed = _filter_issues_by_engine(
        _result("GC-001.01", "MM-001.01", "XM-001.01"), ["GC-001", "MM-001"]
    )
    assert _kept(narrowed) == ["GC-001.01", "MM-001.01"]


@pytest.mark.parametrize("code", ALL_CODES)
def test_each_engine_can_be_selected_alone(code):
    """Naming one engine keeps its issues and drops the others'."""
    narrowed = _filter_issues_by_engine(_result(*(f"{c}.01" for c in ALL_CODES)), [code])
    assert _kept(narrowed) == [f"{code}.01"]


def test_selection_keeps_an_engines_data_quality_notes_with_its_verdicts():
    """Rule ids like "XM-001.DATA" belong to XM-001 and travel with it."""
    narrowed = _filter_issues_by_engine(
        _result("XM-001.01", "XM-001.DATA", "GC-001.01"), ["XM-001"]
    )
    assert _kept(narrowed) == ["XM-001.01", "XM-001.DATA"]


def test_an_unrecognised_selection_returns_the_run_untouched():
    """Never narrow to nothing on a name this module does not know."""
    result = _result("GC-001.01", "MM-001.01")
    assert _kept(_filter_issues_by_engine(result, ["SB-001"])) == ["GC-001.01", "MM-001.01"]
    assert _kept(_filter_issues_by_engine(result, [])) == ["GC-001.01", "MM-001.01"]


def test_stats_are_recomputed_for_the_narrowed_list():
    """Narrowed issues under unnarrowed totals read as data going missing."""
    result = {
        "audit_issues": [
            _issue("MM-001.01", band="critical"),
            _issue("MM-001.DATA", mechanism="data_quality", band="low"),
            _issue("GC-001.01", band="high"),
        ],
        "issue_stats": {"total": 3, "critical": 1, "high": 1, "medium": 0, "low": 0},
    }
    stats = _filter_issues_by_engine(result, ["MM-001"])["issue_stats"]

    assert stats["total"] == 1  # the data-quality note is counted apart
    assert stats["critical"] == 1
    assert stats["high"] == 0
    assert stats["data_quality"] == 1
