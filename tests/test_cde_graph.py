"""CDE LangGraph wrapper must match CDEStateMachine.evaluate_transition() exactly.

No prior test suite covered `evaluate_transition()` directly, so these cases
are derived straight from its own docstring/branches (app/services/
cde_state_machine.py) — each assertion below is checked against both the
underlying gate function and the graph wrapper, so the wrapper can never
silently diverge from the tested gate logic.
"""

import pytest

from app.digital_inspector.cde_graph import build_cde_graph, check_transition
from app.services.cde_state_machine import CDEStateMachine

CASES = [
    # (label, current, target, kwargs, expected_allowed)
    ("same-state-noop", "WIP", "WIP", {}, True),
    ("wip-to-shared-clean", "WIP", "SHARED", {}, True),
    (
        "wip-to-shared-critical-issues",
        "WIP",
        "SHARED",
        {"critical_issues_count": 1},
        False,
    ),
    (
        "wip-to-shared-ids-failed",
        "WIP",
        "SHARED",
        {"ids_check_passed": False},
        False,
    ),
    (
        "wip-to-shared-bad-filename",
        "WIP",
        "SHARED",
        {"filename": "not-a-valid-iso19650-name.ifc"},
        False,
    ),
    (
        "shared-to-published-no-approval",
        "SHARED",
        "PUBLISHED",
        {},
        False,
    ),
    (
        "shared-to-published-approved",
        "SHARED",
        "PUBLISHED",
        {"approved_by": "Jane Doe"},
        True,
    ),
    ("any-to-archived", "SHARED", "ARCHIVED", {}, True),
    ("wip-to-archived", "WIP", "ARCHIVED", {}, True),
    ("shared-rollback-to-wip", "SHARED", "WIP", {}, True),
    ("invalid-wip-to-published", "WIP", "PUBLISHED", {}, False),
]


@pytest.mark.parametrize("label,current,target,kwargs,expected_allowed", CASES, ids=[c[0] for c in CASES])
def test_graph_matches_evaluate_transition(label, current, target, kwargs, expected_allowed):
    direct = CDEStateMachine.evaluate_transition(current, target, **kwargs)
    assert direct.allowed == expected_allowed, f"{label}: fixture's expectation disagrees with the gate itself"

    # All CASES targets are real CDEState values (including the
    # "invalid-wip-to-published" case -- PUBLISHED is a valid state, it's
    # just not a reachable transition from WIP per evaluate_transition's
    # own fallthrough), so the graph routes and evaluates identically.
    wrapped = check_transition(current, target, **kwargs)
    assert wrapped["allowed"] == direct.allowed
    assert wrapped["reason"] == direct.reason
    assert wrapped["target_state"] == direct.target_state.value


def test_graph_topology_has_one_node_per_cde_state():
    graph = build_cde_graph()
    nodes = set(graph.get_graph().nodes) - {"__start__", "__end__"}
    assert nodes == {"WIP", "SHARED", "PUBLISHED", "ARCHIVED"}


def test_check_transition_rejects_unknown_target_state():
    # An unrecognized target_state raises inside CDEState(...) before
    # routing even begins, exactly as calling evaluate_transition()
    # directly would.
    with pytest.raises(ValueError):
        check_transition("WIP", "NOT-A-REAL-STATE")
