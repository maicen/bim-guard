"""Thin LangGraph wrapper around the ISO 19650 CDE state machine.

`CDEStateMachine.evaluate_transition()` (app.services.cde_state_machine) is
a small, already-tested, synchronous gate function used for real compliance
decisions, and `CDEStateMachine.transition_project()` performs the actual
transactional DB write + lineage recording. Neither is touched here.

This module exists only so the Digital Inspector agent can expose "can this
project transition to Shared, and if not, why" as a tool, and so the CDE
topology can be visualized/documented via `.get_graph().draw_mermaid()` —
every node still calls straight into `evaluate_transition()` for its gate
decision, so this can never diverge from the real gate logic's tested
outcomes.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.modules.contracts import CDEState
from app.services.cde_state_machine import CDEStateMachine

_TARGET_STATES = [CDEState.WIP, CDEState.SHARED, CDEState.PUBLISHED, CDEState.ARCHIVED]


class CDETransitionState(TypedDict, total=False):
    """Input/output state for one transition-gate check."""

    current_state: str
    target_state: str
    filename: str
    critical_issues_count: int
    ids_check_passed: bool
    is_approved: bool
    approved_by: str
    result: dict[str, Any]


def _route_to_target(state: CDETransitionState) -> str:
    """Conditional edge: dispatch to the node matching the requested target state."""
    target = CDEState(state["target_state"])
    if target not in _TARGET_STATES:
        return CDEState.WIP.value
    return target.value


def _make_gate_node(target: CDEState):
    """Build a node that evaluates the real gate for a transition into `target`."""

    def node(state: CDETransitionState) -> dict[str, Any]:
        outcome = CDEStateMachine.evaluate_transition(
            state["current_state"],
            target.value,
            filename=state.get("filename", ""),
            critical_issues_count=state.get("critical_issues_count", 0),
            ids_check_passed=state.get("ids_check_passed", True),
            is_approved=state.get("is_approved", False),
            approved_by=state.get("approved_by", ""),
        )
        return {
            "result": {
                "allowed": outcome.allowed,
                "reason": outcome.reason,
                "target_state": outcome.target_state.value,
            }
        }

    return node


def build_cde_graph():
    """Compile a StateGraph whose nodes are the four CDE states.

    Routing: START -> (conditional, on `target_state`) -> the matching
    state's gate node -> END. Each gate node's only job is calling
    `CDEStateMachine.evaluate_transition()` — this graph adds no gate logic
    of its own.
    """
    graph = StateGraph(CDETransitionState)

    for target in _TARGET_STATES:
        graph.add_node(target.value, _make_gate_node(target))
        graph.add_edge(target.value, END)

    graph.set_conditional_entry_point(
        _route_to_target, {target.value: target.value for target in _TARGET_STATES}
    )

    return graph.compile()


def check_transition(
    current_state: str,
    target_state: str,
    *,
    filename: str = "",
    critical_issues_count: int = 0,
    ids_check_passed: bool = True,
    is_approved: bool = False,
    approved_by: str = "",
) -> dict[str, Any]:
    """Run the compiled CDE graph for one transition-gate check.

    Convenience wrapper so callers (the Digital Inspector tool, tests) don't
    need to recompile the graph or shape the input state by hand.
    """
    graph = build_cde_graph()
    result = graph.invoke(
        {
            "current_state": current_state,
            "target_state": target_state,
            "filename": filename,
            "critical_issues_count": critical_issues_count,
            "ids_check_passed": ids_check_passed,
            "is_approved": is_approved,
            "approved_by": approved_by,
        }
    )
    return result["result"]
