"""Tests for the opt-in SHACL side-channel wired into orchestrate_workflow.

Covers `BIMGuard_App._run_shacl_compliance` (app.modules.orchestrator). These
only exercise the bridge's plumbing (short-circuits, no crash on a real IFC
model), not a genuine SHACL violation: bot_graph.py does not yet mirror IFC
Pset properties onto the graph as literals (see its module docstring and
_run_shacl_compliance's own docstring), so a rule referencing a raw or
engine-computed property currently always conforms rather than firing --
that enrichment wiring is a separate follow-up.
"""

import ifcopenshell
import ifcopenshell.api

from app.modules.orchestrator import BIMGuard_App


def _noop_log_progress(*_args, **_kwargs) -> None:
    return None


def _door_ifc_model():
    model = ifcopenshell.file(schema="IFC4")
    ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcProject", name="Test")
    ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcDoor", name="Door D1")
    return model


class _FakeReader:
    def __init__(self, ifc_file):
        self.ifc_file = ifc_file


_DOOR_WIDTH_RULE = {
    "rule_id": "CODE-9.6.3.1",
    "description": "Door clear width shall be at least 900mm",
    "severity": "mandatory",
    "target_ifc_class": "IfcDoor",
    "property_name": "calculatedClearWidth",
    "operator": ">=",
    "check_value": "900",
    "unit": "mm",
}


def test_disabled_by_default_returns_empty_without_touching_rules():
    issues, error = BIMGuard_App._run_shacl_compliance(
        enable_shacl=False,
        m2_reader=_FakeReader(_door_ifc_model()),
        ifc_error=None,
        library_rules=[_DOOR_WIDTH_RULE],
        project_id=1,
        log_progress=_noop_log_progress,
    )

    assert issues == []
    assert error is None


def test_enabled_but_no_shacl_eligible_rules_is_a_noop():
    issues, error = BIMGuard_App._run_shacl_compliance(
        enable_shacl=True,
        m2_reader=_FakeReader(_door_ifc_model()),
        ifc_error=None,
        library_rules=[{"rule_id": "X", "operator": "unique_within_scope"}],
        project_id=1,
        log_progress=_noop_log_progress,
    )

    assert issues == []
    assert error is None


def test_enabled_with_eligible_rule_runs_without_crashing():
    # No enrichment wiring yet, so calculatedClearWidth has no values on the
    # graph and the shape conforms -- this proves the bridge runs end to end
    # against a real ifcopenshell model without error, not that it can flag
    # a real violation (see module docstring).
    issues, error = BIMGuard_App._run_shacl_compliance(
        enable_shacl=True,
        m2_reader=_FakeReader(_door_ifc_model()),
        ifc_error=None,
        library_rules=[_DOOR_WIDTH_RULE],
        project_id=1,
        log_progress=_noop_log_progress,
    )

    assert error is None
    assert issues == []


def test_enabled_with_ifc_error_is_skipped():
    issues, error = BIMGuard_App._run_shacl_compliance(
        enable_shacl=True,
        m2_reader=_FakeReader(_door_ifc_model()),
        ifc_error="parse failed",
        library_rules=[_DOOR_WIDTH_RULE],
        project_id=1,
        log_progress=_noop_log_progress,
    )

    assert issues == []
    assert error is None


def test_run_rule_compliance_survives_rules_service_failure_before_library_rules_bound():
    """Verify a pre-`try` failure still leaves `library_rules` bound.

    `rules_service` is None here, so
    `library_rules = rules_service.list_by_theme(...)` raises inside the try
    block before `library_rules` would otherwise be assigned -- this only
    passes because `library_rules` is pre-declared, not just assigned in the
    try (see the comment at its declaration).
    """
    app = BIMGuard_App()

    result = app._run_rule_compliance(
        rules_service=None,
        rule_folder="",
        selected_theme="Architecture",
        ifc={"m2_reader": None, "ifc_error": None, "ifc_type_counts": {}},
        project_id=1,
        log_progress=_noop_log_progress,
        enable_shacl=True,
    )

    assert result["rule_compliance_error"] is not None
    assert result["shacl_issues"] == []
    assert result["shacl_error"] is None
